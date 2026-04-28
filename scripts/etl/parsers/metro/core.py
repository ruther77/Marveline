"""Core du parser METRO v2 — assemblage final.

Fonctions publiques :
  - parse(fichier) → list[LigneParsee]
  - parse_facture(fichier) → tuple[list[LigneParsee], FactureMetadata]
  - parse_with_facture_metrics(fichier) → tuple[list[LigneParsee], dict]
"""
from __future__ import annotations

import gc
import logging
from pathlib import Path
from typing import Optional

from app.etl_types import LigneParsee

from scripts.etl.parsers.metro.columns import (
    ExtractedLine,
    extract_line,
    group_by_y,
    line_text,
    parse_fr_number,
)
from scripts.etl.parsers.metro.conditionnement import extract_conditionnement
from scripts.etl.parsers.metro.constants import (
    ARTICLES_DIVERS_KEYWORDS,
    DISCOUNT_PATTERNS,
    NON_PRODUCT_PATTERNS,
    SOURCE_FOURNISSEUR,
    TVA_CODE_TO_CENTIEME,
)
from scripts.etl.parsers.metro.facture import (
    RE_DONT_COTIS,
    build_facture_metadata,
    extract_discount_amount,
    extract_header,
    extract_promo_ratio,
    extract_surcharge_amount,
    extract_total_ht,
    select_best_adjustments,
)
from scripts.etl.parsers.metro.tokenizer import (
    TokenType,
    build_designation,
    build_designation_raw,
    extract_container,
    extract_degree,
    extract_volume_ml,
)
from scripts.etl.parsers.brand_dictionary import get_brand_dictionary

logger = logging.getLogger(__name__)

# Charger le brand dictionary au module load
_brand_dict = get_brand_dictionary()
_known_brands = _brand_dict.as_frozenset()

# ── Extraction de marque — régie-aware, dictionary-first ─────────────────────

# Mots qui sont des PRODUITS, jamais des marques
_PRODUCT_WORDS: frozenset[str] = frozenset({
    # Aliments
    "EPINARD", "BEURRE", "CREME", "LAIT", "FROMAGE", "YAOURT", "OEUF",
    "PAIN", "BRIOCHE", "CROISSANT", "FARINE", "SEMOULE", "RIZ", "PATE",
    "SUCRE", "CHOCOLAT", "CONFITURE", "MIEL", "BONBON", "BISCUIT", "GATEAU",
    "TOMATE", "CAROTTE", "OIGNON", "POMME", "BANANE", "ORANGE", "SALADE",
    "HARICOT", "LENTILLE", "POIS", "CHAMPIGNON", "POIVRON", "COURGETTE",
    "POULET", "BOEUF", "PORC", "AGNEAU", "VEAU", "CANARD", "DINDE",
    "SAUMON", "THON", "CREVETTE", "MOULE", "HUITRE",
    "CHIPS", "CACAHUETE", "OLIVE", "CORNICHON",
    "HUILE", "VINAIGRE", "MOUTARDE", "MAYO", "MAYONNAISE", "MAYONAISE",
    "KETCHUP", "SAUCE", "SEL", "POIVRE", "CURRY", "PAPRIKA",
    # Boissons (mots produit, pas marques)
    "EAU", "SODA", "JUS", "SIROP", "CAFE", "THE", "LIMONADE",
    "VODKA", "WHISKY", "WHISKEY", "COGNAC", "RHUM", "GIN", "PASTIS",
    "BIERE", "BEER", "VIN", "CHAMPAGNE", "CREMANT", "PROSECCO",
    # Qualificatifs vin (appellations = pas des marques)
    "ROUGE", "BLANC", "ROSE", "BRUT", "SEC", "DOUX", "DEMI",
    "BLONDE", "BRUNE", "AMBREE", "NOIR",
    # Fournitures
    "SERVIETTE", "GOBELET", "ASSIETTE", "COUTEAU", "FOURCHETTE",
    "BOBINE", "ROULEAU", "FILM", "ALU", "PAPIER", "TAMPON",
    "JAVEL", "SAVON", "LESSIVE", "EPONGE",
    "POT", "BOL", "BLOC", "SET", "BOULE", "PAILLE", "GOB", "COUV",
    "SABOT", "BRIDE", "ESSOREUR", "PLANCH",
    # Termes génériques souvent capturés à tort comme marques (step 5 heuristique)
    "MIE", "AMBRE", "SAC", "POUDRE", "MARBREE", "TRANCHE", "DOREE", "PALET",
    "GRO", "MAIS", "SWEET", "CLOU", "GIROFLE", "SECHE", "MOULU",
    "STEAK", "HACHE", "FILET", "COTE", "JAMBON", "SAUCISSE",
    "GLACE", "SORBET", "ESQUIMAU",
    "BARQUETTE", "CAISSETTE", "NAPPE",
    # Descripteurs génériques
    "ALLEGEE", "ENTIER", "ENTIERE", "NATURE", "COMPLET", "BIO",
    "FRAIS", "SURGELE", "CONSERVE", "SECHE",
    "GRAND", "PETIT", "GROS", "MINI", "MAXI",
})

