"""Pipeline ETL catalogue alimentaire — orchestration import (M05).

Service d'import ETL : prend une liste de LigneParsee (issues d'un parser
fournisseur), applique la déduplication ADR-07, persiste les nouveaux produits
et les conflits dans etl_conflicts.

Références :
    ADR-07 : déduplication Jaro-Winkler (seuils 0.85 / 0.75)
    ADR-08 : pipeline ETL — appelé par Celery tasks (etl_tasks.py)
    ADR-15 : etl_import_id FK nullable dans etl_conflicts (SET NULL)
    ADR-25 : enrichissement facture fournisseur (LigneParsee + FactureMetadata)
"""
import dataclasses
import logging
from typing import Optional

logger = logging.getLogger(__name__)

from sqlalchemy import select as _sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue.catalogue_produit import CatalogueProduit
from app.models.catalogue.etl_conflict import EtlConflict
from app.repositories.catalogue.catalogue_produit import AsyncCatalogueProduitRepository
from app.repositories.catalogue.etl_conflict import AsyncEtlConflictRepository
from app.repositories.catalogue.etl_import import AsyncEtlImportRepository
from app.services.catalogue.etl_classification import classify_by_knn, classify_categorie_code
from app.services.catalogue.etl_deduplication import (
    DecisionDeduplication,
    ResultatDeduplication,
    build_idf_from_candidates,
    classify_designation,
    is_ean_valid,
    normalize_designation,
)
from app.etl_types import FactureMetadata, LigneParsee
from scripts.etl.parsers._shared.conditionnement import extract_colisage_from_text

# ── Constantes (pas de magic strings) ────────────────────────────────────────

_STATUT_RUNNING = "RUNNING"
_STATUT_PREVIEW = "PREVIEW"
_STATUT_SUCCES = "SUCCES"
_STATUT_PARTIEL = "PARTIEL"
_TYPE_EAN_COLLISION = "EAN_COLLISION"
_TYPE_DESIGNATION_PROCHE = "DESIGNATION_PROCHE"
_SUGGESTION_MERGED = "MERGED"
_SUGGESTION_KEPT_SEPARATE = "KEPT_SEPARATE"
_RESULT_OK = "ok"
_RESULT_CONFLIT = "conflit"
_RESULT_ERREUR = "erreur"
_CODE_AUTRE = "AUTRE"

# Tolérance sur le volume pour détecter "même produit" (ex: 250 vs 255 ml = OK)
_VOLUME_TOLERANCE_PCT = 0.05  # 5%


def _same_physical_attrs(ligne: LigneParsee, produit: CatalogueProduit) -> bool:
    """Détermine si une LigneParsee et un CatalogueProduit désignent le même
    produit logique (même volume ±5%, même unite_base, même degré alcool exact).

    Le **colisage n'est PAS un critère** : un même produit (ex: 1664 25cL) peut
    arriver en packs 18/20/24 selon la référence fournisseur. Le colisage est un
    attribut d'emballage tracé dans la table pivot catalogue_produit_colisages.

    Utilisé pour décider si un EAN entrant ≠ EAN stocké doit :
      - Être ajouté comme EAN secondaire au produit existant (attrs identiques
        → même produit, EAN cross-pays ou cross-pack)
      - Créer un produit distinct (attrs différents → variantes réelles)

    Un attribut non renseigné des deux côtés (NULL/NULL) ne bloque pas le match.
    """
    # Unité de base : match exact requis (kg ≠ L ≠ piece)
    if ligne.unite_base and produit.unite_base:
        if ligne.unite_base.lower() != produit.unite_base.lower():
            return False

    # Degré alcool : match exact (5.5 ≠ 7.0)
    if ligne.degre_alcool is not None and hasattr(produit, "degre_alcool"):
        prod_deg = getattr(produit, "degre_alcool", None)
        if prod_deg is not None and abs(ligne.degre_alcool - prod_deg) > 0.05:
            return False

    # Volume unitaire : tolérance ±5% (250ml ≈ 255ml OK)
    if ligne.volume_unitaire_ml and produit.volume_unitaire_ml:
        lv, pv = ligne.volume_unitaire_ml, produit.volume_unitaire_ml
        tolerance = max(lv, pv) * _VOLUME_TOLERANCE_PCT
        if abs(lv - pv) > tolerance:
            return False

    return True


# ── Helpers de construction ───────────────────────────────────────────────────


