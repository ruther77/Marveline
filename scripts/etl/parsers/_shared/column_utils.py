"""Utilitaires colonnes PDF génériques : groupement par Y, extraction texte, parse nombre."""
from __future__ import annotations

import re
from typing import Optional

from scripts.etl.parsers._shared.constants import RE_FR_NUMBER


def group_by_y(words: list[dict], line_tolerance: float = 5.0) -> dict[float, list[dict]]:
    """Regroupe les mots par ligne (tolérance en points Y).

    Args:
        words: Mots pdfplumber (dicts avec 'top', 'x0').
        line_tolerance: Écart max en Y pour deux mots sur la même ligne.
    """
    lines: dict[float, list[dict]] = {}
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        y = word["top"]
        match = next((k for k in lines if abs(y - k) < line_tolerance), None)
        if match is not None:
            lines[match].append(word)
        else:
            lines[y] = [word]
    return lines


def line_text(words: list[dict]) -> str:
    """Texte de la ligne reconstitué (pour debug et pattern matching)."""
    return " ".join(w["text"] for w in sorted(words, key=lambda w: w["x0"]))


def extract_col_text(words: list[dict], x_min: float, x_max: float) -> str:
    """Extrait le texte des mots dans la zone [x_min, x_max]."""
    in_col = [
        w for w in words
        if x_min <= w["x0"] <= x_max
        or x_min <= (w["x0"] + w["x1"]) / 2 <= x_max
    ]
    in_col.sort(key=lambda w: w["x0"])
    return " ".join(w["text"] for w in in_col).strip()


def merge_numeric_words(
    words: list[dict],
    col_bounds: tuple[float, float],
    gap_pts: float = 12.0,
) -> list[dict]:
    """Fusionne les mots numériques adjacents (séparateur milliers).

    Ex: ["1" x0=480, "503,20" x0=489] → ["1 503,20" x0=480]
    """
    col_min, col_max = col_bounds
    in_col = sorted(
        [w for w in words if col_min <= w["x0"] <= col_max],
        key=lambda w: w["x0"],
    )
    if len(in_col) < 2:
        return words

    merged: list[dict] = []
    consumed: set[int] = set()
    i = 0
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
            if gap <= gap_pts and re.match(r"^[\d,.\s-]+$", nxt_text):
                text_parts.append(nxt_text)
                x1 = nxt["x1"]
                consumed.add(id(nxt))
                j += 1
            else:
                break

        if len(text_parts) > 1:
            merged.append({
                "text": " ".join(text_parts),
                "x0": x0, "x1": x1, "top": current["top"],
            })
        else:
            consumed.discard(id(current))
        i = j if j > i + 1 else i + 1

    result = [w for w in words if id(w) not in consumed]
    result.extend(merged)
    return result


def parse_fr_number(raw: str) -> Optional[float]:
    """Parse un nombre format français (virgule décimale, suffixe '-' négatif)."""
    if not raw:
        return None
    s = raw.strip()
    if not s or not RE_FR_NUMBER.match(s):
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
