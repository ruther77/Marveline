"""Parser fournisseur TAIYAT v2 — package.

Re-export de l'interface publique pour compatibilité avec
`import_pipeline._PARSERS` et les scripts CLI (`taiyat_bulk_*`).
"""
from scripts.etl.parsers.taiyat.core import (
    parse,
    parse_facture,
    parse_with_facture_metrics,
)

__all__ = ["parse", "parse_facture", "parse_with_facture_metrics"]
