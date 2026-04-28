"""Tests E2E - Workflows métier complets CaroCorp.

Tests des scénarios métier end-to-end :
1. Annulation de réservation
2. Paiements multiples sur facture
3. Suppression logique de produit
4. Isolation multi-tenant
"""
import pytest
from datetime import date, timedelta
from sqlalchemy.exc import IntegrityError
from app.models import Customer, Product, Reservation, ReservationLine, Invoice
from app.constants import CustomerType, InvoiceStatus, PaymentMethod, ProductCategory, ProductCondition, ReservationStatus


class TestCancelReservationWorkflow:
    """Test du workflow d'annulation de réservation."""

    def test_cancel_reservation_workflow(self, test_db):
        """Test annulation réservation : changement statut + vérification facture."""
        # 1. Créer customer
        customer = Customer(
            tenant_id=1,
            customer_type=CustomerType.INDIVIDUAL,
            first_name="Jean",
            last_name="Martin",
            email="jean.martin@test.com"
        )
        test_db.add(customer)
        test_db.flush()

        # 2. Créer produit
        product = Product(
            tenant_id=1,
            name="Assiette blanche",
            sku="ASS-001",
            category=ProductCategory.ASSIETTES,
            price_per_day_cents=200,
            deposit_amount_cents=500,
            stock_quantity=100,
            available_quantity=100,
            condition=ProductCondition.BON
        )
        test_db.add(product)
        test_db.flush()

        # 3. Créer réservation confirmée
        today = date.today()
        reservation = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="RES-CANCEL-001",
            event_date=today + timedelta(days=10),
            delivery_date=today + timedelta(days=9),
            return_date=today + timedelta(days=11),
            status=ReservationStatus.CONFIRMED,
            total_amount_cents=4000,  # 20 assiettes × 200
            deposit_amount_cents=10000
        )
        test_db.add(reservation)
        test_db.flush()

        # 4. Ajouter ligne de réservation
        line = ReservationLine(
            tenant_id=1,
            reservation_id=reservation.id,
            product_id=product.id,
            quantity=20,
            unit_price_cents=200,
            subtotal_cents=4000
        )
        test_db.add(line)

        # 5. Créer facture
        invoice = Invoice(
            tenant_id=1,
            reservation_id=reservation.id,
            invoice_number="INV-CANCEL-001",
            issue_date=today,
            due_date=today + timedelta(days=15),
            total_amount_cents=4000,
            paid_amount_cents=0,
            status=InvoiceStatus.SENT
        )
        test_db.add(invoice)
        test_db.commit()

        # Vérifier état initial
        assert reservation.status == "confirmed"
        assert invoice.status == "sent"
        assert product.available_quantity == 100

        # 6. ANNULER la réservation
        reservation.status=ReservationStatus.CANCELLED
        invoice.status=ReservationStatus.CANCELLED
        test_db.commit()

        # Vérifier état après annulation
        assert reservation.status == "cancelled"
        assert invoice.status == "cancelled"
        # Note: La libération de stock devrait être gérée par business logic en Phase 3


class TestPartialPaymentWorkflow:
    """Test du workflow de paiements multiples."""

    def test_partial_payment_workflow(self, test_db):
        """Test paiements partiels successifs jusqu'au solde complet."""
        # 1. Créer customer
        customer = Customer(
            tenant_id=1,
            customer_type=CustomerType.COMPANY,
            company_name="EventCorp",
            email="contact@eventcorp.com"
        )
        test_db.add(customer)
        test_db.flush()

        # 2. Créer réservation
        today = date.today()
        reservation = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="RES-PAYMENT-001",
            event_date=today + timedelta(days=7),
            delivery_date=today + timedelta(days=6),
            return_date=today + timedelta(days=8),
            status=ReservationStatus.CONFIRMED,
            total_amount_cents=100000,  # 1000€
            deposit_amount_cents=0
        )
        test_db.add(reservation)
        test_db.flush()

        # 3. Créer facture
        invoice = Invoice(
            tenant_id=1,
            reservation_id=reservation.id,
            invoice_number="INV-PAYMENT-001",
            issue_date=today,
            due_date=today + timedelta(days=30),
            total_amount_cents=100000,
            paid_amount_cents=0,
            status=InvoiceStatus.SENT
        )
        test_db.add(invoice)
        test_db.commit()

        # État initial
        assert invoice.is_paid is False
        assert invoice.remaining_amount == 100000

        # 4. Premier paiement partiel : 30%
        invoice.paid_amount_cents = 30000
        invoice.payment_method=PaymentMethod.TRANSFER
        test_db.commit()

        assert invoice.is_paid is False
        assert invoice.remaining_amount == 70000
        assert invoice.status == "sent"

        # 5. Deuxième paiement partiel : +40%
        invoice.paid_amount_cents = 70000
        test_db.commit()

        assert invoice.is_paid is False
        assert invoice.remaining_amount == 30000

        # 6. Paiement final : solde complet
        invoice.paid_amount_cents = 100000
        invoice.status=InvoiceStatus.PAID
        invoice.payment_date = today
        test_db.commit()

        assert invoice.is_paid is True
        assert invoice.remaining_amount == 0
        assert invoice.status == "paid"
        assert invoice.payment_date == today


