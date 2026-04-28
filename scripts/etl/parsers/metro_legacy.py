"""Parser fournisseur METRO — factures PDF (ADR-08).

Implemente l'interface parse(fichier) -> list[LigneParsee]
requise par scripts.etl.import_pipeline._load_lignes().

Format d'entree : PDF METRO, extraction par coordonnees X.

Colonnes extraites (positions en points PDF — source : WORKFLOW_METRO.md §3.1) :
  EAN           (x: 20-88)
  N° article    (x: 89-122)
  Designation   (x: 123-254)
  Regie         (x: 255-275)  -> categorie_code
  Prix unitaire (x: 395-450)
  Montant ligne (x: 479-525)
  TVA code      (x: 526-550)

Mapping regie -> categorie_code (WORKFLOW_METRO.md §8) :
  S -> ALC_SPIRITUEUX | B -> ALC_BIERE | M -> ALC_CHAMPAGNE | T -> ALC_VIN
  E -> ALI_EPICERIE   | F -> ALI_FRAIS | D -> NON_ALI_DROGUERIE

References :
  WORKFLOW_METRO.md : format PDF, nomenclature fichiers, mapping categories
  ADR-08 : contrat parse(fichier) -> list[LigneParsee]
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from app.etl_types import FactureMetadata, LigneParsee

logger = logging.getLogger(__name__)

# -- Constantes de colonnes (positions X en points PDF) -----------------------

_COL_EAN = (20, 88)
_COL_ARTICLE = (89, 122)
_COL_DESIGNATION = (123, 254)
_COL_REGIE = (255, 275)
_COL_PRIX = (395, 450)
_COL_MONTANT = (479, 525)
_COL_TVA = (526, 550)

_LINE_TOLERANCE = 5  # points — deux mots a moins de 5pt en Y -> meme ligne

# -- Mapping regie METRO -> categorie_code catalogue alimentaire ---------------

_REGIE_TO_CATEGORIE: dict[str, str] = {
    "S": "ALC_SPIRITUEUX",
    "B": "ALC_BIERE",
    "M": "ALC_CHAMPAGNE",
    "T": "ALC_VIN",
    "E": "ALI_EPICERIE",
    "F": "ALI_FRAIS",
    "D": "NON_ALI_DROGUERIE",
}

_SOURCE_FOURNISSEUR = "METRO"
_UNITE_BASE_DEFAULT = "piece"  # les factures METRO n'indiquent pas l'unite

# Mapping code TVA METRO → taux centièmes (convention BigInteger)
_TVA_CODE_TO_CENTIEME: dict[str, int] = {
    "A": 2000,   # 20.00%
    "B": 550,    # 5.50%
    "C": 1000,   # 10.00%
    "D": 210,    # 2.10%
}

# -- Regexes -------------------------------------------------------------------

_RE_EAN = re.compile(r"^[0-9]{8,14}$")
_RE_ARTICLE = re.compile(r"^[0-9]{6,7}$")
_RE_FICTIF = re.compile(r"^(?:PROMO|0000)")  # EANs synthetiques a ignorer
_RE_FR_NUMBER = re.compile(r"^-?[0-9][0-9\s]*[,.]?[0-9]*-?$")
_RE_TOTAL_HT = re.compile(r"Total\s*H\.?T\.?\s*:?\s*([\d\s]+[,\.]\d{2}-?)", re.IGNORECASE)

# En-tête facture METRO — extraction numéro et date
_RE_FACTURE_NUM = re.compile(
    r"FACTURE\s+([\d/()]+[^\s]*)\s*.*?\((\d{3}-\d+)\)",
    re.IGNORECASE,
)
_RE_FACTURE_DATE = re.compile(
    r"Date\s+facture\s*[*:]?\s*:?\s*(\d{2}-\d{2}-\d{4})",
    re.IGNORECASE,
)
_RE_DISCOUNT_LINE = re.compile(
    r"(?:\d+\s*POUR\s*\d+|OFFRE\s+\w+\s+PLUS\s+PAYEZ\s+MOINS|REMISE|PROMO|AVOIR|RETOUR).*?([\d\s]+[,\.]\d{2})\s*-",
    re.IGNORECASE,
)
_RE_SURCHARGE_LINE = re.compile(
    r"PLUS\s*:\s*(?:COTIS\.?\s*SEC.{0,8}SOCIALE|FRAIS\s+TRANSPORT|FRAIS\s+LIVRAISON|PORT\s+FORFAIT|CONSIGNE).*?([\d\s]+[,\.]\d{2})",
    re.IGNORECASE,
)
# Récap cotis sécu (total, ligne unique en pied de facture) — prioritaire sur les Plus:
_RE_DONT_COTIS = re.compile(
    r"DONT\s*:\s*COTIS\.?\s*SEC.{0,8}SOCIALE\s+([\d\s]+[,\.]\d{2})",
    re.IGNORECASE,
)

_RE_TVA_CODE     = re.compile(r'^[ABCD]$')
_RE_PRIX_MONTANT = re.compile(r'^-?\d[\d\s]*[,\.]\d{2,3}-?$')  # nombre FR 2-3 décimales
_RE_QTE          = re.compile(r'^\d{1,2}$')                   # quantité entière courte

_NON_PRODUCT_PATTERNS = [
    re.compile(r"^PRIX\s+AU\s+KG\s+OU\s+AU\s+LITRE", re.IGNORECASE),
    re.compile(r"^PLUS\s*:\s*COTIS", re.IGNORECASE),
    re.compile(r"^ICS\s*:", re.IGNORECASE),
    re.compile(r"^N[°O]?\s*LOT", re.IGNORECASE),
    re.compile(r"^DLC\s*:", re.IGNORECASE),
    re.compile(r"^DLUO\s*:", re.IGNORECASE),
    re.compile(r"^TVA\s*INTRA", re.IGNORECASE),
    re.compile(r"^SIRET", re.IGNORECASE),
    re.compile(r"^N\s*OMBRE\s+DE\s+COLIS", re.IGNORECASE),
    re.compile(r"POIDS\s+TOTAL", re.IGNORECASE),
    re.compile(r"TOTAL\s+A\s+PAYER", re.IGNORECASE),
    re.compile(r"MONTANT\s+HORS\s+T\.?V\.?A", re.IGNORECASE),
    re.compile(r"TOTAL\s+VOLUME", re.IGNORECASE),
    re.compile(r"^\*{3,}"),
]

_DISCOUNT_PATTERNS = [
    re.compile(r"^\d+\s*POUR\s*\d+", re.IGNORECASE),
    re.compile(r"^OFFRE\s+\w+\s+PLUS\s+PAYEZ\s+MOINS", re.IGNORECASE),
    re.compile(r"^REMISE\s", re.IGNORECASE),
    re.compile(r"^RETOUR\s+\d+", re.IGNORECASE),
    re.compile(r"^REPRISE\s", re.IGNORECASE),
    re.compile(r"^AVOIR\s", re.IGNORECASE),
    re.compile(r"PROMO\s*:", re.IGNORECASE),
]

# OCR confusions courantes chiffres/lettres sur PDFs METRO
_OCR_DIGIT_MAP = {
    "O": "0",
    "Q": "0",
    "D": "0",
    "I": "1",
    "L": "1",
    "|": "1",
    "Z": "2",
    "S": "5",
    "B": "8",
    "G": "6",
}


# -- Helpers bas niveau --------------------------------------------------------


def _extract_col(words: list[dict], x_min: float, x_max: float) -> str:
    """Extrait le texte des mots dont le centre ou le debut est dans [x_min, x_max]."""
    in_col = [
        w
        for w in words
        if x_min <= w["x0"] <= x_max or x_min <= (w["x0"] + w["x1"]) / 2 <= x_max
    ]
    in_col.sort(key=lambda w: w["x0"])
    return " ".join(w["text"] for w in in_col).strip()


def _line_text(words: list[dict]) -> str:
    return " ".join(w["text"] for w in sorted(words, key=lambda w: w["x0"]))


def _group_by_y(words: list[dict]) -> dict[float, list[dict]]:
    """Regroupe les mots par ligne (tolerance _LINE_TOLERANCE points en Y)."""
    lines: dict[float, list[dict]] = {}
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        y = word["top"]
        match = next((k for k in lines if abs(y - k) < _LINE_TOLERANCE), None)
        if match is not None:
            lines[match].append(word)
        else:
            lines[y] = [word]
    return lines


def _ocr_to_digits(raw: str) -> str:
    up = (raw or "").upper()
    mapped = "".join(_OCR_DIGIT_MAP.get(ch, ch) for ch in up)
    return re.sub(r"\D", "", mapped)


def _is_real_ean(ean: str) -> bool:
    """Retourne True si l'EAN est un code-barres reel (pas synthetique)."""
    return bool(_RE_EAN.match(ean)) and not bool(_RE_FICTIF.match(ean))