def _refine_regie_code(regie_code: str, designation_norm: str) -> str:
    """Affine un code régie générique en code final des 91 catégories.

    Utilise le contexte de la désignation pour déterminer la sous-catégorie.
    """
    if regie_code == "ALC_VIN":
        # Rosé avant rouge (sinon "rouge" matche les rosés avec "rouge" dans le nom)
        rose_kw = ("rose", "rse", "rse ", "tavel")
        if any(k in designation_norm for k in rose_kw):
            return "ALC_VIN_ROSE"
        blanc_kw = ("blanc", "blc", "chardonnay", "sauvignon", "muscadet",
                    "riesling", "chablis", "sancerre", "pouilly", "viognier",
                    "gewurz", "chardon", "ribeaup")
        if any(k in designation_norm for k in blanc_kw):
            return "ALC_VIN_BLC"
        # Défaut vin = rouge (le plus courant en restauration)
        return "ALC_VIN_RGE"

    if regie_code == "ALC_CHAMPAGNE":
        return "ALC_APERO"

    if regie_code == "ALC_SPIRIT":
        return "ALC_SPIRITUEUX"

    return regie_code


# Catégories finales — les 91 codes valides pour le catalogue
_FINAL_CATEGORIES: frozenset[str] = frozenset({
    "ALC_BIERE", "ALC_VIN_RGE", "ALC_VIN_BLC", "ALC_VIN_ROSE",
    "ALC_SPIRITUEUX", "ALC_LIQUEUR", "ALC_APERO",
    "BOIS_EAU", "BOIS_SODA", "BOIS_JUS", "BOIS_SIROP",
    "BOIS_ENERG", "BOIS_CAFE", "BOIS_THE", "BOIS_CHOCO",
    "BOUL_BRIOCHE", "BOUL_PAIN", "BOUL_VIEN",
    "COND_BOUILLON", "COND_SEL", "COND_HUILE", "COND_VINAIGRE",
    "COND_SAUCE", "COND_EPICE",
    "CONS_LEGUME", "CONS_PLAT", "CONS_POISSON", "CONS_SAUCE",
    "ENTR_LESSIVE", "ENTR_NETTOY", "ENTR_VAISS",
    "EPIC_SEMOULE", "EPIC_LEGUM_SEC", "EPIC_PATE", "EPIC_RIZ",
    "FL_AROMATE", "FL_SALADE", "FL_LEGUME", "FL_FRUIT",
    "FRAIS_BOEUF", "FRAIS_PORC", "FRAIS_AGNEAU", "FRAIS_VOLAILLE",
    "FRAIS_CHARC", "FRAIS_SAUCISSE", "FRAIS_JAMBON", "FRAIS_LARDON",
    "FRAIS_POISSON", "FRAIS_CRUST", "FRAIS_COQUIL", "FRAIS_OEUF",
    "FRAIS_TRAIT",
    "HYG_CORPS", "HYG_PAPIER",
    "LAIT_CREME", "LAIT_BEURRE", "LAIT_FROMAGE", "LAIT_YAOURT",
    "LAIT_DESSERT", "LAIT_UHT",
    "MONDE_HALAL", "MONDE_ASIE", "MONDE_ORIENT",
    "MONDE_AMERIQUE", "MONDE_AFRIQUE",
    "PRO_FILM", "PRO_PROTECT", "PRO_ETIQ", "PRO_EMBALL", "PRO_JETABLE",
    "SNACK_CHIPS", "SNACK_FRUIT_SEC", "SNACK_BISCUIT",
    "SUCR_LEVURE", "SUCR_AROME", "SUCR_NAPPAGE", "SUCR_FARINE",
    "SUCR_CEREAL", "SUCR_CONF", "SUCR_SUCRE", "SUCR_CHOCO",
    "SUCR_BONBON", "SUCR_BISC", "SUCR_GATEAU", "SUCR_VIEN",
    "SURG_VIANDE", "SURG_POISSON", "SURG_GLACE", "SURG_PATISS",
    "SURG_LEGUME",
})


