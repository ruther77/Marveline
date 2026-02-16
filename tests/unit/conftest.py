"""Conftest pour tests unitaires — pas de DB, Redis cleanup actif."""
import pytest

from app.core.redis import redis_client


@pytest.fixture(autouse=True)
def cleanup_redis_between_tests():
    """Nettoie les clés Redis entre chaque test unitaire.

    Même pattern que tests/conftest.py — nécessaire car test_redis.py
    utilise Redis réel et les clés persistent entre les tests/runs.
    """
    patterns = [
        "rate_limit:*", "refresh_wl:*", "access_bl:*", "token_family:*",
        "bf_email:*", "bf_ip:*", "bf_lock:*", "bf_alert:*",
        "session:*", "session_idx:*",
        "mfa_session:*",
        "pwd_reset:*", "pwd_reset_rate:*",
        "csrf:*",
    ]
    for pattern in patterns:
        for key in redis_client.client.scan_iter(pattern):
            redis_client.client.delete(key)
    yield
    for pattern in patterns:
        for key in redis_client.client.scan_iter(pattern):
            redis_client.client.delete(key)
