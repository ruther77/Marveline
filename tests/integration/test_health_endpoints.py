"""Tests d'intégration pour les endpoints health checks."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


def test_health_liveness_always_ok(client: TestClient):
    """Test GET /health - liveness probe toujours healthy.

    Le endpoint /health ne vérifie aucune dépendance externe.
    Il doit toujours retourner 200 OK avec status="ok".
    Utilisé par Kubernetes liveness probe.
    """
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}


def test_health_live_alias(client: TestClient):
    """Test GET /health/live - alias pour /health.

    Certains load balancers préfèrent /health/live.
    Doit retourner exactement la même chose que /health.
    """
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}


def test_health_ready_all_healthy(client: TestClient):
    """Test GET /health/ready - readiness probe avec dépendances saines.

    Quand PostgreSQL et Redis sont opérationnels,
    doit retourner 200 OK avec status="ready" et checks détaillés.
    """
    response = client.get("/api/v1/health/ready")

    # Debug: afficher réponse si échec
    if response.status_code != 200:
        print(f"\n❌ Status: {response.status_code}")
        print(f"Response: {response.text}")

    assert response.status_code == 200
    data = response.json()

    # Vérifier structure réponse
    assert data["status"] == "ready"
    assert data["service"] == "CaroCorp"
    assert "version" in data
    assert "checks" in data

    # Vérifier PostgreSQL healthy
    assert "postgres" in data["checks"]
    postgres_check = data["checks"]["postgres"]
    assert postgres_check["status"] == "healthy"
    assert "latency_ms" in postgres_check
    assert postgres_check["latency_ms"] >= 0  # Latence positive
    # Note: pool_size/pool_checked_out absents en mode test (Connection pas Engine)

    # Vérifier Redis healthy
    assert "redis" in data["checks"]
    redis_check = data["checks"]["redis"]
    assert redis_check["status"] == "healthy"
    assert "latency_ms" in redis_check
    assert "memory_used_mb" in redis_check
    assert "connected_clients" in redis_check
    assert redis_check["latency_ms"] >= 0  # Latence positive


@patch("app.api.v1.endpoints.health.check_postgres")
def test_health_ready_postgres_down(mock_check_postgres, client: TestClient):
    """Test GET /health/ready - PostgreSQL down → 503 Service Unavailable.

    Quand PostgreSQL est inaccessible (timeout, connection refused),
    doit retourner 503 avec status="not_ready" et error message.
    Kubernetes arrête d'envoyer du trafic au pod.
    """
    # Mock PostgreSQL down
    mock_check_postgres.return_value = (
        False,  # is_healthy = False
        {
            "status": "unhealthy",
            "error": "connection timeout"
        }
    )

    response = client.get("/api/v1/health/ready")

    # Doit retourner 503 Service Unavailable
    assert response.status_code == 503

    # Vérifier contenu réponse (peut être dict ou string selon FastAPI)
    # On vérifie juste que "not_ready" apparaît dans la réponse
    response_text = response.text if hasattr(response, 'text') else str(response.json())
    assert "not_ready" in response_text or "unhealthy" in response_text


@patch("app.api.v1.endpoints.health.check_redis")
def test_health_ready_redis_down(mock_check_redis, client: TestClient):
    """Test GET /health/ready - Redis down → 503 Service Unavailable.

    Quand Redis est inaccessible (PING timeout, connection refused),
    doit retourner 503 avec status="not_ready" et error message.
    """
    # Mock Redis down
    mock_check_redis.return_value = (
        False,  # is_healthy = False
        {
            "status": "unhealthy",
            "error": "PING timeout"
        }
    )

    response = client.get("/api/v1/health/ready")

    # Doit retourner 503 Service Unavailable
    assert response.status_code == 503

    # Vérifier que la réponse contient "not_ready" ou "unhealthy"
    response_text = response.text if hasattr(response, 'text') else str(response.json())
    assert "not_ready" in response_text or "unhealthy" in response_text


def test_health_ready_response_format(client: TestClient):
    """Test format de réponse /health/ready conforme au standard.

    Vérifie que la structure JSON respecte le format attendu:
    - status: string ("ready" | "not_ready")
    - service: string
    - version: string
    - checks: dict avec postgres + redis
    - Chaque check contient: status + métriques spécifiques
    """
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    data = response.json()

    # Vérifier types
    assert isinstance(data["status"], str)
    assert isinstance(data["service"], str)
    assert isinstance(data["version"], str)
    assert isinstance(data["checks"], dict)

    # Vérifier présence clés obligatoires
    required_keys = {"status", "service", "version", "checks"}
    assert set(data.keys()) == required_keys

    # Vérifier checks obligatoires
    assert "postgres" in data["checks"]
    assert "redis" in data["checks"]

    # Vérifier métriques PostgreSQL
    postgres = data["checks"]["postgres"]
    assert "status" in postgres
    assert postgres["status"] in ["healthy", "unhealthy"]

    if postgres["status"] == "healthy":
        assert "latency_ms" in postgres
        assert isinstance(postgres["latency_ms"], (int, float))
        # pool_size optionnel (absent en mode test)

    # Vérifier métriques Redis
    redis = data["checks"]["redis"]
    assert "status" in redis
    assert redis["status"] in ["healthy", "unhealthy"]

    if redis["status"] == "healthy":
        assert "latency_ms" in redis
        assert "memory_used_mb" in redis
        assert isinstance(redis["latency_ms"], (int, float))
        assert isinstance(redis["memory_used_mb"], (int, float))


def test_health_ready_latency_metrics(client: TestClient):
    """Test que les métriques de latence sont réalistes.

    Vérifie que:
    - PostgreSQL SELECT 1 latency < 100ms (base locale)
    - Redis PING latency < 50ms (base locale)
    - Pool metrics sont cohérents (checked_out <= pool_size)
    """
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    data = response.json()

    # Vérifier latence PostgreSQL réaliste
    postgres = data["checks"]["postgres"]
    if postgres["status"] == "healthy":
        assert 0 <= postgres["latency_ms"] < 100, \
            f"PostgreSQL latency {postgres['latency_ms']}ms trop élevée (seuil 100ms)"

        # Pool metrics cohérents (uniquement si présents - production seulement)
        if "pool_size" in postgres and "pool_checked_out" in postgres:
            assert postgres["pool_checked_out"] <= postgres["pool_size"], \
                "Connexions checked_out ne peut pas dépasser pool_size"

    # Vérifier latence Redis réaliste
    redis = data["checks"]["redis"]
    if redis["status"] == "healthy":
        assert 0 <= redis["latency_ms"] < 50, \
            f"Redis latency {redis['latency_ms']}ms trop élevée (seuil 50ms)"

        # Métriques Redis cohérentes
        assert redis["memory_used_mb"] > 0, "Redis devrait utiliser au moins 1MB"
        assert redis["connected_clients"] > 0, "Au moins 1 client Redis connecté"
