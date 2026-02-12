"""Tests de concurrence et race conditions."""
import pytest
from datetime import date, timedelta
import threading
from fastapi.testclient import TestClient
from app.models.product import Product
from app.models.customer import Customer
from app.constants import CustomerType, ProductCategory, ProductCondition, ReservationStatus


# ═══════════════════════════════════════════════════════════════════════════
# Tests Race Conditions Stock
# ═══════════════════════════════════════════════════════════════════════════

def test_concurrent_stock_reservation_race_condition(client: TestClient, test_db, auth_headers_real):
    """Test réservations concurrentes sur même produit."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Concurrent",
        last_name="Customer",
        email="concurrent@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    product = Product(
        tenant_id=1,
        name="Race Product",
        sku="RACE-PRODUCT",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,  # Seulement 10 disponibles
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add_all([customer, product])
    test_db.commit()
    test_db.refresh(product)

    results = []

    def create_and_confirm_reservation():
        """Thread worker pour créer + confirmer réservation."""
        reservation_data = {
            "customer_id": customer.id,
            "event_date": str(date.today() + timedelta(days=10)),
            "delivery_date": str(date.today() + timedelta(days=9)),
            "return_date": str(date.today() + timedelta(days=11)),
            "event_location": "Test",
            "lines": [{"product_id": product.id, "quantity": 8}]  # Demande 8
        }

        create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
        if create_response.status_code == 201:
            reservation_id = create_response.json()["id"]
            confirm_response = client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=auth_headers_real)
            results.append(confirm_response.status_code)
        else:
            results.append(create_response.status_code)

    # Lancer 2 threads simultanément demandant chacun 8 unités (total 16 > 10)
    thread1 = threading.Thread(target=create_and_confirm_reservation)
    thread2 = threading.Thread(target=create_and_confirm_reservation)

    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()

    # Une des deux doit échouer (stock insuffisant)
    assert 400 in results or len([r for r in results if r == 200]) == 1


def test_concurrent_product_creation_duplicate_sku(client: TestClient, auth_headers_admin):
    """Test créations concurrentes avec même SKU."""
    results = []

    def create_product():
        """Thread worker pour créer produit."""
        product_data = {
            "name": "Concurrent Product",
            "sku": "CONCURRENT-SKU",  # Même SKU
            "category": "autre",
            "price_per_day_cents": 1000,
            "deposit_amount_cents": 2000,
            "stock_quantity": 10,
            "available_quantity": 10,
            "condition": "bon"
        }

        response = client.post("/api/v1/products", json=product_data, headers=auth_headers_admin)
        results.append(response.status_code)

    # Lancer 2 threads créant produit avec même SKU
    thread1 = threading.Thread(target=create_product)
    thread2 = threading.Thread(target=create_product)

    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()

    # Une des deux doit échouer (duplicate SKU)
    assert 400 in results or results.count(201) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Tests Performance Pagination
# ═══════════════════════════════════════════════════════════════════════════

def test_list_products_pagination_performance(client: TestClient, test_db, auth_headers_real):
    """Test performance pagination sur grande liste."""
    # Créer 100 produits
    products = []
    for i in range(100):
        product = Product(
            tenant_id=1,
            name=f"Perf Product {i}",
            sku=f"PERF-SKU-{i:03d}",
            category=ProductCategory.AUTRE,
            price_per_day=1000,
            deposit_amount=2000,
            stock_quantity=10,
            available_quantity=10,
            condition=ProductCondition.BON,
            is_active=True
        )
        products.append(product)

    test_db.add_all(products)
    test_db.commit()

    # Tester pagination
    import time
    start = time.time()

    response = client.get("/api/v1/products?skip=0&limit=50", headers=auth_headers_real)

    duration = time.time() - start

    assert response.status_code == 200
    assert len(response.json()["items"]) <= 50
    assert duration < 2.0  # Moins de 2 secondes


def test_search_customers_performance(client: TestClient, test_db, auth_headers_real):
    """Test performance recherche clients."""
    # Créer 50 clients
    customers = []
    for i in range(50):
        customer = Customer(
            tenant_id=1,
            customer_type=CustomerType.INDIVIDUAL,
            first_name=f"FirstName{i}",
            last_name=f"LastName{i}",
            email=f"perf{i}@example.com",
            phone="+33612345678",
            city="Paris",
            postal_code="75001",
            is_active=True
        )
        customers.append(customer)

    test_db.add_all(customers)
    test_db.commit()

    # Tester recherche
    import time
    start = time.time()

    response = client.get("/api/v1/customers?search_query=FirstName1", headers=auth_headers_real)

    duration = time.time() - start

    assert response.status_code == 200
    assert duration < 1.0  # Moins de 1 seconde


# ═══════════════════════════════════════════════════════════════════════════
# Tests Bulk Operations
# ═══════════════════════════════════════════════════════════════════════════

def test_create_multiple_reservations_sequentially(client: TestClient, test_db, auth_headers_real):
    """Test créer plusieurs réservations séquentiellement."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Bulk",
        last_name="Customer",
        email="bulk@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    product = Product(
        tenant_id=1,
        name="Bulk Product",
        sku="BULK-PRODUCT",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=100,
        available_quantity=100,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add_all([customer, product])
    test_db.commit()

    # Créer 10 réservations
    reservation_ids = []
    for i in range(10):
        reservation_data = {
            "customer_id": customer.id,
            "event_date": str(date.today() + timedelta(days=10 + i)),
            "delivery_date": str(date.today() + timedelta(days=9 + i)),
            "return_date": str(date.today() + timedelta(days=11 + i)),
            "event_location": f"Test Location {i}",
            "lines": [{"product_id": product.id, "quantity": 2}]
        }

        response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
        assert response.status_code == 201
        reservation_ids.append(response.json()["id"])

    assert len(reservation_ids) == 10


