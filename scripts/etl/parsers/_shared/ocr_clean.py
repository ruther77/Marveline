"""Nettoyage OCR et expansion abréviations — générique.

Les fonctions ne connaissent aucun dictionnaire d'abréviations fournisseur :
`expand_abbreviation` exige un `abbrev_dict` explicite.
"""
from __future__ import annotations

import re

from scripts.etl.parsers._shared.constants import OCR_DIGIT_MAP


def ocr_to_digits(raw: str) -> str:
    """Nettoie les confusions OCR lettres/chiffres pour les champs numériques."""
    up = (raw or "").upper()
    mapped = "".join(OCR_DIGIT_MAP.get(ch, ch) for ch in up)
    return re.sub(r"\D", "", mapped)


def clean_ocr_token(token: str) -> str:
    """Nettoie un token de désignation des artefacts OCR.

    Règles :
      - Lettre minuscule parasite en préfixe d'un mot majuscule → supprimer
      - Lettre minuscule parasite entre deux majuscules/chiffres → supprimer
      - Lettre minuscule parasite en suffixe d'un mot majuscule → supprimer
      - Préfixe "c" ou "l" collé à un nombre → supprimer
    """
    if not token or len(token) < 2:
        return token

    m_prefix = re.match(r"^([a-z]{1,2})([A-Z][A-Z0-9].*)$", token)
    if m_prefix:
        token = m_prefix.group(2)

    cleaned = []
    i = 0
    chars = list(token)
    while i < len(chars):
        ch = chars[i]
        if ch.islower():
            prev_digit = i > 0 and chars[i - 1].isdigit()
            next_digit = i < len(chars) - 1 and chars[i + 1].isdigit()
            # Préserver 'x' ou '*' entre chiffres : pattern multiplicateur ("12x120gr")
            if ch in ("x", "*") and prev_digit and next_digit:
                cleaned.append(ch)
                i += 1
                continue
            prev_upper = i > 0 and (chars[i - 1].isupper() or chars[i - 1].isdigit())
            next_upper = i < len(chars) - 1 and (chars[i + 1].isupper() or chars[i + 1].isdigit())
            at_end = i == len(chars) - 1 and prev_upper
            if (prev_upper and next_upper) or at_end:
                i += 1
                continue
        cleaned.append(ch)
        i += 1
    token = "".join(cleaned)

    m_num_prefix = re.match(r"^[a-z](\d.*)$", token)
    if m_num_prefix:
        token = m_num_prefix.group(1)

    return token


def expand_abbreviation(token: str, abbrev_dict: dict[str, str]) -> str:
    """Expanse une abréviation fournisseur.

    Args:
        token: Token en majuscules ou non.
        abbrev_dict: Dictionnaire spécifique au fournisseur. Obligatoire.

    Returns:
        Token expansé ou inchangé si pas dans le dictionnaire.
    """
    if not abbrev_dict:
        return token
    upper = token.upper()
    return abbrev_dict.get(upper, token)
