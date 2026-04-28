"""Parser fournisseur METRO v2 — package (ADR-08).

Re-export des 3 fonctions publiques pour compatibilité avec
import_pipeline._PARSERS et les endpoints admin ETL.
"""
from scripts.etl.parsers.metro.core import (
    parse,
    parse_facture,
    parse_with_facture_metrics,
)

__all__ = ["parse", "parse_facture", "parse_with_facture_metrics"]
