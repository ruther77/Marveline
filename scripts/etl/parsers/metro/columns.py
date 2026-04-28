"""Extraction structurée par colonnes X — parser METRO v2.

Chaque ligne PDF est décomposée en ExtractedLine avec tous les champs.
Les primitives (group_by_y, line_text, extract_col_text, merge_numeric_words,
parse_fr_number) sont fournies par `_shared/column_utils.py`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from scripts.etl.parsers._shared.column_utils import (
    extract_col_text as _extract_col_text,
    group_by_y,
    line_text,
    merge_numeric_words,
    parse_fr_number,
)
from scripts.etl.parsers.metro.constants import (
    COL_ARTICLE,
    COL_COLISAGE,
    COL_DESIGNATION,
    COL_EAN,
    COL_MONTANT,
    COL_PRIX,
    COL_PROMO,
    COL_QUANTITE,
    COL_REGIE,
    COL_TVA,
    COL_VOL_ALCOOL,
    COL_VOLUME,
    MERGE_GAP_PTS,
    RE_EAN,
    RE_FICTIF,
    RE_QTE,
    RE_TVA_CODE,
    REGIE_TO_CATEGORIE,
    VALID_REGIES,
)
from scripts.etl.parsers.metro.ocr_clean import ocr_to_digits
from scripts.etl.parsers.metro.tokenizer import DesigToken, tokenize_designation

__all__ = [
    "ExtractedLine",
    "extract_line",
    "group_by_y",
    "line_text",
    "parse_fr_number",
]


@dataclass
class ExtractedLine:
    """Ligne produit METRO extraite avec tous les champs structurés."""
    ean: Optional[str] = None
    article: Optional[str] = None
    designation_tokens: list[DesigToken] = field(default_factory=list)
    regie: Optional[str] = None
    categorie_code: Optional[str] = None
    vol_alcool: Optional[float] = None
    volume_litre: Optional[float] = None
    prix_unitaire: Optional[float] = None
    colisage: Optional[int] = None
    quantite: Optional[int] = None
    montant_ht: Optional[float] = None
    tva_code: Optional[str] = None
    promo: bool = False
    page_number: Optional[int] = None
    y_position: Optional[float] = None


# ── Helpers internes ─────────────────────────────────────────────────────────


def _merge_numeric_words(words: list[dict], col_bounds: tuple[float, float]) -> list[dict]:
    """Façade METRO : fusion des mots numériques adjacents avec MERGE_GAP_PTS METRO."""
    return merge_numeric_words(words, col_bounds, gap_pts=MERGE_GAP_PTS)


def _normalize_ean(ean_raw: str) -> Optional[str]:
    """Normalise un EAN potentiellement bruité par OCR."""
    cleaned = ocr_to_digits(ean_raw)
    if not cleaned:
        return None
    candidates: list[str] = []
    if 8 <= len(cleaned) <= 14:
        candidates.append(cleaned)
    candidates.extend(re.findall(r"\d{8,14}", cleaned))
    for cand in candidates:
        if RE_EAN.match(cand) and not RE_FICTIF.match(cand):
            return cand
    return None


def _normalize_article(article_raw: str) -> Optional[str]:
    """Normalise le n° article (6-7 chiffres)."""
    cleaned = ocr_to_digits(article_raw)
    if not cleaned:
        return None
    match = re.search(r"\d{6,7}", cleaned)
    return match.group(0) if match else None


# ── Extraction principale ─────────────────────────────────────────────────────


def extract_line(
    words: list[dict],
    known_brands: frozenset[str] | None = None,
) -> Optional[ExtractedLine]:
    """Extrait une ligne produit structurée depuis les mots pdfplumber.

    Retourne None si la ligne n'est pas une ligne produit valide
    (pas d'EAN ni d'article détecté).
    """
    merged = _merge_numeric_words(words, (COL_MONTANT[0] - 10, COL_MONTANT[1]))
    merged = _merge_numeric_words(merged, COL_PRIX)

    result = ExtractedLine()

    ean_text = _extract_col_text(merged, *COL_EAN)
    if ean_text:
        result.ean = _normalize_ean(ean_text)

    article_text = _extract_col_text(merged, *COL_ARTICLE)
    if article_text:
        result.article = _normalize_article(article_text)

    if result.ean is None and result.article is None:
        return None

    regie_words = [
        w for w in merged
        if COL_REGIE[0] <= w["x0"] <= COL_REGIE[1]
        or COL_REGIE[0] <= (w["x0"] + w["x1"]) / 2 <= COL_REGIE[1]
    ]
    for rw in regie_words:
        candidate = rw["text"].strip().upper()
        if len(candidate) == 1 and candidate in VALID_REGIES:
            result.regie = candidate
            result.categorie_code = REGIE_TO_CATEGORIE.get(candidate)
            break

    result.designation_tokens = tokenize_designation(
        merged, COL_DESIGNATION[0], COL_DESIGNATION[1], known_brands
    )

    vol_text = _extract_col_text(merged, *COL_VOL_ALCOOL)
    if vol_text:
        val = parse_fr_number(vol_text)
        if val is not None and 0 < val <= 100:
            result.vol_alcool = val

    volume_text = _extract_col_text(merged, *COL_VOLUME)
    if volume_text:
        val = parse_fr_number(volume_text)
        if val is not None and val > 0:
            result.volume_litre = val

    prix_text = _extract_col_text(merged, *COL_PRIX)
    if prix_text:
        val = parse_fr_number(prix_text)
        if val is not None:
            result.prix_unitaire = val

    colisage_text = _extract_col_text(merged, *COL_COLISAGE).strip()
    if colisage_text and RE_QTE.match(colisage_text):
        result.colisage = int(colisage_text)

    qte_text = _extract_col_text(merged, *COL_QUANTITE).strip()
    if qte_text:
        first_token = qte_text.split()[0]
        if RE_QTE.match(first_token):
            result.quantite = int(first_token)

    montant_text = _extract_col_text(merged, *COL_MONTANT)
    if montant_text:
        m_val = re.search(r"-?\d[\d\s]*[,\.]\d{2,3}-?", montant_text)
        raw_montant = m_val.group(0).strip() if m_val else montant_text
        val = parse_fr_number(raw_montant)
        if val is not None:
            result.montant_ht = val

    tva_text = _extract_col_text(merged, *COL_TVA).upper().strip()
    if tva_text and RE_TVA_CODE.match(tva_text):
        result.tva_code = tva_text

    promo_text = _extract_col_text(merged, *COL_PROMO).strip().upper()
    result.promo = promo_text == "P"

    return result