# Mapping régie METRO → familles de catégories autorisées
_REGIE_TO_FAMILIES: dict[str, tuple[str, ...]] = {
    "S": ("ALC_SPIRITUEUX", "ALC_LIQUEUR"),
    "B": ("ALC_BIERE",),
    "M": ("ALC_APERO",),  # champagnes, mousseux
    "T": ("ALC_VIN_RGE", "ALC_VIN_BLC", "ALC_VIN_ROSE", "ALC_APERO"),
    "E": (  # épicerie = tout sauf alcool et frais
        "BOIS_EAU", "BOIS_SODA", "BOIS_JUS", "BOIS_SIROP", "BOIS_ENERG",
        "BOIS_CAFE", "BOIS_THE", "BOIS_CHOCO",
        "COND_BOUILLON", "COND_SEL", "COND_HUILE", "COND_VINAIGRE",
        "COND_SAUCE", "COND_EPICE",
        "CONS_LEGUME", "CONS_PLAT", "CONS_POISSON", "CONS_SAUCE",
        "EPIC_SEMOULE", "EPIC_LEGUM_SEC", "EPIC_PATE", "EPIC_RIZ",
        "SUCR_LEVURE", "SUCR_AROME", "SUCR_NAPPAGE", "SUCR_FARINE",
        "SUCR_CEREAL", "SUCR_CONF", "SUCR_SUCRE", "SUCR_CHOCO",
        "SUCR_BONBON", "SUCR_BISC", "SUCR_GATEAU", "SUCR_VIEN",
        "SNACK_CHIPS", "SNACK_FRUIT_SEC", "SNACK_BISCUIT",
        "BOUL_BRIOCHE", "BOUL_PAIN", "BOUL_VIEN",
        "SURG_VIANDE", "SURG_POISSON", "SURG_GLACE", "SURG_PATISS", "SURG_LEGUME",
        "MONDE_HALAL", "MONDE_ASIE", "MONDE_ORIENT", "MONDE_AMERIQUE", "MONDE_AFRIQUE",
        "LAIT_CREME", "LAIT_BEURRE", "LAIT_FROMAGE", "LAIT_YAOURT",
        "LAIT_DESSERT", "LAIT_UHT",
    ),
    "F": (  # frais
        "FRAIS_BOEUF", "FRAIS_PORC", "FRAIS_AGNEAU", "FRAIS_VOLAILLE",
        "FRAIS_CHARC", "FRAIS_SAUCISSE", "FRAIS_JAMBON", "FRAIS_LARDON",
        "FRAIS_POISSON", "FRAIS_CRUST", "FRAIS_COQUIL", "FRAIS_OEUF", "FRAIS_TRAIT",
        "FL_AROMATE", "FL_SALADE", "FL_LEGUME", "FL_FRUIT",
    ),
    "D": (  # droguerie = non-alimentaire
        "ENTR_LESSIVE", "ENTR_NETTOY", "ENTR_VAISS",
        "HYG_CORPS", "HYG_PAPIER",
        "PRO_FILM", "PRO_PROTECT", "PRO_ETIQ", "PRO_EMBALL", "PRO_JETABLE",
    ),
}

# Fallback par régie quand aucune sous-catégorie ne matche
_REGIE_FALLBACK: dict[str, str] = {
    "S": "ALC_SPIRITUEUX",
    "B": "ALC_BIERE",
    "M": "ALC_APERO",
    "T": "ALC_VIN_RGE",
    "E": "AUTRE",  # trop large pour un fallback unique
    "F": "FRAIS_TRAIT",
    "D": "PRO_JETABLE",
}


def _resolve_categorie_code(
    ligne: LigneParsee,
    designation_norm: str,
    labelled: list[tuple[str, str]],
) -> str:
    """Résout le code catégorie — régie-first, keywords en raffinement.

    Architecture :
      1. Code déjà final (91 codes) → garder
      2. Code régie alcool → affiner par contexte (vin RGE/BLC/ROSE)
      3. Keywords statiques → filtrer par famille régie si régie connue
      4. KNN restreint à la même famille régie
      5. Fallback régie (mieux que AUTRE)
      6. AUTRE
    """
    parser_code = ligne.categorie_code

    # Extraire la régie depuis le parser_code si possible
    regie = None
    _CODE_TO_REGIE = {
        "ALC_BIERE": "B", "ALC_SPIRITUEUX": "S", "ALC_CHAMPAGNE": "M",
        "ALC_VIN": "T", "ALC_APERO": "M", "ALC_LIQUEUR": "S",
        "ALC_VIN_RGE": "T", "ALC_VIN_BLC": "T", "ALC_VIN_ROSE": "T",
        "ALI_EPICERIE": "E", "ALI_FRAIS": "F", "NON_ALI_DROGUERIE": "D",
    }
    if parser_code:
        regie = _CODE_TO_REGIE.get(parser_code)

    # 1. Code déjà final → garder
    if parser_code and parser_code in _FINAL_CATEGORIES:
        return parser_code

    # 2. Code régie alcool → affiner
    if parser_code:
        refined = _refine_regie_code(parser_code, designation_norm)
        if refined in _FINAL_CATEGORIES:
            return refined

    # 3. Keywords statiques
    kw_code = classify_categorie_code(designation_norm)
    if kw_code != _CODE_AUTRE:
        # Si on a une régie, vérifier que le keyword est cohérent
        if regie and regie in _REGIE_TO_FAMILIES:
            allowed = _REGIE_TO_FAMILIES[regie]
            if kw_code in allowed:
                return kw_code
            # Keyword incohérent avec la régie — confiance aux keywords quand
            # la régie est clairement fausse (erreur OCR fréquente) :
            # - Alcool détecté dans régie E/F/D
            # - Alimentaire détecté dans régie D (droguerie = souvent OCR erroné)
            if kw_code.startswith("ALC_") and regie in ("E", "F", "D"):
                return kw_code
            if regie == "D" and not kw_code.startswith("PRO_") and not kw_code.startswith("ENTR_") and not kw_code.startswith("HYG_"):
                return kw_code
        else:
            return kw_code

    # 4. KNN restreint à la famille régie
    if len(labelled) >= 5:
        if regie and regie in _REGIE_TO_FAMILIES:
            allowed = set(_REGIE_TO_FAMILIES[regie])
            family_labelled = [(n, c) for n, c in labelled if c in allowed]
            if len(family_labelled) >= 3:
                knn_code = classify_by_knn(designation_norm, family_labelled, seuil=0.80)
                if knn_code != _CODE_AUTRE:
                    return knn_code
        else:
            knn_code = classify_by_knn(designation_norm, labelled, seuil=0.80)
            if knn_code != _CODE_AUTRE:
                return knn_code

    # 5. Fallback régie (mieux que AUTRE)
    if regie and regie in _REGIE_FALLBACK:
        fallback = _REGIE_FALLBACK[regie]
        if fallback != _CODE_AUTRE:
            return fallback

    return _CODE_AUTRE


