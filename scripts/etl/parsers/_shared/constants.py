"""Constantes génériques partagées par les parsers fournisseur.

Parties spécifiques (colonnes PDF, codes TVA, abréviations, régies) restent
dans le module `constants.py` de chaque parser.
"""
from __future__ import annotations

import re
from typing import Final

# ── Contenants reconnus (génériques) ─────────────────────────────────────────

CONTAINERS: frozenset[str] = frozenset({
    "VP", "BTE", "BOITE", "PET", "BID", "BIDON",
    "FUT", "CAN", "BAG", "BIB", "BOUT", "PACK", "VRAC",
})

# ── Regexes génériques ───────────────────────────────────────────────────────

RE_EAN: Final = re.compile(r"^[0-9]{8,14}$")
RE_ARTICLE: Final = re.compile(r"^[0-9]{6,7}$")
RE_FICTIF: Final = re.compile(r"^(?:PROMO|0000)")
RE_FR_NUMBER: Final = re.compile(r"^-?[0-9][0-9\s]*[,.]?[0-9]*-?$")
RE_PRIX_MONTANT: Final = re.compile(r"^-?\d[\d\s]*[,\.]\d{2,3}-?$")
RE_QTE: Final = re.compile(r"^\d{1,3}$")

# Degré alcool : "40D", "5.5D", "5,5D", "37.5D"
RE_DEGREE: Final = re.compile(r"^(\d+(?:[.,]\d+)?)D$", re.IGNORECASE)

# Conditionnement quantité + unité : "75CL", "500G", "2.5KG", "1L", "33CL"
UNITS_PATTERN: Final = r"(?:GR?|KG|MGR?|ML|CL|DL|LT?|OZ|LB|PC(?:ES|S)?)"
RE_QTY_UNIT: Final = re.compile(
    rf"^(\d+(?:[.,]\d+)?)\s*({UNITS_PATTERN})$",
    re.IGNORECASE,
)

# Multiplicateur seul : "X6", "X20", "*6"
RE_MULTIPLIER_ONLY: Final = re.compile(r"^[X*](\d+)$", re.IGNORECASE)

# Multiplicateur + quantité + unité : "18X25CL", "6X140G", "6*50CL"
RE_MULTIPLIER_QTY: Final = re.compile(
    rf"^(\d+)[X*](\d+(?:[.,]\d+)?)\s*({UNITS_PATTERN})$",
    re.IGNORECASE,
)

# ── Mapping unités ───────────────────────────────────────────────────────────

UNIT_NORMALIZE: dict[str, str] = {
    "G": "g", "GR": "g", "KG": "kg", "MG": "mg", "MGR": "mg",
    "ML": "mL", "CL": "cL", "DL": "dL", "L": "L", "LT": "L",
    "OZ": "oz", "LB": "lb",
    "PC": "piece", "PCS": "piece", "PCES": "piece",
}

# Volume en mL par unité normalisée (conversion volume_unitaire_ml).
# Les poids sont convertis 1:1 (densité ~eau/jus) pour que volume_unitaire_ml
# devienne le "contenu unitaire" comparable cross-vendor, que le produit soit
# liquide (33cL) ou solide (340g). `unite_base` reste la source de vérité sur
# l'unité réelle (g/kg/L…).
UNIT_TO_ML: dict[str, float] = {
    "mL": 1.0, "cL": 10.0, "dL": 100.0, "L": 1000.0,
    "g": 1.0, "kg": 1000.0, "mg": 0.001,
}

# ── OCR : confusions courantes chiffres/lettres ──────────────────────────────

OCR_DIGIT_MAP: dict[str, str] = {
    "O": "0", "Q": "0", "D": "0",
    "I": "1", "L": "1", "|": "1",
    "Z": "2", "S": "5", "B": "8", "G": "6",
}