# Mots d'appellation vin / terroir (jamais des marques)
_WINE_TERROIR_WORDS: frozenset[str] = frozenset({
    "AOC", "AOP", "IGP", "AC", "CB", "MIL", "MILLESIME",
    "BORDEAUX", "MEDOC", "BOURGOGNE", "PROVENCE", "LANGUEDOC",
    "COTES", "COTE", "CHATEAU", "DOMAINE", "SAINT", "HAUT",
    "PAUILLAC", "MARGAUX", "POMEROL", "FRONSAC", "GRAVES",
    "EMILION", "MOULIS", "LISTRAC", "LALANDE",
    "ANJOU", "TAVEL", "BEAUJOLAIS", "SANCERRE", "CHABLIS",
    "MUSCADET", "POUILLY", "ALSACE", "RIESLING",
})

# Domaines/châteaux connus (sont des marques pour le vin)
_WINE_DOMAINS: dict[str, str] = {
    "MOUTON CADET": "MOUTON CADET",
    "MOUTON CAD": "MOUTON CADET",
    "MOET": "MOËT & CHANDON", "MOET&CHANDON": "MOËT & CHANDON",
    "VEUVE CLICQUOT": "VEUVE CLICQUOT", "CLICQUOT": "VEUVE CLICQUOT",
    "CLIQUOT": "VEUVE CLICQUOT",
    "RUINART": "RUINART", "MUMM": "MUMM",
    "TAITTINGER": "TAITTINGER", "BOLLINGER": "BOLLINGER",
    "POMMERY": "POMMERY", "LANSON": "LANSON",
    "NICOLAS FEUILLATTE": "NICOLAS FEUILLATTE",
    "LABEGORCE": "LABEGORCE", "MONDESIR": "MONDESIR",
    "LAJARDE": "LAJARDE", "VERGNES": "VERGNES",
    "DAUPHINS": "C. DAUPHINS", "C. DAUPHINS": "C. DAUPHINS",
    "MAURIN": "MAURIN", "MAZET": "MAZET",
    "MURAIL": "MURAIL", "BERGERIE": "BERGERIE",
    "DELLAC": "DELLAC", "OCEADE": "OCEADE", "DILLON": "DILLON",
    "STJAMES": "SAINT JAMES", "ST JAMES": "SAINT JAMES",
    "LAUR": "M. LAUR", "M. LAUR": "M. LAUR",
    "MARTINI": "MARTINI",
    "PAVEIL": "PAVEIL DE LUZE", "PAVEIL DE LUZE": "PAVEIL DE LUZE",
    "MAUCAILL": "MAUCAILLOU", "MAUCAILLOU": "MAUCAILLOU",
    "GISCOURS": "GISCOURS", "CLEMENT PICHON": "CLEMENT PICHON",
    "FUGUE NENIN": "FUGUE DE NENIN", "NENIN": "FUGUE DE NENIN",
    "LAMOTH": "LAMOTHE JOUBERT", "LADMOTH": "LAMOTHE JOUBERT",
    # Champagnes & mousseux
    "MUSCADOR": "MUSCADOR",
    "VEUVE ELISABETH": "VEUVE ELISABETH",
    "PELLETIER": "PELLETIER", "CH PELLETIER": "PELLETIER",
    "FEUILLATTE": "NICOLAS FEUILLATTE", "FEUILLATE": "NICOLAS FEUILLATTE",
    "NFEUILLATTE": "NICOLAS FEUILLATTE",
    "ROMET": "ROMET",
    # Vins — châteaux / domaines fréquents
    "CHAMPAGNE ARCINS": "CH. CHAMPAGNE D'ARCINS", "ARCINS": "CH. CHAMPAGNE D'ARCINS",
    "BEAUSEJOUR": "CH. BEAUSÉJOUR", "BEAUSEJOUR HOST": "CH. BEAUSÉJOUR",
    "CONNET TALBOT": "CONNÉTABLE DE TALBOT", "TALBOT": "CONNÉTABLE DE TALBOT",
    "CLOS CURE": "CLOS LA CURE",
    "VIGNOT": "VIGNOT",
    "JP CHENET": "JP CHENET", "CHENET": "JP CHENET",
    "DEGAVES": "DÉGAVES",
    "COSTIS": "CH. COSTIS",
    "LA POINTE": "CH. LA POINTE",
    "ROC CAZAD": "ROC DE CAZADE", "CAZAD": "ROC DE CAZADE",
    "PERRON ROLL": "CH. PERRON", "CRX PERRON": "CH. PERRON",
    "TOUR PRIGNAC": "TOUR DE PRIGNAC", "PRIGNAC": "TOUR DE PRIGNAC",
    "TOUR DE BESSAN": "TOUR DE BESSAN",
    "TOUR DE PEZ": "TOUR DE PEZ",
    "PRIEURE SOL": "PRIEURÉ DE LA SOLITUDE",
    "CHATAIGNER": "CHATAIGNER",
    "PUY VALLON": "PUY VALLON",
    "DARTOIS": "DARTOIS",
    "FLEUR CHAP": "FLEUR CHAPILLON",
    "BAJAC": "BAJAC",
    "BROZ": "BROZ",
    "LAROS TRINT": "LAROSE TRINTAUDON",
    "GADLETS BONNAT": "GADLETS BONNAT",
    "HT POINTE": "CH. HAUTE POINTE",
    # Session 2 — derniers domaines fréquents
    "CADET ROUGE": "MOUTON CADET", "MOUTON CA": "MOUTON CADET",
    "EMILE DURAND": "EMILE DURAND", "CHABLIS": "EMILE DURAND",
    "EXCEL. STL": "EXCELLENCE STL",
    "TERRASSON": "TERRASSON",
    "DULUC DUCRU": "DULUC DE DUCRU",
    "MONDES": "MONDES",
    "RIBEAUP": "RIBEAUPIERRE",
    "M&C ICE": "MOËT & CHANDON",
}