def _build_produit(
    ligne: LigneParsee,
    designation_norm: str,
    labelled: list[tuple[str, str]],
) -> CatalogueProduit:
    """Construit un CatalogueProduit depuis une LigneParsee et la norme calculée."""
    # Colisage enrichi depuis conditionnement texte (bug 2026-04-24 : METRO
    # stocke souvent colisage=1 en colonne PDF alors que le conditionnement
    # texte indique "lot de 150", "(10x500)", etc.). On n'écrase que si
    # ligne.colisage est None ou 1.
    colisage = ligne.colisage
    if not colisage or colisage == 1:
        extracted = extract_colisage_from_text(ligne.conditionnement) \
            or extract_colisage_from_text(ligne.designation)
        if extracted:
            colisage = extracted

    return CatalogueProduit(
        ean=ligne.ean if is_ean_valid(ligne.ean) else None,
        designation=ligne.designation,
        designation_norm=designation_norm or None,
        marque=ligne.marque,
        unite_base=ligne.unite_base,
        conditionnement=ligne.conditionnement,
        colisage=colisage,
        volume_unitaire_ml=ligne.volume_unitaire_ml,
        source_fournisseur=ligne.source_fournisseur,
        categorie_code=_resolve_categorie_code(ligne, designation_norm, labelled),
        prix_unitaire_cts=ligne.prix_unitaire_cts,
        taux_tva_centieme=ligne.taux_tva_centieme,
    )


def _build_conflit_desig(
    etl_import_id: int,
    ligne: LigneParsee,
    designation_entrante: str,
    resultat: ResultatDeduplication,
    designation_existante: Optional[str],
    ean_b: Optional[str],
) -> EtlConflict:
    """Construit un EtlConflict de type DESIGNATION_PROCHE."""
    ean_a = ligne.ean if is_ean_valid(ligne.ean) else None
    return EtlConflict(
        etl_import_id=etl_import_id,
        catalogue_produit_id=resultat.candidate_id,
        designation_entrante=designation_entrante,
        designation_existante=designation_existante,
        score_similarite=resultat.score,
        type_conflit=_TYPE_DESIGNATION_PROCHE,
        ean_a=ean_a,
        ean_b=ean_b,
        suggestion=_SUGGESTION_MERGED,
    )


def _find_candidate_norm(
    candidate_id: Optional[int],
    candidates: list[tuple[int, str]],
) -> Optional[str]:
    """Retrouve la designation_norm du candidat dans la liste pré-chargée."""
    if candidate_id is None:
        return None
    return next((norm for cid, norm in candidates if cid == candidate_id), None)


def _compute_final_statut(nb_conflit: int, nb_erreur: int) -> str:
    """Retourne SUCCES si aucun conflit ni erreur, PARTIEL sinon."""
    if nb_conflit == 0 and nb_erreur == 0:
        return _STATUT_SUCCES
    return _STATUT_PARTIEL