def _normalize_ean(ean_raw: str) -> Optional[str]:
    """Normalise un EAN potentiellement bruite par OCR.

    Strategie:
    - nettoie les confusions OCR lettres/chiffres
    - garde uniquement les candidats issus de la colonne EAN
    """
    cleaned = _ocr_to_digits(ean_raw)
    if not cleaned:
        return None

    candidates: list[str] = []
    if 8 <= len(cleaned) <= 14:
        candidates.append(cleaned)
    candidates.extend(re.findall(r"\d{8,14}", cleaned))

    for cand in candidates:
        if _is_real_ean(cand):
            return cand
    return None


def _normalize_article(article_raw: str) -> Optional[str]:
    """Normalise le numero article (6-7 chiffres) depuis sa colonne dediee."""
    cleaned = _ocr_to_digits(article_raw)
    if not cleaned:
        return None
    match = re.search(r"\d{6,7}", cleaned)
    if match:
        return match.group(0)
    return None


def _parse_fr_number(raw: str) -> Optional[float]:
    """Parse un nombre FR (espaces milliers + virgule decimal + suffixe '-')."""
    if not raw:
        return None

    s = raw.strip()
    if not s or not _RE_FR_NUMBER.match(s):
        return None

    negative_suffix = s.endswith("-")
    if negative_suffix:
        s = s[:-1]

    s = s.replace(" ", "").replace(",", ".")

    try:
        value = float(s)
    except ValueError:
        return None

    if negative_suffix:
        value = -value
    return value


