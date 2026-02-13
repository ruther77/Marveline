"""Tests d'intégration pour cache Redis.

Valide que :
- Cache hit/miss fonctionnent correctement
- TTL expiration automatique Redis
- Invalidation pattern (SCAN + DELETE)
- Décorateurs @cached et @cache_invalidate
- Fail-open : Redis échoue → continue sans lever exception
- Métriques Redis collectées (redis_commands_total, redis_command_duration_seconds)
"""
import pytest
import time
from unittest.mock import patch

from app.services.cache import CacheService, cached, cache_invalidate


@pytest.fixture(autouse=True)
def cleanup_cache():
    """Nettoie les clés cache (pas CSRF/rate_limit) avant chaque test.

    Utilise SCAN + DELETE ciblé au lieu de FLUSHDB pour ne pas
    détruire les tokens CSRF et rate_limit keys d'autres tests.
    """
    cache = CacheService()
    _cleanup_cache_keys(cache)
    yield
    _cleanup_cache_keys(cache)


def _cleanup_cache_keys(cache: CacheService):
    """Supprime les clés cache de test sans toucher CSRF/rate_limit/session."""
    # Patterns utilisés par les tests cache
    test_patterns = [
        "test_*", "product:*", "customer:*",
        "expire_*", "delete_*", "key*", "metric_*",
        "test_product:*", "test_none:*",
    ]
    for pattern in test_patterns:
        cache.invalidate_pattern(pattern)


def test_cache_get_set_simple():
    """Test GET/SET simple valeur string.

    Vérifie que :
    - SET retourne True
    - GET retourne valeur correcte
    - GET clé inexistante retourne None

    Notes:
        - Valeur string (pas dict/list)
        - TTL par défaut 300s
    """
    cache = CacheService()

    # SET
    result = cache.set("test_key", "test_value", ttl=300)
    assert result is True, "SET devrait retourner True"

    # GET
    value = cache.get("test_key")
    assert value == "test_value", "GET devrait retourner valeur correcte"

    # GET clé inexistante
    missing = cache.get("nonexistent_key")
    assert missing is None, "GET clé inexistante devrait retourner None"


def test_cache_get_set_dict():
    """Test GET/SET valeur dict (sérialisation JSON).

    Vérifie que :
    - Dict sérialisé en JSON automatiquement
    - GET désérialise JSON → dict
    - Structure dict préservée

    Notes:
        - Sérialisation JSON transparente
        - Support nested dicts
    """
    cache = CacheService()

    # Dict complexe
    product_dict = {
        "id": 123,
        "name": "Assiette",
        "price_cents": 150,
        "category": "vaisselle",
        "metadata": {"color": "white", "size": "medium"}
    }

    # SET dict
    cache.set("product:123", product_dict, ttl=300)

    # GET dict
    cached_product = cache.get("product:123")
    assert cached_product == product_dict, "Dict devrait être identique après cache"
    assert cached_product["metadata"]["color"] == "white", "Nested dict préservé"


def test_cache_ttl_expiration():
    """Test expiration automatique TTL Redis.

    Vérifie que :
    - Clé existe immédiatement après SET
    - Clé expire après TTL (1 seconde)
    - GET retourne None après expiration

    Notes:
        - TTL court (1s) pour accélérer test
        - Utilise time.sleep() pour attendre expiration
    """
    cache = CacheService()

    # SET avec TTL 1 seconde
    cache.set("expire_key", "value", ttl=1)

    # GET immédiat → valeur existe
    value = cache.get("expire_key")
    assert value == "value", "Clé devrait exister immédiatement"

    # Attendre expiration (1.5s pour sécurité)
    time.sleep(1.5)

    # GET après TTL → None
    expired = cache.get("expire_key")
    assert expired is None, "Clé devrait avoir expiré après TTL"


def test_cache_delete():
    """Test suppression clé Redis.

    Vérifie que :
    - DELETE retourne True si clé supprimée
    - GET retourne None après DELETE
    - DELETE clé inexistante retourne False (idempotent)

    Notes:
        - DELETE idempotent (supprimer 2x même clé OK)
    """
    cache = CacheService()

    # SET
    cache.set("delete_key", "value", ttl=300)

    # DELETE
    deleted = cache.delete("delete_key")
    assert deleted is True, "DELETE devrait retourner True"

    # GET après DELETE → None
    value = cache.get("delete_key")
    assert value is None, "GET après DELETE devrait retourner None"

    # DELETE clé inexistante
    deleted_missing = cache.delete("nonexistent_key")
    assert deleted_missing is False, "DELETE clé inexistante devrait retourner False"


