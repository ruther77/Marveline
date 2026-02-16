"""Tests d'intégration pour le cache Redis dans BaseRepository.

Valide :
- Cache HIT/MISS sur get_by_id()
- Sérialisation ORM ↔ dict (to_dict, from_dict)
- Invalidation cache sur update/delete
- Isolation multi-tenant du cache
"""
import pytest
from app.models.product import Product
from app.repositories.product import ProductRepository
from app.core.cache import cache_service


@pytest.fixture(autouse=True)
def clear_cache():
    """Nettoie le cache Redis avant chaque test."""
    cache_service.flush_all()
    yield
    cache_service.flush_all()


def test_repository_get_by_id_cache_miss_then_hit(test_db, test_tenant):
    """Test cache MISS puis cache HIT sur get_by_id()."""
    repo = ProductRepository(test_db)

    # Créer un produit
    product = Product(
        tenant_id=test_tenant.id,
        name="Assiette Cache Test",
        sku="CACHE-001",
        category="assiettes",
        price_per_day=250,
        available_quantity=10,
        stock_quantity=10,
        is_active=True
    )
    repo.create(product)
    test_db.commit()

    # Premier appel → cache MISS (query DB)
    result1 = repo.get_by_id(product.id, test_tenant.id)
    assert result1 is not None
    assert result1.name == "Assiette Cache Test"
    assert result1.sku == "CACHE-001"

    # Vérifier que le cache est maintenant rempli
    cache_key = f"product:{test_tenant.id}:{product.id}"
    cached_data = cache_service.get(cache_key)
    assert cached_data is not None

    # Deuxième appel → cache HIT (pas de query DB)
    result2 = repo.get_by_id(product.id, test_tenant.id)
    assert result2 is not None
    assert result2.name == "Assiette Cache Test"
    assert result2.id == product.id


def test_repository_cache_invalidation_on_update(test_db, test_tenant):
    """Test invalidation cache après update()."""
    repo = ProductRepository(test_db)

    # Créer produit
    product = Product(
        tenant_id=test_tenant.id,
        name="Produit Original",
        sku="UPDATE-001",
        category="verres",
        price_per_day=100,
        available_quantity=5,
        stock_quantity=5,
        is_active=True
    )
    repo.create(product)
    test_db.commit()

    # Cache le produit
    result1 = repo.get_by_id(product.id, test_tenant.id)
    assert result1.name == "Produit Original"

    # Vérifier cache rempli
    cache_key = f"product:{test_tenant.id}:{product.id}"
    assert cache_service.get(cache_key) is not None

    # Modifier le produit
    product.name = "Produit Modifié"
    repo.update(product)
    test_db.commit()

    # Cache doit être invalidé
    assert cache_service.get(cache_key) is None

    # Prochain get_by_id re-cache la nouvelle version
    result2 = repo.get_by_id(product.id, test_tenant.id)
    assert result2.name == "Produit Modifié"
    assert cache_service.get(cache_key) is not None


def test_repository_cache_invalidation_on_soft_delete(test_db, test_tenant):
    """Test invalidation cache après soft_delete()."""
    repo = ProductRepository(test_db)

    # Créer produit
    product = Product(
        tenant_id=test_tenant.id,
        name="Produit à Supprimer",
        sku="DELETE-001",
        category="couverts",
        price_per_day=150,
        available_quantity=3,
        stock_quantity=3,
        is_active=True
    )
    repo.create(product)
    test_db.commit()

    # Cache le produit
    repo.get_by_id(product.id, test_tenant.id)
    cache_key = f"product:{test_tenant.id}:{product.id}"
    assert cache_service.get(cache_key) is not None

    # Soft delete
    success = repo.soft_delete(product.id, test_tenant.id)
    assert success is True
    test_db.commit()

    # Cache doit être invalidé
    assert cache_service.get(cache_key) is None


def test_repository_cache_multi_tenant_isolation(test_db, test_tenant, test_tenant2):
    """Test isolation cache entre tenants différents."""
    repo = ProductRepository(test_db)

    # Créer produit pour tenant1
    product1 = Product(
        tenant_id=test_tenant.id,
        name="Produit Tenant 1",
        sku="TENANT1-001",
        category="nappes",
        price_per_day=200,
        available_quantity=8,
        stock_quantity=8,
        is_active=True
    )
    repo.create(product1)
    test_db.commit()

    # Créer produit pour tenant2 (même ID possible)
    product2 = Product(
        tenant_id=test_tenant2.id,
        name="Produit Tenant 2",
        sku="TENANT2-001",
        category="decorations",
        price_per_day=300,
        available_quantity=6,
        stock_quantity=6,
        is_active=True
    )
    repo.create(product2)
    test_db.commit()

    # Cache les deux produits
    result1 = repo.get_by_id(product1.id, test_tenant.id)
    result2 = repo.get_by_id(product2.id, test_tenant2.id)

    # Vérifier clés cache différentes (isolation tenant_id)
    cache_key1 = f"product:{test_tenant.id}:{product1.id}"
    cache_key2 = f"product:{test_tenant2.id}:{product2.id}"

    cached1 = cache_service.get(cache_key1)
    cached2 = cache_service.get(cache_key2)

    assert cached1 is not None
    assert cached2 is not None
    assert cached1["name"] == "Produit Tenant 1"
    assert cached2["name"] == "Produit Tenant 2"

    # Tentative cross-tenant access → None (pas de cache leak)
    result_cross = repo.get_by_id(product1.id, test_tenant2.id)
    assert result_cross is None