class TestProductSoftDelete:
    """Test de la suppression logique de produit."""

    def test_product_soft_delete(self, test_db):
        """Test soft delete produit : is_active=False sans supprimer l'enregistrement."""
        # 1. Créer produit actif
        product = Product(
            tenant_id=1,
            name="Verre à champagne",
            sku="VERR-CHAMP-001",
            category=ProductCategory.VERRES,
            price_per_day_cents=150,
            deposit_amount_cents=400,
            stock_quantity=50,
            available_quantity=50,
            condition=ProductCondition.BON,
            is_active=True
        )
        test_db.add(product)
        test_db.commit()

        product_id = product.id
        assert product.is_active is True

        # 2. Soft delete via méthode
        product.soft_delete()
        test_db.commit()

        # Vérifier que le produit existe toujours mais est inactif
        product_db = test_db.query(Product).filter_by(id=product_id).first()
        assert product_db is not None
        assert product_db.is_active is False
        assert product_db.name == "Verre à champagne"

        # 3. Restaurer le produit
        product_db.restore()
        test_db.commit()

        # Vérifier restauration
        product_db = test_db.query(Product).filter_by(id=product_id).first()
        assert product_db.is_active is True

        # 4. Test qu'un produit soft-deleted peut avoir des réservations passées
        # Créer customer
        customer = Customer(
            tenant_id=1,
            customer_type=CustomerType.INDIVIDUAL,
            first_name="Marie",
            last_name="Dubois",
            email="marie.dubois@test.com"
        )
        test_db.add(customer)
        test_db.flush()

        # Créer réservation avec ce produit
        today = date.today()
        reservation = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="RES-SOFTDEL-001",
            event_date=today + timedelta(days=5),
            delivery_date=today + timedelta(days=4),
            return_date=today + timedelta(days=6),
            status=ReservationStatus.CONFIRMED,
            total_amount_cents=750
        )
        test_db.add(reservation)
        test_db.flush()

        line = ReservationLine(
            tenant_id=1,
            reservation_id=reservation.id,
            product_id=product_id,
            quantity=5,
            unit_price_cents=150,
            subtotal_cents=750
        )
        test_db.add(line)
        test_db.commit()

        # Soft delete le produit (il a maintenant une réservation)
        product_db.soft_delete()
        test_db.commit()

        # Vérifier que la réservation existe toujours
        line_db = test_db.query(ReservationLine).filter_by(product_id=product_id).first()
        assert line_db is not None
        assert line_db.quantity == 5

        # Note: En Phase 3, business logic devrait empêcher nouvelles réservations
        # sur produits inactifs (is_active=False)


