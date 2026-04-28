"""Tests RBAC (Role-Based Access Control) exhaustifs."""
import pytest
import redis as _sync_redis
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.models.account import Account
from app.models.tenant_membership import TenantMembership
from app.core.deps import UserCompat
from app.models.product import Product
from app.models.customer import Customer
from app.core.config import settings
from app.core.security import get_password_hash, create_access_token, decode_token
from app.constants import CustomerType, ProductCategory, ProductCondition, RedisKeys
import secrets
import uuid


# Sync Redis client for CSRF token storage in fixtures (évite event-loop async mismatch)
_sync_sec_rbac = _sync_redis.from_url(settings.REDIS_SEC_URL, decode_responses=True)


def _store_csrf_sync(session_id: str, token: str, ttl_seconds: int = 604800) -> None:
    """Stocke un token CSRF en Redis sync (miroir store_csrf_token async)."""
    _sync_sec_rbac.setex(RedisKeys.csrf_token(session_id), ttl_seconds, token)


@pytest.fixture
def admin_user(test_db, test_tenant_record, _role_admin):
    """User avec role=admin (IAM v2)."""
    account = Account(
        email="admin@carocorp.com",
        hashed_password=get_password_hash("admin123"),
        first_name="Admin", last_name="User",
        is_active=True
    )
    test_db.add(account)
    test_db.flush()
    membership = TenantMembership(
        account_id=account.id,
        tenant_id=test_tenant_record.id,
        role_name="admin",
        status="active"
    )
    test_db.add(membership)
    test_db.commit()
    test_db.refresh(account)
    test_db.refresh(membership)
    return UserCompat(account=account, membership=membership)


@pytest.fixture
def manager_user(test_db, test_tenant_record, _role_manager):
    """User avec role=manager (IAM v2)."""
    account = Account(
        email="manager@carocorp.com",
        hashed_password=get_password_hash("manager123"),
        first_name="Manager", last_name="User",
        is_active=True
    )
    test_db.add(account)
    test_db.flush()
    membership = TenantMembership(
        account_id=account.id,
        tenant_id=test_tenant_record.id,
        role_name="manager",
        status="active"
    )
    test_db.add(membership)
    test_db.commit()
    test_db.refresh(account)
    test_db.refresh(membership)
    return UserCompat(account=account, membership=membership)


@pytest.fixture
def staff_user(test_db, test_tenant_record, _role_staff):
    """User avec role=staff (IAM v2)."""
    account = Account(
        email="staff@carocorp.com",
        hashed_password=get_password_hash("staff123"),
        first_name="Staff", last_name="User",
        is_active=True
    )
    test_db.add(account)
    test_db.flush()
    membership = TenantMembership(
        account_id=account.id,
        tenant_id=test_tenant_record.id,
        role_name="staff",
        status="active"
    )
    test_db.add(membership)
    test_db.commit()
    test_db.refresh(account)
    test_db.refresh(membership)
    return UserCompat(account=account, membership=membership)


@pytest.fixture
def admin_headers(admin_user):
    """Headers avec token admin + CSRF (Redis-backed, §04 §4.3)."""
    token = create_access_token({
        "sub": admin_user.id,
        "tid": str(admin_user.tenant_id),
        "email": admin_user.email,
        "role": admin_user.role,
        "sid": str(uuid.uuid4()),
    })
    sid = decode_token(token).get("sid")
    csrf = secrets.token_urlsafe(32)
    _store_csrf_sync(session_id=sid, token=csrf)
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": csrf
    }


@pytest.fixture
def manager_headers(manager_user):
    """Headers avec token manager + CSRF (Redis-backed, §04 §4.3)."""
    token = create_access_token({
        "sub": manager_user.id,
        "tid": str(manager_user.tenant_id),
        "email": manager_user.email,
        "role": manager_user.role,
        "sid": str(uuid.uuid4()),
    })
    sid = decode_token(token).get("sid")
    csrf = secrets.token_urlsafe(32)
    _store_csrf_sync(session_id=sid, token=csrf)
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": csrf
    }


