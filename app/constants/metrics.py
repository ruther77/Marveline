"""Constantes pour métriques Prometheus."""

import re
from typing import List, Tuple

# ── Path Normalization Patterns ──────────────────────────────────────────

PATH_NORMALIZATION_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r'/api/v1/products/\d+'), '/api/v1/products/{id}'),
    (re.compile(r'/api/v1/customers/\d+'), '/api/v1/customers/{id}'),
    (re.compile(r'/api/v1/reservations/\d+'), '/api/v1/reservations/{id}'),
    (re.compile(r'/api/v1/invoices/\d+'), '/api/v1/invoices/{id}'),
    (re.compile(r'/api/v1/audit/\d+'), '/api/v1/audit/{id}'),
]
"""Patterns regex pour normaliser les paths avec IDs numériques.

Évite la cardinalité infinie dans les labels Prometheus en remplaçant
/api/v1/products/123 → /api/v1/products/{id}

Usage:
    for pattern, replacement in PATH_NORMALIZATION_PATTERNS:
        if pattern.match(path):
            return pattern.sub(replacement, path)
"""
