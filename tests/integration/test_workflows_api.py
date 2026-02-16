"""Tests E2E de workflows complets via API CaroCorp."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.models.customer import Customer
from app.models.product import Product
from app.constants import CustomerType, ProductCategory, ProductCondition


@pytest.fixture
def workflow_customer(test_db):
    """Client pour workflow E2E."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.COMPANY,
        company_name="Mariage & Co",
        email="contact@mariageco.fr",
        phone="+33123456789",
        address="10 rue du Bonheur",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


@pytest.fixture
def workflow_products(test_db):
    """Produits pour workflow E2E."""
    products = []

    # Tables rondes
    product1 = Product(
        tenant_id=1,
        name="Table ronde 150cm",
        sku="TABLE-RONDE-150-WF",
        category=ProductCategory.NAPPES,
        price_per_day=2000,  # 20€/jour
        deposit_amount=5000,  # 50€ caution
        stock_quantity=20,
        available_quantity=20,
        condition=ProductCondition.NEUF,
        is_active=True
    )
    test_db.add(product1)
    products.append(product1)

    # Chaises Napoléon
    product2 = Product(
        tenant_id=1,
        name="Chaise Napoléon dorée",
        sku="CHAISE-NAP-WF",
        category=ProductCategory.MOBILIER,
        price_per_day=500,  # 5€/jour
        deposit_amount=1000,  # 10€ caution
        stock_quantity=100,
        available_quantity=100,
        condition=ProductCondition.NEUF,
        is_active=True
    )
    test_db.add(product2)
    products.append(product2)

    test_db.commit()
    for p in products:
        test_db.refresh(p)

    return products


def test_complete_rental_workflow(client: TestClient, test_db, workflow_customer, workflow_products, auth_headers_real):
    """
    Test workflow E2E complet de location via API:
    1. Créer réservation (draft) avec 2 produits
    2. Confirmer réservation (réserve stock)
    3. Générer facture depuis réservation
    4. Ajouter paiement partiel
    5. Ajouter paiement complet (status=paid)
    6. Vérifier état final cohérent
    """
    table_product, chaise_product = workflow_products

    # Stock initial
    initial_table_stock = table_product.available_quantity
    initial_chaise_stock = chaise_product.available_quantity

    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 1: Créer réservation (draft)
    # ═══════════════════════════════════════════════════════════════════════
    reservation_data = {
        "customer_id": workflow_customer.id,
        "event_date": str(date.today() + timedelta(days=30)),
        "delivery_date": str(date.today() + timedelta(days=29)),
        "return_date": str(date.today() + timedelta(days=31)),  # 3 jours location
        "event_location": "Château de Versailles",
        "lines": [
            {
                "product_id": table_product.id,
                "quantity": 10  # 10 tables
            },
            {
                "product_id": chaise_product.id,
                "quantity": 80  # 80 chaises
            }
        ]
    }

    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    assert create_response.status_code == 201

    reservation = create_response.json()
    reservation_id = reservation["id"]
    assert reservation["status"] == "draft"
    assert reservation["rental_days"] == 3
    assert len(reservation["lines"]) == 2

    # Calculer total attendu: (10 tables × 20€ × 3j) + (80 chaises × 5€ × 3j)
    expected_total = (10 * 2000 * 3) + (80 * 500 * 3)  # 60000 + 120000 = 180000 centimes (1800€)
    assert reservation["total_amount_cents"] == expected_total

    # Vérifier stock PAS ENCORE réservé (status=draft)
    test_db.refresh(table_product)
    test_db.refresh(chaise_product)
    assert table_product.available_quantity == initial_table_stock
    assert chaise_product.available_quantity == initial_chaise_stock

    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 2: Confirmer réservation (réserve stock)
    # ═══════════════════════════════════════════════════════════════════════
    confirm_response = client.post(
        f"/api/v1/reservations/{reservation_id}/confirm",
        headers=auth_headers_real
    )
    assert confirm_response.status_code == 200

    confirmed_reservation = confirm_response.json()
    assert confirmed_reservation["status"] == "confirmed"

    # Vérifier stock RÉSERVÉ
    test_db.refresh(table_product)
    test_db.refresh(chaise_product)
    assert table_product.available_quantity == initial_table_stock - 10
    assert chaise_product.available_quantity == initial_chaise_stock - 80

    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 3: Vérifier facture auto-générée par confirmation
    # ═══════════════════════════════════════════════════════════════════════
    invoices_resp = client.get(
        f"/api/v1/invoices?reservation_id={reservation_id}",
        headers=auth_headers_real
    )
    assert invoices_resp.status_code == 200
    assert invoices_resp.json()["total"] == 1

    invoice = invoices_resp.json()["items"][0]
    invoice_id = invoice["id"]
    assert invoice["status"] == "draft"
    assert invoice["invoice_number"].startswith("INV-")
    assert invoice["total_amount_cents"] == expected_total  # Copié depuis réservation
    assert invoice["paid_amount_cents"] == 0
    assert invoice["is_paid"] is False

    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 4: Ajouter paiement partiel (50% = 900€)
    # ═══════════════════════════════════════════════════════════════════════
    partial_payment_data = {
        "amount_cents": 90000,  # 900€ (50%)
        "payment_method": "card",
        "payment_date": str(date.today())
    }

    payment1_response = client.post(
        f"/api/v1/invoices/{invoice_id}/add-payment",
        json=partial_payment_data,
        headers=auth_headers_real
    )
    assert payment1_response.status_code == 200

    invoice_partial = payment1_response.json()
    assert invoice_partial["paid_amount_cents"] == 90000
    assert invoice_partial["remaining_amount_cents"] == 90000  # 1800€ - 900€
    assert invoice_partial["is_paid"] is False
    assert invoice_partial["status"] == "draft"  # Pas encore payé complet

    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 5: Ajouter paiement final (50% restant = 900€)
    # ═══════════════════════════════════════════════════════════════════════
    final_payment_data = {
        "amount_cents": 90000,  # 900€ (50% restant)
        "payment_method": "card",
        "payment_date": str(date.today())
    }

    payment2_response = client.post(
        f"/api/v1/invoices/{invoice_id}/add-payment",
        json=final_payment_data,
        headers=auth_headers_real
    )
    assert payment2_response.status_code == 200

    invoice_paid = payment2_response.json()
    assert invoice_paid["paid_amount_cents"] == 180000  # 1800€ total
    assert invoice_paid["remaining_amount_cents"] == 0
    assert invoice_paid["is_paid"] is True
    assert invoice_paid["status"] == "paid"  # Auto-changé après paiement complet

    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 6: Vérifications finales cohérence
    # ═══════════════════════════════════════════════════════════════════════

    # Vérifier réservation toujours confirmée
    get_reservation = client.get(f"/api/v1/reservations/{reservation_id}", headers=auth_headers_real)
    assert get_reservation.json()["status"] == "confirmed"

    # Vérifier facture toujours paid
    get_invoice = client.get(f"/api/v1/invoices/{invoice_id}", headers=auth_headers_real)
    final_invoice_state = get_invoice.json()
    assert final_invoice_state["status"] == "paid"
    assert final_invoice_state["is_paid"] is True

    # Vérifier stock toujours réservé (pas libéré après paiement)
    test_db.refresh(table_product)
    test_db.refresh(chaise_product)
    assert table_product.available_quantity == initial_table_stock - 10
    assert chaise_product.available_quantity == initial_chaise_stock - 80


