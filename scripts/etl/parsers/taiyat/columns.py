"""Extraction structurée par colonnes X — parser TAIYAT v2.

Décompose chaque ligne PDF en ExtractedLineTAIYAT avec tous les champs.
Spécificités TAIYAT vs METRO :
  - Pas d'EAN ni d'article fournisseur dans la ligne PDF
  - PU et montants en TTC (pas HT)
  - Code TVA numérique "1"/"2" (pas A/B/C/D)
  - Colonne Provenance isolée (pays d'origine)
  - Remise inline dans PU TTC : "24.000-100.0%" → prix effectif + flag remise
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from scripts.etl.parsers._shared.column_utils import (
    extract_col_text,
    parse_fr_number,
)
from scripts.etl.parsers._shared.tokenizer import DesigToken, tokenize_designation
from scripts.etl.parsers.taiyat.constants import (
    COL_CAL,
    COL_CAT,
    COL_COLIS,
    COL_DESIGNATION,
    COL_MONTANT_TTC,
    COL_PIECES,
    COL_PROVENANCE,
    COL_PU_HT,
    COL_PU_TTC,
    COL_TVA,
    COL_UV,
    RE_QTE,
    RE_TVA_CODE,
)

__all__ = [
    "ExtractedLineTAIYAT",
    "extract_line",
]


@dataclass
class ExtractedLineTAIYAT:
    """Ligne produit TAIYAT extraite avec tous les champs structurés."""
    colis: Optional[float] = None
    designation_tokens: list[DesigToken] = field(default_factory=list)
    cal: Optional[str] = None
    cat: Optional[str] = None
    pays_origine: Optional[str] = None
    prix_ht_unit: Optional[float] = None
    pieces: Optional[int] = None                 # = colisage TAIYAT
    uv: Optional[str] = None                     # c/p/u/k
    prix_ttc_unit_base: Optional[float] = None   # PU TTC avant remise
    remise_pct: Optional[float] = None           # 0-100 ; None si pas de remise
    prix_ttc_unit_effectif: Optional[float] = None  # PU TTC après remise
    est_remise: bool = False
    montant_ttc: Optional[float] = None
    tva_code: Optional[str] = None
    page_number: Optional[int] = None
    y_position: Optional[float] = None


# ── Parsing PU TTC avec remise inline ─────────────────────────────────────────

_RE_PU_TTC_DISCOUNT = re.compile(r"^(\d+[,.]\d+)(?:-(\d+[,.]\d+)%)?$")


def _parse_pu_ttc(raw: str) -> tuple[Optional[float], Optional[float], Optional[float], bool]:
    """Parse "24.000" ou "24.000-100.0%" → (base, pct, effectif, est_remise).

    Returns:
        (prix_base, discount_pct, prix_effectif, est_remise_ttc)
    """
    if not raw:
        return None, None, None, False
    match = _RE_PU_TTC_DISCOUNT.match(raw.strip())
    if not match:
        return None, None, None, False

    base = parse_fr_number(match.group(1))
    pct = parse_fr_number(match.group(2)) if match.group(2) else None

    if base is None:
        return None, pct, None, pct is not None
    if pct is None:
        return base, None, base, False

    pct = max(0.0, min(pct, 100.0))
    effective = round(base * (1.0 - (pct / 100.0)), 3)
    return base, pct, effective, True


# ── Extraction principale ─────────────────────────────────────────────────────


def extract_line(
    words: list[dict],
    known_brands: frozenset[str] | None = None,
) -> Optional[ExtractedLineTAIYAT]:
    """Extrait une ligne produit TAIYAT depuis les mots pdfplumber.

    Retourne None si la ligne n'est pas une ligne produit valide :
    la validité exige `colis`, `montant_ttc` et `prix_ttc_unit_effectif` non nuls
    (pas d'EAN/article requis contrairement à METRO).
    """
    result = ExtractedLineTAIYAT()

    # ── Colis (qté commandée, obligatoire) ────────────────────────────────
    colis_text = extract_col_text(words, *COL_COLIS).strip()
    if colis_text:
        val = parse_fr_number(colis_text.split()[0])
        if val is not None:
            result.colis = val

    # ── Montant TTC (obligatoire) ─────────────────────────────────────────
    montant_text = extract_col_text(words, *COL_MONTANT_TTC).strip()
    if montant_text:
        # Prendre le premier nombre décimal trouvé dans la zone
        m_val = re.search(r"-?\d[\d\s]*[,\.]\d{2}-?", montant_text)
        raw_mt = m_val.group(0).strip() if m_val else montant_text
        val = parse_fr_number(raw_mt)
        if val is not None:
            result.montant_ttc = val

    # ── PU TTC (obligatoire, avec remise inline potentielle) ──────────────
    pu_ttc_text = extract_col_text(words, *COL_PU_TTC).strip()
    if pu_ttc_text:
        # Le token peut être "24.000" ou "24.000-100.0%" (selon pdfplumber)
        # Si plusieurs mots, concaténer sans espace.
        joined = "".join(pu_ttc_text.split())
        base, pct, eff, is_remise = _parse_pu_ttc(joined)
        result.prix_ttc_unit_base = base
        result.remise_pct = pct
        result.prix_ttc_unit_effectif = eff
        result.est_remise = is_remise

    # ── Validation minimale : abandonner si ligne incomplète ──────────────
    if (
        result.colis is None
        or result.montant_ttc is None
        or result.prix_ttc_unit_effectif is None
    ):
        return None

    # ── Désignation (tokens sémantiques) ──────────────────────────────────
    result.designation_tokens = tokenize_designation(
        words, COL_DESIGNATION[0], COL_DESIGNATION[1],
        known_brands=known_brands,
    )

    # ── Cal + Cat (métadonnées TAIYAT, 1 chiffre) ─────────────────────────
    cal_text = extract_col_text(words, *COL_CAL).strip()
    if cal_text and RE_QTE.match(cal_text):
        result.cal = cal_text

    cat_text = extract_col_text(words, *COL_CAT).strip()
    if cat_text and RE_QTE.match(cat_text):
        result.cat = cat_text

    # ── Provenance (pays d'origine, MAJUSCULES) ───────────────────────────
    prov_text = extract_col_text(words, *COL_PROVENANCE).strip()
    if prov_text:
        # Peut contenir "(Hollande)" en suffixe pour PAYS-BAS — nettoyer
        prov_clean = re.sub(r"\s*\([^)]+\)\s*", "", prov_text).strip()
        if prov_clean and prov_clean.upper() == prov_clean:
            result.pays_origine = prov_clean

    # ── PU HT ─────────────────────────────────────────────────────────────
    pu_ht_text = extract_col_text(words, *COL_PU_HT).strip()
    if pu_ht_text:
        val = parse_fr_number(pu_ht_text)
        if val is not None:
            result.prix_ht_unit = val

    # ── Pièces (colisage) ─────────────────────────────────────────────────
    pieces_text = extract_col_text(words, *COL_PIECES).strip()
    if pieces_text:
        first = pieces_text.split()[0]
        if RE_QTE.match(first):
            result.pieces = int(first)

    # ── Uv (unité de vente : c/p/u/k) ─────────────────────────────────────
    uv_text = extract_col_text(words, *COL_UV).strip()
    if uv_text and len(uv_text) == 1 and uv_text.lower() in "cpuk":
        result.uv = uv_text.lower()

    # ── Code TVA (1 ou 2) ─────────────────────────────────────────────────
    tva_text = extract_col_text(words, *COL_TVA).strip()
    if tva_text and RE_TVA_CODE.match(tva_text):
        result.tva_code = tva_text

    return result