def _extract_total_ht(text: str) -> Optional[float]:
    match = _RE_TOTAL_HT.search(text or "")
    if not match:
        return None
    return _parse_fr_number(match.group(1))


def _extract_header(text: str) -> dict[str, Optional[str]]:
    """Extrait numéro de facture et date depuis le texte de la première page.

    Patterns METRO (stables sur toutes les factures 2020-2025) :
      Nº FACTURE 0/0(135)0016/005048② (016-243302)
      Date facture : 13-03-2024 19:19
    """
    header: dict[str, Optional[str]] = {
        "numero_facture": None,
        "numero_interne": None,
        "date_facture": None,
    }

    m_num = _RE_FACTURE_NUM.search(text or "")
    if m_num:
        # Nettoyage : retirer les caractères Unicode parasites (②, ①, etc.)
        raw = m_num.group(1)
        header["numero_facture"] = re.sub(r"[^\d/()]", "", raw)
        header["numero_interne"] = m_num.group(2)

    m_date = _RE_FACTURE_DATE.search(text or "")
    if m_date:
        header["date_facture"] = m_date.group(1)

    return header


def _extract_discount_amount(line: str) -> Optional[float]:
    match = _RE_DISCOUNT_LINE.search(line)
    if not match:
        return None
    val = _parse_fr_number(match.group(1))
    if val is None:
        return None
    return -abs(val)


def _extract_surcharge_amount(line: str) -> Optional[float]:
    match = _RE_SURCHARGE_LINE.search(line)
    if not match:
        return None
    val = _parse_fr_number(match.group(1))
    if val is None:
        return None
    return abs(val)


def _select_best_adjustments(total_ht: Optional[float], montant_base: float, adjustment_candidates: list[float]) -> tuple[float, list[float]]:
    """Selectionne les ajustements qui ameliorent la coherence avec le total HT.

    Les ajustements detectes (reductions negatives et supplements positifs)
    sont candidats. On applique uniquement ceux qui reduisent effectivement
    l'ecart absolu avec le total declare.
    """
    if total_ht is None or not adjustment_candidates:
        return 0.0, []

    target = total_ht - montant_base
    selected: list[float] = []
    running = 0.0
    current_diff = abs(target - running)

    remaining = list(adjustment_candidates)
    while remaining:
        best_index = None
        best_diff = current_diff

        for i, amount in enumerate(remaining):
            candidate_diff = abs(target - (running + amount))
            if candidate_diff + 1e-9 < best_diff:
                best_diff = candidate_diff
                best_index = i

        if best_index is None:
            break

        chosen = remaining.pop(best_index)
        selected.append(chosen)
        running += chosen
        current_diff = best_diff

    return round(running, 2), selected


