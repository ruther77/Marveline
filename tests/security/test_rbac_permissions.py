"""Tests RBAC (Role-Based Access Control) exhaustifs."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.models.user import User
from app.models.product import Product
from app.models.customer import Customer
from app.core.security import get_password_hash, create_access_token
from app.constants import CustomerType, ProductCategory, ProductCondition


@pytest.fixture
def admin_user(test_db):
    """User avec role=admin."""
    user = User(
        tenant_id=1,
        email="admin@carocorp.com",
        hashed_password=get_password_hash("admin123"),
        full_name="Admin User",
        role="admin",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def manager_user(test_db):
    """User avec role=manager."""
    user = User(
        tenant_id=1,
        email="manager@carocorp.com",
        hashed_password=get_password_hash("manager123"),
        full_name="Manager User",
        role="manager",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def staff_user(test_db):
    """User avec role=staff."""
    user = User(
        tenant_id=1,
        email="staff@carocorp.com",
        hashed_password=get_password_hash("staff123"),
        full_name="Staff User",
        role="staff",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def admin_headers(admin_user, csrf_token):
    """Headers avec token admin + CSRF."""
    token = create_access_token({
        "sub": admin_user.id,
        "tenant_id": admin_user.tenant_id,
        "email": admin_user.email,
        "role": admin_user.role
    })
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": csrf_token
    }


@pytest.fixture
def manager_headers(manager_user, csrf_token):
    """Headers avec token manager + CSRF."""
    token = create_access_token({
        "sub": manager_user.id,
        "tenant_id": manager_user.tenant_id,
        "email": manager_user.email,
        "role": manager_user.role
    })
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": csrf_token
    }


@pytest.fixture
def staff_headers(staff_user, csrf_token):
    """Headers avec token staff + CSRF."""
    token = create_access_token({
        "sub": staff_user.id,
        "tenant_id": staff_user.tenant_id,
        "email": staff_user.email,
        "role": staff_user.role
    })
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": csrf_token
    }


# ═══════════════════════════════════════════════════════════════════════════
# Tests RBAC Products (admin only pour CUD)
# ═══════════════════════════════════════════════════════════════════════════

def test_admin_can_create_product(client: TestClient, admin_headers):
    """Test admin peut créer produit."""
    product_data = {
        "name": "Admin Product",
        "sku": "ADMIN-SKU-001",
        "category": "autre",
        "price_per_day_cents": 1000,
        "deposit_amount_cents": 2000,
        "stock_quantity": 10,
        "available_quantity": 10,
        "condition": "bon"
    }

    response = client.post("/api/v1/products", json=product_data, headers=admin_headers)

    assert response.status_code == 201


def test_manager_cannot_create_product(client: TestClient, manager_headers):
    """Test manager ne peut pas créer produit."""
    product_data = {
        "name": "Manager Product",
        "sku": "MANAGER-SKU-001",
        "category": "autre",
        "price_per_day_cents": 1000,
        "deposit_amount_cents": 2000,
        "stock_quantity": 10,
        "available_quantity": 10,
        "condition": "bon"
    }

    response = client.post("/api/v1/products", json=product_data, headers=manager_headers)

    assert response.status_code == 403
    assert "permission" in response.json()["detail"].lower()


def test_staff_cannot_create_product(client: TestClient, staff_headers):
    """Test staff ne peut pas créer produit."""
    product_data = {
        "name": "Staff Product",
        "sku": "STAFF-SKU-001",
        "category": "autre",
        "price_per_day_cents": 1000,
        "deposit_amount_cents": 2000,
        "stock_quantity": 10,
        "available_quantity": 10,
        "condition": "bon"
    }

    response = client.post("/api/v1/products", json=product_data, headers=staff_headers)

    assert response.status_code == 403


def test_admin_can_update_product(client: TestClient, test_db, admin_headers):
    """Test admin peut mettre à jour produit."""
    product = Product(
        tenant_id=1,
        name="Original Product",
        sku="UPDATE-RBAC",
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

    update_data = {"name": "Updated Product"}

    response = client.patch(f"/api/v1/products/{product.id}", json=update_data, headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Product"


def test_staff_cannot_update_product(client: TestClient, test_db, staff_headers):
    """Test staff ne peut pas mettre à jour produit."""
    product = Product(
        tenant_id=1,
        name="Protected Product",
        sku="PROTECTED-RBAC",
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

    update_data = {"name": "Hacked Product"}

    response = client.patch(f"/api/v1/products/{product.id}", json=update_data, headers=staff_headers)

    assert response.status_code == 403


def test_admin_can_delete_product(client: TestClient, test_db, admin_headers):
    """Test admin peut supprimer produit."""
    product = Product(
        tenant_id=1,
        name="Delete Product",
        sku="DELETE-RBAC",
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

    response = client.delete(f"/api/v1/products/{product.id}", headers=admin_headers)

    assert response.status_code == 204


def test_staff_cannot_delete_product(client: TestClient, test_db, staff_headers):
    """Test staff ne peut pas supprimer produit."""
    product = Product(
        tenant_id=1,
        name="Protected Delete",
        sku="PROTECTED-DELETE",
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

    response = client.delete(f"/api/v1/products/{product.id}", headers=staff_headers)

    assert response.status_code == 403


def test_all_roles_can_read_products(client: TestClient, test_db, admin_headers, manager_headers, staff_headers):
    """Test tous les rôles peuvent lire produits."""
    product = Product(
        tenant_id=1,
        name="Public Product",
        sku="PUBLIC-RBAC",
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

    # Admin
    response_admin = client.get(f"/api/v1/products/{product.id}", headers=admin_headers)
    assert response_admin.status_code == 200

    # Manager
    response_manager = client.get(f"/api/v1/products/{product.id}", headers=manager_headers)
    assert response_manager.status_code == 200

    # Staff
    response_staff = client.get(f"/api/v1/products/{product.id}", headers=staff_headers)
    assert response_staff.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Tests RBAC Customers (tous rôles peuvent créer/modifier)
# ═══════════════════════════════════════════════════════════════════════════

def test_staff_can_create_customer(client: TestClient, staff_headers):
    """Test staff peut créer client."""
    customer_data = {
        "customer_type": "individual",
        "first_name": "Staff",
        "last_name": "Created",
        "email": "staffcreated@example.com",
        "phone": "+33612345678",
        "city": "Paris",
        "postal_code": "75001"
    }

    response = client.post("/api/v1/customers", json=customer_data, headers=staff_headers)

    assert response.status_code == 201


def test_manager_can_create_customer(client: TestClient, manager_headers):
    """Test manager peut créer client."""
    customer_data = {
        "customer_type": "individual",
        "first_name": "Manager",
        "last_name": "Created",
        "email": "managercreated@example.com",
        "phone": "+33612345678",
        "city": "Paris",
        "postal_code": "75001"
    }

    response = client.post("/api/v1/customers", json=customer_data, headers=manager_headers)

    assert response.status_code == 201


# ═══════════════════════════════════════════════════════════════════════════
# Tests RBAC Reservations (tous rôles)
# ═══════════════════════════════════════════════════════════════════════════

def test_staff_can_create_reservation(client: TestClient, test_db, staff_headers):
    """Test staff peut créer réservation."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Test",
        last_name="Customer",
        email="testcustomer@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    product = Product(
        tenant_id=1,
        name="Test Product",
        sku="RES-PRODUCT",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add_all([customer, product])
    test_db.commit()

    reservation_data = {
        "customer_id": customer.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test Location",
        "lines": [{"product_id": product.id, "quantity": 1}]
    }

    response = client.post("/api/v1/reservations", json=reservation_data, headers=staff_headers)

    assert response.status_code == 201


