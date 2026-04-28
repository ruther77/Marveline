"""Nettoyage OCR et expansion abréviations — façade METRO.

Délégue à `_shared/ocr_clean.py` en bindant le dictionnaire d'abréviations METRO.
Interface publique préservée : `ocr_to_digits`, `clean_ocr_token`, `expand_abbreviation`.
"""
from scripts.etl.parsers._shared.ocr_clean import clean_ocr_token, ocr_to_digits
from scripts.etl.parsers._shared.ocr_clean import expand_abbreviation as _expand_shared
from scripts.etl.parsers.metro.constants import ABBREVIATIONS

__all__ = ["ocr_to_digits", "clean_ocr_token", "expand_abbreviation"]


def expand_abbreviation(token: str, abbrev_dict: dict[str, str] | None = None) -> str:
    """Expanse une abréviation METRO connue.

    Args:
        token: Token à expandre.
        abbrev_dict: Dictionnaire custom ; si None, utilise ABBREVIATIONS METRO.
    """
    if abbrev_dict is None:
        abbrev_dict = ABBREVIATIONS
    return _expand_shared(token, abbrev_dict)