def _is_non_product_designation(desig: str) -> bool:
    """Heuristiques pour rejeter les lignes non-produit dans la colonne designation."""
    if not desig:
        return True

    text = re.sub(r"\s+", " ", desig).strip()
    if not text or not any(c.isalpha() for c in text):
        return True

    # Rejeter les designations trop courtes / artefacts OCR ("a", "i", etc.)
    if len(text) < 4 or re.search(r"[A-Za-z]{2,}", text) is None:
        return True

    for pattern in _NON_PRODUCT_PATTERNS:
        if pattern.search(text):
            return True

    for pattern in _DISCOUNT_PATTERNS:
        if pattern.search(text):
            return True

    return False


_MERGE_GAP_PTS = 12  # écart max en points X pour fusionner deux mots numériques


def _merge_numeric_words(words: list[dict], col_bounds: tuple[float, float]) -> list[dict]:
    """Fusionne les mots numériques adjacents dans une colonne (séparateur milliers).

    Ex: mots ["1" x0=480, "503,20" x0=489] dans _COL_MONTANT
        → mot fusionné ["1 503,20" x0=480] qui sera parsé en 1503.20 par _parse_fr_number.
    """
    col_min, col_max = col_bounds
    in_col = sorted(
        [w for w in words if col_min <= w["x0"] <= col_max],
        key=lambda w: w["x0"],
    )
    if len(in_col) < 2:
        return words

    merged: list[dict] = []
    i = 0
    consumed: set[int] = set()
    while i < len(in_col):
        current = in_col[i]
        text_parts = [current["text"].strip()]
        x0 = current["x0"]
        x1 = current["x1"]
        consumed.add(id(current))

        j = i + 1
        while j < len(in_col):
            nxt = in_col[j]
            gap = nxt["x0"] - x1
            nxt_text = nxt["text"].strip()
            # Fusionner si adjacent et le fragment est numérique
            if gap <= _MERGE_GAP_PTS and re.match(r"^[\d,.\s-]+$", nxt_text):
                text_parts.append(nxt_text)
                x1 = nxt["x1"]
                consumed.add(id(nxt))
                j += 1
            else:
                break

        if len(text_parts) > 1:
            merged_text = " ".join(text_parts)
            merged.append({
                "text": merged_text,
                "x0": x0,
                "x1": x1,
                "top": current["top"],
            })
        i = j if j > i + 1 else i + 1

    # Reconstruire la liste : mots hors colonne + mots non fusionnés + mots fusionnés
    result = [w for w in words if id(w) not in consumed]
    result.extend(merged)
    # Remettre les mots in-col non consommés (fragment isolé = pas fusionné)
    for w in in_col:
        if id(w) not in consumed:
            pass  # déjà dans result via la première compréhension
    return result