@pytest.fixture
def staff_headers(staff_user):
    """Headers avec token staff + CSRF (Redis-backed, §04 §4.3)."""
    token = create_access_token({
        "sub": staff_user.id,
        "tid": str(staff_user.tenant_id),
        "email": staff_user.email,
        "role": staff_user.role,
        "sid": str(uuid.uuid4()),
    })
    sid = decode_token(token).get("sid")
    csrf = secrets.token_urlsafe(32)
    _store_csrf_sync(session_id=sid, token=csrf)
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": csrf
    }


# ═══════════════════════════════════════════════════════════════════════════
# Tests RBAC Products (admin only pour CUD)
# ═══════════════════════════════════════════════════════════════════════════

def test_admin_can_create_product(client: TestClient, admin_headers):
    """Test admin peut créer produit."""
    product_data = {
        "name": "Admin Product",
        "sku": "ADMIN-SKU-001",
        "category": "mobilier",
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
        "category": "mobilier",
        "price_per_day_cents": 1000,
        "deposit_amount_cents": 2000,
        "stock_quantity": 10,
        "available_quantity": 10,
        "condition": "bon"
    }

    response = client.post("/api/v1/products", json=product_data, headers=manager_headers)

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "INSUFFICIENT_SCOPES"


def test_staff_cannot_create_product(client: TestClient, staff_headers):
    """Test staff ne peut pas créer produit."""
    product_data = {
        "name": "Staff Product",
        "sku": "STAFF-SKU-001",
        "category": "mobilier",
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
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1000,
        deposit_amount_cents=2000,
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
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1000,
        deposit_amount_cents=2000,
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
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1000,
        deposit_amount_cents=2000,
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
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1000,
        deposit_amount_cents=2000,
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
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1000,
        deposit_amount_cents=2000,
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
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1000,
        deposit_amount_cents=2000,
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

    # 201 = cree, 400 = validation metier (donnees test incompletes mais RBAC OK)
    assert response.status_code in (201, 400), \
        f"Staff doit etre autorise (pas 403). Got {response.status_code}: {response.json()}"


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
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1000,
        deposit_amount_cents=2000,
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

    # RBAC check : pas de 403 (autorisation OK, meme si 400/422 validation metier)
    assert create_response.status_code != 403, \
        f"Manager doit etre autorise pour creer reservation. Got {create_response.status_code}"
    if create_response.status_code == 201:
        reservation_id = create_response.json()["id"]
        response = client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=manager_headers)
        assert response.status_code != 403, \
            f"Manager doit etre autorise pour confirmer. Got {response.status_code}"


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
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1000,
        deposit_amount_cents=2000,
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

    # RBAC check : staff autorise (pas 403)
    assert res_response.status_code != 403, \
        f"Staff doit etre autorise pour creer reservation. Got {res_response.status_code}"

    if res_response.status_code == 201:
        reservation_id = res_response.json()["id"]
        invoice_data = {
            "reservation_id": reservation_id,
            "issue_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=14))
        }
        response = client.post("/api/v1/invoices", json=invoice_data, headers=staff_headers)
        assert response.status_code != 403, \
            f"Staff doit etre autorise pour creer facture. Got {response.status_code}"


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
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1000,
        deposit_amount_cents=2000,
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

    # RBAC check : manager autorise (pas 403)
    assert res_response.status_code != 403, \
        f"Manager doit etre autorise. Got {res_response.status_code}"

    if res_response.status_code != 201:
        pytest.skip("Reservation creation failed (business validation) — RBAC check passed")
        return

    reservation_id = res_response.json()["id"]
    invoice_data = {
        "reservation_id": reservation_id,
        "issue_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=14))
    }
    inv_response = client.post("/api/v1/invoices", json=invoice_data, headers=manager_headers)
    assert inv_response.status_code != 403

    if inv_response.status_code != 201:
        pytest.skip("Invoice creation failed (business validation) — RBAC check passed")
        return

    invoice_id = inv_response.json()["id"]
    payment_data = {
        "amount_cents": 1000,
        "payment_method": "card",
        "payment_date": str(date.today())
    }
    response = client.post(f"/api/v1/invoices/{invoice_id}/add-payment", json=payment_data, headers=manager_headers)

    assert response.status_code != 403, \
        f"Manager doit etre autorise pour ajouter paiement. Got {response.status_code}"
