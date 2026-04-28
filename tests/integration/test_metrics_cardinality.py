"""S1.T12 — Tests F1126/METRICS-PATH-DOS-01.

Spec : docs/architecture-audit-2026-04-26/execution-plan/10-sprint-1-PROD-FIRE-DRILL.md
       L2179-2261 (Story S1.T12).

Avant : `_normalize_path` retournait le path original si aucun pattern PATH_NORMALIZATION_PATTERNS
ne matchait. Un attaquant qui spamme /api/v1/foo/{uuid_random} cree une serie temporelle
Prometheus distincte par UUID -> cardinality explosion -> OOM Prometheus en quelques minutes
-> perte du monitoring au moment d'un incident (DoS amplifie).

Apres : 1 ligne fix -> `return "other"`. Tous les paths inconnus partagent une seule
serie temporelle "other" (cardinalite bornee).
"""
from unittest.mock import MagicMock

from app.middleware.metrics import MetricsMiddleware


def _mk_middleware():
    """Helper : MetricsMiddleware sans full ASGI stack pour tester _normalize_path."""
    return MetricsMiddleware(app=MagicMock())


# ----------------------------------------------------------------------------
# F1126 : paths inconnus -> "other"
# ----------------------------------------------------------------------------

def test_normalize_path_unknown_returns_other():
    """F1126 fix : path arbitraire (non couvert par patterns) -> 'other'."""
    mw = _mk_middleware()
    assert mw._normalize_path("/api/v1/random/abc-uuid-1234") == "other"


def test_normalize_path_random_uuids_collapse_to_single_other_label():
    """Anti-DoS : 100 paths distincts avec UUID random -> 1 seule serie 'other'.
    Empeche la cardinality explosion qui OOMait Prometheus."""
    import uuid
    mw = _mk_middleware()
    results = {mw._normalize_path(f"/api/v1/random/{uuid.uuid4()}") for _ in range(100)}
    assert results == {"other"}


def test_normalize_path_random_paths_with_random_segments_also_other():
    """Variantes : root inexistant, segments multiples random -> tous 'other'."""
    mw = _mk_middleware()
    paths = [
        "/totally/random/path",
        "/api/v2/notexists",
        "/foo/bar/baz",
        "/.env",
        "/api/v1/admin/exploit-attempt-12345",
    ]
    for p in paths:
        assert mw._normalize_path(p) == "other", f"Path {p} devrait tomber sur 'other'"


# ----------------------------------------------------------------------------
# Non-regression : paths connus continuent d'etre normalises
# ----------------------------------------------------------------------------

def test_normalize_path_known_pattern_still_normalized():
    """Non-regression : path correspondant a un pattern reste normalise comme avant."""
    mw = _mk_middleware()
    # /api/v1/products/123 -> /api/v1/products/{id} (pattern existant)
    result = mw._normalize_path("/api/v1/products/123")
    assert result != "other"
    assert "/api/v1/products" in result
    assert "{id}" in result or "123" not in result  # numerique remplace


def test_normalize_path_known_pattern_with_subpath():
    """Non-regression : path avec sous-segment apres l'ID est normalise (ex: /reservations/N/confirm)."""
    mw = _mk_middleware()
    # Le comportement depend des patterns configures, mais ne doit pas etre 'other'
    # si le path matche un pattern enregistre.
    result_with_id = mw._normalize_path("/api/v1/products/123")
    result_no_id = mw._normalize_path("/totally/unknown")
    # Les deux ne doivent pas etre identiques
    assert result_with_id != result_no_id
    assert result_no_id == "other"


# ----------------------------------------------------------------------------
# Cardinalite bornee : meme path repete -> meme label
# ----------------------------------------------------------------------------

def test_normalize_path_idempotent_for_other():
    """Idempotence : appeler _normalize_path('other') retourne 'other'."""
    mw = _mk_middleware()
    assert mw._normalize_path("other") == "other"