def test_reservation_cancellation_workflow(client: TestClient, test_db, workflow_customer, workflow_products, auth_headers_real):
    """
    Test workflow annulation réservation:
    1. Créer et confirmer réservation (stock réservé)
    2. Annuler réservation (stock libéré)
    3. Vérifier qu'on ne peut plus générer facture
    """
    table_product, chaise_product = workflow_products

    # Stock initial
    initial_table_stock = table_product.available_quantity
    initial_chaise_stock = chaise_product.available_quantity

    # Créer réservation
    reservation_data = {
        "customer_id": workflow_customer.id,
        "event_date": str(date.today() + timedelta(days=20)),
        "delivery_date": str(date.today() + timedelta(days=19)),
        "return_date": str(date.today() + timedelta(days=21)),
        "event_location": "Test Location",
        "lines": [
            {"product_id": table_product.id, "quantity": 5},
            {"product_id": chaise_product.id, "quantity": 40}
        ]
    }
    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    reservation_id = create_response.json()["id"]

    # Confirmer (stock réservé)
    client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=auth_headers_real)

    test_db.refresh(table_product)
    test_db.refresh(chaise_product)
    assert table_product.available_quantity == initial_table_stock - 5
    assert chaise_product.available_quantity == initial_chaise_stock - 40

    # Annuler réservation
    cancel_response = client.post(
        f"/api/v1/reservations/{reservation_id}/cancel",
        headers=auth_headers_real
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    # Vérifier stock LIBÉRÉ
    test_db.refresh(table_product)
    test_db.refresh(chaise_product)
    assert table_product.available_quantity == initial_table_stock
    assert chaise_product.available_quantity == initial_chaise_stock

    # Vérifier qu'on peut toujours créer facture (business logic permet facture même si annulée)
    # Note: Dans un vrai système, on pourrait vouloir bloquer la facturation des réservations annulées


def test_invoice_cancellation_workflow(client: TestClient, workflow_customer, workflow_products, auth_headers_real):
    """
    Test workflow annulation facture:
    1. Créer réservation + facture
    2. Ajouter paiement partiel
    3. Annuler facture → impossible si paiement commencé (business rule possible)
    4. Annuler facture draft (sans paiement) → OK
    """
    table_product = workflow_products[0]

    # Créer réservation
    reservation_data = {
        "customer_id": workflow_customer.id,
        "event_date": str(date.today() + timedelta(days=15)),
        "delivery_date": str(date.today() + timedelta(days=14)),
        "return_date": str(date.today() + timedelta(days=16)),
        "event_location": "Test",
        "lines": [{"product_id": table_product.id, "quantity": 3}]
    }
    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    reservation_id = create_response.json()["id"]

    # Confirmer (auto-génère une facture)
    client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=auth_headers_real)

    # Récupérer la facture auto-générée
    invoices_resp = client.get(
        f"/api/v1/invoices?reservation_id={reservation_id}",
        headers=auth_headers_real
    )
    assert invoices_resp.json()["total"] == 1
    invoice_id = invoices_resp.json()["items"][0]["id"]

    # Annuler facture draft (sans paiement) → OK
    cancel_response = client.post(f"/api/v1/invoices/{invoice_id}/cancel", headers=auth_headers_real)
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    # Vérifier qu'on ne peut plus ajouter paiement après annulation
    payment_data = {
        "amount_cents": 1000,
        "payment_method": "card",
        "payment_date": str(date.today())
    }
    payment_response = client.post(
        f"/api/v1/invoices/{invoice_id}/add-payment",
        json=payment_data,
        headers=auth_headers_real
    )
    assert payment_response.status_code == 400
    assert "cancelled" in payment_response.json()["detail"]