def test_manager_can_confirm_reservation(client: TestClient, test_db, manager_headers):
    """Test manager peut confirmer réservation."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Confirm",
        last_name="Customer",
        email="confirmcustomer@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    product = Product(
        tenant_id=1,
        name="Confirm Product",
        sku="CONFIRM-PRODUCT",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add_all([customer, product])
    test_db.commit()

    reservation_data = {
        "customer_id": customer.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": product.id, "quantity": 1}]
    }

    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=manager_headers)
    reservation_id = create_response.json()["id"]

    # Confirmer
    response = client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=manager_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


# ═══════════════════════════════════════════════════════════════════════════
# Tests RBAC Invoices (tous rôles)
# ═══════════════════════════════════════════════════════════════════════════

def test_staff_can_create_invoice(client: TestClient, test_db, staff_headers):
    """Test staff peut créer facture."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Invoice",
        last_name="Customer",
        email="invoicecustomer@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    product = Product(
        tenant_id=1,
        name="Invoice Product",
        sku="INVOICE-PRODUCT",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add_all([customer, product])
    test_db.commit()

    # Créer réservation d'abord
    reservation_data = {
        "customer_id": customer.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": product.id, "quantity": 1}]
    }
    res_response = client.post("/api/v1/reservations", json=reservation_data, headers=staff_headers)
    reservation_id = res_response.json()["id"]

    # Créer facture
    invoice_data = {
        "reservation_id": reservation_id,
        "issue_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=14))
    }

    response = client.post("/api/v1/invoices", json=invoice_data, headers=staff_headers)

    assert response.status_code == 201


def test_manager_can_add_payment(client: TestClient, test_db, manager_headers):
    """Test manager peut ajouter paiement."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Payment",
        last_name="Customer",
        email="paymentcustomer@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    product = Product(
        tenant_id=1,
        name="Payment Product",
        sku="PAYMENT-PRODUCT",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add_all([customer, product])
    test_db.commit()

    # Créer réservation + facture
    reservation_data = {
        "customer_id": customer.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": product.id, "quantity": 1}]
    }
    res_response = client.post("/api/v1/reservations", json=reservation_data, headers=manager_headers)
    reservation_id = res_response.json()["id"]

    invoice_data = {
        "reservation_id": reservation_id,
        "issue_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=14))
    }
    inv_response = client.post("/api/v1/invoices", json=invoice_data, headers=manager_headers)
    invoice_id = inv_response.json()["id"]

    # Ajouter paiement
    payment_data = {
        "amount_cents": 1000,
        "payment_method": "card",
        "payment_date": str(date.today())
    }

    response = client.post(f"/api/v1/invoices/{invoice_id}/add-payment", json=payment_data, headers=manager_headers)

    assert response.status_code == 200