# ── Handlers par cas ──────────────────────────────────────────────────────────


async def _record_colisage_observed(
    produit_repo: AsyncCatalogueProduitRepository,
    produit_id: Optional[int],
    ligne: LigneParsee,
) -> None:
    """Enregistre le colisage observé sur la ligne dans le pivot (idempotent)."""
    if not produit_id or not ligne.colisage or ligne.colisage <= 1:
        return
    try:
        await produit_repo.record_colisage(
            produit_id=produit_id,
            colisage=ligne.colisage,
            source_fournisseur=ligne.source_fournisseur,
        )
    except Exception as exc:
        logger.warning(
            "Enregistrement colisage échoué produit_id=%s colisage=%s: %s",
            produit_id, ligne.colisage, exc,
        )


async def _handle_ean_match(
    ligne: LigneParsee,
    produit_existant: CatalogueProduit,
    conflict_repo: AsyncEtlConflictRepository,
    produit_repo: AsyncCatalogueProduitRepository,
    etl_import_id: int,
) -> str:
    """EAN trouvé : doublon exact (ok) ou collision cross-fournisseur (conflit)."""
    if produit_existant.source_fournisseur == ligne.source_fournisseur:
        # Mettre à jour les données fournisseur (ADR-25)
        if ligne.prix_unitaire_cts is not None:
            produit_existant.prix_unitaire_cts = ligne.prix_unitaire_cts
        if ligne.taux_tva_centieme is not None:
            produit_existant.taux_tva_centieme = ligne.taux_tva_centieme
        if ligne.conditionnement:
            produit_existant.conditionnement = ligne.conditionnement
        if ligne.unite_base:
            produit_existant.unite_base = ligne.unite_base
        await _record_colisage_observed(produit_repo, produit_existant.id, ligne)
        return _RESULT_OK
    existing = await conflict_repo.get_existing_pending(
        ligne.designation, produit_existant.id
    )
    if existing is not None:
        return _RESULT_CONFLIT
    conflict = EtlConflict(
        etl_import_id=etl_import_id,
        catalogue_produit_id=produit_existant.id,
        designation_entrante=ligne.designation,
        designation_existante=produit_existant.designation,
        score_similarite=None,
        type_conflit=_TYPE_EAN_COLLISION,
        ean_a=ligne.ean,
        ean_b=produit_existant.ean,
        suggestion=_SUGGESTION_KEPT_SEPARATE,
    )
    await conflict_repo.create(conflict)
    return _RESULT_CONFLIT


