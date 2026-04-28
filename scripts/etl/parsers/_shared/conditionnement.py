"""Extraction conditionnement non destructive depuis tokens — générique.

Travaille sur les DesigToken déjà classifiés au lieu de regex sur string.
La désignation n'est JAMAIS amputée : seuls les tokens PACKAGING/MULTIPLIER/CONTAINER
sont routés vers leurs attributs respectifs.
"""
from __future__ import annotations

import re
from typing import Optional

from scripts.etl.parsers._shared.constants import (
    RE_MULTIPLIER_ONLY,
    RE_MULTIPLIER_QTY,
    RE_QTY_UNIT,
    UNIT_NORMALIZE,
)
from scripts.etl.parsers._shared.tokenizer import DesigToken, TokenType


# Regex extract_colisage_from_text : ordre de priorité
#   "lot de 150"            → 150
#   "(10×500)" ou "(10x500)" → 10 (premier nombre avant multiplicateur)
#   "12×33cL" / "12x33cL"    → 12 (premier nombre du multiplicateur)
#   "x6" seul                → 6
_RE_COND_LOT_DE = re.compile(r"lot\s+de\s+(\d+)", re.IGNORECASE)
_RE_COND_PAREN_MULT = re.compile(r"\((\d+)\s*[×xX]\s*\d+")
_RE_COND_MULT_QTY = re.compile(r"(?<!\d)(\d+)\s*[×xX]\s*\d+")
_RE_COND_X_ONLY = re.compile(r"(?<![0-9a-zA-Z])[xX](\d+)(?![0-9a-zA-Z])")


def extract_colisage_from_text(text: Optional[str]) -> Optional[int]:
    """Extrait un colisage depuis un texte (conditionnement ou désignation).

    Utilisé en fallback quand la colonne PDF ne donne pas le colisage
    (ex: METRO qui stocke la quantité commandée, pas le lot intérieur).

    Retourne None si aucun pattern ne matche. Valeurs > 10_000 ignorées
    (protection contre ID produits parasites).
    """
    if not text:
        return None
    for rx in (_RE_COND_LOT_DE, _RE_COND_PAREN_MULT, _RE_COND_MULT_QTY, _RE_COND_X_ONLY):
        m = rx.search(text)
        if m:
            try:
                v = int(m.group(1))
            except (TypeError, ValueError):
                continue
            if 1 < v <= 10_000:
                return v
    return None


def extract_conditionnement(
    tokens: list[DesigToken],
) -> tuple[Optional[str], str, Optional[str]]:
    """Extrait conditionnement, unité de base et contenant depuis les tokens.

    Returns:
        (conditionnement, unite_base, contenant)
    """
    parts: list[str] = []
    unite = "piece"
    contenant: Optional[str] = None

    for t in tokens:
        if t.token_type == TokenType.CONTAINER:
            contenant = t.cleaned.upper()

        elif t.token_type == TokenType.MULTIPLIER:
            upper = t.cleaned.upper()
            m_full = RE_MULTIPLIER_QTY.match(upper)
            if m_full:
                nb = m_full.group(1)
                qty = m_full.group(2).replace(",", ".")
                raw_unit = m_full.group(3).upper()
                norm_unit = UNIT_NORMALIZE.get(raw_unit, raw_unit.lower())
                parts.append(f"{nb}×{qty}{norm_unit}")
                if norm_unit != "piece":
                    unite = norm_unit
            else:
                m_only = RE_MULTIPLIER_ONLY.match(upper)
                if m_only:
                    parts.append(f"lot de {m_only.group(1)}")
                elif upper.startswith("LOT DE "):
                    parts.append(upper.lower())

        elif t.token_type == TokenType.PACKAGING:
            upper = t.cleaned.upper()
            m = RE_QTY_UNIT.match(upper)
            if m:
                qty = m.group(1).replace(",", ".")
                raw_unit = m.group(2).upper()
                norm_unit = UNIT_NORMALIZE.get(raw_unit, raw_unit.lower())
                parts.append(f"{qty}{norm_unit}")
                if norm_unit != "piece" and unite == "piece":
                    unite = norm_unit

    conditionnement = ", ".join(parts) if parts else None
    return conditionnement, unite, contenant
