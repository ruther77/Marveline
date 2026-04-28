"""Constantes du parser TAIYAT v2 — colonnes PDF, codes TVA, routing tenant.

Les parts génériques (CONTAINERS, regex numériques/unités, UNIT_*, OCR_DIGIT_MAP)
sont ré-exportées depuis `_shared/constants.py`.

Colonnes calibrées sur audit pdfplumber (facture TAIYAT standard, positions X en points).
"""
import re
from typing import Final

from scripts.etl.parsers._shared.constants import (  # noqa: F401
    CONTAINERS,
    OCR_DIGIT_MAP,
    RE_DEGREE,
    RE_FR_NUMBER,
    RE_MULTIPLIER_ONLY,
    RE_MULTIPLIER_QTY,
    RE_QTE,
    RE_QTY_UNIT,
    UNIT_NORMALIZE,
    UNIT_TO_ML,
    UNITS_PATTERN,
)

# ── Colonnes PDF TAIYAT (positions X en points) ──────────────────────────────
# Mesurées sur TAIYAT_INCONTOURNABLE_214370_05032024.pdf (page A4, 595pt width).
# Gardes de sécurité : bornes resserrées pour éviter le chevauchement.

COL_COLIS: Final = (45, 65)                # "Colis" - quantité commandée
COL_DESIGNATION: Final = (65, 290)         # "Désignation" - zone produit
COL_CAL: Final = (290, 312)                # "Cal" - calibre (1 chiffre)
COL_CAT: Final = (312, 330)                # "Cat" - catégorie (1 chiffre)
COL_PROVENANCE: Final = (330, 383)         # "Provenance" - pays d'origine
COL_PU_HT: Final = (383, 417)              # "P.U. HT"
COL_PIECES: Final = (417, 447)             # "Pièces" - colisage
COL_UV: Final = (447, 462)                 # "Uv" - c/p/u/k
COL_PU_TTC: Final = (462, 506)             # "P.U. TTC" (+ éventuel suffixe -XX.X%)
COL_MONTANT_TTC: Final = (506, 558)        # "MT TTC"
COL_TVA: Final = (558, 567)                # "T" - code TVA (1 ou 2)

LINE_TOLERANCE: Final = 3.0   # points Y — PDF TAIYAT est plus serré que METRO
MERGE_GAP_PTS: Final = 12.0

SOURCE_FOURNISSEUR: Final = "TAIYAT"

# ── Mapping code TVA TAIYAT → taux centièmes ─────────────────────────────────

TVA_CODE_TO_CENTIEME: dict[str, int] = {
    "1": 550,    # 5.50% (alimentaire)
    "2": 2000,   # 20.00%
}

RE_TVA_CODE: Final = re.compile(r"^[12]$")

# ── Mapping unité de vente (Uv) → unite_base ─────────────────────────────────

UV_TO_UNITE: dict[str, str] = {
    "c": "colis",
    "p": "piece",
    "u": "piece",
    "k": "kg",
}

# ── Routing multi-tenant TAIYAT ──────────────────────────────────────────────
# INCONTOURNABLE = restaurant (tenant 3), NOUTAM = épicerie (tenant 2).

CLIENT_TO_TENANT: dict[str, int] = {
    "INCONTOURNABLE": 3,
    "NOUTAM": 2,
}

# ── Abréviations TAIYAT (désignations en français plein, peu d'abréviations) ─

ABBREVIATIONS: dict[str, str] = {}

# ── Pays de provenance (filtre de sécurité désignation) ──────────────────────
# Si le layout glisse et qu'un pays déborde dans COL_DESIGNATION, on l'exclut
# de la désignation finale via `build_designation(extra_noise_words=...)`.

PAYS_PROVENANCE: frozenset[str] = frozenset({
    "FRANCE", "ESPAGNE", "ITALIE", "PORTUGAL", "ALLEMAGNE", "BELGIQUE",
    "PAYS-BAS", "HOLLANDE", "POLOGNE", "ROUMANIE", "MAROC", "TUNISIE", "EGYPTE",
    "CAMEROUN", "SENEGAL", "COTE", "IVOIRE", "GHANA", "BENIN", "TOGO", "MALI",
    "GUINEE", "NIGERIA", "CONGO", "KENYA", "HONDURAS", "BRESIL", "COLOMBIE",
    "COSTA-RICA", "MEXIQUE", "PEROU", "ARGENTINE", "CHILI", "EQUATEUR",
    "CHINE", "THAILANDE", "VIETNAM", "INDE", "INDONESIE", "JAPON",
    "NORVEGE", "SUEDE", "SURINAME", "BURUNDI", "RWANDA", "CAMBODGE",
    "LAOS", "PHILIPPINES", "MALAISIE", "BANGLADESH", "PAKISTAN",
    "MADAGASCAR", "MAURICE", "REUNION", "ANTILLES", "MARTINIQUE", "GUADELOUPE",
    "TAIWAN", "COREE", "TURQUIE", "IRAN", "LIBAN", "ISRAEL",
})

# ── Regexes en-tête facture ──────────────────────────────────────────────────

RE_FACTURE_NUM: Final = re.compile(r"FACTURE\s*N[°O]?\s*(\d+)", re.IGNORECASE)
RE_DATE_EXPLICIT: Final = re.compile(r"Date\s*:\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
RE_DATE_ANY: Final = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
RE_CODE_CLIENT: Final = re.compile(r"Code\s*Client\s*:\s*(\d+)", re.IGNORECASE)
RE_TOTAL_TTC_EUR: Final = re.compile(r"([0-9][0-9\s]*[.,][0-9]{2})\s*EUR\b", re.IGNORECASE)
RE_NUMERIC_LINE: Final = re.compile(r"^[0-9][0-9\s.,]*$")

# ── Seuils qualité ───────────────────────────────────────────────────────────

LINE_TOLERANCE_EUR: Final = 0.02
TOTAL_TOLERANCE_EUR: Final = 0.05