async def _handle_classification(
    ligne: LigneParsee,
    candidates: list[tuple[int, str]],
    labelled: list[tuple[str, str]],
    produit_repo: AsyncCatalogueProduitRepository,
    conflict_repo: AsyncEtlConflictRepository,
    etl_import_id: int,
) -> str:
    """Classification Jaro-Winkler avec logique multi-EAN.

    Règles (audit 2026-04-24) :
      - NEW : crée un nouveau CatalogueProduit
      - MATCH désignation :
          - EAN entrant absent OU = EAN candidat → merge (comportement standard)
          - EAN entrant ≠ EAN candidat :
              - attributs physiques identiques → AJOUTE EAN comme secondaire
              - attributs physiques différents → crée un produit distinct
      - CONFLIT sans EAN valide des deux côtés → log conflit DESIGNATION_PROCHE
      - CONFLIT avec EANs valides différents → crée produit distinct (pas de conflit)
    """
    resultat = classify_designation(ligne.designation, candidates)
    if resultat.decision == DecisionDeduplication.NEW:
        produit = _build_produit(ligne, resultat.designation_norm, labelled)
        await produit_repo.create(produit)
        if (
            produit.designation_norm
            and produit.categorie_code
            and produit.categorie_code != _CODE_AUTRE
        ):
            labelled.append((produit.designation_norm, produit.categorie_code))
        # Auto-enrichissement du brand dictionary
        try:
            from scripts.etl.parsers.brand_dictionary import get_brand_dictionary
            bd = get_brand_dictionary()
            bd.enrich_from_validated_product(
                ligne.designation, produit.categorie_code,
            )
        except Exception:
            pass  # Ne pas bloquer l'import si le brand dict échoue
        await _record_colisage_observed(produit_repo, produit.id, ligne)
        return _RESULT_OK

    # Récupérer le candidat pour les deux cas suivants
    ean_a = ligne.ean if is_ean_valid(ligne.ean) else None
    candidate_product: Optional[CatalogueProduit] = None
    ean_b: Optional[str] = None
    if resultat.candidate_id is not None:
        candidate_product = await produit_repo.get_by_id(resultat.candidate_id)
        if candidate_product is not None:
            ean_b = candidate_product.ean

    # MATCH désignation : décider merge vs secondary-EAN vs produit distinct
    if resultat.decision == DecisionDeduplication.MATCH:
        # Cas 1 : EAN entrant absent OU déjà = EAN candidat → merge classique
        if not ean_a or not ean_b or not is_ean_valid(ean_b) or ean_a == ean_b:
            if candidate_product is not None:
                await _record_colisage_observed(produit_repo, candidate_product.id, ligne)
            return _RESULT_OK
        # Cas 2 : EANs valides différents → regarder les attributs physiques
        if candidate_product is not None and _same_physical_attrs(ligne, candidate_product):
            # Même produit logique, EAN cross-pays → ajouter EAN secondaire
            try:
                await produit_repo.add_secondary_ean(
                    candidate_product.id, ean_a, ligne.source_fournisseur,
                )
            except Exception as exc:
                logger.warning(
                    "Ajout EAN secondaire échoué pour produit_id=%s ean=%s: %s",
                    candidate_product.id, ean_a, exc,
                )
            await _record_colisage_observed(produit_repo, candidate_product.id, ligne)
            return _RESULT_OK
        # Cas 3 : attributs physiques différents → produit distinct
        produit = _build_produit(ligne, resultat.designation_norm, labelled)
        await produit_repo.create(produit)
        if produit.designation_norm and produit.categorie_code and produit.categorie_code != _CODE_AUTRE:
            labelled.append((produit.designation_norm, produit.categorie_code))
        await _record_colisage_observed(produit_repo, produit.id, ligne)
        return _RESULT_OK

    cand_norm = _find_candidate_norm(resultat.candidate_id, candidates)

    # CONFLIT (Jaro-Winkler zone floue, 0.85-0.95) avec EANs valides différents
    # → produits distincts par définition, pas de conflit
    if ean_a and ean_b and is_ean_valid(ean_b) and ean_a != ean_b:
        if candidate_product is not None and _same_physical_attrs(ligne, candidate_product):
            # Même produit logique détecté malgré CONFLIT fuzzy → secondary EAN
            try:
                await produit_repo.add_secondary_ean(
                    candidate_product.id, ean_a, ligne.source_fournisseur,
                )
            except Exception as exc:
                logger.warning(
                    "Ajout EAN secondaire échoué pour produit_id=%s ean=%s: %s",
                    candidate_product.id, ean_a, exc,
                )
            await _record_colisage_observed(produit_repo, candidate_product.id, ligne)
            return _RESULT_OK
        produit = _build_produit(ligne, resultat.designation_norm, labelled)
        await produit_repo.create(produit)
        if produit.designation_norm and produit.categorie_code and produit.categorie_code != _CODE_AUTRE:
            labelled.append((produit.designation_norm, produit.categorie_code))
        await _record_colisage_observed(produit_repo, produit.id, ligne)
        return _RESULT_OK

    existing = await conflict_repo.get_existing_pending(
        ligne.designation, resultat.candidate_id
    )
    if existing is not None:
        return _RESULT_CONFLIT
    conflict = _build_conflit_desig(
        etl_import_id, ligne, ligne.designation, resultat, cand_norm, ean_b
    )
    await conflict_repo.create(conflict)
    return _RESULT_CONFLIT


# ── Orchestration par ligne ───────────────────────────────────────────────────


async def _process_ligne(
    ligne: LigneParsee,
    candidates: list[tuple[int, str]],
    labelled: list[tuple[str, str]],
    produit_repo: AsyncCatalogueProduitRepository,
    conflict_repo: AsyncEtlConflictRepository,
    etl_import_id: int,
) -> str:
    """Traite une ligne : validation → EAN → classification. Retourne _RESULT_*."""
    if not ligne.designation or not ligne.unite_base or not ligne.source_fournisseur:
        logger.warning(
            "ETL ligne rejetée (champs requis manquants) import=%s desig=%r ean=%s source=%s",
            etl_import_id, ligne.designation, ligne.ean, ligne.source_fournisseur,
        )
        return _RESULT_ERREUR
    if is_ean_valid(ligne.ean):
        produit_existant = await produit_repo.get_by_ean(ligne.ean)  # type: ignore[arg-type]
        if produit_existant is not None:
            return await _handle_ean_match(
                ligne, produit_existant, conflict_repo, produit_repo, etl_import_id
            )
    return await _handle_classification(
        ligne, candidates, labelled, produit_repo, conflict_repo, etl_import_id
    )


