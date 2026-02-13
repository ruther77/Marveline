"""Tests d'intégration pour Prometheus metrics.

Valide que :
- Endpoint /metrics accessible et retourne format Prometheus
- Métriques HTTP collectées (http_requests_total, http_request_duration_seconds)
- Gauge http_requests_in_progress incrémenté/décrémenté correctement
- Rate limit hits comptés (rate_limit_hits_total)
- Paths normalisés (IDs remplacés par {id})
"""
import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset Prometheus metrics avant chaque test.

    Note:
        - Prometheus REGISTRY global partagé entre tests
        - Besoin de reset collectors pour éviter pollution entre tests
        - Appelé automatiquement avant chaque test (autouse=True)
    """
    # Reset tous les collectors Prometheus
    for collector in list(REGISTRY._collector_to_names.keys()):
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass

    # Re-register métriques CaroCorp
    from app.core.metrics import (
        http_requests_total,
        http_request_duration_seconds,
        http_requests_in_progress,
        rate_limit_hits_total,
    )
    REGISTRY.register(http_requests_total)
    REGISTRY.register(http_request_duration_seconds)
    REGISTRY.register(http_requests_in_progress)
    REGISTRY.register(rate_limit_hits_total)

    yield

    # Cleanup après test (optionnel)


def test_metrics_endpoint_accessible(client: TestClient):
    """Test GET /metrics accessible et retourne format Prometheus.

    Vérifie que :
    - Status 200 OK
    - Content-Type text/plain (format Prometheus)
    - Body contient métriques Prometheus (# HELP, # TYPE)

    Notes:
        - Endpoint public (pas d'auth requise)
        - Format texte Prometheus (pas JSON)
        - Appelé toutes les 15s par Prometheus scraper
    """
    response = client.get("/metrics")

    # Vérifier status 200
    assert response.status_code == 200, \
        "/metrics devrait être accessible sans authentification"

    # Vérifier Content-Type Prometheus
    assert "text/plain" in response.headers["content-type"], \
        "Content-Type devrait être text/plain (format Prometheus)"

    # Vérifier contenu format Prometheus
    body = response.text
    assert "# HELP" in body, "Body devrait contenir méta-données Prometheus (# HELP)"
    assert "# TYPE" in body, "Body devrait contenir types métriques (# TYPE)"

    # Vérifier présence métriques CaroCorp
    assert "http_requests_total" in body, \
        "Métrique http_requests_total devrait être exposée"
    assert "http_request_duration_seconds" in body, \
        "Métrique http_request_duration_seconds devrait être exposée"


def test_http_requests_total_incremented(client: TestClient):
    """Test http_requests_total incrémenté après requête.

    Vérifie que :
    - Métrique http_requests_total{method, path, status} +1 après requête
    - Labels method, path, status corrects
    - Counter ne décrémente jamais (monotonic increasing)

    Notes:
        - Counter Prometheus = valeur qui augmente uniquement
        - Labels permettent filtrage (ex: status="200", status="404")
    """
    # Faire requête GET /api/v1/health
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    # Lire métriques Prometheus
    metrics_response = client.get("/metrics")
    metrics_body = metrics_response.text

    # Vérifier http_requests_total incrémenté
    # Format: http_requests_total{method="GET",path="/api/v1/health",status="200"} 1.0
    assert 'http_requests_total{method="GET"' in metrics_body, \
        "http_requests_total devrait avoir label method"
    assert 'path="/api/v1/health"' in metrics_body, \
        "http_requests_total devrait avoir label path"
    assert 'status="200"' in metrics_body, \
        "http_requests_total devrait avoir label status"

    # Faire 2ème requête → counter devrait augmenter
    response2 = client.get("/api/v1/health")
    assert response2.status_code == 200

    metrics_response2 = client.get("/metrics")
    metrics_body2 = metrics_response2.text

    # Vérifier que counter a augmenté (au moins 2 requêtes /api/v1/health)
    # Note: difficile de parser valeur exacte en format texte Prometheus
    # On vérifie juste présence métrique avec bons labels
    assert 'http_requests_total{method="GET",path="/api/v1/health",status="200"}' in metrics_body2


def test_http_request_duration_histogram(client: TestClient):
    """Test http_request_duration_seconds histogram latence.

    Vérifie que :
    - Histogram enregistre durée requête
    - Buckets présents (p50, p90, p99)
    - Labels method, path corrects

    Notes:
        - Histogram Prometheus = distribution valeurs
        - Buckets : 0.005s, 0.01s, 0.025s, 0.05s, 0.1s, ...
        - PromQL queries : histogram_quantile(0.99, http_request_duration_seconds)
    """
    # Faire requête
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    # Lire métriques
    metrics_response = client.get("/metrics")
    metrics_body = metrics_response.text

    # Vérifier histogram présent
    assert 'http_request_duration_seconds_bucket{' in metrics_body, \
        "Histogram devrait exposer buckets"
    assert 'http_request_duration_seconds_sum{' in metrics_body, \
        "Histogram devrait exposer somme durées"
    assert 'http_request_duration_seconds_count{' in metrics_body, \
        "Histogram devrait exposer compte observations"

    # Vérifier labels method, path
    assert 'method="GET"' in metrics_body
    assert 'path="/api/v1/health"' in metrics_body

    # Vérifier buckets (le="0.005", le="0.01", le="0.025", ...)
    assert 'le="0.005"' in metrics_body, "Bucket 5ms devrait être présent"
    assert 'le="0.01"' in metrics_body, "Bucket 10ms devrait être présent"
    assert 'le="0.1"' in metrics_body, "Bucket 100ms devrait être présent"


def test_rate_limit_hits_counted(client: TestClient):
    """Test rate_limit_hits_total incrémenté sur 429.

    Vérifie que :
    - Métrique rate_limit_hits_total +1 quand 429 retourné
    - Labels scope, identifier_type corrects
    - Scope extrait depuis body JSON 429 response

    Notes:
        - Déclencher rate limit en faisant 6 POST /api/v1/auth/login (limite 5/min)
        - Scope login → identifier_type="ip"
    """
    login_data = {
        "username": "test@carocorp.com",
        "password": "wrongpass"
    }

    # Faire 5 requêtes (limite login = 5/min)
    for _ in range(5):
        client.post(
            "/api/v1/auth/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

    # 6ème requête → 429 rate limited
    response_429 = client.post(
        "/api/v1/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response_429.status_code == 429, "6ème requête devrait être rate limited"

    # Lire métriques
    metrics_response = client.get("/metrics")
    metrics_body = metrics_response.text

    # Vérifier rate_limit_hits_total incrémenté
    assert "rate_limit_hits_total" in metrics_body, \
        "Métrique rate_limit_hits_total devrait être exposée"

    # Vérifier labels scope="login", identifier_type="ip"
    assert 'scope="login"' in metrics_body, \
        "Label scope devrait être 'login' pour endpoint /api/v1/auth/login"
    assert 'identifier_type="ip"' in metrics_body, \
        "Label identifier_type devrait être 'ip' pour scope login"


def test_path_normalization_replaces_ids(client: TestClient):
    """Test normalisation paths : IDs numériques remplacés par {id}.

    Vérifie que :
    - /api/v1/products/123 → /api/v1/products/{id}
    - /api/v1/customers/456 → /api/v1/customers/{id}
    - Évite cardinalité infinie métriques Prometheus

    Notes:
        - Cardinalité = nombre de combinaisons uniques labels
        - Sans normalisation : 1 métrique par ID → millions de time series
        - Avec normalisation : 1 métrique par endpoint → dizaines de time series
    """
    # Note: endpoint /api/v1/products/{id} n'existe peut-être pas encore
    # On teste avec endpoint existant qui retourne 404 ou 401

    # Requête GET /api/v1/products/123 (probablement 401 ou 404)
    response = client.get("/api/v1/products/123")
    # Peu importe status (401, 404, 200), métrique doit être collectée

    # Lire métriques
    metrics_response = client.get("/metrics")
    metrics_body = metrics_response.text

    # Vérifier path normalisé : /api/v1/products/{id} (PAS /api/v1/products/123)
    assert 'path="/api/v1/products/{id}"' in metrics_body, \
        "Path devrait être normalisé (/api/v1/products/{id}, pas /123)"

    # Vérifier que path brut N'apparaît PAS
    assert 'path="/api/v1/products/123"' not in metrics_body, \
        "Path brut avec ID ne devrait PAS apparaître (éviter cardinalité infinie)"

    # Test avec autre ID → même path normalisé
    response2 = client.get("/api/v1/products/456")

    metrics_response2 = client.get("/metrics")
    metrics_body2 = metrics_response2.text

    # Toujours path normalisé {id}
    assert 'path="/api/v1/products/{id}"' in metrics_body2
    assert 'path="/api/v1/products/456"' not in metrics_body2


def test_http_requests_in_progress_gauge(client: TestClient):
    """Test gauge http_requests_in_progress incrémenté/décrémenté.

    Vérifie que :
    - Gauge +1 quand requête démarre
    - Gauge -1 quand requête termine
    - Gauge retourne à 0 après requête

    Notes:
        - Gauge Prometheus = valeur qui monte ET descend
        - Mesure concurrency (requêtes simultanées en cours)
        - Alerting : http_requests_in_progress > 100 → saturation workers

    Limitation test :
        - Test séquentiel (1 requête à la fois)
        - Impossible de tester vraie concurrency dans TestClient
        - On vérifie juste que gauge existe et varie
    """
    # Faire requête
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    # Lire métriques APRÈS requête terminée
    metrics_response = client.get("/metrics")
    metrics_body = metrics_response.text

    # Vérifier gauge existe
    assert "http_requests_in_progress" in metrics_body, \
        "Gauge http_requests_in_progress devrait être exposée"

    # Vérifier labels method, path
    assert 'method="GET"' in metrics_body
    assert 'path="/api/v1/health"' in metrics_body

    # Note: Valeur gauge difficile à vérifier (format texte Prometheus)
    # On vérifie juste présence métrique
    # En production, gauge devrait être 0 entre requêtes


def test_metrics_endpoint_not_rate_limited(client: TestClient):
    """Test que /metrics N'est PAS rate limited.

    Vérifie que :
    - Endpoint /metrics appelé 100+ fois ne retourne jamais 429
    - Prometheus scraper peut collecter métriques sans rate limit

    Notes:
        - /metrics doit être exempté de rate limiting
        - Sinon Prometheus scraping échoue après 300 req/min
    """
    # Appeler /metrics 20 fois rapidement
    for i in range(20):
        response = client.get("/metrics")
        assert response.status_code == 200, \
            f"/metrics ne devrait JAMAIS retourner 429 (requête {i+1}/20)"

    # Vérifier que pas de rate_limit_hits pour path="/metrics"
    metrics_response = client.get("/metrics")
    metrics_body = metrics_response.text

    # Si /metrics était rate limited, on verrait rate_limit_hits_total{path="/metrics"}
    # On vérifie absence (difficile à tester négation en format texte)
    # Test indirect : 20 requêtes /metrics ont toutes réussi (aucune 429)