# Private labels METRO
_PRIVATE_LABEL_MAP: dict[str, str] = {
    "ARO": "ARO", "MPRO": "METRO PRO", "MC": "MARQUE COMMUNE",
    "MP": "METRO PRO", "MPD": "METRO PRO", "MCHEF": "METRO CHEF",
    "METRO CHEF": "METRO CHEF", "MARQUE COMMUNE": "MARQUE COMMUNE",
}

# Abréviations catégorie METRO (à ignorer pour la marque)
_CATEGORY_ABBREVS: frozenset[str] = frozenset({
    "WH", "CH", "COG", "COG.", "BDX", "BURG", "PROV",
    "RS", "RSE", "RGE", "BLC", "BLE", "BLDE", "SPE", "SUP",
    "DM", "PRS", "TRAD", "ORIG",
})


def _extract_brand(
    tokens: list,
    regie: Optional[str],
    designation: str,
) -> tuple[Optional[str], Optional[str]]:
    """Extraction de marque — dictionary-first, régie-aware.

    Retourne (marque, brand_category) ou (None, None).

    Stratégie par priorité :
      1. Brand dict multi-mots (exact)
      2. Brand dict single word
      3. Domaines vin (si régie T/M)
      4. Private labels (ARO, MPRO, MC)
      5. Heuristique régie-aware (exclut mots-produit + terroir)
      6. NULL (pas de marque = mieux qu'une fausse)
    """
    from scripts.etl.parsers.metro.ocr_clean import expand_abbreviation as _expand

    marque = None
    brand_cat: Optional[str] = None

    is_wine = regie in ("T", "M")
    is_food = regie in ("E", "F")
    # Détection vin par désignation si régie absente
    if not is_wine and regie is None:
        desig_up = designation.upper()
        _WINE_HINTS = ("BORDEAUX", "MEDOC", "BOURGOGNE", "COTES DU RHONE",
                        "SAINT EMILION", "ST EM", "PAYS OC", "IGP MED",
                        "CHAMPAGNE", "PROSECCO", "CREMANT", "ROSE ANJOU")
        if any(h in desig_up for h in _WINE_HINTS):
            is_wine = True

    # ── 1. Brand dict multi-mots ─────────────────────────────────────────
    desig_words = [
        _expand(t.cleaned) if t.token_type == TokenType.WORD else t.cleaned
        for t in tokens if t.token_type in (TokenType.BRAND, TokenType.WORD)
    ]
    for i in range(len(desig_words)):
        match = _brand_dict.lookup_multiword(desig_words, i)
        if match:
            brand_name, brand_entry, _n = match
            if brand_entry.primary_category() == "_PRIVATE_LABEL":
                # Private label → utiliser le nom mappé (ARO, METRO PRO...)
                upper = brand_name.upper()
                marque = _PRIVATE_LABEL_MAP.get(upper, brand_name)
            else:
                marque = brand_name
            all_texts = [t.cleaned for t in tokens]
            brand_cat = _brand_dict.resolve_category(brand_name, all_texts)
            return marque, brand_cat

    # ── 2. Brand dict single word ────────────────────────────────────────
    non_noise = [t for t in tokens if t.token_type != TokenType.NOISE]
    for idx, t in enumerate(non_noise):
        if t.token_type == TokenType.BRAND:
            expanded = _expand(t.cleaned)
            entry = _brand_dict.lookup(t.cleaned) or _brand_dict.lookup(expanded)
            if entry:
                if entry.primary_category() == "_PRIVATE_LABEL":
                    upper = t.cleaned.upper()
                    marque = _PRIVATE_LABEL_MAP.get(upper, t.cleaned)
                else:
                    marque = t.cleaned
                all_texts = [tk.cleaned for tk in tokens]
                brand_cat = _brand_dict.resolve_category(
                    expanded if _brand_dict.lookup(expanded) else t.cleaned,
                    all_texts,
                )
                return marque, brand_cat
            break
        if t.token_type == TokenType.NUMERIC and idx == 0:
            entry = _brand_dict.lookup(t.cleaned)
            if entry and entry.source == "seed":
                marque = t.cleaned
                all_texts = [tk.cleaned for tk in tokens]
                brand_cat = _brand_dict.resolve_category(t.cleaned, all_texts)
                return marque, brand_cat
            break

    # ── 3. Domaines / marques connues (vin, apéritifs, spiritueux) ──────
    desig_upper = designation.upper()
    for domain_key, domain_name in _WINE_DOMAINS.items():
        if domain_key in desig_upper:
            return domain_name, None
    # Si régie vin et aucun domaine → pas de marque (appellation ≠ marque)
    if is_wine:
        return None, None

    # ── 4. Private labels (scan tous les tokens, pas seulement le premier) ─
    for t in tokens:
        upper = t.cleaned.upper()
        if upper in _PRIVATE_LABEL_MAP:
            return _PRIVATE_LABEL_MAP[upper], None

    # ── 5. Heuristique régie-aware ───────────────────────────────────────
    # Seulement pour régie S (spirits), B (bière), D (droguerie) et inconnu
    # Pour E (épicerie) et F (frais) : trop de faux positifs
    if is_food:
        return None, None

    word_tokens = [
        t for t in tokens
        if t.token_type in (TokenType.BRAND, TokenType.WORD)
    ]
    import re as _re
    brand_parts: list[str] = []
    for t in word_tokens:
        cleaned = t.cleaned.upper()
        expanded = _expand(cleaned).upper()
        if cleaned in _CATEGORY_ABBREVS or expanded in _CATEGORY_ABBREVS:
            continue
        if cleaned in _PRODUCT_WORDS or expanded in _PRODUCT_WORDS:
            if brand_parts:
                break
            continue
        if cleaned in _WINE_TERROIR_WORDS:
            if brand_parts:
                break
            continue
        # Exclure codes article/technique (R600, VN50, CCO100, 2P, 96X170)
        if _re.match(r'^[A-Z]\d{2,}$', cleaned) or _re.match(r'^\d+[A-Z]+\d+', cleaned):
            if brand_parts:
                break
            continue
        # Exclure mots trop courts (1-2 lettres) sauf marques connues
        if len(cleaned) <= 2 and cleaned not in {"3M", "BP", "LU", "JB"}:
            continue
        brand_parts.append(expanded if len(expanded) > len(cleaned) else cleaned)
        if len(brand_parts) >= 3:
            break

    if brand_parts:
        return " ".join(brand_parts), None

    # ── 6. NULL ──────────────────────────────────────────────────────────
    return None, None