# ── Point d'entrée principal ──────────────────────────────────────────────────


def compute_line_confidence(ligne: LigneParsee) -> int:
    """Score de confiance 0-100 pour une ligne parsée.

    Critères pondérés :
      - EAN valide (8/13 digits) : 25pts, EAN présent invalide : 10pts
      - Catégorie résolue non AUTRE : 20pts
      - Prix unitaire > 0 : 20pts
      - Quantité > 0 : 15pts
      - Marque identifiée : 10pts
      - Montants cohérents (qte*pu ≈ ht) : 10pts
    """
    import re
    score = 0
    if ligne.ean:
        if re.match(r"^\d{8}(\d{5})?$", ligne.ean):
            score += 25
        else:
            score += 10
    if ligne.categorie_code and ligne.categorie_code != "AUTRE":
        score += 20
    if ligne.prix_unitaire_cts and ligne.prix_unitaire_cts > 0:
        score += 20
    if ligne.quantite and ligne.quantite > 0:
        score += 15
    if ligne.marque:
        score += 10
    if (
        ligne.quantite
        and ligne.prix_unitaire_cts
        and ligne.montant_ht_cts is not None
    ):
        expected = round(ligne.quantite * ligne.prix_unitaire_cts)
        if abs(expected - ligne.montant_ht_cts) < 2:
            score += 10
    return min(score, 100)


def _apply_facture_metadata(
    import_obj: "EtlImport",
    metadata: Optional[FactureMetadata],
) -> None:
    """Copie les métadonnées facture sur l'EtlImport (ADR-25)."""
    if metadata is None:
        return
    import_obj.numero_facture = metadata.numero_facture
    import_obj.date_facture = metadata.date_facture
    import_obj.montant_ht_total = metadata.montant_ht_total
    import_obj.montant_tva_total = metadata.montant_tva_total
    import_obj.montant_ttc_total = metadata.montant_ttc_total
    import_obj.vendor_code = metadata.vendor_code
    import_obj.quality_score = metadata.quality_score
    import_obj.ecart_reconciliation = metadata.ecart_reconciliation
    import_obj.client_name = metadata.client_name
    import_obj.target_tenant_id = metadata.target_tenant_id


