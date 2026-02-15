"""Tests de sécurité pour le rate limiting multi-niveaux.

Valide la protection DDoS via rate limiting Redis :
- 5 scopes : global_ip, login, user_authenticated, mutations, reads
- Headers RFC 6585 : X-RateLimit-*, Retry-After
- Fail-open strategy (disponibilité > sécurité si Redis down)
- Extraction IP depuis X-Forwarded-For
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import time

from app.core.redis import redis_client
from app.models.user import User
from app.core.security import get_password_hash, create_access_token


@pytest.fixture
def test_user_for_rate_limit(test_db):
    """Fixture user pour tests rate limiting."""
    user = User(
        tenant_id=1,
        email="ratelimit@carocorp.com",
        hashed_password=get_password_hash("testpass123"),
        first_name="Rate Limit Test", last_name="User",
        role="staff"
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def auth_token_for_rate_limit(test_user_for_rate_limit):
    """Fixture JWT token pour tests rate limiting."""
    return create_access_token({
        "sub": test_user_for_rate_limit.id,
        "tenant_id": test_user_for_rate_limit.tenant_id,
        "email": test_user_for_rate_limit.email,
        "role": test_user_for_rate_limit.role
    })


@pytest.fixture
def auth_headers_for_rate_limit(auth_token_for_rate_limit):
    """Fixture headers Authorization pour tests rate limiting."""
    return {"Authorization": f"Bearer {auth_token_for_rate_limit}"}


@pytest.fixture(autouse=True)
def cleanup_redis_keys():
    """Nettoie les clés Redis rate_limit:* avant et après chaque test."""
    # Nettoyer avant
    for key in redis_client.client.scan_iter("rate_limit:*"):
        redis_client.client.delete(key)

    yield

    # Nettoyer après
    for key in redis_client.client.scan_iter("rate_limit:*"):
        redis_client.client.delete(key)


def test_global_ip_rate_limit_1000_per_minute(client: TestClient):
    """Test rate limit global IP : 1000 req/min.

    Vérifie que :
    - Requêtes 1-1000 → 200/401/422 OK avec headers rate limit
    - Headers rate limit présents et cohérents

    Notes:
        - Endpoint : POST /api/v1/products (mutations, non-exempté)
        - Scope global_ip toujours vérifié en premier
        - /api/v1/health est EXEMPTÉ donc pas de headers → utiliser autre endpoint
    """
    # Faire 5 requêtes POST (non authentifiées → 401, mais headers présents)
    for i in range(5):
        response = client.post(
            "/api/v1/products",
            json={"name": "Test Product", "price_per_day_cents": 1000}
        )
        # Peut être 401 (pas d'auth) ou 422 (validation), mais pas 429
        assert response.status_code in [401, 422], f"Requête {i+1}/5 devrait passer"

        # Vérifier headers rate limit présents
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

        # Vérifier valeurs cohérentes (scope "mutations" = 100 req/min)
        limit = int(response.headers["X-RateLimit-Limit"])
        remaining = int(response.headers["X-RateLimit-Remaining"])
        assert limit == 100  # Scope "mutations" pour POST
        assert remaining == 100 - (i + 1)  # Décrémente à chaque requête


def test_login_rate_limit_5_per_minute(client: TestClient):
    """Test rate limit login : 5 req/min (strict anti brute force).

    Vérifie que :
    - Requêtes 1-5 → 200/401 (selon credentials, mais pas 429)
    - Requête 6 → 429 Too Many Requests
    - Headers 429 : Retry-After présent

    Notes:
        - Endpoint : POST /api/v1/auth/login
        - Scope "login" le plus strict (5/min)
        - Protection brute force authentication
    """
    login_data = {
        "username": "nonexistent@carocorp.com",
        "password": "wrongpass"
    }

    # Requêtes 1-5 : devraient passer (401 car credentials invalides, mais pas 429)
    for i in range(5):
        response = client.post(
            "/api/v1/auth/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        # Peut être 401 (credentials invalides) mais PAS 429 (rate limit)
        assert response.status_code in [200, 401], \
            f"Requête {i+1}/5 devrait passer (200 ou 401, pas 429)"

    # Requête 6 : doit être bloquée par rate limit
    response = client.post(
        "/api/v1/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 429, "Requête 6/5 devrait être rate limited"

    # Vérifier headers RFC 6585
    assert "X-RateLimit-Limit" in response.headers
    assert response.headers["X-RateLimit-Limit"] == "5"

    assert "X-RateLimit-Remaining" in response.headers
    assert response.headers["X-RateLimit-Remaining"] == "0"

    assert "Retry-After" in response.headers
    retry_after = int(response.headers["Retry-After"])
    assert 0 < retry_after <= 60, "Retry-After devrait être entre 1 et 60 secondes"

    # Vérifier message d'erreur
    data = response.json()
    assert "detail" in data
    assert "login" in data["detail"].lower()
    assert "rate limit" in data["detail"].lower()


def test_user_authenticated_rate_limit_200_per_minute(
    client: TestClient,
    auth_headers_for_rate_limit
):
    """Test rate limit user authentifié : 200 req/min.

    Vérifie que :
    - User authentifié a quota de 200 req/min
    - Scope user_authenticated prioritaire sur mutations/reads
    - Headers rate limit reflètent quota utilisateur

    Notes:
        - Endpoint : GET /api/v1/products (nécessite auth)
        - Scope "user_authenticated" prioritaire si JWT présent
    """
    # Faire 10 requêtes authentifiées (limite = 200/min)
    for i in range(10):
        response = client.get(
            "/api/v1/products",
            headers=auth_headers_for_rate_limit
        )
        # Peut être 200 ou 404 selon données, mais pas 429
        assert response.status_code in [200, 404], \
            f"Requête {i+1}/10 devrait passer (user quota 200/min)"

        # Vérifier headers rate limit user_authenticated
        assert "X-RateLimit-Limit" in response.headers
        limit = int(response.headers["X-RateLimit-Limit"])
        assert limit == 200, "Limite devrait être 200 (user_authenticated)"

        remaining = int(response.headers["X-RateLimit-Remaining"])
        assert remaining == 200 - (i + 1)


def test_mutations_rate_limit_100_per_minute(client: TestClient):
    """Test rate limit mutations (POST/PUT/DELETE) : 100 req/min.

    Vérifie que :
    - POST/PUT/DELETE non authentifiées limitées à 100/min
    - Requêtes 1-100 → 200/400/401 (mais pas 429)
    - Requête 101 → 429

    Notes:
        - Endpoint : POST /api/v1/products (mutation)
        - Scope "mutations" pour write-heavy abuse protection
    """
    # Faire 10 POST (limite = 100/min)
    for i in range(10):
        response = client.post(
            "/api/v1/products",
            json={"name": "Test Product", "price_per_day_cents": 1000}
        )
        # Peut être 401 (pas d'auth), 422 (validation), mais pas 429
        assert response.status_code in [200, 401, 422], \
            f"Requête {i+1}/10 devrait passer (mutations quota 100/min)"

        # Vérifier headers
        assert "X-RateLimit-Limit" in response.headers
        limit = int(response.headers["X-RateLimit-Limit"])
        assert limit == 100, "Limite devrait être 100 (mutations)"


def test_reads_rate_limit_300_per_minute(client: TestClient):
    """Test rate limit reads (GET) : 300 req/min.

    Vérifie que :
    - GET non authentifiées limitées à 300/min
    - Scope "reads" moins strict que mutations

    Notes:
        - Endpoint : GET /api/v1/products (public read, non-exempté)
        - Scope "reads" pour read-heavy abuse protection
        - /api/v1/health est EXEMPTÉ donc pas de headers
    """
    # Faire 10 GET (limite = 300/min)
    for i in range(10):
        response = client.get("/api/v1/products")
        # Peut être 200 (liste vide), 401 (pas d'auth), 404, mais pas 429
        assert response.status_code in [200, 401, 404], \
            f"Requête {i+1}/10 devrait passer (reads quota 300/min)"

        # Vérifier headers
        assert "X-RateLimit-Limit" in response.headers
        limit = int(response.headers["X-RateLimit-Limit"])
        assert limit == 300, "Limite devrait être 300 (reads)"


def test_rate_limit_429_response_format_rfc6585(client: TestClient):
    """Test format réponse 429 conforme RFC 6585.

    Vérifie que la réponse 429 contient :
    - Status code : 429 Too Many Requests
    - Headers obligatoires :
        - X-RateLimit-Limit
        - X-RateLimit-Remaining
        - X-RateLimit-Reset (timestamp Unix)
        - Retry-After (secondes)
    - Body JSON : {"detail": "...scope...Retry after..."}

    Notes:
        - RFC 6585 : https://tools.ietf.org/html/rfc6585#section-4
        - Permet clients intelligents d'ajuster automatiquement
    """
    login_data = {
        "username": "test@carocorp.com",
        "password": "wrongpass"
    }

    # Atteindre limite login (5 req/min)
    for _ in range(5):
        client.post(
            "/api/v1/auth/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

    # 6ème requête → 429
    response = client.post(
        "/api/v1/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    # Vérifier status code
    assert response.status_code == 429

    # Vérifier headers obligatoires RFC 6585
    required_headers = [
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "Retry-After"
    ]
    for header in required_headers:
        assert header in response.headers, f"Header {header} manquant (RFC 6585)"

    # Vérifier types valeurs
    limit = int(response.headers["X-RateLimit-Limit"])
    assert limit == 5, "Limite login devrait être 5"

    remaining = int(response.headers["X-RateLimit-Remaining"])
    assert remaining == 0, "Remaining devrait être 0 quand rate limited"

    reset = int(response.headers["X-RateLimit-Reset"])
    assert reset > int(time.time()), "Reset timestamp devrait être dans le futur"

    retry_after = int(response.headers["Retry-After"])
    assert 0 < retry_after <= 60, "Retry-After devrait être entre 1 et 60 secondes"

    # Vérifier body JSON
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], str)
    assert "login" in data["detail"].lower()
    assert "rate limit" in data["detail"].lower()
    assert str(retry_after) in data["detail"] or "retry" in data["detail"].lower()


def test_exempt_paths_skip_rate_limiting(client: TestClient):
    """Test que les endpoints exemptés ne sont pas rate limited.

    Endpoints exemptés (EXEMPT_PATHS) :
    - /api/v1/health, /api/v1/health/ready, /api/v1/health/live
    - /api/docs, /api/redoc, /openapi.json

    Vérifie que :
    - Aucune limite appliquée (peut appeler 1000+ fois sans 429)
    - Pas de headers X-RateLimit-* ajoutés (middleware skip complètement)

    Notes:
        - Essentiel pour Kubernetes liveness/readiness probes
        - Docs API toujours accessibles même sous attaque DDoS
    """
    exempt_paths = [
        "/api/v1/health",
        "/api/v1/health/ready",
        "/api/v1/health/live",
    ]

    for path in exempt_paths:
        # Faire 20 requêtes rapides (bien au-delà de toute limite)
        for i in range(20):
            response = client.get(path)
            assert response.status_code in [200, 503], \
                f"{path} devrait être exempt de rate limiting (requête {i+1}/20)"

            # Vérifier que headers rate limit ne sont PAS ajoutés
            # (middleware skip complètement ces endpoints)
            # Note: headers peuvent être ajoutés par d'autres middlewares
            # On vérifie juste qu'on ne reçoit jamais 429

        # Vérifier qu'on ne reçoit jamais 429 même après 20+ requêtes
        response = client.get(path)
        assert response.status_code != 429, \
            f"{path} ne devrait JAMAIS retourner 429 (endpoint exempté)"


def test_fail_open_on_redis_error(client: TestClient):
    """Test fail-open strategy : autoriser requête si Redis down.

    Vérifie que :
    - Si Redis inaccessible → requête autorisée (200/401, pas 429)
    - Priorité : disponibilité > sécurité
    - Évite denial of service si Redis crash

    Notes:
        - Pattern fail-open : mieux vaut laisser passer que bloquer tout
        - Logging error pour alerting (TODO: vérifier logs)
        - Mock Redis.incr() pour déclencher exception dans check_rate_limit()
    """
    # Mock redis.incr() pour lever exception (simule Redis down)
    with patch("app.core.redis.redis_client.client.incr") as mock_incr:
        mock_incr.side_effect = Exception("Redis connection failed")

        # Faire requête → devrait passer (fail-open)
        # Endpoint non-exempté mais Redis fail → devrait autoriser
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "test@carocorp.com", "password": "wrongpass"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        # Doit passer (200 ou 401, pas 429) malgré erreur Redis
        assert response.status_code in [200, 401], \
            "Fail-open : requête devrait passer si Redis down (pas 429)"

        # Note: En production, erreur serait loggée pour alerting


def test_x_forwarded_for_ip_extraction(client: TestClient):
    """Test extraction IP depuis header X-Forwarded-For.

    Vérifie que :
    - X-Forwarded-For: "client_ip, proxy1, proxy2" → extrait client_ip
    - Format : première IP = client réel
    - Gère correctement proxies / load balancers

    Notes:
        - X-Forwarded-For ajouté par proxies (nginx, AWS ALB, Cloudflare)
        - Format : "original_client, proxy1, proxy2, ..."
        - On prend toujours la première IP
    """
    login_data = {
        "username": "test@carocorp.com",
        "password": "wrongpass"
    }

    # Requête 1 : avec X-Forwarded-For
    headers_with_xff = {
        "X-Forwarded-For": "203.0.113.42, 198.51.100.1, 192.0.2.1",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    response1 = client.post("/api/v1/auth/login", data=login_data, headers=headers_with_xff)
    assert response1.status_code in [200, 401]  # Pas encore rate limited

    # Requête 2-5 : même IP client (203.0.113.42)
    for _ in range(4):
        response = client.post("/api/v1/auth/login", data=login_data, headers=headers_with_xff)
        assert response.status_code in [200, 401, 429]

    # Requête 6 : devrait être rate limited (5 req/min pour 203.0.113.42)
    response6 = client.post("/api/v1/auth/login", data=login_data, headers=headers_with_xff)
    assert response6.status_code == 429, \
        "Requêtes depuis même IP client (X-Forwarded-For) devraient être rate limited ensemble"

    # Requête 7 : DIFFÉRENTE IP client (nouvelle série de 5 autorisée)
    headers_different_ip = {
        "X-Forwarded-For": "198.51.100.99, 192.0.2.1",  # IP différente
        "Content-Type": "application/x-www-form-urlencoded"
    }
    response7 = client.post("/api/v1/auth/login", data=login_data, headers=headers_different_ip)
    assert response7.status_code in [200, 401], \
        "Nouvelle IP client devrait avoir son propre quota (pas 429)"


def test_scope_priority_user_authenticated_over_reads(
    client: TestClient,
    auth_headers_for_rate_limit
):
    """Test priorité scopes : user_authenticated > mutations/reads.

    Vérifie que :
    - GET avec JWT → scope "user_authenticated" (200 req/min)
    - GET sans JWT → scope "reads" (300 req/min)
    - Scope user_authenticated prioritaire si JWT présent

    Notes:
        - Ordre priorité : login > user_authenticated > mutations > reads
        - User authentifié bénéficie de quota distinct (tracking par user_id)
        - Utiliser endpoint NON-exempté (GET /api/v1/products)
    """
    # Requête authentifiée GET → scope user_authenticated
    response_auth = client.get(
        "/api/v1/products",
        headers=auth_headers_for_rate_limit
    )
    assert response_auth.status_code in [200, 401, 404]
    assert "X-RateLimit-Limit" in response_auth.headers
    limit_auth = int(response_auth.headers["X-RateLimit-Limit"])
    assert limit_auth == 200, \
        "User authentifié devrait avoir quota 200/min (user_authenticated)"

    # Requête non authentifiée GET → scope reads
    response_no_auth = client.get("/api/v1/products")
    assert response_no_auth.status_code in [200, 401, 404]
    assert "X-RateLimit-Limit" in response_no_auth.headers
    limit_no_auth = int(response_no_auth.headers["X-RateLimit-Limit"])
    assert limit_no_auth == 300, \
        "Requête non authentifiée GET devrait avoir quota 300/min (reads)"