# ── Filtres désignation ──────────────────────────────────────────────────────


def _is_non_product_designation(desig: str) -> bool:
    """Rejette les lignes non-produit."""
    if not desig:
        return True
    text = desig.strip()
    if not text or len(text) < 3:
        return True
    if not any(c.isalpha() for c in text):
        # Autoriser les numériques purs si ≥ 3 chars (ex: "1664")
        if not (text.isdigit() and len(text) >= 3):
            return True
    for pattern in NON_PRODUCT_PATTERNS:
        if pattern.search(text):
            return True
    for pattern in DISCOUNT_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _compute_real_quantity(
    nb_colis: Optional[int],
    colisage: Optional[int],
) -> Optional[float]:
    """Calcule la quantité réelle reçue = nb_colis × colisage.

    Sur METRO : QTE = nombre de plateaux/colis commandés,
    COL = unités par plateau. La quantité réelle = QTE × COL.
    Ex: QTE=2, COL=12 → 24 bouteilles reçues.
    """
    if nb_colis is None:
        return None
    if colisage is not None and colisage > 1:
        return float(nb_colis * colisage)
    return float(nb_colis)


# ── Construction LigneParsee ─────────────────────────────────────────────────


def _compute_pu_cts(extracted: ExtractedLine) -> Optional[int]:
    """Calcule le prix unitaire en centimes.

    Priorité : colonne PU du PDF. Fallback : HT / QTE si les deux existent.
    """
    if extracted.prix_unitaire:
        return round(extracted.prix_unitaire * 100)
    # Fallback : déduire PU depuis HT et QTE
    if extracted.montant_ht and extracted.quantite and extracted.quantite > 0:
        pu = extracted.montant_ht / extracted.quantite
        return round(pu * 100)
    return None