def test_repository_serialization_datetime(test_db, test_tenant):
    """Test sérialisation/désérialisation datetime via cache."""
    repo = ProductRepository(test_db)

    # Créer produit
    product = Product(
        tenant_id=test_tenant.id,
        name="Produit Datetime Test",
        sku="DATETIME-001",
        category="mobilier",
        price_per_day=120,
        available_quantity=4,
        stock_quantity=4,
        is_active=True
    )
    repo.create(product)
    test_db.commit()

    # Cache le produit (sérialise datetime → ISO string)
    result1 = repo.get_by_id(product.id, test_tenant.id)
    created_at_original = result1.created_at

    # Vérifier cache contient ISO string
    cache_key = f"product:{test_tenant.id}:{product.id}"
    cached_data = cache_service.get(cache_key)
    assert isinstance(cached_data["created_at"], str)  # ISO format

    # Récupérer depuis cache (désérialise ISO string → datetime)
    cache_service.flush_all()  # Vider pour forcer re-query
    result2 = repo.get_by_id(product.id, test_tenant.id)  # Cache MISS + re-cache

    # Maintenant récupérer depuis cache
    result3 = repo.get_by_id(product.id, test_tenant.id)  # Cache HIT

    # Datetime doit être reconstitué correctement
    assert result3.created_at is not None
    assert result3.created_at.isoformat() == created_at_original.isoformat()


def test_repository_cache_respects_include_inactive(test_db, test_tenant):
    """Test que le cache respecte le filtre include_inactive.

    Note: Test simplifié pour compatibilité avec SAVEPOINTs nested.
    """
    repo = ProductRepository(test_db)

    # Créer produit actif
    product_active = Product(
        tenant_id=test_tenant.id,
        name="Produit Actif",
        sku="ACTIVE-001",
        category="assiettes",
        price_per_day=180,
        available_quantity=2,
        stock_quantity=2,
        is_active=True
    )
    repo.create(product_active)

    # Créer produit inactif DIRECTEMENT (sans soft_delete pour éviter problème SAVEPOINT)
    product_inactive = Product(
        tenant_id=test_tenant.id,
        name="Produit Inactif",
        sku="INACTIVE-001",
        category="verres",
        price_per_day=150,
        available_quantity=3,
        stock_quantity=3,
        is_active=False  # ← Créé directement inactif
    )
    repo.create(product_inactive)
    test_db.commit()

    # Test 1: Cache produit actif
    result1 = repo.get_by_id(product_active.id, test_tenant.id, include_inactive=False)
    assert result1 is not None
    assert result1.is_active is True

    cache_key_active = f"product:{test_tenant.id}:{product_active.id}"
    cached_active = cache_service.get(cache_key_active)
    assert cached_active is not None
    assert cached_active["is_active"] is True

    # Test 2: get_by_id avec include_inactive=False ne retourne PAS le produit inactif
    result2 = repo.get_by_id(product_inactive.id, test_tenant.id, include_inactive=False)
    assert result2 is None

    # Test 3: get_by_id avec include_inactive=True retourne le produit inactif
    result3 = repo.get_by_id(product_inactive.id, test_tenant.id, include_inactive=True)
    assert result3 is not None
    assert result3.is_active is False

    # Vérifier que le cache a été rempli avec le produit inactif
    cache_key_inactive = f"product:{test_tenant.id}:{product_inactive.id}"
    cached_inactive = cache_service.get(cache_key_inactive)
    assert cached_inactive is not None
    assert cached_inactive["is_active"] is False


def test_repository_cache_preserves_dirty_session_state(test_db, test_tenant):
    """Test que get_by_id() préserve l'état dirty de la session (identity map).

    Scénario du bug corrigé :
    1. get_by_id() charge un produit depuis DB → le cache dans Redis
    2. Le code modifie available_quantity en mémoire (dirty state)
    3. get_by_id() est rappelé → cache HIT → merge() écrasait le dirty state
    Après fix : get_by_id() détecte l'instance dans l'identity map et la retourne
    directement, préservant les modifications non flush.
    """
    repo = ProductRepository(test_db)

    # Créer un produit avec stock=20
    product = Product(
        tenant_id=test_tenant.id,
        name="Produit Identity Map",
        sku="IDENTITY-MAP-001",
        category="assiettes",
        price_per_day=250,
        available_quantity=20,
        stock_quantity=20,
        is_active=True
    )
    repo.create(product)
    test_db.commit()

    # 1. Premier get_by_id → cache MISS, charge depuis DB, remplit le cache
    result1 = repo.get_by_id(product.id, test_tenant.id)
    assert result1 is not None
    assert result1.available_quantity == 20

    # Vérifier que le cache Redis contient available_quantity=20
    cache_key = f"product:{test_tenant.id}:{product.id}"
    cached = cache_service.get(cache_key)
    assert cached is not None
    assert cached["available_quantity"] == 20

    # 2. Modifier available_quantity en mémoire (dirty state, pas encore flush)
    result1.available_quantity = 12  # Simule une réservation de 8 unités

    # 3. get_by_id à nouveau → cache HIT
    # AVANT FIX : merge() écrasait available_quantity=12 avec 20 (stale cache)
    # APRÈS FIX : identity map détecte l'instance, retourne directement
    result2 = repo.get_by_id(product.id, test_tenant.id)

    # L'instance retournée doit avoir le dirty state préservé
    assert result2 is result1  # Même objet Python (identity map)
    assert result2.available_quantity == 12  # Dirty state préservé, pas écrasé

    # 4. Flush + commit pour persister
    test_db.flush()
    test_db.commit()
    test_db.refresh(product)
    assert product.available_quantity == 12
