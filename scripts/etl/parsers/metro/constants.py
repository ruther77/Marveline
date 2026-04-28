"""Constantes du parser METRO v2 — colonnes PDF, régies, abréviations.

Les parts génériques (CONTAINERS, regex numériques/unités, UNIT_*, OCR_DIGIT_MAP)
sont importées depuis `_shared/constants.py` et ré-exportées pour compatibilité
avec les modules internes METRO.

Colonnes calibrées sur audit pdfplumber (551 PDFs, positions X en points).
"""
import re
from typing import Final

# Ré-exports génériques depuis _shared (backward-compat avec modules METRO)
from scripts.etl.parsers._shared.constants import (  # noqa: F401
    CONTAINERS,
    OCR_DIGIT_MAP,
    RE_ARTICLE,
    RE_DEGREE,
    RE_EAN,
    RE_FICTIF,
    RE_FR_NUMBER,
    RE_MULTIPLIER_ONLY,
    RE_MULTIPLIER_QTY,
    RE_PRIX_MONTANT,
    RE_QTE,
    RE_QTY_UNIT,
    UNIT_NORMALIZE,
    UNIT_TO_ML,
    UNITS_PATTERN,
)

# ── Colonnes PDF METRO (positions X en points) ───────────────────────────────

COL_EAN: Final = (20, 88)
COL_ARTICLE: Final = (89, 122)
COL_DESIGNATION: Final = (120, 260)
COL_REGIE: Final = (260, 278)
COL_VOL_ALCOOL: Final = (278, 305)
COL_VAP: Final = (305, 350)
COL_VOLUME: Final = (350, 395)
COL_PRIX: Final = (395, 450)
COL_COLISAGE: Final = (449, 463)
COL_QUANTITE: Final = (463, 487)
COL_MONTANT: Final = (487, 530)
COL_TVA: Final = (528, 555)
COL_PROMO: Final = (555, 575)

LINE_TOLERANCE: Final = 5  # points Y — deux mots à moins de 5pt → même ligne
MERGE_GAP_PTS: Final = 12  # écart max X pour fusionner mots numériques adjacents

SOURCE_FOURNISSEUR: Final = "METRO"

# ── Mapping régie METRO → categorie_code ─────────────────────────────────────

REGIE_TO_CATEGORIE: dict[str, str] = {
    "S": "ALC_SPIRITUEUX",
    "B": "ALC_BIERE",
    "M": "ALC_CHAMPAGNE",
    "T": "ALC_VIN",
    "E": "ALI_EPICERIE",
    "F": "ALI_FRAIS",
    "D": "NON_ALI_DROGUERIE",
}

VALID_REGIES: frozenset[str] = frozenset(REGIE_TO_CATEGORIE.keys())

# ── Mapping code TVA METRO → taux centièmes ──────────────────────────────────

TVA_CODE_TO_CENTIEME: dict[str, int] = {
    "A": 2000,   # 20.00%
    "B": 550,    # 5.50%
    "C": 1000,   # 10.00%
    "D": 210,    # 2.10%
}

RE_TVA_CODE: Final = re.compile(r"^[ABCD]$")

# ── Abréviations METRO (expansions désignation) ──────────────────────────────

ABBREVIATIONS: dict[str, str] = {
    "BLDE": "BLONDE",
    "BLE": "BLONDE",
    "WH": "WHISKY",
    "CH": "CHAMPAGNE",
    "MC": "MARQUE COMMUNE",
    "BLC": "BLANC",
    "RGE": "ROUGE",
    "RS": "ROSE",
    "SPE": "SPECIALE",
    "SUP": "SUPERIEUR",
    "ORIG": "ORIGINAL",
    "TRAD": "TRADITION",
    "DM": "DEMI",
    "PRS": "PRESSION",
    "BURG": "BOURGOGNE",
    "BDX": "BORDEAUX",
    "PROV": "PROVENCE",
    "COG": "COGNAC",
    "COG.": "COGNAC",
    "DESPERAD": "DESPERADOS",
    "SCHWEPPE": "SCHWEPPES",
    "MPRO": "METRO PROFESSIONAL",
}

# ── Patterns non-produit ─────────────────────────────────────────────────────

NON_PRODUCT_PATTERNS: list[re.Pattern[str]] = [
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

DISCOUNT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\d+\s*POUR\s*\d+", re.IGNORECASE),
    re.compile(r"^OFFRE\s+\w+\s+PLUS\s+PAYEZ\s+MOINS", re.IGNORECASE),
    re.compile(r"^REMISE\s", re.IGNORECASE),
    re.compile(r"^RETOUR\s+\d+", re.IGNORECASE),
    re.compile(r"^REPRISE\s", re.IGNORECASE),
    re.compile(r"^AVOIR\s", re.IGNORECASE),
    re.compile(r"PROMO\s*:", re.IGNORECASE),
]

# Mots-clés articles divers (non catalogue)
ARTICLES_DIVERS_KEYWORDS: tuple[str, ...] = (
    "CONSIGNE", "LIVRAISON", "LIDVRAISON",
    "PALETTE", "FRAIS TRANSPORT",
    "PRESTATION SAV", "PIECES DETACHEES",
    "R600A CONGEL", "R290 MPRO", "R600 CAVE", "R600 MPRO",
    "PDIDS TOTAL", "POIDS TOTPAL",
    "SCISSE SECHE", "SCISSE VIENNOISE",
    "SHARP M-ONDES", "BALANCE SUPREME", "BALANCE FW",
    "FLEURS PLANTES", "BLOCS PASSE",
    "MISE EN ROUTE", "CAISSE SES BK",
    "CAISSE COCA PLEIN",
    "KENW-BLENDER", "BALAI FIBRE",
)
