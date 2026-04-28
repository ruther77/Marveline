"""Tokenisation sémantique — façade METRO.

Délégue à `_shared/tokenizer.py` en bindant ABBREVIATIONS METRO.
Interface publique préservée : TokenType, DesigToken, classify_token,
tokenize_designation, build_designation, build_designation_raw, extract_degree,
extract_container, extract_volume_ml.
"""
from __future__ import annotations

from typing import Optional

from scripts.etl.parsers._shared.tokenizer import (
    DesigToken,
    TokenType,
    build_designation_raw,
    extract_colisage,
    extract_container,
    extract_degree,
    extract_volume_ml,
)
from scripts.etl.parsers._shared.tokenizer import build_designation as _build_designation_shared
from scripts.etl.parsers._shared.tokenizer import classify_token as _classify_token_shared
from scripts.etl.parsers._shared.tokenizer import tokenize_designation as _tokenize_designation_shared
from scripts.etl.parsers.metro.constants import ABBREVIATIONS

__all__ = [
    "TokenType",
    "DesigToken",
    "classify_token",
    "tokenize_designation",
    "build_designation",
    "build_designation_raw",
    "extract_degree",
    "extract_container",
    "extract_volume_ml",
    "extract_colisage",
]


def classify_token(text: str, known_brands: frozenset[str] | None = None) -> TokenType:
    """Classifie un token METRO (ABBREVIATIONS METRO liées)."""
    return _classify_token_shared(text, known_brands, ABBREVIATIONS)


def tokenize_designation(
    words: list[dict],
    x_min: float,
    x_max: float,
    known_brands: frozenset[str] | None = None,
) -> list[DesigToken]:
    """Tokenise la zone désignation METRO (case-sensitive, ABBREVIATIONS METRO)."""
    return _tokenize_designation_shared(
        words, x_min, x_max, known_brands,
        abbrev_dict=ABBREVIATIONS,
        case_fold=False,
    )


def build_designation(tokens: list[DesigToken]) -> str:
    """Construit la désignation METRO avec expansions ABBREVIATIONS."""
    return _build_designation_shared(tokens, abbrev_dict=ABBREVIATIONS)