def _parse_rtl_fields(words: list[dict]) -> dict:
    """Extrait les champs numériques RTL (TVA, montant, prix, qté) par signature lexicale.

    Scanne les mots de droite à gauche pour trouver chaque champ par sa forme plutôt
    que par sa position X. Retourne aussi pivot_x (x0 du champ le plus à gauche trouvé)
    utilisé pour délimiter la zone de désignation.

    Pré-traitement : fusionne les mots numériques adjacents dans les colonnes
    prix/montant pour gérer les séparateurs de milliers (ex: "1 503,20" → 1503.20).
    """
    # Fusionner les fragments numériques séparés par espace (milliers)
    merged = _merge_numeric_words(words, _COL_MONTANT)
    merged = _merge_numeric_words(merged, _COL_PRIX)

    sorted_rtl = sorted(merged, key=lambda w: w["x0"], reverse=True)
    result: dict = {"tva": None, "montant": None, "prix": None, "qte": None, "pivot_x": _COL_PRIX[0]}
    pivot_candidates: list[float] = []
    prix_word: Optional[dict] = None

    for w in sorted_rtl:
        text = w["text"].strip().upper()
        x0 = w["x0"]

        if result["tva"] is None and _RE_TVA_CODE.match(text) and x0 >= _COL_TVA[0]:
            result["tva"] = text
            pivot_candidates.append(x0)
        elif result["montant"] is None and _RE_PRIX_MONTANT.match(text) and _COL_MONTANT[0] <= x0 <= _COL_MONTANT[1]:
            result["montant"] = _parse_fr_number(text)
            pivot_candidates.append(x0)
        elif result["prix"] is None and _RE_PRIX_MONTANT.match(text) and _COL_PRIX[0] <= x0 <= _COL_PRIX[1]:
            result["prix"] = _parse_fr_number(text)
            pivot_candidates.append(x0)
            prix_word = w

    if prix_word is not None:
        prix_x0 = prix_word["x0"]
        left_of_prix = [w for w in merged if w["x0"] < prix_x0]
        if left_of_prix:
            nearest = max(left_of_prix, key=lambda w: w["x0"])
            if _RE_QTE.match(nearest["text"].strip()):
                result["qte"] = int(nearest["text"].strip())
                pivot_candidates.append(nearest["x0"])

    if pivot_candidates:
        result["pivot_x"] = min(pivot_candidates)
    return result


def _extract_left_zone(words: list[dict], pivot_x: float) -> dict:
    """Extrait EAN, article, régie et désignation dans la zone x0 < pivot_x − 5."""
    left = sorted([w for w in words if w["x0"] < pivot_x - 5], key=lambda w: w["x0"])
    ean: Optional[str] = None
    article: Optional[str] = None
    regie: Optional[str] = None
    desig_words: list[str] = []

    for w in left:
        text = w["text"].strip()
        x0 = w["x0"]

        if ean is None and _COL_EAN[0] <= x0 <= _COL_EAN[1]:
            norm = _normalize_ean(text)
            if norm:
                ean = norm
                continue

        if article is None and _COL_ARTICLE[0] <= x0 <= _COL_ARTICLE[1]:
            norm = _normalize_article(text)
            if norm:
                article = norm
                continue

        if regie is None and _COL_REGIE[0] <= x0 <= _COL_REGIE[1] and text.upper() in _REGIE_TO_CATEGORIE:
            regie = text.upper()
            continue

        if any(c.isalpha() for c in text):
            desig_words.append(text)

    return {
        "ean": ean,
        "article": article,
        "regie": regie,
        "categorie_code": _REGIE_TO_CATEGORIE.get(regie) if regie else None,
        "designation": " ".join(desig_words),
    }


# -- Extraction conditionnement / unité depuis la désignation -----------------

_UNITS_PATTERN = r"(?:GR?|KG|MGR?|ML|CL|DL|LT?|OZ|LB|PC(?:ES|S)?)"

# Multiplicateur + quantité+unité : "X20 700G", "6X140G", "X6", "16*125G"
_RE_CONDIT_MULT = re.compile(
    rf"(?:^|\s)(\d+)\s*[X*x]\s*(\d+(?:[.,]\d+)?)\s*({_UNITS_PATTERN})\b",
    re.IGNORECASE,
)
# Multiplicateur seul : "X6", "X 24", "x12"
_RE_CONDIT_MULT_ONLY = re.compile(
    r"(?:^|\s)[Xx]\s*(\d+)\b",
)
# Quantité + unité : "500G", "2.5KG", "75CL", "1L", "25LT"
_RE_CONDIT_QTY = re.compile(
    rf"\b(\d+(?:[.,]\d+)?)\s*({_UNITS_PATTERN})\b",
    re.IGNORECASE,
)
# Contenants structurés : "BID 25L", "BTE 12", "SAC 500G", "BOUT 75CL"
_RE_CONDIT_CONTAINER = re.compile(
    r"\b(BID|BIDON|BTE|BOITE|SAC|SACHET|BOUT|BOUTEILLE|BTLLE|PQT|PAQUET|"
    r"PACK|LOT|BQTTE|BARQUETTE|CARTON|ETUI|POT|TUBE|FLACON|SEAU|POCHE|"
    r"DOSETTE|CAPSULE|BRIQUE|ROULEAU|CAISSE|FUT|BOTTE|FILET)"
    rf"(?:\s+(?:DE\s+)?\d+(?:[.,]\d+)?\s*(?:{_UNITS_PATTERN})?)?\b",
    re.IGNORECASE,
)