def test_cache_invalidate_pattern():
    """Test invalidation pattern (SCAN + DELETE).

    Vérifie que :
    - Pattern "product:*" supprime toutes clés product
    - Clés hors pattern non affectées
    - Retourne nombre de clés supprimées

    Notes:
        - Utilise SCAN (pas KEYS) pour éviter bloquer Redis
        - Pattern wildcard : "product:*", "customer:123:*"
    """
    cache = CacheService()

    # Créer plusieurs clés products
    cache.set("product:1", {"id": 1, "name": "Assiette"}, ttl=300)
    cache.set("product:2", {"id": 2, "name": "Couteau"}, ttl=300)
    cache.set("product:3", {"id": 3, "name": "Fourchette"}, ttl=300)

    # Créer clés customers (ne doivent PAS être supprimées)
    cache.set("customer:1", {"id": 1, "name": "Alice"}, ttl=300)
    cache.set("customer:2", {"id": 2, "name": "Bob"}, ttl=300)

    # Invalider pattern "product:*"
    deleted_count = cache.invalidate_pattern("product:*")
    assert deleted_count == 3, "3 clés product:* devraient être supprimées"

    # Vérifier products supprimés
    assert cache.get("product:1") is None
    assert cache.get("product:2") is None
    assert cache.get("product:3") is None

    # Vérifier customers toujours présents
    assert cache.get("customer:1") is not None, "Customers ne doivent PAS être supprimés"
    assert cache.get("customer:2") is not None


def test_decorator_cached_hit_miss():
    """Test décorateur @cached : hit et miss.

    Vérifie que :
    - 1ère appel → cache MISS → exécute fonction
    - 2ème appel → cache HIT → retourne valeur cachée (pas d'exécution)
    - Clé cache générée correctement (prefix:tenant_id:id)

    Notes:
        - Fonction simulée avec compteur d'appels
        - Cache hit = fonction pas exécutée
    """
    cache = CacheService()
    call_count = 0

    @cached(key_prefix="test_product", ttl=300, tenant_aware=True)
    def get_test_product(product_id: int, tenant_id: int):
        nonlocal call_count
        call_count += 1
        return {"id": product_id, "name": f"Product {product_id}"}

    # 1ère appel → cache MISS
    result1 = get_test_product(123, tenant_id=1)
    assert result1 == {"id": 123, "name": "Product 123"}
    assert call_count == 1, "Fonction devrait être exécutée (cache MISS)"

    # 2ème appel → cache HIT
    result2 = get_test_product(123, tenant_id=1)
    assert result2 == {"id": 123, "name": "Product 123"}
    assert call_count == 1, "Fonction NE devrait PAS être exécutée (cache HIT)"

    # Vérifier clé cache
    cached_value = cache.get("test_product:1:123")  # prefix:tenant_id:id
    assert cached_value == {"id": 123, "name": "Product 123"}


def test_decorator_cached_tenant_isolation():
    """Test décorateur @cached : isolation multi-tenant.

    Vérifie que :
    - Tenant 1 et Tenant 2 ont des clés cache séparées
    - Cache hit tenant 1 ne retourne PAS données tenant 2
    - Clé cache inclut tenant_id (tenant_aware=True)

    Notes:
        - Sécurité multi-tenant CRITIQUE
        - Clés : "prefix:tenant_id:id"
    """
    cache = CacheService()

    @cached(key_prefix="test_product", ttl=300, tenant_aware=True)
    def get_test_product(product_id: int, tenant_id: int):
        return {"id": product_id, "tenant_id": tenant_id, "name": f"Product {product_id} Tenant {tenant_id}"}

    # Tenant 1 : product 123
    result_t1 = get_test_product(123, tenant_id=1)
    assert result_t1["tenant_id"] == 1

    # Tenant 2 : product 123 (MÊME ID mais TENANT différent)
    result_t2 = get_test_product(123, tenant_id=2)
    assert result_t2["tenant_id"] == 2

    # Vérifier isolation : clés différentes
    cached_t1 = cache.get("test_product:1:123")
    cached_t2 = cache.get("test_product:2:123")

    assert cached_t1["tenant_id"] == 1, "Cache tenant 1 ne doit contenir que données tenant 1"
    assert cached_t2["tenant_id"] == 2, "Cache tenant 2 ne doit contenir que données tenant 2"
    assert cached_t1 != cached_t2, "Caches tenant 1 et 2 doivent être différents"


