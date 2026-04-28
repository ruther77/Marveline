"""Auto-fill multi-étages des lignes ETL (S1-S4).

Objectif : remplir automatiquement EAN, marque, catégorie, conditionnement,
volume, prix et TVA d'une ligne parsée en s'appuyant sur le catalogue
existant, l'historique de corrections et le TF-IDF, plutôt que d'attendre
que l'opérateur clique "Appliquer" sur chaque bannière.

Chaque auto-fill est tracé dans `ligne.auto_applied_fields` pour que le
frontend puisse afficher un badge "auto X%" révocable par champ.

Étages (dans l'ordre, chaque étage ne remplit que les champs encore vides) :

    S1 — Désignation normalisée exacte (score 1.0)
         Si normalize_designation(ligne) == cp.designation_norm, match certain.
         Source dominante pour TAIYAT/ETHAN (nombreuses références réutilisées).

    S2 — article_fournisseur exact + même source_fournisseur (score 1.0)
         Principalement utile pour GNANAM (code interne sur facture OCR).

    S3 — Replay de l'historique de corrections (score 0.95)
         Si l'opérateur a déjà corrigé "VIMTO SODA 1L" → EAN X dans le passé,
         on l'applique aux nouveaux imports avec même designation_norm.

    S4 — Soft TF-IDF avec seuils graduels
         score ≥ 0.90 → auto-apply silencieux
         0.80 ≤ score < 0.90 → auto-apply avec badge révocable
         < 0.80 → suggestion uniquement (comportement existant)

Les étages supérieurs ne réécrivent jamais un champ déjà rempli par un étage
précédent ou par l'opérateur.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl_types import LigneParsee
from app.models.catalogue.catalogue_produit import CatalogueProduit
from app.services.catalogue.etl_deduplication import (
    build_idf_from_candidates, classify_designation_top_n,
    normalize_designation,
)

logger = logging.getLogger(__name__)

# Champs que l'auto-fill peut remplir (pas les montants calculés : HT, TTC).
_AUTOFILL_FIELDS: tuple[str, ...] = (
    "ean", "marque", "categorie_code", "conditionnement",
    "volume_unitaire_ml", "prix_unitaire_cts", "taux_tva_centieme",
)

# Seuils TF-IDF (S4)
AUTO_APPLY_SILENT = 0.90   # ≥ : apply silencieux
AUTO_APPLY_BADGE = 0.80    # ≥ : apply avec badge révocable
SUGGEST_ONLY = 0.70        # ≥ : suggestion (déjà en place)


def _produit_field(produit: CatalogueProduit, field: str) -> Any:
    """Getter robuste : centralise les champs catalogue équivalents."""
    return getattr(produit, field, None)


def _record_autofill(
    ligne: LigneParsee | dict,
    field: str,
    value: Any,
    source: str,
    score: float,
    candidate_id: Optional[int],
    candidate_designation: Optional[str],
) -> None:
    """Pose un champ + trace la source dans auto_applied_fields."""
    if value is None or value == "":
        return
    # Support mutation sur dataclass OR dict (le service tourne sur les deux
    # selon l'appelant : run_import passe des LigneParsee, le script backfill
    # passe des dict JSONB)
    if isinstance(ligne, dict):
        if ligne.get(field):
            return  # jamais écraser
        ligne[field] = value
        meta = ligne.setdefault("auto_applied_fields", {}) or {}
        if not isinstance(meta, dict):
            meta = {}
            ligne["auto_applied_fields"] = meta
        meta[field] = {
            "source": source,
            "score": round(float(score), 3),
            "candidate_id": candidate_id,
            "candidate_designation": candidate_designation,
        }
        ligne["auto_applied_fields"] = meta
    else:
        if getattr(ligne, field, None):
            return
        setattr(ligne, field, value)
        meta = ligne.auto_applied_fields or {}
        meta[field] = {
            "source": source,
            "score": round(float(score), 3),
            "candidate_id": candidate_id,
            "candidate_designation": candidate_designation,
        }
        ligne.auto_applied_fields = meta


def _get(ligne: LigneParsee | dict, field: str) -> Any:
    if isinstance(ligne, dict):
        return ligne.get(field)
    return getattr(ligne, field, None)


def _missing_fields(ligne: LigneParsee | dict) -> list[str]:
    """Liste des champs auto-fillables encore vides."""
    return [f for f in _AUTOFILL_FIELDS if not _get(ligne, f)]


def _apply_from_produit(
    ligne: LigneParsee | dict,
    produit: CatalogueProduit,
    source: str,
    score: float,
) -> int:
    """Copie les champs du produit existant sur la ligne (sans écraser).

    L'EAN ne se copie JAMAIS d'un fournisseur vers un autre : les codes-barres
    appartiennent au producteur et deux fournisseurs distincts vendant la même
    désignation normalisée ne partagent pas nécessairement le même EAN. Sans
    ce garde-fou, un match TF-IDF sur désignation copie l'EAN METRO sur une
    ligne TAIYAT et crée un faux EAN_COLLISION à la validation.
    """
    ligne_src = _get(ligne, "source_fournisseur")
    produit_src = getattr(produit, "source_fournisseur", None)
    filled = 0
    for field in _AUTOFILL_FIELDS:
        value = _produit_field(produit, field)
        if value is None:
            continue
        if _get(ligne, field):
            continue
        if field == "ean" and ligne_src and produit_src and ligne_src != produit_src:
            continue
        _record_autofill(
            ligne, field, value, source=source, score=score,
            candidate_id=produit.id,
            candidate_designation=produit.designation,
        )
        filled += 1
    return filled


# ── S1 : Désignation normalisée exacte ──────────────────────────────────────


async def auto_fill_layer_norm_exact(
    db: AsyncSession, lignes: list,
) -> int:
    """S1 — Match certain par designation_norm identique.

    Une query groupée pour toutes les normes présentes → O(1) au lieu de N.
    """
    if not lignes:
        return 0
    norms: dict[str, list] = {}
    for l in lignes:
        desig = _get(l, "designation") or _get(l, "designation_raw") or ""
        if not desig:
            continue
        norm = normalize_designation(desig)
        if norm:
            norms.setdefault(norm, []).append(l)
    if not norms:
        return 0
    rows = await db.execute(
        select(CatalogueProduit)
        .where(CatalogueProduit.designation_norm.in_(list(norms.keys())))
    )
    match_by_norm: dict[str, CatalogueProduit] = {}
    for prod in rows.scalars():
        # Si plusieurs produits partagent la même norme, on garde celui qui
        # a un EAN (le plus informatif). Déterministe via l'ID.
        existing = match_by_norm.get(prod.designation_norm)
        if existing is None:
            match_by_norm[prod.designation_norm] = prod
        elif not existing.ean and prod.ean:
            match_by_norm[prod.designation_norm] = prod
    filled = 0
    for norm, ligne_list in norms.items():
        prod = match_by_norm.get(norm)
        if not prod:
            continue
        for l in ligne_list:
            filled += _apply_from_produit(l, prod, source="norm_exact", score=1.0)
    return filled


# ── S2 : article_fournisseur exact + similarité designation ─────────────────


def _jaccard_tokens(a: Optional[str], b: Optional[str]) -> float:
    """Similarité Jaccard des tokens entre deux strings normalisées."""
    if not a or not b:
        return 0.0
    ta = set((a or "").split())
    tb = set((b or "").split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# Seuil Jaccard minimum entre la désignation actuelle et la désignation
# historique attachée au même article_fournisseur. Protège contre les codes
# fournisseurs collisionnés (cas ETHAN : art_four=124 → CAPRISUN + OASIS).
_S2_MIN_JACCARD = 0.35


async def auto_fill_layer_article_fournisseur(
    db: AsyncSession, lignes: list, vendor_code: Optional[str],
) -> int:
    """S2 — Match par code article fournisseur via historique des imports,
    avec **guard de similarité** pour éviter les collisions de codes.

    `CatalogueProduit` ne porte pas `article_fournisseur` → on cherche le code
    dans les `EtlImport.lignes_data` (JSONB) des imports VALIDATED avec même
    vendor_code, et on réutilise les champs consolidés (EAN/marque/cat/cond).

    Protection : on n'applique QUE si les deux désignations partagent assez
    de tokens (Jaccard ≥ {_S2_MIN_JACCARD}). Sinon on suppose une collision
    de code fournisseur et on skip.
    """
    if not lignes or not vendor_code:
        return 0
    codes: dict[str, list] = {}
    for l in lignes:
        if not _missing_fields(l):
            continue
        code = _get(l, "article_fournisseur")
        if not code:
            continue
        codes.setdefault(str(code), []).append(l)
    if not codes:
        return 0

    from app.models.catalogue.etl_import import EtlImport as _EI
    rows = await db.execute(
        select(_EI.lignes_data).where(
            _EI.vendor_code == vendor_code,
            _EI.statut.in_(["VALIDATED", "SUCCES", "PARTIEL"]),
            _EI.lignes_data.isnot(None),
        )
    )
    # Pour chaque code : liste de toutes les lignes historiques (on choisira
    # la bonne par similarité à chaque ligne courante, plutôt qu'un "best"
    # global qui ignore la correspondance sémantique).
    hist_by_code: dict[str, list[dict]] = {}
    for (lignes_data,) in rows.all():
        if not lignes_data:
            continue
        for hl in lignes_data:
            if not isinstance(hl, dict):
                continue
            hcode = hl.get("article_fournisseur")
            if not hcode or str(hcode) not in codes:
                continue
            hist_by_code.setdefault(str(hcode), []).append(hl)

    filled = 0
    for code, ligne_list in codes.items():
        candidates = hist_by_code.get(code) or []
        if not candidates:
            continue
        for l in ligne_list:
            # Trouver la ligne historique la plus similaire à la ligne courante.
            cur_norm = normalize_designation(
                _get(l, "designation") or _get(l, "designation_raw") or ""
            )
            best_hist: Optional[dict] = None
            best_sim = 0.0
            for hl in candidates:
                hist_norm = hl.get("designation_norm") or normalize_designation(
                    hl.get("designation") or ""
                )
                sim = _jaccard_tokens(cur_norm, hist_norm)
                if sim > best_sim:
                    best_sim = sim
                    best_hist = hl
            # Guard : si la meilleure similarité reste trop faible, on
            # considère que le code fournisseur est collisionné sur deux
            # produits distincts → ne pas propager.
            if best_hist is None or best_sim < _S2_MIN_JACCARD:
                continue
            for field in _AUTOFILL_FIELDS:
                value = best_hist.get(field)
                if value is None or value == "":
                    continue
                if field == "categorie_code" and value == "AUTRE":
                    continue
                if _get(l, field):
                    continue
                _record_autofill(
                    l, field, value, source="article_four", score=round(best_sim, 2),
                    candidate_id=None,
                    candidate_designation=best_hist.get("designation"),
                )
                filled += 1
    return filled


# ── S3 : Replay corrections manuelles historiques ───────────────────────────


async def auto_fill_layer_correction_history(
    db: AsyncSession, lignes: list,
) -> int:
    """S3 — Si l'opérateur a déjà corrigé (designation_norm, field), rejouer.

    On ne rejoue que les corrections vers des valeurs non vides, et seulement
    pour les champs encore vides sur la ligne. Score 0.95 (forte confiance
    sans être certaine : opérateur humain).
    """
    if not lignes:
        return 0
    from app.models.catalogue.etl_correction_history import EtlCorrectionHistory

    norms: set[str] = set()
    for l in lignes:
        desig = _get(l, "designation") or _get(l, "designation_raw") or ""
        if desig:
            norms.add(normalize_designation(desig))
    norms.discard("")
    if not norms:
        return 0
    # Charger TOUTES les corrections (volume petit, 100-1000 typ) et normaliser
    # les clés côté Python — l'historique contient du legacy uppercase stocké
    # tel quel (ligne.designation) alors que normalize_designation produit du
    # lowercase ascii. Sans re-normalisation, zéro match (bug 2026-04-24).
    rows = await db.execute(
        select(
            EtlCorrectionHistory.designation_norm,
            EtlCorrectionHistory.field_corrected,
            EtlCorrectionHistory.new_value,
        )
        .where(
            EtlCorrectionHistory.field_corrected.in_(list(_AUTOFILL_FIELDS)),
            EtlCorrectionHistory.new_value.isnot(None),
        )
        .order_by(EtlCorrectionHistory.id.desc())
    )
    # Map {norm_renormalized → {field → last_value}} : le plus récent gagne
    # (ORDER BY id DESC + dict first wins → on prend la première occurrence)
    history: dict[str, dict[str, str]] = {}
    for raw_norm, field, new_val in rows.all():
        key = normalize_designation(raw_norm)
        if not key or key not in norms:
            continue
        entry = history.setdefault(key, {})
        if field not in entry:  # first in DESC = le plus récent
            entry[field] = new_val
    if not history:
        return 0
    filled = 0
    for l in lignes:
        desig = _get(l, "designation") or _get(l, "designation_raw") or ""
        norm = normalize_designation(desig)
        if not norm or norm not in history:
            continue
        for field, raw_value in history[norm].items():
            if _get(l, field):
                continue
            value: Any = raw_value
            # Coerce types numériques
            if field in {"prix_unitaire_cts", "taux_tva_centieme", "volume_unitaire_ml"}:
                try:
                    value = int(raw_value)
                except (TypeError, ValueError):
                    continue
            _record_autofill(
                l, field, value, source="correction_history",
                score=0.95, candidate_id=None, candidate_designation=None,
            )
            filled += 1
    return filled


# ── S4 : Seuils graduels sur TF-IDF ─────────────────────────────────────────


async def auto_fill_layer_tfidf(
    db: AsyncSession, lignes: list, preview_candidates: list,
    repo, candidates_marques: Optional[dict[int, Optional[str]]] = None,
) -> int:
    """S4 — Similar products avec seuils graduels et matching smart marque-aware.

    - score ≥ 0.90 : auto-apply silencieux
    - 0.80 ≤ score < 0.90 : auto-apply avec source="tfidf_auto_soft" (badge UI)
    - 0.70 ≤ score < 0.80 : suggestion seulement (on stocke similar_products
                            mais on n'auto-apply pas)

    Si `candidates_marques` est fourni, active le scoring smart : les lignes
    avec même marque que le candidat reçoivent un bonus (crucial cross-vendor
    TAIYAT↔METRO).
    """
    if not preview_candidates:
        return 0
    build_idf_from_candidates(preview_candidates)
    filled = 0
    for l in lignes:
        if _get(l, "ean"):
            continue  # déjà match direct
        desig = _get(l, "designation") or _get(l, "designation_raw") or ""
        if not desig.strip():
            continue
        marque_entrante = _get(l, "marque")
        top = classify_designation_top_n(
            desig, preview_candidates, seuil=SUGGEST_ONLY, n=3,
            marque_entrante=marque_entrante,
            candidates_marques=candidates_marques,
        )
        if not top:
            # Nettoyer le slot si pas de match
            if isinstance(l, dict):
                l["similar_products"] = None
            else:
                l.similar_products = None
            continue

        # Enrichir + poser similar_products (pour l'UI fallback)
        enriched_similar = []
        for t in top:
            prod = await repo.get_by_id(t["candidate_id"])
            enriched_similar.append({
                "candidate_id": t["candidate_id"],
                "designation": prod.designation if prod else t["designation_norm"],
                "ean": prod.ean if prod else None,
                "categorie_code": prod.categorie_code if prod else None,
                "marque": prod.marque if prod else None,
                "conditionnement": prod.conditionnement if prod else None,
                "volume_unitaire_ml": getattr(prod, "volume_unitaire_ml", None) if prod else None,
                "prix_unitaire_cts": prod.prix_unitaire_cts if prod else None,
                "taux_tva_centieme": getattr(prod, "taux_tva_centieme", None) if prod else None,
                "score": t["score"],
            })
        if isinstance(l, dict):
            l["similar_products"] = enriched_similar
        else:
            l.similar_products = enriched_similar

        # Auto-apply selon seuil
        best = top[0]
        best_score = float(best.get("score", 0))
        if best_score < AUTO_APPLY_BADGE:
            continue  # juste suggestion, pas d'auto-apply
        prod = await repo.get_by_id(best["candidate_id"])
        if not prod:
            continue
        source = "tfidf_auto" if best_score >= AUTO_APPLY_SILENT else "tfidf_auto_soft"
        filled += _apply_from_produit(l, prod, source=source, score=best_score)
    return filled


# ── Orchestration ──────────────────────────────────────────────────────────


async def run_auto_fill(
    db: AsyncSession,
    lignes: list,
    *,
    vendor_code: Optional[str] = None,
    preview_candidates: Optional[list] = None,
    produit_repo=None,
) -> dict[str, int]:
    """Orchestre les 4 couches d'auto-fill. Retourne stats pour logs.

    Idempotent : une seconde exécution ne touchera que les champs encore vides.
    """
    from app.repositories.catalogue.catalogue_produit import (
        AsyncCatalogueProduitRepository,
    )
    if produit_repo is None:
        produit_repo = AsyncCatalogueProduitRepository(db)
    if preview_candidates is None:
        preview_candidates = await produit_repo.get_all_candidates()

    # Construire la map {id: marque} pour le scoring smart en S4
    candidates_marques: dict[int, Optional[str]] = {}
    try:
        from app.models.catalogue.catalogue_produit import CatalogueProduit
        cand_ids = [cid for cid, _ in preview_candidates]
        if cand_ids:
            rows = await db.execute(
                select(CatalogueProduit.id, CatalogueProduit.marque)
                .where(CatalogueProduit.id.in_(cand_ids))
            )
            candidates_marques = {row_id: row_marque for row_id, row_marque in rows.all()}
    except Exception as exc:
        logger.debug("Auto-fill: brand map build failed: %s", exc)

    s1 = await auto_fill_layer_norm_exact(db, lignes)
    s2 = await auto_fill_layer_article_fournisseur(db, lignes, vendor_code)
    s3 = await auto_fill_layer_correction_history(db, lignes)
    s4 = await auto_fill_layer_tfidf(
        db, lignes, preview_candidates, produit_repo,
        candidates_marques=candidates_marques,
    )

    # S5 — OpenFoodFacts (enrichissement EAN externe, best-effort, plafonné)
    # N'appelle OFF que pour les lignes SANS EAN après S1-S4, avec marque+désignation.
    s5 = 0
    try:
        from app.services.catalogue.off_enrichment import batch_enrich_lignes_with_off
        s5 = await batch_enrich_lignes_with_off(lignes, max_lookups=20)
    except Exception as exc:
        logger.debug("OFF enrichment skipped: %s", exc)

    stats = {"s1_norm_exact": s1, "s2_article_four": s2,
             "s3_history": s3, "s4_tfidf": s4, "s5_off": s5,
             "total_fields": s1 + s2 + s3 + s4 + s5}
    logger.info("Auto-fill stats: %s", stats)
    return stats