def _extracted_to_ligne(extracted: ExtractedLine) -> Optional[LigneParsee]:
    """Convertit une ExtractedLine en LigneParsee.

    Assemble la désignation depuis les tokens, extrait les attributs structurés.
    """
    tokens = extracted.designation_tokens

    designation = build_designation(tokens)
    designation_raw = build_designation_raw(tokens)

    if _is_non_product_designation(designation):
        return None

    # Attributs structurés depuis les tokens
    degree = extract_degree(tokens) or extracted.vol_alcool
    container = extract_container(tokens)
    volume_ml = extract_volume_ml(tokens)

    # Conditionnement non destructif
    conditionnement, unite_base, contenant_from_cond = extract_conditionnement(tokens)

    # Volume depuis la colonne PDF si pas trouvé dans les tokens
    # Valide pour toutes les régies (colonne X≈353 = volume en litres)
    if volume_ml is None and extracted.volume_litre is not None:
        candidate_ml = round(extracted.volume_litre * 1000)
        # Sanity check : volume réaliste (1mL - 50L)
        if 1 <= candidate_ml <= 50000:
            volume_ml = candidate_ml

    # Conditionnement fallback depuis colonne volume PDF
    if conditionnement is None and volume_ml is not None and volume_ml > 0:
        if volume_ml >= 1000 and volume_ml % 1000 == 0:
            conditionnement = f"{volume_ml // 1000}L"
            if unite_base == "piece":
                unite_base = "L"
        elif volume_ml >= 10:
            conditionnement = f"{volume_ml // 10}cL"
            if unite_base == "piece":
                unite_base = "cL"
        else:
            conditionnement = f"{volume_ml}mL"
            if unite_base == "piece":
                unite_base = "mL"

    # Colisage dans le conditionnement si présent
    if conditionnement and extracted.colisage and extracted.colisage > 1:
        if "lot de" not in conditionnement and "×" not in conditionnement:
            conditionnement = f"{conditionnement}, lot de {extracted.colisage}"

    # Fallback colisage seul si conditionnement reste None (token hors bounds COL_DESIGNATION)
    if conditionnement is None and extracted.colisage and extracted.colisage > 1:
        conditionnement = f"lot de {extracted.colisage}"

    # Contenant : token > colonne
    contenant = contenant_from_cond or container

    # Marque : dictionary-first, régie-aware
    marque, brand_cat = _extract_brand(tokens, extracted.regie, designation)

    # Catégorie : brand_dict override la régie quand celle-ci est générique
    # _PRIVATE_LABEL = marque propre METRO → ne pas override, garder la régie
    _GENERIC_CATEGORIES = {"NON_ALI_DROGUERIE", "AUTRE", None}
    categorie = extracted.categorie_code
    if brand_cat and brand_cat != "_PRIVATE_LABEL" and categorie in _GENERIC_CATEGORIES:
        categorie = brand_cat

    # Classifier keyword si catégorie toujours None (régie absente/inconnue)
    if categorie is None:
        from app.services.catalogue.etl_deduplication import normalize_designation as _norm_desig
        from app.services.catalogue.etl_classification import classify_categorie_code as _classify
        classified = _classify(_norm_desig(designation))
        if classified and classified != "AUTRE":
            categorie = classified

    # Quantité réelle = nb_colis × colisage.
    # Fallback : si QTE absente du PDF mais HT et PU connus → HT / PU (prix par unité).
    real_qty = _compute_real_quantity(extracted.quantite, extracted.colisage)
    if (real_qty is None
            and extracted.montant_ht is not None
            and extracted.prix_unitaire is not None
            and extracted.prix_unitaire > 0):
        deduced = round(extracted.montant_ht / extracted.prix_unitaire)
        if deduced > 0:
            real_qty = float(deduced)

    return LigneParsee(
        designation=designation,
        unite_base=unite_base,
        source_fournisseur=SOURCE_FOURNISSEUR,
        ean=extracted.ean,
        categorie_code=categorie,
        conditionnement=conditionnement,
        marque=marque,
        # Champs financiers
        quantite=real_qty,
        prix_unitaire_cts=_compute_pu_cts(extracted),
        montant_ht_cts=round(extracted.montant_ht * 100) if extracted.montant_ht else None,
        taux_tva_centieme=TVA_CODE_TO_CENTIEME.get(extracted.tva_code) if extracted.tva_code else None,
        # Champs enrichis v2
        article_fournisseur=extracted.article,
        degre_alcool=degree,
        contenant=contenant,
        volume_unitaire_ml=volume_ml,
        colisage=extracted.colisage,
        designation_raw=designation_raw,
        # Coordonnées PDF (Phase 2)
        page_number=extracted.page_number,
        y_position=extracted.y_position,
    )


