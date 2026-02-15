"""Tests unitaires pour BaseRepository."""
import pytest
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.repositories.base import BaseRepository
from app.models.base import Base, TenantMixin, SoftDeleteMixin
from app.models.product import Product


# ═══════════════════════════════════════════════════════════════════════════
# Modèles de test (sans TenantMixin pour tester edge cases)
# ═══════════════════════════════════════════════════════════════════════════

class SimpleModel(Base):
    """Modèle simple sans TenantMixin ni SoftDeleteMixin."""
    __tablename__ = "test_simple_models"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def test_product_for_base(test_db):
    """Fixture produit pour tests BaseRepository."""
    product = Product(
        tenant_id=1,
        name="Product Base Test",
        sku="PROD-BASE-001",
        category="assiettes",
        price_per_day=100,
        stock_quantity=50,
        available_quantity=30,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def test_product_inactive(test_db):
    """Fixture produit soft-deleted."""
    product = Product(
        tenant_id=1,
        name="Product Inactive",
        sku="PROD-INACTIVE-001",
        category="verres",
        price_per_day=50,
        stock_quantity=20,
        available_quantity=0,
        is_active=False  # Soft-deleted
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


# ═══════════════════════════════════════════════════════════════════════════
# Tests filtres avec opérateurs de comparaison
# ═══════════════════════════════════════════════════════════════════════════

def test_list_filter_operator_gt(test_db, test_product_for_base):
    """Test filtre avec opérateur 'gt' (greater than)."""
    repo = BaseRepository(test_db, Product)

    # Créer produit avec price_per_day=200
    product_high_price = Product(
        tenant_id=1,
        name="Product High Price",
        sku="PROD-HIGH-001",
        category="assiettes",
        price_per_day=200,
        stock_quantity=10,
        available_quantity=10,
        is_active=True
    )
    test_db.add(product_high_price)
    test_db.commit()

    # Filtrer avec price_per_day__gt=150 (> 150)
    results, total = repo.list(
        tenant_id=1,
        filters={"price_per_day__gt": 150}
    )

    assert total >= 1
    assert product_high_price.id in [p.id for p in results]
    assert test_product_for_base.id not in [p.id for p in results]  # 100 < 150


def test_list_filter_operator_gte(test_db, test_product_for_base):
    """Test filtre avec opérateur 'gte' (greater than or equal)."""
    repo = BaseRepository(test_db, Product)

    # Filtrer avec price_per_day__gte=100 (>= 100)
    results, total = repo.list(
        tenant_id=1,
        filters={"price_per_day__gte": 100}
    )

    assert total >= 1
    assert test_product_for_base.id in [p.id for p in results]  # 100 >= 100


def test_list_filter_operator_lt(test_db, test_product_for_base):
    """Test filtre avec opérateur 'lt' (less than)."""
    repo = BaseRepository(test_db, Product)

    # Créer produit avec price_per_day=50
    product_low_price = Product(
        tenant_id=1,
        name="Product Low Price",
        sku="PROD-LOW-001",
        category="assiettes",
        price_per_day=50,
        stock_quantity=10,
        available_quantity=10,
        is_active=True
    )
    test_db.add(product_low_price)
    test_db.commit()

    # Filtrer avec price_per_day__lt=75 (< 75)
    results, total = repo.list(
        tenant_id=1,
        filters={"price_per_day__lt": 75}
    )

    assert total >= 1
    assert product_low_price.id in [p.id for p in results]  # 50 < 75
    assert test_product_for_base.id not in [p.id for p in results]  # 100 > 75


def test_list_filter_operator_lte(test_db, test_product_for_base):
    """Test filtre avec opérateur 'lte' (less than or equal)."""
    repo = BaseRepository(test_db, Product)

    # Filtrer avec price_per_day__lte=100 (<= 100)
    results, total = repo.list(
        tenant_id=1,
        filters={"price_per_day__lte": 100}
    )

    assert total >= 1
    assert test_product_for_base.id in [p.id for p in results]  # 100 <= 100


def test_list_filter_operator_ne(test_db, test_product_for_base):
    """Test filtre avec opérateur 'ne' (not equal)."""
    repo = BaseRepository(test_db, Product)

    # Créer produit avec price_per_day=200
    product_different = Product(
        tenant_id=1,
        name="Product Different",
        sku="PROD-DIFF-001",
        category="assiettes",
        price_per_day=200,
        stock_quantity=10,
        available_quantity=10,
        is_active=True
    )
    test_db.add(product_different)
    test_db.commit()

    # Filtrer avec price_per_day__ne=100 (!= 100)
    results, total = repo.list(
        tenant_id=1,
        filters={"price_per_day__ne": 100}
    )

    assert product_different.id in [p.id for p in results]  # 200 != 100
    assert test_product_for_base.id not in [p.id for p in results]  # 100 == 100


def test_list_filter_unknown_operator(test_db, test_product_for_base):
    """Test filtre avec opérateur inconnu (doit être ignoré)."""
    repo = BaseRepository(test_db, Product)

    # Filtrer avec opérateur inconnu "unknown"
    results, total = repo.list(
        tenant_id=1,
        filters={"price_per_day__unknown": 100}
    )

    # Opérateur inconnu ignoré, tous les produits retournés
    assert total >= 1


def test_list_filter_invalid_field(test_db, test_product_for_base):
    """Test filtre sur champ inexistant (doit être ignoré)."""
    repo = BaseRepository(test_db, Product)

    # Filtrer sur champ inexistant
    results, total = repo.list(
        tenant_id=1,
        filters={"nonexistent_field__gt": 100}
    )

    # Champ inexistant ignoré, tous les produits retournés
    assert total >= 1


# ═══════════════════════════════════════════════════════════════════════════
# Tests count() avec opérateurs
# ═══════════════════════════════════════════════════════════════════════════

def test_count_filter_operator_gt(test_db, test_product_for_base):
    """Test count avec opérateur 'gt'."""
    repo = BaseRepository(test_db, Product)

    # Créer produit avec price_per_day=200
    product_high_price = Product(
        tenant_id=1,
        name="Product High Count",
        sku="PROD-COUNT-001",
        category="assiettes",
        price_per_day=200,
        stock_quantity=10,
        available_quantity=10,
        is_active=True
    )
    test_db.add(product_high_price)
    test_db.commit()

    # Compter avec price_per_day__gt=150
    count = repo.count(
        tenant_id=1,
        filters={"price_per_day__gt": 150}
    )

    assert count >= 1


def test_count_filter_operator_lte(test_db, test_product_for_base):
    """Test count avec opérateur 'lte'."""
    repo = BaseRepository(test_db, Product)

    # Compter avec price_per_day__lte=100
    count = repo.count(
        tenant_id=1,
        filters={"price_per_day__lte": 100}
    )

    assert count >= 1


# ═══════════════════════════════════════════════════════════════════════════
# Tests hard_delete()
# ═══════════════════════════════════════════════════════════════════════════

def test_hard_delete_success(test_db, test_product_for_base):
    """Test suppression physique réussie."""
    repo = BaseRepository(test_db, Product)

    product_id = test_product_for_base.id

    # Supprimer physiquement
    result = repo.hard_delete(product_id, tenant_id=1)

    assert result is True

    # Vérifier que l'entité n'existe plus
    deleted_product = test_db.query(Product).filter(Product.id == product_id).first()
    assert deleted_product is None


def test_hard_delete_product_not_found(test_db):
    """Test hard_delete sur produit inexistant."""
    repo = BaseRepository(test_db, Product)

    result = repo.hard_delete(9999, tenant_id=1)

    assert result is False


def test_hard_delete_cross_tenant(test_db, test_product_for_base):
    """Test hard_delete cross-tenant échoue."""
    repo = BaseRepository(test_db, Product)

    # Tenter de supprimer avec mauvais tenant_id
    result = repo.hard_delete(test_product_for_base.id, tenant_id=2)

    assert result is False

    # Vérifier que l'entité existe toujours
    product = test_db.query(Product).filter(Product.id == test_product_for_base.id).first()
    assert product is not None


# ═══════════════════════════════════════════════════════════════════════════
# Tests exists()
# ═══════════════════════════════════════════════════════════════════════════

def test_exists_true(test_db, test_product_for_base):
    """Test exists retourne True pour entité existante."""
    repo = BaseRepository(test_db, Product)

    result = repo.exists(test_product_for_base.id, tenant_id=1)

    assert result is True


def test_exists_false(test_db):
    """Test exists retourne False pour entité inexistante."""
    repo = BaseRepository(test_db, Product)

    result = repo.exists(9999, tenant_id=1)

    assert result is False


def test_exists_cross_tenant(test_db, test_product_for_base):
    """Test exists cross-tenant retourne False."""
    repo = BaseRepository(test_db, Product)

    result = repo.exists(test_product_for_base.id, tenant_id=2)

    assert result is False


def test_exists_includes_inactive(test_db, test_product_inactive):
    """Test exists avec include_inactive=True trouve produits soft-deleted."""
    repo = BaseRepository(test_db, Product)

    # Sans include_inactive (défaut False)
    result_without = repo.exists(test_product_inactive.id, tenant_id=1, include_inactive=False)
    assert result_without is False

    # Avec include_inactive=True
    result_with = repo.exists(test_product_inactive.id, tenant_id=1, include_inactive=True)
    assert result_with is True


# ═══════════════════════════════════════════════════════════════════════════
# Tests restore()
# ═══════════════════════════════════════════════════════════════════════════

def test_restore_success(test_db, test_product_inactive):
    """Test restauration d'une entité soft-deleted."""
    repo = BaseRepository(test_db, Product)

    assert test_product_inactive.is_active is False

    # Restaurer
    result = repo.restore(test_product_inactive.id, tenant_id=1)

    assert result is True
    test_db.refresh(test_product_inactive)
    assert test_product_inactive.is_active is True


def test_restore_product_not_found(test_db):
    """Test restore sur produit inexistant."""
    repo = BaseRepository(test_db, Product)

    result = repo.restore(9999, tenant_id=1)

    assert result is False


def test_restore_already_active(test_db, test_product_for_base):
    """Test restore sur produit déjà actif échoue."""
    repo = BaseRepository(test_db, Product)

    assert test_product_for_base.is_active is True

    # Tenter de restaurer un produit déjà actif
    result = repo.restore(test_product_for_base.id, tenant_id=1)

    assert result is False  # Déjà actif, rien à restaurer


def test_restore_cross_tenant(test_db, test_product_inactive):
    """Test restore cross-tenant échoue."""
    repo = BaseRepository(test_db, Product)

    # Tenter de restaurer avec mauvais tenant_id
    result = repo.restore(test_product_inactive.id, tenant_id=2)

    assert result is False

    # Vérifier que le produit est toujours inactif
    test_db.refresh(test_product_inactive)
    assert test_product_inactive.is_active is False


# ═══════════════════════════════════════════════════════════════════════════
# Tests modèle sans TenantMixin
# ═══════════════════════════════════════════════════════════════════════════

def test_model_without_tenant_mixin(test_db):
    """Test BaseRepository avec modèle sans TenantMixin."""
    # Créer table pour SimpleModel
    SimpleModel.__table__.create(test_db.bind, checkfirst=True)

    try:
        repo = BaseRepository(test_db, SimpleModel)

        # Vérifier que _has_tenant_mixin() retourne False
        assert repo._has_tenant_mixin() is False

        # Créer entité (pas besoin de tenant_id)
        simple = SimpleModel(name="Test Simple", value=42)
        test_db.add(simple)
        test_db.commit()
        test_db.refresh(simple)

        # get_by_id sans tenant_id devrait fonctionner
        # Mais BaseRepository exige tenant_id, donc passer 0 ou None
        # La ligne 64 "return query" sera exécutée (pas de filtre tenant)
        result = repo.get_by_id(simple.id, tenant_id=0)

        assert result is not None
        assert result.name == "Test Simple"
    finally:
        # Nettoyer
        SimpleModel.__table__.drop(test_db.bind, checkfirst=True)
