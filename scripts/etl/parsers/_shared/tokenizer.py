"""Tokenisation sémantique de la zone désignation — générique.

Chaque mot (token) est classifié : DEGREE, CONTAINER, MULTIPLIER, PACKAGING,
NUMERIC, WORD, BRAND, NOISE.

La désignation est reconstruite depuis BRAND + NUMERIC + WORD ; les autres
tokens alimentent les attributs structurés (degré, conditionnement, contenant).

Aucune dépendance à un fournisseur : les paramètres `known_brands` et
`abbrev_dict` sont fournis par l'appelant.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from scripts.etl.parsers._shared.constants import (
    CONTAINERS,
    RE_DEGREE,
    RE_MULTIPLIER_ONLY,
    RE_MULTIPLIER_QTY,
    RE_QTY_UNIT,
    UNIT_NORMALIZE,
    UNIT_TO_ML,
)
from scripts.etl.parsers._shared.ocr_clean import clean_ocr_token, expand_abbreviation


class TokenType(Enum):
    BRAND = "brand"
    WORD = "word"
    DEGREE = "degree"
    PACKAGING = "packaging"
    CONTAINER = "container"
    MULTIPLIER = "multiplier"
    NUMERIC = "numeric"
    NOISE = "noise"


@dataclass
class DesigToken:
    """Token classifié de la zone désignation."""
    raw: str
    cleaned: str
    token_type: TokenType
    x0: float = 0.0


def classify_token(
    text: str,
    known_brands: frozenset[str] | None = None,
    abbrev_dict: dict[str, str] | None = None,
) -> TokenType:
    """Classifie un token de désignation.

    Ordre de priorité (premier match gagne) :
      1. Degré alcool ("40D", "5.5D")
      2. Contenant connu (VP, BTE, PET...)
      3. Multiplicateur + unité ("18X25CL", "6X140G")
      4. Multiplicateur seul ("X6", "X20")
      5. Quantité + unité ("75CL", "500G", "2.5KG")
      6. Marque connue (lookup dans known_brands)
      7. Purement numérique → NUMERIC (ex: "1664")
      8. Contient au moins une lettre → WORD
      9. Sinon → NOISE
    """
    upper = text.upper().strip()
    if not upper:
        return TokenType.NOISE

    if RE_DEGREE.match(upper):
        return TokenType.DEGREE

    if upper in CONTAINERS:
        return TokenType.CONTAINER

    if RE_MULTIPLIER_QTY.match(upper):
        return TokenType.MULTIPLIER

    if RE_MULTIPLIER_ONLY.match(upper):
        return TokenType.MULTIPLIER

    if upper.startswith("LOT DE "):
        return TokenType.MULTIPLIER

    if RE_QTY_UNIT.match(upper):
        return TokenType.PACKAGING

    if known_brands and upper in known_brands:
        return TokenType.BRAND

    # Forme expansée (abréviation) dans le brand dict
    if known_brands and abbrev_dict:
        expanded = expand_abbreviation(upper, abbrev_dict).upper()
        if expanded != upper and expanded in known_brands:
            return TokenType.BRAND

    if upper.isdigit():
        return TokenType.NUMERIC

    # Unité seule sans nombre ("CL", "ML", "G", "KG", "L") → PACKAGING
    if upper in {"CL", "ML", "G", "GR", "GRS", "KG", "L", "LT", "DL", "MG"}:
        return TokenType.PACKAGING

    if any(c.isalpha() for c in upper):
        return TokenType.WORD

    return TokenType.NOISE


def _split_compound_token(text: str) -> list[str]:
    """Découpe un token composé collé sans espace.

    Patterns gérés : "COCONUT37.5D70CL", "APPLE37.50D", "VPX8",
    "25CLX12" (inversé), "75C" (C → CL), "12%100CL", "MONBAZIL.75CL",
    "37.5D70", "COG.COURVOISIER".
    """
    if not text:
        return []
    if len(text) <= 1:
        return [text]

    if "." in text and not text.replace(".", "").replace(",", "").isdigit():
        dot_split = re.split(r"(?<=\.)(?=[A-Z])", text)
        if len(dot_split) > 1:
            return [p for p in dot_split if p]

    m_inv = re.match(
        r"^(\d+(?:[.,]\d+)?(?:CL|ML|L|G|KG|LT))([X*]\d+)$",
        text, re.IGNORECASE,
    )
    if m_inv:
        return [m_inv.group(1), m_inv.group(2)]

    m_star = re.match(
        r"^(\d+)\*(\d+(?:[.,]\d+)?(?:CL|ML|L|G|KG|LT))$",
        text, re.IGNORECASE,
    )
    if m_star:
        return [f"{m_star.group(1)}X{m_star.group(2)}"]

    m_pct = re.match(
        r"^\d+%(\d+(?:CL|ML|L|G|KG|LT))$",
        text, re.IGNORECASE,
    )
    if m_pct:
        return [m_pct.group(1)]

    _UNIT_ABBREV = {
        "C": "CL", "M": "ML", "K": "KG",
    }
    m_abbrev = re.match(r"^(\d+(?:[.,]\d+)?)([CMK])$", text)
    if m_abbrev:
        return [m_abbrev.group(1) + _UNIT_ABBREV[m_abbrev.group(2)]]

    m_unit_cont = re.match(
        r"^(\d+(?:[.,]\d+)?(?:CL|ML|L|G|KG|LT))(PET|VP|BTE|BID|CAN|FUT)$",
        text, re.IGNORECASE,
    )
    if m_unit_cont:
        return [m_unit_cont.group(1), m_unit_cont.group(2)]

    m_sc = re.match(r"^(\d+)(SC|PCE?S?|PCES)$", text, re.IGNORECASE)
    if m_sc:
        return [f"lot de {m_sc.group(1)}"]

    parts: list[str] = []
    remaining = text

    while remaining:
        m_am = re.match(
            r"^([A-Za-z]+?)(\d+X\d+(?:[.,]\d+)?(?:CL|ML|G|KG|L|LT)\w*)",
            remaining, re.IGNORECASE,
        )
        if m_am and len(m_am.group(1)) >= 2:
            parts.append(m_am.group(1))
            remaining = m_am.group(2)
            continue

        m = re.match(
            r"^([A-Za-z]+?)(\d+(?:[.,]\d+)?(?:D|CL|ML|G|KG|L|LT)\w*)",
            remaining, re.IGNORECASE,
        )
        if m and len(m.group(1)) >= 2:
            parts.append(m.group(1))
            remaining = m.group(2)
            continue

        m_trail = re.match(
            r"^([A-Za-z]+?)(\d+[.,]?\d*\.?)$",
            remaining,
        )
        if m_trail and len(m_trail.group(1)) >= 2:
            parts.append(m_trail.group(1))
            remaining = m_trail.group(2).rstrip(".")
            if remaining:
                parts.append(remaining)
            remaining = ""
            continue

        m2 = re.match(r"^(VP|BTE|PET|BID|CAN)(X\d+.*)$", remaining, re.IGNORECASE)
        if m2:
            parts.append(m2.group(1))
            remaining = m2.group(2)
            continue

        m3 = re.match(
            r"^(\d+(?:[.,]\d+)?D)(\d+(?:[.,]\d+)?(?:CL|ML|G|KG|L|LT)?\w*)",
            remaining, re.IGNORECASE,
        )
        if m3 and m3.group(2):
            parts.append(m3.group(1))
            remaining = m3.group(2)
            continue

        parts.append(remaining)
        break

    return [p for p in parts if p]


def _is_noise_single_char(text: str) -> bool:
    """Détecte les lettres parasites isolées (artefacts OCR)."""
    return len(text) == 1 and text.isalpha() and text.islower()


def tokenize_designation(
    words: list[dict],
    x_min: float,
    x_max: float,
    known_brands: frozenset[str] | None = None,
    abbrev_dict: dict[str, str] | None = None,
    case_fold: bool = False,
) -> list[DesigToken]:
    """Tokenise les mots PDF dans la zone désignation [x_min, x_max].

    Args:
        words: Mots pdfplumber (dicts 'text', 'x0', 'x1').
        x_min, x_max: Zone désignation.
        known_brands: Marques connues (classification BRAND). Frozenset en majuscules.
        abbrev_dict: Dictionnaire d'abréviations à expanser pour le lookup BRAND.
        case_fold: Si True, normalise les tokens via upper() avant lookup brand.
                   Nécessaire pour les factures où les produits sont en CapitalCase
                   (ex: TAIYAT "Maggi" vs brand dict "MAGGI").
    """
    in_zone = [
        w for w in words
        if x_min <= w["x0"] <= x_max
        or x_min <= (w["x0"] + w["x1"]) / 2 <= x_max
    ]
    in_zone.sort(key=lambda w: w["x0"])

    tokens: list[DesigToken] = []
    for w in in_zone:
        raw = w["text"].strip()
        if not raw:
            continue
        cleaned = clean_ocr_token(raw)

        if _is_noise_single_char(cleaned):
            tokens.append(DesigToken(raw=raw, cleaned=cleaned, token_type=TokenType.NOISE, x0=w["x0"]))
            continue

        sub_parts = _split_compound_token(cleaned)

        for part in sub_parts:
            # case_fold : uppercase avant classification pour le lookup brand
            classify_input = part.upper() if case_fold else part
            token_type = classify_token(classify_input, known_brands, abbrev_dict)
            tokens.append(DesigToken(
                raw=raw if len(sub_parts) == 1 else part,
                cleaned=part,
                token_type=token_type,
                x0=w["x0"],
            ))

    # Post-traitement 1 : fusionner NUMERIC + unité seule → PACKAGING
    merged_tokens: list[DesigToken] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if (
            t.token_type == TokenType.NUMERIC
            and i + 1 < len(tokens)
            and tokens[i + 1].token_type == TokenType.PACKAGING
            and tokens[i + 1].cleaned.upper() in {"CL", "ML", "G", "KG", "L", "LT", "DL"}
        ):
            combined = t.cleaned + tokens[i + 1].cleaned
            merged_tokens.append(DesigToken(
                raw=f"{t.raw} {tokens[i + 1].raw}",
                cleaned=combined,
                token_type=TokenType.PACKAGING,
                x0=t.x0,
            ))
            i += 2
        else:
            merged_tokens.append(t)
            i += 1
    tokens = merged_tokens

    # Post-traitement 2 : nombre en position 0 suivi d'un WORD = quantité, pas marque
    if (
        len(tokens) >= 2
        and tokens[0].token_type in (TokenType.NUMERIC, TokenType.BRAND)
        and tokens[0].cleaned in _QTY_PREFIXES
        and tokens[1].token_type in (TokenType.WORD, TokenType.CONTAINER, TokenType.NOISE)
    ):
        tokens[0] = DesigToken(
            raw=tokens[0].raw,
            cleaned=tokens[0].cleaned,
            token_type=TokenType.NOISE,
            x0=tokens[0].x0,
        )

    return tokens


# Nombres typiques de colisage/quantité (exposé module-level pour extract_colisage fallback).
# Si un de ces nombres apparaît en position 0 du libellé, le post-traitement le reclasse
# en NOISE (pour ne pas polluer la désignation) — mais il peut être un colisage candidat.
_QTY_PREFIXES = frozenset({
    "1", "2", "3", "4", "5", "6", "8", "10", "12", "15", "18", "20",
    "24", "25", "30", "40", "50", "60", "80", "100", "125", "150",
    "200", "250", "300", "500", "750", "1000",
})


def build_designation(
    tokens: list[DesigToken],
    abbrev_dict: dict[str, str] | None = None,
    extra_noise_words: frozenset[str] | None = None,
) -> str:
    """Construit la désignation depuis les tokens BRAND + NUMERIC + WORD.

    Args:
        tokens: Tokens classifiés.
        abbrev_dict: Dictionnaire d'expansion (ex: BLDE → BLONDE pour METRO).
        extra_noise_words: Mots supplémentaires à exclure (ex: pays de provenance TAIYAT).
    """
    _BRAND_NUMS = frozenset({"1664", "86", "51", "7UP"})
    _NOISE_SINGLES = frozenset({
        "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
        "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    })
    _TECH_NOISE = frozenset({
        "VP", "BTE", "PET", "BID", "FUT", "CAN", "BIB",
        "VPX", "1PRIX6", "1PRIX",
    })
    extra_noise = extra_noise_words or frozenset()

    parts: list[str] = []
    for t in tokens:
        if t.token_type in (TokenType.BRAND, TokenType.NUMERIC, TokenType.WORD):
            text = t.cleaned
            if t.token_type == TokenType.WORD and abbrev_dict:
                text = expand_abbreviation(text, abbrev_dict)
            if t.token_type == TokenType.NUMERIC and text not in _BRAND_NUMS:
                continue
            upper = text.upper().rstrip(".")
            if upper in _NOISE_SINGLES:
                continue
            if len(text) == 2 and text.endswith(".") and text[0].isalpha():
                continue
            if upper in _TECH_NOISE:
                continue
            if upper in extra_noise:
                continue
            if re.match(r"^\d+(?:CL|ML|L|KG|G)X\d+$", text, re.I):
                continue
            if parts and text.upper() == parts[-1].upper():
                continue
            parts.append(text)

    # Fix A (audit 2026-04-24) : si la désignation finale est trop pauvre
    # (≤1 token, typiquement une marque seule comme "1664"), on enrichit avec
    # les attributs physiques (degré, volume, contenant) pour discriminer les
    # variantes. Sans ça, "1664 5.5D 75CL VP" et "1664 5.5D 25CL X6 VP" se
    # retrouvent avec la même désignation normalisée "1664" → sur-merge par
    # Jaro-Winkler.
    if len(parts) <= 1:
        for t in tokens:
            if t.token_type == TokenType.DEGREE:
                parts.append(t.cleaned.upper())
            elif t.token_type == TokenType.PACKAGING:
                parts.append(t.cleaned.upper())
            elif t.token_type == TokenType.MULTIPLIER:
                parts.append(t.cleaned.upper())
            elif t.token_type == TokenType.CONTAINER:
                # Container = VP/BTE/PET/CAN — utile pour distinguer canette vs bouteille
                parts.append(t.cleaned.upper())

    return " ".join(parts)


def build_designation_raw(tokens: list[DesigToken]) -> str:
    """Construit la désignation brute (tous les tokens, sans nettoyage)."""
    return " ".join(t.raw for t in tokens)


def extract_degree(tokens: list[DesigToken]) -> Optional[float]:
    """Extrait le degré alcool depuis les tokens DEGREE."""
    for t in tokens:
        if t.token_type == TokenType.DEGREE:
            m = RE_DEGREE.match(t.cleaned.upper())
            if m:
                return float(m.group(1).replace(",", "."))
    return None


def extract_container(tokens: list[DesigToken]) -> Optional[str]:
    """Extrait le type de contenant depuis les tokens CONTAINER."""
    for t in tokens:
        if t.token_type == TokenType.CONTAINER:
            return t.cleaned.upper()
    return None


_RE_MULT_LOOSE = re.compile(
    r"^(\d+)[xX*](\d+(?:[.,]\d+)?)$"
)


def extract_volume_ml(tokens: list[DesigToken]) -> Optional[int]:
    """Extrait le volume unitaire en mL depuis les tokens PACKAGING ou MULTIPLIER.

    Fallback : détecte les paires séparées "<NxM>" + "<UNITE>" (ex: "50x125" + "gr",
    "12x0,5" + "L") que le tokenizer classe en WORD/NUMERIC isolé + PACKAGING unité.
    """
    for t in tokens:
        if t.token_type == TokenType.PACKAGING:
            m = RE_QTY_UNIT.match(t.cleaned.upper())
            if m:
                qty = float(m.group(1).replace(",", "."))
                raw_unit = m.group(2).upper()
                norm_unit = UNIT_NORMALIZE.get(raw_unit, raw_unit.lower())
                ml_factor = UNIT_TO_ML.get(norm_unit)
                if ml_factor is not None:
                    return round(qty * ml_factor)
        if t.token_type == TokenType.MULTIPLIER:
            m = RE_MULTIPLIER_QTY.match(t.cleaned.upper())
            if m:
                qty = float(m.group(2).replace(",", "."))
                raw_unit = m.group(3).upper()
                norm_unit = UNIT_NORMALIZE.get(raw_unit, raw_unit.lower())
                ml_factor = UNIT_TO_ML.get(norm_unit)
                if ml_factor is not None:
                    return round(qty * ml_factor)

    # Fallback : paires séparées "NxM" + "UNITE" (TAIYAT écrit "50x125 gr")
    for i, t in enumerate(tokens):
        m_loose = _RE_MULT_LOOSE.match(t.cleaned.upper())
        if not m_loose:
            continue
        for next_tok in tokens[i + 1:i + 3]:
            if next_tok.token_type != TokenType.PACKAGING:
                continue
            unit_m = re.match(r"^([A-Z]+)$", next_tok.cleaned.upper())
            if not unit_m:
                continue
            raw_unit = unit_m.group(1)
            norm_unit = UNIT_NORMALIZE.get(raw_unit, raw_unit.lower())
            ml_factor = UNIT_TO_ML.get(norm_unit)
            if ml_factor is None:
                continue
            qty = float(m_loose.group(2).replace(",", "."))
            return round(qty * ml_factor)
    return None


def extract_colisage(tokens: list[DesigToken]) -> Optional[int]:
    """Extrait le colisage depuis les tokens.

    Ordre de priorité :
      1. Token MULTIPLIER standard (ex: "12X120G" → 12, "X6" → 6)
      2. Fallback : nombre en position 0 reclassé NOISE par le post-traitement
         _QTY_PREFIXES (ex: "150 SUCETTES FRUIT" → 150).
    """
    for t in tokens:
        if t.token_type == TokenType.MULTIPLIER:
            m_full = RE_MULTIPLIER_QTY.match(t.cleaned.upper())
            if m_full:
                return int(m_full.group(1))
            m_only = RE_MULTIPLIER_ONLY.match(t.cleaned.upper())
            if m_only:
                return int(m_only.group(1))
    # Fallback : nombre _QTY_PREFIXES en position 0 (reclassé NOISE par le post-traitement)
    if tokens and tokens[0].token_type == TokenType.NOISE and tokens[0].cleaned in _QTY_PREFIXES:
        try:
            return int(tokens[0].cleaned)
        except ValueError:
            return None
    return None
