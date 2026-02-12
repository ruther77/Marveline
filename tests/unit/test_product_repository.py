"""Tests unitaires pour ProductRepository."""
import pytest
from app.repositories.product import ProductRepository
from app.models.product import Product
from app.constants import ProductCategory


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def test_product_assiette(test_db):
    """Fixture produit catégorie assiette."""
    product = Product(
        tenant_id=1,
        name="Assiette Blanche 27cm",
        sku="ASS-WHITE-27",
        category=ProductCategory.ASSIETTE,
        price_per_day=50,
        stock_quantity=100,
        available_quantity=80,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def test_product_verre(test_db):
    """Fixture produit catégorie verre."""
    product = Product(
        tenant_id=1,
        name="Verre à Vin 35cl",
        sku="VER-WINE-35",
        category=ProductCategory.VERRE,
        price_per_day=30,
        stock_quantity=200,
        available_quantity=150,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def test_product_unavailable(test_db):
    """Fixture produit indisponible (available_quantity = 0)."""
    product = Product(
        tenant_id=1,
        name="Assiette Rupture",
        sku="ASS-OUT-STOCK",
        category=ProductCategory.ASSIETTE,
        price_per_day=50,
        stock_quantity=50,
        available_quantity=0,  # Rupture de stock
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def test_product_inactive(test_db):
    """Fixture produit inactif (soft-deleted)."""
    product = Product(
        tenant_id=1,
        name="Assiette Obsolète",
        sku="ASS-OBSOLETE",
        category=ProductCategory.ASSIETTE,
        price_per_day=50,
        stock_quantity=20,
        available_quantity=20,
        is_active=False  # Soft-deleted
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


# ═══════════════════════════════════════════════════════════════════════════
# Tests list_by_category()
# ═══════════════════════════════════════════════════════════════════════════

def test_list_by_category_assiette(test_db, test_product_assiette, test_product_verre):
    """Liste les produits de catégorie 'assiette'."""
    repo = ProductRepository(test_db)

    results, total = repo.list_by_category("assiette", tenant_id=1)

    assert len(results) >= 1
    assert all(p.category == "assiette" for p in results)
    assert test_product_assiette.id in [p.id for p in results]
    assert test_product_verre.id not in [p.id for p in results]


def test_list_by_category_verre(test_db, test_product_assiette, test_product_verre):
    """Liste les produits de catégorie 'verre'."""
    repo = ProductRepository(test_db)

    results, total = repo.list_by_category("verre", tenant_id=1)

    assert len(results) >= 1
    assert all(p.category == "verre" for p in results)
    assert test_product_verre.id in [p.id for p in results]
    assert test_product_assiette.id not in [p.id for p in results]


def test_list_by_category_empty(test_db):
    """Catégorie sans produits retourne liste vide."""
    repo = ProductRepository(test_db)

    results, total = repo.list_by_category("mobilier", tenant_id=1)

    assert results == []
    assert total == 0


# ═══════════════════════════════════════════════════════════════════════════
# Tests list_available()
# ═══════════════════════════════════════════════════════════════════════════

def test_list_available_excludes_unavailable(
    test_db,
    test_product_assiette,
    test_product_unavailable
):
    """Liste disponible exclut les produits avec available_quantity = 0."""
    repo = ProductRepository(test_db)

    results = repo.list_available(tenant_id=1)

    assert test_product_assiette.id in [p.id for p in results]
    assert test_product_unavailable.id not in [p.id for p in results]


def test_list_available_excludes_inactive(
    test_db,
    test_product_assiette,
    test_product_inactive
):
    """Liste disponible exclut les produits soft-deleted."""
    repo = ProductRepository(test_db)

    results = repo.list_available(tenant_id=1)

    assert test_product_assiette.id in [p.id for p in results]
    assert test_product_inactive.id not in [p.id for p in results]


def test_list_available_with_category_filter(
    test_db,
    test_product_assiette,
    test_product_verre
):
    """Liste disponible avec filtre catégorie."""
    repo = ProductRepository(test_db)

    results = repo.list_available(tenant_id=1, category="assiette")

    assert all(p.category == "assiette" for p in results)
    assert all(p.available_quantity > 0 for p in results)
    assert test_product_assiette.id in [p.id for p in results]
    assert test_product_verre.id not in [p.id for p in results]


# ═══════════════════════════════════════════════════════════════════════════
# Tests check_availability()
# ═══════════════════════════════════════════════════════════════════════════

def test_check_availability_sufficient_stock(test_db, test_product_assiette):
    """Vérifie disponibilité avec stock suffisant."""
    repo = ProductRepository(test_db)

    # Product a available_quantity = 80
    assert repo.check_availability(test_product_assiette.id, 50, tenant_id=1) is True


def test_check_availability_insufficient_stock(test_db, test_product_assiette):
    """Vérifie disponibilité avec stock insuffisant."""
    repo = ProductRepository(test_db)

    # Product a available_quantity = 80
    assert repo.check_availability(test_product_assiette.id, 100, tenant_id=1) is False


def test_check_availability_exact_stock(test_db, test_product_assiette):
    """Vérifie disponibilité avec quantité exacte."""
    repo = ProductRepository(test_db)

    # Product a available_quantity = 80
    assert repo.check_availability(test_product_assiette.id, 80, tenant_id=1) is True


def test_check_availability_product_not_found(test_db):
    """Vérifie disponibilité pour produit inexistant retourne False."""
    repo = ProductRepository(test_db)

    assert repo.check_availability(9999, 10, tenant_id=1) is False


# ═══════════════════════════════════════════════════════════════════════════
# Tests reserve_stock()
# ═══════════════════════════════════════════════════════════════════════════

def test_reserve_stock_success(test_db, test_product_assiette):
    """Réserve du stock avec succès."""
    repo = ProductRepository(test_db)

    initial_available = test_product_assiette.available_quantity  # 80

    result = repo.reserve_stock(test_product_assiette.id, 20, tenant_id=1)

    assert result is True
    test_db.refresh(test_product_assiette)
    assert test_product_assiette.available_quantity == initial_available - 20


def test_reserve_stock_insufficient(test_db, test_product_assiette):
    """Réserve du stock échoue si stock insuffisant."""
    repo = ProductRepository(test_db)

    initial_available = test_product_assiette.available_quantity  # 80

    result = repo.reserve_stock(test_product_assiette.id, 100, tenant_id=1)

    assert result is False
    test_db.refresh(test_product_assiette)
    assert test_product_assiette.available_quantity == initial_available  # Inchangé


def test_reserve_stock_product_not_found(test_db):
    """Réserve du stock échoue si produit inexistant."""
    repo = ProductRepository(test_db)

    result = repo.reserve_stock(9999, 10, tenant_id=1)

    assert result is False


def test_reserve_stock_exact_quantity(test_db, test_product_assiette):
    """Réserve exactement la quantité disponible."""
    repo = ProductRepository(test_db)

    available = test_product_assiette.available_quantity  # 80

    result = repo.reserve_stock(test_product_assiette.id, available, tenant_id=1)

    assert result is True
    test_db.refresh(test_product_assiette)
    assert test_product_assiette.available_quantity == 0


# ═══════════════════════════════════════════════════════════════════════════
# Tests release_stock()
# ═══════════════════════════════════════════════════════════════════════════

def test_release_stock_success(test_db, test_product_assiette):
    """Libère du stock avec succès."""
    repo = ProductRepository(test_db)

    initial_available = test_product_assiette.available_quantity  # 80

    result = repo.release_stock(test_product_assiette.id, 10, tenant_id=1)

    assert result is True
    test_db.refresh(test_product_assiette)
    assert test_product_assiette.available_quantity == initial_available + 10


def test_release_stock_capped_at_stock_quantity(test_db, test_product_assiette):
    """Libère du stock mais plafonné à stock_quantity."""
    repo = ProductRepository(test_db)

    # Product : stock_quantity=100, available_quantity=80
    # Libérer 30 devrait donner 110, mais plafonné à 100

    result = repo.release_stock(test_product_assiette.id, 30, tenant_id=1)

    assert result is True
    test_db.refresh(test_product_assiette)
    assert test_product_assiette.available_quantity == 100  # Plafonné
    assert test_product_assiette.available_quantity == test_product_assiette.stock_quantity


def test_release_stock_product_not_found(test_db):
    """Libère du stock échoue si produit inexistant."""
    repo = ProductRepository(test_db)

    result = repo.release_stock(9999, 10, tenant_id=1)

    assert result is False


def test_release_stock_from_zero(test_db, test_product_unavailable):
    """Libère du stock depuis available_quantity = 0."""
    repo = ProductRepository(test_db)

    # Product : available_quantity = 0
    result = repo.release_stock(test_product_unavailable.id, 10, tenant_id=1)

    assert result is True
    test_db.refresh(test_product_unavailable)
    assert test_product_unavailable.available_quantity == 10


# ═══════════════════════════════════════════════════════════════════════════
# Tests search_by_name()
# ═══════════════════════════════════════════════════════════════════════════

def test_search_by_name_finds_by_name(test_db, test_product_assiette):
    """Recherche par nom du produit."""
    repo = ProductRepository(test_db)

    results = repo.search_by_name("Blanche", tenant_id=1)

    assert len(results) >= 1
    assert test_product_assiette.id in [p.id for p in results]


def test_search_by_name_finds_by_sku(test_db, test_product_assiette):
    """Recherche par SKU du produit."""
    repo = ProductRepository(test_db)

    results = repo.search_by_name("ASS-WHITE", tenant_id=1)

    assert len(results) >= 1
    assert test_product_assiette.id in [p.id for p in results]


def test_search_by_name_case_insensitive(test_db, test_product_assiette):
    """Recherche insensible à la casse."""
    repo = ProductRepository(test_db)

    results_lower = repo.search_by_name("blanche", tenant_id=1)
    results_upper = repo.search_by_name("BLANCHE", tenant_id=1)

    assert len(results_lower) >= 1
    assert len(results_upper) >= 1
    assert test_product_assiette.id in [p.id for p in results_lower]
    assert test_product_assiette.id in [p.id for p in results_upper]


# ═══════════════════════════════════════════════════════════════════════════
# Tests Multi-Tenant Isolation
# ═══════════════════════════════════════════════════════════════════════════

def test_list_by_category_cross_tenant_isolation(test_db, test_product_assiette):
    """Vérifie isolation multi-tenant dans list_by_category."""
    # Créer produit tenant=2
    product_tenant2 = Product(
        tenant_id=2,
        name="Assiette Tenant 2",
        sku="ASS-T2",
        category=ProductCategory.ASSIETTE,
        price_per_day=50,
        stock_quantity=50,
        available_quantity=50,
        is_active=True
    )
    test_db.add(product_tenant2)
    test_db.commit()

    repo = ProductRepository(test_db)

    # Liste tenant=1 ne doit PAS voir product_tenant2
    results, total = repo.list_by_category("assiette", tenant_id=1)

    assert all(p.tenant_id == 1 for p in results)
    assert product_tenant2.id not in [p.id for p in results]


def test_check_availability_cross_tenant(test_db, test_product_assiette):
    """Vérifie qu'on ne peut pas checker disponibilité d'un autre tenant."""
    repo = ProductRepository(test_db)

    # Product appartient à tenant=1
    # Tenter de checker avec tenant=2 → False (not found)
    result = repo.check_availability(test_product_assiette.id, 10, tenant_id=2)

    assert result is False