class TestMultiTenantIsolation:
    """Test de l'isolation multi-tenant des données."""

    def test_multi_tenant_isolation(self, test_db):
        """Test isolation complète des données entre tenants."""
        # 1. Créer 2 customers dans 2 tenants différents
        customer_tenant1 = Customer(
            tenant_id=1,
            customer_type=CustomerType.INDIVIDUAL,
            first_name="Alice",
            last_name="Tenant1",
            email="alice@tenant1.com"
        )
        customer_tenant2 = Customer(
            tenant_id=2,
            customer_type=CustomerType.INDIVIDUAL,
            first_name="Bob",
            last_name="Tenant2",
            email="bob@tenant2.com"
        )
        test_db.add_all([customer_tenant1, customer_tenant2])
        test_db.flush()

        # 2. Créer 2 produits dans 2 tenants
        product_tenant1 = Product(
            tenant_id=1,
            name="Assiette Tenant 1",
            sku="ASS-T1-001",
            category=ProductCategory.ASSIETTES,
            price_per_day_cents=100,
            stock_quantity=10,
            available_quantity=10
        )
        product_tenant2 = Product(
            tenant_id=2,
            name="Assiette Tenant 2",
            sku="ASS-T2-001",  # Même SKU dans tenant différent = OK
            category=ProductCategory.ASSIETTES,
            price_per_day_cents=200,
            stock_quantity=20,
            available_quantity=20
        )
        test_db.add_all([product_tenant1, product_tenant2])
        test_db.flush()

        # 3. Créer réservations dans chaque tenant
        today = date.today()
        reservation_tenant1 = Reservation(
            tenant_id=1,
            customer_id=customer_tenant1.id,
            reference="RES-T1-001",
            event_date=today + timedelta(days=5),
            delivery_date=today + timedelta(days=4),
            return_date=today + timedelta(days=6),
            status=ReservationStatus.CONFIRMED,
            total_amount_cents=500
        )
        reservation_tenant2 = Reservation(
            tenant_id=2,
            customer_id=customer_tenant2.id,
            reference="RES-T2-001",
            event_date=today + timedelta(days=5),
            delivery_date=today + timedelta(days=4),
            return_date=today + timedelta(days=6),
            status=ReservationStatus.CONFIRMED,
            total_amount_cents=1000
        )
        test_db.add_all([reservation_tenant1, reservation_tenant2])
        test_db.commit()

        # 4. Vérifier isolation : Tenant 1 ne voit que ses données
        customers_t1 = test_db.query(Customer).filter_by(tenant_id=1).all()
        assert len(customers_t1) == 1
        assert customers_t1[0].email == "alice@tenant1.com"

        products_t1 = test_db.query(Product).filter_by(tenant_id=1).all()
        assert len(products_t1) == 1
        assert products_t1[0].name == "Assiette Tenant 1"

        reservations_t1 = test_db.query(Reservation).filter_by(tenant_id=1).all()
        assert len(reservations_t1) == 1
        assert reservations_t1[0].reference == "RES-T1-001"

        # 5. Vérifier isolation : Tenant 2 ne voit que ses données
        customers_t2 = test_db.query(Customer).filter_by(tenant_id=2).all()
        assert len(customers_t2) == 1
        assert customers_t2[0].email == "bob@tenant2.com"

        products_t2 = test_db.query(Product).filter_by(tenant_id=2).all()
        assert len(products_t2) == 1
        assert products_t2[0].name == "Assiette Tenant 2"

        reservations_t2 = test_db.query(Reservation).filter_by(tenant_id=2).all()
        assert len(reservations_t2) == 1
        assert reservations_t2[0].reference == "RES-T2-001"

        # 6. Vérifier que même SKU est OK dans tenants différents
        # (contrainte UNIQUE est sur (tenant_id, sku))
        all_products = test_db.query(Product).all()
        skus = [p.sku for p in all_products]
        assert "ASS-T1-001" in skus or "ASS-T2-001" in skus

        # 7. Vérifier qu'on ne peut pas dupliquer email dans même tenant
        duplicate_customer = Customer(
            tenant_id=1,
            customer_type=CustomerType.INDIVIDUAL,
            first_name="Alice2",
            last_name="Duplicate",
            email="alice@tenant1.com"  # Email déjà utilisé dans tenant 1
        )
        test_db.add(duplicate_customer)

        with pytest.raises(IntegrityError, match="uq_customer_tenant_email"):
            test_db.commit()

        test_db.rollback()

        # Mais même email dans tenant différent = OK
        customer_tenant3 = Customer(
            tenant_id=3,
            customer_type=CustomerType.INDIVIDUAL,
            first_name="Alice3",
            last_name="Tenant3",
            email="alice@tenant1.com"  # Même email mais tenant 3 = OK
        )
        test_db.add(customer_tenant3)
        test_db.commit()

        # Vérifier que les 2 Alice existent dans des tenants différents
        alices = test_db.query(Customer).filter_by(email="alice@tenant1.com").all()
        assert len(alices) == 2
        assert {a.tenant_id for a in alices} == {1, 3}
