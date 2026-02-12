"""Tests unitaires des repositories (isolation complète)."""
import pytest
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository
from app.repositories.product import ProductRepository
from app.repositories.customer import CustomerRepository
from app.repositories.reservation import ReservationRepository
from app.repositories.invoice import InvoiceRepository
from app.models.product import Product
from app.models.customer import Customer
from app.models.reservation import Reservation, ReservationLine
from app.models.invoice import Invoice
from app.constants import CustomerType, ProductCategory, ProductCondition


# ═══════════════════════════════════════════════════════════════════════════
# Tests BaseRepository[T]
# ═══════════════════════════════════════════════════════════════════════════

def test_base_repository_get_by_id_success(test_db):
    """Test get_by_id retourne entité du bon tenant."""
    product = Product(
        tenant_id=1,
        name="Test Product",
        sku="TEST-SKU-001",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)

    repo = BaseRepository(test_db, Product)
    result = repo.get_by_id(product.id, tenant_id=1)

    assert result is not None
    assert result.id == product.id
    assert result.tenant_id == 1


def test_base_repository_get_by_id_wrong_tenant(test_db):
    """Test get_by_id retourne None pour mauvais tenant."""
    product = Product(
        tenant_id=1,
        name="Test Product",
        sku="TEST-SKU-002",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()

    repo = BaseRepository(test_db, Product)
    # Tenter d'accéder avec tenant_id=2 (pas 1)
    result = repo.get_by_id(product.id, tenant_id=2)

    assert result is None  # Filtré par tenant_id


def test_base_repository_get_by_id_inactive_excluded(test_db):
    """Test get_by_id exclut entités inactives par défaut."""
    product = Product(
        tenant_id=1,
        name="Inactive Product",
        sku="TEST-SKU-003",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=False  # Inactif
    )
    test_db.add(product)
    test_db.commit()

    repo = BaseRepository(test_db, Product)
    result = repo.get_by_id(product.id, tenant_id=1, include_inactive=False)

    assert result is None  # Exclu car inactive


def test_base_repository_get_by_id_inactive_included(test_db):
    """Test get_by_id inclut inactives si demandé."""
    product = Product(
        tenant_id=1,
        name="Inactive Product",
        sku="TEST-SKU-004",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=False
    )
    test_db.add(product)
    test_db.commit()

    repo = BaseRepository(test_db, Product)
    result = repo.get_by_id(product.id, tenant_id=1, include_inactive=True)

    assert result is not None
    assert result.is_active is False


def test_base_repository_list_pagination(test_db):
    """Test list avec pagination."""
    # Créer 15 produits
    for i in range(15):
        product = Product(
            tenant_id=1,
            name=f"Product {i}",
            sku=f"SKU-{i:03d}",
            category=ProductCategory.AUTRE,
            price_per_day=1000,
            deposit_amount=2000,
            stock_quantity=10,
            available_quantity=10,
            condition=ProductCondition.BON,
            is_active=True
        )
        test_db.add(product)
    test_db.commit()

    repo = BaseRepository(test_db, Product)

    # Page 1
    items_page1, total_page1 = repo.list(tenant_id=1, skip=0, limit=10)
    assert len(items_page1) == 10
    assert total_page1 == 15

    # Page 2
    items_page2, total_page2 = repo.list(tenant_id=1, skip=10, limit=10)
    assert len(items_page2) == 5
    assert total_page2 == 15


def test_base_repository_create_requires_tenant_id(test_db):
    """Test create refuse entité sans tenant_id."""
    product = Product(
        # tenant_id manquant intentionnellement
        name="No Tenant Product",
        sku="NO-TENANT-SKU",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )

    repo = BaseRepository(test_db, Product)

    with pytest.raises(ValueError, match="requires tenant_id"):
        repo.create(product)


def test_base_repository_update_success(test_db):
    """Test update modifie entité."""
    product = Product(
        tenant_id=1,
        name="Original Name",
        sku="UPDATE-TEST",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)

    repo = BaseRepository(test_db, Product)
    product.name = "Updated Name"
    updated = repo.update(product)

    assert updated.name == "Updated Name"


def test_base_repository_soft_delete_sets_inactive(test_db):
    """Test soft_delete met is_active=False."""
    product = Product(
        tenant_id=1,
        name="To Delete",
        sku="DELETE-TEST",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()

    repo = BaseRepository(test_db, Product)
    result = repo.soft_delete(product.id, tenant_id=1)

    assert result is True
    test_db.refresh(product)
    assert product.is_active is False


def test_base_repository_soft_delete_wrong_tenant(test_db):
    """Test soft_delete échoue pour mauvais tenant."""
    product = Product(
        tenant_id=1,
        name="Protected Product",
        sku="PROTECTED-SKU",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()

    repo = BaseRepository(test_db, Product)
    result = repo.soft_delete(product.id, tenant_id=2)  # Mauvais tenant

    assert result is False
    test_db.refresh(product)
    assert product.is_active is True  # Inchangé


# ═══════════════════════════════════════════════════════════════════════════
# Tests ProductRepository
# ═══════════════════════════════════════════════════════════════════════════

def test_product_repository_get_by_sku_success(test_db):
    """Test get_by_sku trouve produit."""
    product = Product(
        tenant_id=1,
        name="Unique SKU Product",
        sku="UNIQUE-SKU-001",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()

    repo = ProductRepository(test_db, Product)
    result = repo.get_by_sku("UNIQUE-SKU-001", tenant_id=1)

    assert result is not None
    assert result.sku == "UNIQUE-SKU-001"


def test_product_repository_list_by_category(test_db):
    """Test list_by_category filtre correctement."""
    # Créer produits de différentes catégories
    for cat in ["tables", "tables", "chaises", "chaises", "nappes"]:
        product = Product(
            tenant_id=1,
            name=f"{cat} product",
            sku=f"SKU-{cat}-{id(cat)}",
            category=cat,
            price_per_day=1000,
            deposit_amount=2000,
            stock_quantity=10,
            available_quantity=10,
            condition=ProductCondition.BON,
            is_active=True
        )
        test_db.add(product)
    test_db.commit()

    repo = ProductRepository(test_db, Product)
    tables, total = repo.list(tenant_id=1, filters={"category": "tables"})

    assert total == 2
    assert all(p.category == "tables" for p in tables)


def test_product_repository_check_availability_success(test_db):
    """Test check_availability retourne True si stock suffisant."""
    product = Product(
        tenant_id=1,
        name="Available Product",
        sku="AVAILABLE-SKU",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()

    repo = ProductRepository(test_db, Product)
    result = repo.check_availability(product.id, quantity=5, tenant_id=1)

    assert result is True


def test_product_repository_check_availability_insufficient(test_db):
    """Test check_availability retourne False si stock insuffisant."""
    product = Product(
        tenant_id=1,
        name="Low Stock Product",
        sku="LOW-STOCK-SKU",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=3,  # Seulement 3 disponibles
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()

    repo = ProductRepository(test_db, Product)
    result = repo.check_availability(product.id, quantity=5, tenant_id=1)

    assert result is False


def test_product_repository_reserve_stock_success(test_db):
    """Test reserve_stock décrémente available_quantity."""
    product = Product(
        tenant_id=1,
        name="Reserve Product",
        sku="RESERVE-SKU",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()

    repo = ProductRepository(test_db, Product)
    result = repo.reserve_stock(product.id, quantity=3, tenant_id=1)

    assert result is True
    test_db.refresh(product)
    assert product.available_quantity == 7


def test_product_repository_reserve_stock_insufficient(test_db):
    """Test reserve_stock échoue si stock insuffisant."""
    product = Product(
        tenant_id=1,
        name="Low Stock Product",
        sku="LOW-STOCK-2",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=2,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()

    repo = ProductRepository(test_db, Product)
    result = repo.reserve_stock(product.id, quantity=5, tenant_id=1)

    assert result is False
    test_db.refresh(product)
    assert product.available_quantity == 2  # Inchangé


def test_product_repository_release_stock_success(test_db):
    """Test release_stock incrémente available_quantity."""
    product = Product(
        tenant_id=1,
        name="Release Product",
        sku="RELEASE-SKU",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=5,  # Partiellement réservé
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()

    repo = ProductRepository(test_db, Product)
    result = repo.release_stock(product.id, quantity=3, tenant_id=1)

    assert result is True
    test_db.refresh(product)
    assert product.available_quantity == 8


# ═══════════════════════════════════════════════════════════════════════════
# Tests CustomerRepository
# ═══════════════════════════════════════════════════════════════════════════

def test_customer_repository_get_by_email_success(test_db):
    """Test get_by_email trouve customer."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()

    repo = CustomerRepository(test_db, Customer)
    result = repo.get_by_email("john.doe@example.com", tenant_id=1)

    assert result is not None
    assert result.email == "john.doe@example.com"


def test_customer_repository_get_by_email_case_insensitive(test_db):
    """Test get_by_email est case-insensitive."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Jane",
        last_name="Doe",
        email="Jane.Doe@Example.COM",  # Mixed case
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()

    repo = CustomerRepository(test_db, Customer)
    result = repo.get_by_email("jane.doe@example.com", tenant_id=1)  # Lowercase

    assert result is not None
    assert result.email.lower() == "jane.doe@example.com"


def test_customer_repository_search_by_name(test_db):
    """Test search trouve customers par nom."""
    customers = [
        Customer(
            tenant_id=1,
            customer_type=CustomerType.INDIVIDUAL,
            first_name="Alice",
            last_name="Smith",
            email=f"alice{i}@example.com",
            phone="+33612345678",
            city="Paris",
            postal_code="75001",
            is_active=True
        )
        for i in range(3)
    ]
    test_db.add_all(customers)
    test_db.commit()

    repo = CustomerRepository(test_db, Customer)
    results, total = repo.search("Alice", tenant_id=1)

    assert total == 3
    assert all("alice" in c.first_name.lower() for c in results)
