"""Conftest pour tests unitaires — pas de DB, pas de Redis."""
import pytest


@pytest.fixture(autouse=True)
def cleanup_redis_between_tests():
    """Override du cleanup Redis global — no-op pour tests unitaires."""
    yield