async def run_import(
    db: AsyncSession,
    lignes: list[LigneParsee],
    etl_import_id: int,
    metadata: Optional[FactureMetadata] = None,
    preview_mode: bool = False,
) -> None:
    """Orchestre l'import ETL d'une liste de lignes parsées (ADR-08 + ADR-25).

    Deux modes :
        - preview_mode=False (défaut) : classique catalogue.
          PENDING → RUNNING → (SUCCES | PARTIEL | ECHEC).
        - preview_mode=True : workflow facture fournisseur.
          PENDING → RUNNING → PREVIEW (attend validation opérateur).
          L'import catalogue n'est PAS lancé — seulement comptage + metadata.

    Les conflits sont persistés dans etl_conflicts (ADR-15).
    Le commit est à la charge de l'appelant (Celery task ou endpoint).

    Args:
        db: AsyncSession fournie par la Celery task ou un endpoint admin.
        lignes: Lignes parsées issues d'un parser fournisseur.
        etl_import_id: ID de l'EtlImport déjà créé en DB (statut PENDING).
        metadata: Métadonnées facture (ADR-25). Persistées sur l'EtlImport.
        preview_mode: Si True, s'arrête à PREVIEW sans créer de produits.

    Raises:
        ValueError: Si l'EtlImport n'est pas trouvé en base.
    """
    import_repo = AsyncEtlImportRepository(db)
    produit_repo = AsyncCatalogueProduitRepository(db)
    conflict_repo = AsyncEtlConflictRepository(db)

    import_obj = await import_repo.get_by_id(etl_import_id)
    if import_obj is None:
        raise ValueError(f"EtlImport {etl_import_id} introuvable")

    import_obj.nb_lignes_total = len(lignes)
    _apply_facture_metadata(import_obj, metadata)
    await import_repo.update_statut(import_obj, _STATUT_RUNNING)

    if preview_mode:
        # En mode preview, on ne lance pas l'import catalogue.
        # On affine les catégories (régie générique → 91 codes) via keywords.
        labelled_rows = await db.execute(
            _sa_select(
                CatalogueProduit.designation_norm,
                CatalogueProduit.categorie_code,
            ).where(
                CatalogueProduit.designation_norm.is_not(None),
                CatalogueProduit.categorie_code.is_not(None),
                CatalogueProduit.categorie_code != _CODE_AUTRE,
            )
        )
        preview_labelled: list[tuple[str, str]] = list(labelled_rows.all())

        # Layer 0 : lookup corrections manuelles précédentes
        correction_cache: dict[str, str] = {}
        try:
            from app.models.catalogue.etl_correction_history import EtlCorrectionHistory
            corr_rows = await db.execute(
                select(EtlCorrectionHistory.designation_norm, EtlCorrectionHistory.new_value)
                .where(EtlCorrectionHistory.field_corrected == "categorie_code")
                .order_by(EtlCorrectionHistory.id.desc())
            )
            for row in corr_rows.all():
                if row[0] not in correction_cache:
                    correction_cache[row[0]] = row[1]
        except Exception:
            pass  # Non-bloquant

        # Enrichissement universel depuis la désignation (marque, conditionnement,
        # volume, contenant, degré). Concerne tous les parsers ; no-op si la ligne
        # est déjà complète. Avant classification catégorie : permet à la marque
        # d'alimenter le signal ALC_*, SURG_GLACE, etc.
        from app.services.catalogue.etl_designation_enrichment import (
            enrich_ligne_from_designation,
        )
        for ligne in lignes:
            enrich_ligne_from_designation(ligne)

        for ligne in lignes:
            norm = normalize_designation(ligne.designation)
            # Layer 0 : correction manuelle précédente (match exact)
            if norm in correction_cache:
                ligne.categorie_code = correction_cache[norm]
            else:
                ligne.categorie_code = _resolve_categorie_code(
                    ligne, norm, preview_labelled,
                )
        # Auto-fill multi-couches (S1-S4) : remplit EAN/marque/cat/cond/prix
        # depuis le catalogue existant, l'historique de corrections et le
        # TF-IDF avec seuils graduels. Trace chaque auto-apply dans
        # `ligne.auto_applied_fields` pour que l'UI affiche un badge révocable.
        from app.services.catalogue.etl_auto_fill import run_auto_fill
        preview_candidates = await produit_repo.get_all_candidates()
        vendor_code = metadata.vendor_code if metadata else None
        await run_auto_fill(
            db, lignes,
            vendor_code=vendor_code,
            preview_candidates=preview_candidates,
            produit_repo=produit_repo,
        )

        # Recalcul final de confidence après auto-fill (EAN ajouté → +25pts etc.)
        for ligne in lignes:
            ligne.confidence_score = compute_line_confidence(ligne)

        import_obj.nb_lignes_ok = len(lignes)
        import_obj.lignes_data = [dataclasses.asdict(l) for l in lignes]
        await import_repo.update_statut(import_obj, _STATUT_PREVIEW)
        return

    candidates = await produit_repo.get_all_candidates()

    # Construire l'index IDF Soft TF-IDF pour ce batch
    build_idf_from_candidates(candidates)

    rows = await db.execute(
        _sa_select(
            CatalogueProduit.designation_norm,
            CatalogueProduit.categorie_code,
        ).where(
            CatalogueProduit.designation_norm.is_not(None),
            CatalogueProduit.categorie_code.is_not(None),
            CatalogueProduit.categorie_code != _CODE_AUTRE,
        )
    )
    labelled: list[tuple[str, str]] = list(rows.all())

    nb_ok = nb_conflit = nb_erreur = 0
    for ligne in lignes:
        result = await _process_ligne(
            ligne, candidates, labelled, produit_repo, conflict_repo, etl_import_id
        )
        if result == _RESULT_OK:
            nb_ok += 1
        elif result == _RESULT_CONFLIT:
            nb_conflit += 1
        else:
            nb_erreur += 1

    import_obj.nb_lignes_ok = nb_ok
    import_obj.nb_lignes_conflit = nb_conflit
    import_obj.nb_lignes_erreur = nb_erreur
    await import_repo.update_statut(
        import_obj, _compute_final_statut(nb_conflit, nb_erreur)
    )

    # Observabilité : log un résumé visible même sans DB audit
    logger.info(
        "ETL import=%s source=%s total=%d ok=%d conflit=%d erreur=%d",
        etl_import_id,
        (metadata.vendor_code if metadata else "?"),
        len(lignes), nb_ok, nb_conflit, nb_erreur,
    )
    if nb_erreur > 0 or nb_conflit > 0:
        logger.warning(
            "ETL import=%s : %d lignes en erreur, %d en conflit — voir etl_conflicts et logs WARN",
            etl_import_id, nb_erreur, nb_conflit,
        )

    # Persister le brand dictionary enrichi après chaque batch
    try:
        from scripts.etl.parsers.brand_dictionary import get_brand_dictionary
        get_brand_dictionary().save()
    except Exception:
        pass