# ── Point d'entrée principal ─────────────────────────────────────────────────


def parse_with_facture_metrics(
    fichier: str,
    dedupe_ean: bool = True,
) -> tuple[list[LigneParsee], dict]:
    """Parse un PDF METRO et renvoie lignes + métriques de cohérence montants.

    Signature identique au parser legacy pour compatibilité.
    """
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError(
            "pdfplumber requis pour le parser METRO : pip install pdfplumber"
        ) from exc

    path = Path(fichier)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {fichier}")

    lignes_all_count = 0
    lignes_finales: list[LigneParsee] = []
    seen_eans: set[str] = set()
    prev_dedup_key: Optional[tuple] = None  # dédoublonnage lignes PDF consécutives

    montant_all = 0.0
    montant_final = 0.0
    adjustment_candidates: list[float] = []
    promo_adjustments: list[tuple[tuple[int, int], float]] = []  # ((received, paid), discount_eur)
    discount_detected_count = 0
    surcharge_detected_count = 0
    fallback_no_ean_count = 0

    total_ht_found: Optional[float] = None
    dont_cotis_found: Optional[float] = None
    cotis_plus_total = 0.0
    cotis_plus_count = 0
    header: dict[str, Optional[str]] = {
        "numero_facture": None,
        "numero_interne": None,
        "date_facture": None,
    }

    with pdfplumber.open(path) as pdf:
        nb_pages = len(pdf.pages)
        for page_idx, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""

            if page_idx == 0:
                header = extract_header(page_text)

            if total_ht_found is None:
                ht = extract_total_ht(page_text)
                if ht is not None:
                    total_ht_found = ht

            if dont_cotis_found is None:
                m_dont = RE_DONT_COTIS.search(page_text)
                if m_dont:
                    dont_cotis_found = parse_fr_number(m_dont.group(1))

            words = page.extract_words()
            line_groups = group_by_y(words)

            for y in sorted(line_groups):
                group = line_groups[y]

                # 1) Extraire ligne produit
                extracted = extract_line(group, known_brands=_known_brands)
                ligne: Optional[LigneParsee] = None

                if extracted is not None:
                    extracted.page_number = page_idx
                    extracted.y_position = y
                    ligne = _extracted_to_ligne(extracted)
                    montant = extracted.montant_ht

                    if ligne is not None:
                        desig_up = (ligne.designation or "").upper()
                        is_articles_divers = any(
                            kw in desig_up for kw in ARTICLES_DIVERS_KEYWORDS
                        )

                        if montant is not None and montant < 0:
                            adjustment_candidates.append(montant)
                            discount_detected_count += 1
                            continue  # ligne déjà traitée → ne pas tomber en section 2
                        elif is_articles_divers and montant is not None:
                            adjustment_candidates.append(montant)
                            surcharge_detected_count += 1
                            continue  # évite double-comptage via extract_surcharge_amount
                        elif extracted.prix_unitaire is None and montant is None:
                            ligne = None

                if ligne is not None:
                    montant = extracted.montant_ht if extracted else None
                    fallback_no_ean = ligne.ean is None and montant is not None
                    lignes_all_count += 1
                    if montant is not None:
                        montant_all += montant

                    # Dédoublonnage lignes PDF consécutives
                    dedup_key = (ligne.ean, ligne.montant_ht_cts)
                    if dedup_key == prev_dedup_key and dedup_key != (None, None):
                        continue
                    prev_dedup_key = dedup_key

                    # Dédup EAN (pour mode catalogue)
                    if dedupe_ean and ligne.ean is not None and ligne.ean in seen_eans:
                        continue
                    if dedupe_ean and ligne.ean is not None:
                        seen_eans.add(ligne.ean)

                    lignes_finales.append(ligne)
                    if montant is not None:
                        montant_final += montant
                    if fallback_no_ean:
                        fallback_no_ean_count += 1
                    continue

                # 2) Ajustements candidats
                lt = line_text(group)
                discount = extract_discount_amount(lt)
                if discount is not None:
                    discount_detected_count += 1
                    # Stocker les promos "N POUR M" séparément pour post-processing
                    promo = extract_promo_ratio(lt)
                    if promo:
                        promo_adjustments.append((promo, discount))
                    else:
                        adjustment_candidates.append(discount)
                    continue

                surcharge = extract_surcharge_amount(lt)
                if surcharge is not None:
                    surcharge_detected_count += 1
                    cotis_plus_total += surcharge
                    cotis_plus_count += 1

            if page_idx % 50 == 49:
                gc.collect()
                logger.info(
                    "METRO parser progress: page %d/%d, %d lignes",
                    page_idx + 1, nb_pages, len(lignes_finales),
                )

    # ── Post-processing promos "N POUR M" ─────────────────────────────────
    # Sémantique METRO : montant ligne = QTE × PU_catalogue (AVANT remise).
    # Formule remise : floor(nb_colis / N) × (N - M) × prix_colis
    # La QTE reste inchangée (= QTE REÇUE depuis le PDF, unités gratuites incluses).
    # On réduit montant_ht_cts et on recalcule prix_unitaire_cts.
    import dataclasses as _dc
    import math as _math
    for (received, paid), discount_eur in promo_adjustments:
        free_ratio = received - paid
        if free_ratio <= 0:
            adjustment_candidates.append(discount_eur)
            continue
        abs_discount = abs(discount_eur)

        best_idx: Optional[int] = None
        best_diff = float("inf")
        for idx, ligne in enumerate(lignes_finales):
            if not ligne.montant_ht_cts or not ligne.quantite:
                continue
            ht_eur = ligne.montant_ht_cts / 100
            colisage = ligne.colisage or 1
            nb_colis = ligne.quantite / colisage
            if nb_colis < 1:
                continue
            groupes = _math.floor(nb_colis / received)
            if groupes < 1:
                continue
            prix_colis = ht_eur / nb_colis
            remise_attendue = groupes * free_ratio * prix_colis
            diff = abs(remise_attendue - abs_discount)
            if diff < best_diff:
                best_diff = diff
                best_idx = idx

        # Tolérance : 1€ fixe ou 2% de la remise (grosses commandes)
        tolerance = max(1.0, abs_discount * 0.02)
        if best_idx is not None and best_diff <= tolerance:
            old = lignes_finales[best_idx]
            original_ht = old.montant_ht_cts or 0
            original_qte = old.quantite or 1

            # Montant net = montant_catalogue − remise.
            # PU effectif = montant_net / QTE_reçue (QTE inchangée).
            discount_cts = round(abs_discount * 100)
            new_ht_cts = original_ht - discount_cts
            new_pu_cts = round(new_ht_cts / original_qte) if original_qte else (old.prix_unitaire_cts or 0)

            lignes_finales[best_idx] = type(old)(
                **{
                    **{f.name: getattr(old, f.name) for f in _dc.fields(old)},
                    "prix_unitaire_cts": new_pu_cts,
                    "montant_ht_cts": new_ht_cts,
                    # quantite inchangée : QTE REÇUE depuis le PDF
                }
            )

            logger.info(
                "Promo %d/%d matched %s (diff=%.2f€): HT %d→%d cts, PU %d→%d cts",
                received, paid,
                old.designation[:30], best_diff,
                original_ht, new_ht_cts,
                old.prix_unitaire_cts or 0, new_pu_cts,
            )
        else:
            # Pas de match fiable → ajustement global
            adjustment_candidates.append(discount_eur)

    # Recalculer montant_all après application des remises promo sur les lignes
    montant_all = sum(
        l.montant_ht_cts / 100
        for l in lignes_finales
        if l.montant_ht_cts is not None
    )

    total_ht = total_ht_found

    cotis_total = dont_cotis_found if dont_cotis_found is not None else (
        round(cotis_plus_total, 2) if cotis_plus_count > 0 else 0.0
    )
    if cotis_total > 0:
        adjustment_candidates.append(cotis_total)
        surcharge_detected_count = 1

    adjustments_detected_total = round(sum(adjustment_candidates), 2) if adjustment_candidates else 0.0
    adjustments_applied_total, adjustments_applied = select_best_adjustments(
        total_ht, montant_all, adjustment_candidates
    )

    remises_detectees_total = round(sum(v for v in adjustment_candidates if v < 0), 2)
    remises_appliquees_total = round(sum(v for v in adjustments_applied if v < 0), 2)
    supplements_detectes_total = round(sum(v for v in adjustment_candidates if v > 0), 2)
    supplements_appliques_total = round(sum(v for v in adjustments_applied if v > 0), 2)

    montant_reconcilie = round(montant_all + adjustments_applied_total, 2)
    ecart_ht = None
    ecart_ht_abs = None
    if total_ht is not None:
        ecart_ht = round(total_ht - montant_reconcilie, 2)
        ecart_ht_abs = abs(ecart_ht)

    metrics = {
        "file": str(path),
        "line_count_all": lignes_all_count,
        "line_count_output": len(lignes_finales),
        "fallback_no_ean_count": fallback_no_ean_count,
        "dedupe_ean": dedupe_ean,
        "total_ht_declared": total_ht,
        "montant_produits_all": round(montant_all, 2),
        "montant_produits_output": round(montant_final, 2),
        "discount_count_detected": discount_detected_count,
        "discount_count_applied": len([v for v in adjustments_applied if v < 0]),
        "surcharge_count_detected": surcharge_detected_count,
        "surcharge_count_applied": len([v for v in adjustments_applied if v > 0]),
        "montant_adjustments_detectes": adjustments_detected_total,
        "montant_adjustments_appliques": adjustments_applied_total,
        "montant_remises_detectees": remises_detectees_total,
        "montant_remises_appliquees": remises_appliquees_total,
        "montant_supplements_detectes": supplements_detectes_total,
        "montant_supplements_appliques": supplements_appliques_total,
        "montant_reconcilie": montant_reconcilie,
        "ecart_ht": ecart_ht,
        "ecart_ht_abs": ecart_ht_abs,
        "numero_facture": header.get("numero_facture"),
        "numero_interne": header.get("numero_interne"),
        "date_facture": header.get("date_facture"),
    }

    return lignes_finales, metrics