# Mapping unité brute → unité normalisée
_UNIT_NORMALIZE: dict[str, str] = {
    "G": "g", "GR": "g", "KG": "kg", "MG": "g", "MGR": "g",
    "ML": "mL", "CL": "cL", "DL": "dL", "L": "L", "LT": "L",
    "OZ": "oz", "LB": "lb",
    "PC": "piece", "PCS": "piece", "PCES": "piece",
}


def _extract_conditionnement(designation: str) -> tuple[str, Optional[str], str]:
    """Extrait conditionnement et unité depuis la désignation brute.

    Retourne (designation_nettoyee, conditionnement, unite_base).
    Ex: "KNACK X20 700G" → ("KNACK", "20×700g", "piece")
        "HUILE BID 25LT" → ("HUILE", "bidon 25L", "L")
        "GRAINES DE CHIA 500G" → ("GRAINES DE CHIA", "500g", "g")
    """
    desig = designation
    parts: list[str] = []
    unite = "piece"

    # 1) Multiplicateur + qté+unité : "X20 700G", "6X140G", "16*125G"
    m = _RE_CONDIT_MULT.search(desig)
    if m:
        nb = m.group(1)
        qty = m.group(2).replace(",", ".")
        raw_unit = m.group(3).upper()
        norm_unit = _UNIT_NORMALIZE.get(raw_unit, raw_unit.lower())
        parts.append(f"{nb}×{qty}{norm_unit}")
        unite = norm_unit if norm_unit not in ("piece",) else "piece"
        desig = desig[:m.start()] + desig[m.end():]
    else:
        # 2) Multiplicateur seul : "X6"
        m2 = _RE_CONDIT_MULT_ONLY.search(desig)
        if m2:
            parts.append(f"lot de {m2.group(1)}")
            desig = desig[:m2.start()] + desig[m2.end():]

    # 3) Contenant structuré : "BID 25L", "BTE 12"
    mc = _RE_CONDIT_CONTAINER.search(desig)
    if mc:
        container_text = mc.group(0).strip()
        parts.append(container_text.lower())
        desig = desig[:mc.start()] + desig[mc.end():]
        # Extraire l'unité du contenant si présente ("BTE 33CL" → cL)
        unit_in_container = _RE_CONDIT_QTY.search(container_text)
        if unit_in_container and unite == "piece":
            raw_unit = unit_in_container.group(2).upper()
            unite = _UNIT_NORMALIZE.get(raw_unit, raw_unit.lower())

    # 4) Quantité + unité résiduelle : "500G", "75CL", "2.5KG"
    mq = _RE_CONDIT_QTY.search(desig)
    if mq:
        qty = mq.group(1).replace(",", ".")
        raw_unit = mq.group(2).upper()
        norm_unit = _UNIT_NORMALIZE.get(raw_unit, raw_unit.lower())
        parts.append(f"{qty}{norm_unit}")
        if unite == "piece":
            unite = norm_unit
        desig = desig[:mq.start()] + desig[mq.end():]

    conditionnement = ", ".join(parts) if parts else None

    # Nettoyer la désignation résiduelle
    desig = re.sub(r"\s+", " ", desig).strip()

    return desig, conditionnement, unite


def _words_to_ligne(words: list[dict]) -> Optional[LigneParsee]:
    """Parse une ligne PDF en LigneParsee via extraction sémantique RTL.

    Ne filtre pas sur prix/montant — ce filtrage appartient à parse_with_facture_metrics,
    afin que les tests unitaires puissent fournir des lignes sans champs monétaires.
    """
    rtl = _parse_rtl_fields(words)
    left = _extract_left_zone(words, rtl["pivot_x"])

    if left["ean"] is None and left["article"] is None:
        return None

    if _is_non_product_designation(left["designation"]):
        return None

    raw_desig = left["designation"].strip()
    desig_clean, conditionnement, unite_base = _extract_conditionnement(raw_desig)

    # Si la désignation nettoyée est vide ou trop courte, garder l'originale
    if not desig_clean or len(desig_clean) < 3:
        desig_clean = raw_desig

    return LigneParsee(
        designation=desig_clean,
        unite_base=unite_base,
        source_fournisseur=_SOURCE_FOURNISSEUR,
        ean=left["ean"],
        categorie_code=left["categorie_code"],
        conditionnement=conditionnement,
    )


