"""Enrichissement d'une ligne ETL depuis sa désignation textuelle.

Parser-agnostic. Les parsers non-METRO (ETHAN xlsx, GNANAM vision, EUROCIEL PDF
simple) ne fournissent souvent qu'une désignation brute sans marque, volume,
conditionnement ni catégorie. Ce module réutilise les primitives du tokenizer
METRO (qui travaillent sur une liste de DesigToken) en construisant des tokens
synthétiques depuis une string, puis remplit les champs manquants de la ligne.

Appelé par `run_import` (preview_mode) et par `reclassify` après chaque parse.
"""
from __future__ import annotations

import re
from typing import Optional

from app.etl_types import LigneParsee


# Notation française avec virgule → notation anglaise avec point.
# Le tokenizer METRO a été écrit pour les formats PDF Metro qui utilisent
# des entiers (33CL). Les factures TAIYAT/ETHAN utilisent la convention FR
# avec virgule (0,33L). Sans ce pré-process, "24x0,33l" n'est pas détecté.
_RE_COMMA_DECIMAL = re.compile(r"(\d),(\d)")


def _normalize_for_tokenizer(designation: str) -> str:
    """Pré-process pour robustesse hors-PDF-Metro.

    1. Virgule décimale FR → point (0,33L → 0.33L).
    2. Unités collées en lowercase → uppercase. Sinon `clean_ocr_token` vire
       les lettres minuscules terminales par prudence OCR, ce qui ampute
       "24x0.33l" en "24x0.33" et rate la détection MULTIPLIER.
    """
    if not designation:
        return designation
    s = _RE_COMMA_DECIMAL.sub(r"\1.\2", designation)
    # Mettre en MAJ les unités collées aux chiffres (pas le reste du texte)
    s = re.sub(
        r"(\d)(cl|ml|l|lt|g|kg|mg|dl)\b",
        lambda m: m.group(1) + m.group(2).upper(),
        s, flags=re.IGNORECASE,
    )
    # Idem pour multiplicateurs collés type "24x33CL" → "24X33CL"
    s = re.sub(r"(\d)x(\d)", r"\1X\2", s)
    return s


def _synthetic_words(designation: str) -> list[dict]:
    """Construit des words dicts compatibles tokenize_designation depuis une string.

    Le tokenizer METRO attend `[{'text': str, 'x0': float, 'x1': float}, ...]`.
    On écarte la notion de position PDF en assignant des x0 incrémentaux.
    """
    words: list[dict] = []
    x = 0.0
    normalised = _normalize_for_tokenizer(designation).strip()
    for chunk in normalised.split():
        if not chunk:
            continue
        words.append({"text": chunk, "x0": x, "x1": x + 10.0})
        x += 12.0
    return words


def _lookup_brand_from_tokens(tokens_upper: list[str]) -> Optional[str]:
    """Cherche une marque connue dans la liste de tokens (uppercase).

    Priorité aux marques multi-mots (greedy). Retourne la marque en majuscules
    ou None si aucun match.
    """
    try:
        from scripts.etl.parsers.brand_dictionary import get_brand_dictionary
    except Exception:
        return None
    bd = get_brand_dictionary()

    # Multi-mots d'abord
    i = 0
    while i < len(tokens_upper):
        match = bd.lookup_multiword(tokens_upper, i)
        if match:
            return match[0]
        i += 1

    # Single-token : premier token reconnu (souvent en position 0 ou 1)
    for token in tokens_upper:
        if bd.contains(token):
            return token
    return None


def enrich_ligne_from_designation(ligne: LigneParsee) -> None:
    """Enrichit une LigneParsee depuis sa désignation texte (in-place).

    Ne touche JAMAIS un champ déjà rempli. Idempotent.

    Champs possiblement remplis :
      - marque (lookup brand_dictionary)
      - conditionnement (tokenizer PACKAGING/MULTIPLIER)
      - volume_unitaire_ml (tokenizer PACKAGING volume)
      - contenant (tokenizer CONTAINER)
      - degre_alcool (tokenizer DEGREE)
      - unite_base (déduit du conditionnement)
    """
    designation = (ligne.designation or "").strip()
    if not designation:
        return

    # Import différé : les modules parsers dépendent du PYTHONPATH scripts/
    try:
        from scripts.etl.parsers.brand_dictionary import get_brand_dictionary
        from scripts.etl.parsers.metro.tokenizer import tokenize_designation
        from scripts.etl.parsers.metro.conditionnement import extract_conditionnement
        from scripts.etl.parsers.metro.tokenizer import (
            extract_container, extract_degree, extract_volume_ml,
        )
    except Exception:
        return

    words = _synthetic_words(designation)
    if not words:
        return

    try:
        known_brands = get_brand_dictionary().as_frozenset()
    except Exception:
        known_brands = None

    try:
        tokens = tokenize_designation(words, x_min=-1.0, x_max=1e6, known_brands=known_brands)
    except Exception:
        return

    # Marque : lookup explicite (multi-mots prioritaire)
    if not ligne.marque:
        tokens_upper = [t.cleaned.upper() for t in tokens if t.cleaned]
        brand = _lookup_brand_from_tokens(tokens_upper)
        if brand:
            ligne.marque = brand

    # Conditionnement + unite_base + contenant (via tokens PACKAGING/MULTIPLIER)
    if not ligne.conditionnement:
        try:
            cond, unite, contenant = extract_conditionnement(tokens)
        except Exception:
            cond, unite, contenant = None, "piece", None
        if cond:
            ligne.conditionnement = cond
        # unite_base : on écrase "U" ou valeur vide seulement
        if unite and unite != "piece" and (not ligne.unite_base or ligne.unite_base in {"U", "piece", ""}):
            ligne.unite_base = unite
        if not ligne.contenant and contenant:
            ligne.contenant = contenant

    # Volume unitaire en mL
    if ligne.volume_unitaire_ml is None:
        try:
            vol = extract_volume_ml(tokens)
        except Exception:
            vol = None
        if vol:
            ligne.volume_unitaire_ml = vol

    # Contenant (si pas déjà fait via extract_conditionnement)
    if not ligne.contenant:
        try:
            cont = extract_container(tokens)
        except Exception:
            cont = None
        if cont:
            ligne.contenant = cont

    # Degré alcool
    if ligne.degre_alcool is None:
        try:
            deg = extract_degree(tokens)
        except Exception:
            deg = None
        if deg is not None:
            ligne.degre_alcool = deg