def parse_facture(fichier: str) -> tuple[list[LigneParsee], "FactureMetadata"]:
    """Parse un PDF METRO et retourne lignes enrichies + FactureMetadata (ADR-25)."""
    from scripts.etl.parsers.metro.facture import build_facture_metadata

    lignes, metrics = parse_with_facture_metrics(fichier, dedupe_ean=False)
    metadata = build_facture_metadata(metrics)
    return lignes, metadata


def parse(fichier: str) -> list[LigneParsee]:
    """Parse un PDF METRO — interface ADR-08.

    Déduplique par EAN (première occurrence conservée).
    """
    lignes, metrics = parse_with_facture_metrics(fichier, dedupe_ean=True)

    if metrics.get("total_ht_declared") is not None and metrics.get("ecart_ht_abs") is not None:
        if metrics["ecart_ht_abs"] > 5.0:
            logger.warning(
                "METRO parser coherence: ecart HT eleve (%.2f) pour %s "
                "[decl=%.2f, reconcilie=%.2f, remises=%.2f, suppl=%.2f, fallback_no_ean=%d]",
                metrics["ecart_ht_abs"],
                Path(fichier).name,
                metrics["total_ht_declared"],
                metrics["montant_reconcilie"],
                metrics["montant_remises_appliquees"],
                metrics["montant_supplements_appliques"],
                metrics.get("fallback_no_ean_count", 0),
            )

    logger.info(
        "METRO parser : %d lignes extraites depuis %s",
        len(lignes), Path(fichier).name,
    )
    return lignes