# -- Point d'entree public -----------------------------------------------------


def parse_with_facture_metrics(fichier: str, dedupe_ean: bool = True) -> tuple[list[LigneParsee], dict]:
    """Parse un PDF METRO et renvoie lignes + metriques de coherence montants.

    Notes:
    - Les lignes remises/promo (montant negatif) ne sont pas retournees en LigneParsee
      mais leur total est mesure pour la coherence facture.
    - parse() continue de renvoyer uniquement list[LigneParsee] pour compatibilite ADR-08.
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

    import gc

    lignes_all_count = 0
    lignes_finales: list[LigneParsee] = []
    seen_eans: set[str] = set()

    montant_all = 0.0
    montant_final = 0.0
    adjustment_candidates: list[float] = []
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

            # Extraire en-tête depuis la première page
            if page_idx == 0:
                header = _extract_header(page_text)

            # Chercher Total HT et récap cotis dans le texte brut
            if total_ht_found is None:
                ht = _extract_total_ht(page_text)
                if ht is not None:
                    total_ht_found = ht

            if dont_cotis_found is None:
                m_dont = _RE_DONT_COTIS.search(page_text)
                if m_dont:
                    dont_cotis_found = _parse_fr_number(m_dont.group(1))

            words = page.extract_words()
            line_groups = _group_by_y(words)
            for y in sorted(line_groups):
                group = line_groups[y]

                # 1) Ligne produit candidate
                ligne = _words_to_ligne(group)
                rtl = _parse_rtl_fields(group)
                montant = rtl.get("montant")

                # Filtres monétaires et articles divers
                if ligne is not None:
                    desig_up = (ligne.designation or "").upper()
                    is_articles_divers = any(
                        kw in desig_up for kw in (
                            "CONSIGNE", "LIVRAISON", "PALETTE",
                        )
                    )

                    if montant is not None and montant < 0:
                        # Retour consigne, avoir article : ajustement négatif
                        adjustment_candidates.append(montant)
                        discount_detected_count += 1
                        ligne = None
                    elif is_articles_divers and montant is not None:
                        # CONSIGNE/LIVRAISON positive : pas un produit catalogue,
                        # c'est dans la section "Articles divers" de la facture.
                        # Compté comme ajustement pour la réconciliation.
                        adjustment_candidates.append(montant)
                        surcharge_detected_count += 1
                        ligne = None
                    elif rtl.get("prix") is None and montant is None:
                        ligne = None  # ligne structurelle (en-tête, total…)

                if ligne is not None:
                    # Enrichir LigneParsee avec données financières RTL
                    prix_eur = rtl.get("prix")
                    if prix_eur is not None:
                        ligne.prix_unitaire_cts = round(prix_eur * 100)
                    if montant is not None:
                        ligne.montant_ht_cts = round(montant * 100)
                    qte = rtl.get("qte")
                    if qte is not None:
                        ligne.quantite = float(qte)
                    tva_code = rtl.get("tva")
                    if tva_code and tva_code in _TVA_CODE_TO_CENTIEME:
                        ligne.taux_tva_centieme = _TVA_CODE_TO_CENTIEME[tva_code]

                    fallback_no_ean = ligne.ean is None and montant is not None
                    lignes_all_count += 1
                    if montant is not None:
                        montant_all += montant

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

                line_text = _line_text(group)

                # 2) Ajustements candidats (reductions / supplements)
                discount = _extract_discount_amount(line_text)
                if discount is not None:
                    discount_detected_count += 1
                    adjustment_candidates.append(discount)
                    continue

                surcharge = _extract_surcharge_amount(line_text)
                if surcharge is not None:
                    surcharge_detected_count += 1
                    # Les cotis sécu (Plus:) sont comptées à part — on
                    # utilisera le total Dont: en priorité après la boucle.
                    cotis_plus_total += surcharge
                    cotis_plus_count += 1

            # Libérer la mémoire de la page toutes les 50 pages
            if page_idx % 50 == 49:
                gc.collect()
                logger.info("METRO parser progress: page %d/%d, %d lignes", page_idx + 1, nb_pages, len(lignes_finales))

    total_ht = total_ht_found

    # Cotis sécu : "Dont:" (total exact) prioritaire sur somme des "Plus:"
    cotis_total = dont_cotis_found if dont_cotis_found is not None else (
        round(cotis_plus_total, 2) if cotis_plus_count > 0 else 0.0
    )
    if cotis_total > 0:
        adjustment_candidates.append(cotis_total)
        surcharge_detected_count = 1  # un seul ajustement cotis consolidé

    # La réconciliation utilise montant_all (avant dedup EAN) car le Total HT
    # de la facture METRO inclut toutes les occurrences, y compris les doublons.
    adjustments_detected_total = round(sum(adjustment_candidates), 2) if adjustment_candidates else 0.0
    adjustments_applied_total, adjustments_applied = _select_best_adjustments(total_ht, montant_all, adjustment_candidates)

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


def _euros_to_centimes(val: Optional[float]) -> Optional[int]:
    """Convertit un montant EUR float en centimes int, ou None."""
    if val is None:
        return None
    return round(val * 100)


def parse_facture(fichier: str) -> tuple[list[LigneParsee], FactureMetadata]:
    """Parse un PDF METRO et retourne lignes enrichies + FactureMetadata (ADR-25).

    Contrairement à parse(), les LigneParsee retournées contiennent les champs
    financiers (prix_unitaire_cts, montant_ht_cts) et les metrics sont
    structurées en FactureMetadata pour persistance EtlImport.

    Les doublons EAN sont conserves (dedupe_ean=False) pour garder l'exhaustivite
    financiere de la facture.
    """
    lignes, metrics = parse_with_facture_metrics(fichier, dedupe_ean=False)

    total_ht = metrics.get("total_ht_declared")
    montant_reconcilie = metrics.get("montant_reconcilie")
    ecart = metrics.get("ecart_ht")

    # Estimation TVA 20% si total HT déclaré
    montant_ht_cts = _euros_to_centimes(total_ht or montant_reconcilie)
    montant_tva_cts = round(montant_ht_cts * 2000 / 10000) if montant_ht_cts else None
    montant_ttc_cts = (montant_ht_cts + montant_tva_cts) if montant_ht_cts and montant_tva_cts else None

    # Conversion date DD-MM-YYYY → objet date pour FactureMetadata
    date_facture_obj = None
    raw_date = metrics.get("date_facture")
    if raw_date:
        from datetime import date as date_type
        parts = raw_date.split("-")
        if len(parts) == 3:
            try:
                date_facture_obj = date_type(
                    int(parts[2]), int(parts[1]), int(parts[0]),
                )
            except (ValueError, IndexError):
                logger.warning("Date facture invalide : %s", raw_date)

    # Numéro facture : préférer numero_interne (ex: "016-243302") plus lisible
    numero_facture = metrics.get("numero_interne") or metrics.get("numero_facture")

    # Qualité: bonus si en-tête structuré détecté
    quality = 0
    if numero_facture:
        quality += 10
    if date_facture_obj:
        quality += 10
    if total_ht is not None:
        quality += 30
    line_count = metrics.get("line_count_output", 0)
    if line_count > 0:
        quality += 20
    ecart_abs = metrics.get("ecart_ht_abs")
    if ecart_abs is not None and ecart_abs <= 5.0:
        quality += 30
    elif ecart_abs is not None and ecart_abs <= 20.0:
        quality += 15

    metadata = FactureMetadata(
        vendor_code="METRO",
        numero_facture=numero_facture,
        date_facture=date_facture_obj,
        montant_ht_total=montant_ht_cts,
        montant_tva_total=montant_tva_cts,
        montant_ttc_total=montant_ttc_cts,
        quality_score=min(quality, 100),
        ecart_reconciliation=ecart,
        lignes_brutes=metrics.get("line_count_all", 0),
    )

    return lignes, metadata


def parse(fichier: str) -> list[LigneParsee]:
    """Parse un fichier PDF METRO et retourne les lignes produit normalisees.

    Interface requise par import_pipeline._load_lignes().
    Les doublons d'EAN sont supprimes (premiere occurrence conservee),
    car l'objectif principal de ce parser est l'import catalogue.
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
        len(lignes),
        Path(fichier).name,
    )
    return lignes