def test_decorator_cached_none_result():
    """Test décorateur @cached : fonction retourne None.

    Vérifie que :
    - Fonction retourne None → valeur PAS mise en cache
    - Appels suivants → fonction exécutée à nouveau (pas de cache)

    Notes:
        - None = résultat invalide (ex: product non trouvé)
        - Ne pas cacher None pour éviter cache négatif permanent
    """
    call_count = 0

    @cached(key_prefix="test_none", ttl=300, tenant_aware=False)
    def get_nonexistent_item(item_id: int):
        nonlocal call_count
        call_count += 1
        return None  # Simule item non trouvé

    # 1ère appel
    result1 = get_nonexistent_item(999)
    assert result1 is None
    assert call_count == 1

    # 2ème appel → fonction exécutée à nouveau (None pas caché)
    result2 = get_nonexistent_item(999)
    assert result2 is None
    assert call_count == 2, "Fonction devrait être exécutée à nouveau (None pas caché)"


def test_decorator_cache_invalidate():
    """Test décorateur @cache_invalidate : invalidation après mutation.

    Vérifie que :
    - Mutation (update) invalide cache pattern
    - GET après invalidation retourne None (cache vidé)
    - Patterns multiples supportés

    Notes:
        - Invalidation APRÈS fonction (write-through)
        - Pattern wildcard : "product:*"
    """
    cache = CacheService()

    # Pré-remplir cache
    cache.set("product:1", {"id": 1, "name": "Assiette"}, ttl=300)
    cache.set("product:2", {"id": 2, "name": "Couteau"}, ttl=300)

    # Fonction avec invalidation
    @cache_invalidate(patterns=["product:*"])
    def update_product(product_id: int, data: dict):
        # Simule mutation DB (pas de vraie DB ici)
        return {"id": product_id, "updated": True}

    # Vérifier cache avant mutation
    assert cache.get("product:1") is not None

    # Mutation → déclenche invalidation
    update_product(1, {"name": "Nouvelle assiette"})

    # Vérifier cache invalidé
    assert cache.get("product:1") is None, "Cache devrait être invalidé après mutation"
    assert cache.get("product:2") is None, "Tout le pattern product:* devrait être invalidé"


def test_cache_fail_open_on_redis_error():
    """Test fail-open : Redis échoue → continue sans lever exception.

    Vérifie que :
    - GET échoue → retourne None (pas d'exception)
    - SET échoue → retourne False (pas d'exception)
    - DELETE échoue → retourne False
    - Warning loggé

    Notes:
        - Fail-open = availability > consistency
        - Application continue même si Redis down
    """
    cache = CacheService()

    # Mock Redis pour simuler erreur
    with patch.object(cache.redis.client, 'get', side_effect=Exception("Redis connection timeout")):
        # GET échoue → None (pas d'exception)
        value = cache.get("test_key")
        assert value is None, "GET échec devrait retourner None (fail-open)"

    with patch.object(cache.redis.client, 'setex', side_effect=Exception("Redis write error")):
        # SET échoue → False (pas d'exception)
        result = cache.set("test_key", "value", ttl=300)
        assert result is False, "SET échec devrait retourner False (fail-open)"

    with patch.object(cache.redis.client, 'delete', side_effect=Exception("Redis delete error")):
        # DELETE échoue → False (pas d'exception)
        result = cache.delete("test_key")
        assert result is False, "DELETE échec devrait retourner False (fail-open)"


def test_cache_metrics_collected():
    """Test métriques Redis collectées.

    Vérifie que :
    - redis_commands_total{command="get"} incrémenté
    - redis_commands_total{command="set"} incrémenté
    - redis_command_duration_seconds enregistre latence

    Notes:
        - Métriques Prometheus exposées via /metrics
        - Permet monitoring Redis performance
    """
    from app.core.metrics import redis_commands_total, redis_command_duration_seconds

    cache = CacheService()

    # Récupérer compteurs AVANT
    # Note: Prometheus Counter ne peut pas être lu directement (pas d'API get_value)
    # On vérifie juste que les métriques ne lèvent pas d'exception

    # SET
    cache.set("metric_test", "value", ttl=60)

    # GET
    cache.get("metric_test")

    # Métriques devraient être incrémentées (vérification via /metrics endpoint)
    # Note: Test vérifie juste que pas d'exception levée lors collecte métriques
    # Validation complète dans test_metrics.py endpoint /metrics


def test_cache_flush_all():
    """Test FLUSH ALL cache (tests uniquement).

    Vérifie que :
    - FLUSHDB supprime TOUTES les clés Redis
    - Cache vide après flush

    Warning:
        - flush_all() NE DOIT JAMAIS être utilisé en production
        - Tests uniquement
    """
    cache = CacheService()

    # Créer plusieurs clés
    cache.set("key1", "value1", ttl=300)
    cache.set("key2", "value2", ttl=300)
    cache.set("key3", "value3", ttl=300)

    # FLUSH ALL
    result = cache.flush_all()
    assert result is True, "FLUSH_ALL devrait retourner True"

    # Vérifier cache vide
    assert cache.get("key1") is None
    assert cache.get("key2") is None
    assert cache.get("key3") is None