def test_filter_products_by_multiple_criteria(client: TestClient, test_db, auth_headers_real):
    """Test filtrer produits par plusieurs critères."""
    # Créer produits variés
    for cat in ["assiette", "verre", "nappe"]:
        for i in range(5):
            product = Product(
                tenant_id=1,
                name=f"{cat} Product {i}",
                sku=f"{cat.upper()}-{i:02d}",
                category=cat,
                price_per_day=1000,
                deposit_amount=2000,
                stock_quantity=10,
                available_quantity=i % 3,  # 0, 1 ou 2
                condition=ProductCondition.BON,
                is_active=i % 2 == 0  # Alternance actif/inactif
            )
            test_db.add(product)
    test_db.commit()

    # Filtrer par category + available_only
    response = client.get("/api/v1/products?category=assiette&available_only=true", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["category"] == "assiette"
        assert item["available_quantity"] > 0


# ═══════════════════════════════════════════════════════════════════════════
# Tests Transaction Atomicity
# ═══════════════════════════════════════════════════════════════════════════

def test_confirm_reservation_rollback_on_error(client: TestClient, test_db, auth_headers_real):
    """Test rollback si confirm échoue (transaction atomique)."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Rollback",
        last_name="Customer",
        email="rollback@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    product1 = Product(
        tenant_id=1,
        name="Product 1",
        sku="ROLLBACK-PRODUCT-1",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    product2 = Product(
        tenant_id=1,
        name="Product 2",
        sku="ROLLBACK-PRODUCT-2",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=2,  # Stock limité
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add_all([customer, product1, product2])
    test_db.commit()

    # Créer réservation avec 2 lignes (une va échouer)
    reservation_data = {
        "customer_id": customer.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [
            {"product_id": product1.id, "quantity": 5},
            {"product_id": product2.id, "quantity": 5}  # > stock disponible
        ]
    }

    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    reservation_id = create_response.json()["id"]

    # Tenter de confirmer (doit échouer)
    response = client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=auth_headers_real)

    assert response.status_code == 400

    # Rollback pour annuler les flush() de la transaction échouée
    test_db.rollback()

    # Vérifier que le stock de product1 n'a PAS été modifié (rollback)
    test_db.refresh(product1)
    assert product1.available_quantity == 10  # Inchangé


def test_cancel_reservation_releases_all_stock(client: TestClient, test_db, auth_headers_real):
    """Test annulation libère tout le stock."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Cancel",
        last_name="Stock",
        email="cancelstock@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    product1 = Product(
        tenant_id=1,
        name="Product A",
        sku="CANCEL-PRODUCT-A",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=20,
        available_quantity=20,
        condition=ProductCondition.BON,
        is_active=True
    )
    product2 = Product(
        tenant_id=1,
        name="Product B",
        sku="CANCEL-PRODUCT-B",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=30,
        available_quantity=30,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add_all([customer, product1, product2])
    test_db.commit()

    # Créer et confirmer réservation
    reservation_data = {
        "customer_id": customer.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [
            {"product_id": product1.id, "quantity": 5},
            {"product_id": product2.id, "quantity": 10}
        ]
    }

    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    reservation_id = create_response.json()["id"]

    client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=auth_headers_real)

    test_db.refresh(product1)
    test_db.refresh(product2)
    assert product1.available_quantity == 15  # 20 - 5
    assert product2.available_quantity == 20  # 30 - 10

    # Annuler
    client.post(f"/api/v1/reservations/{reservation_id}/cancel", headers=auth_headers_real)

    # Vérifier libération stock
    test_db.refresh(product1)
    test_db.refresh(product2)
    assert product1.available_quantity == 20  # Restauré
    assert product2.available_quantity == 30  # Restauré


def test_multiple_payments_accumulate_correctly(client: TestClient, test_db, auth_headers_real):
    """Test paiements multiples s'accumulent correctement."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Multi",
        last_name="Payment",
        email="multipayment@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()

    from app.models.reservation import Reservation
    from app.models.invoice import Invoice

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-MULTI-PAY",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()

    invoice = Invoice(
        tenant_id=1,
        reservation_id=reservation.id,
        invoice_number="INV-MULTI-PAY",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount=10000,
        paid_amount=0,
        status=ReservationStatus.DRAFT
    )
    test_db.add(invoice)
    test_db.commit()

    # Paiements multiples
    payments = [2000, 3000, 2000, 3000]  # Total 10000
    for amount in payments:
        payment_data = {
            "amount_cents": amount,
            "payment_method": "card",
            "payment_date": str(date.today())
        }

        response = client.post(f"/api/v1/invoices/{invoice.id}/add-payment", json=payment_data, headers=auth_headers_real)
        assert response.status_code == 200

    # Vérifier total payé
    final_response = client.get(f"/api/v1/invoices/{invoice.id}", headers=auth_headers_real)
    final_invoice = final_response.json()

    assert final_invoice["paid_amount_cents"] == 10000
    assert final_invoice["is_paid"] is True
    assert final_invoice["status"] == "paid"
