"""Tests unitaires des modèles Phase 2 - CaroCorp."""
import pytest
from datetime import date, timedelta
from sqlalchemy.exc import IntegrityError
from app.models import Customer, Product, Reservation, ReservationLine, Invoice


class TestCustomerModel:
    """Tests du modèle Customer."""

    def test_create_individual_customer(self, test_db):
        """Test création client particulier."""
        customer = Customer(
            tenant_id=1,
            customer_type="individual",
            first_name="Marie",
            last_name="Dupont",
            email="marie.dupont@example.com",
            phone="0601020304"
        )
        test_db.add(customer)
        test_db.commit()

        assert customer.id is not None
        assert customer.display_name == "Marie Dupont"
        assert customer.is_active is True

    def test_create_company_customer(self, test_db):
        """Test création client entreprise."""
        customer = Customer(
            tenant_id=1,
            customer_type="company",
            company_name="EventCo SAS",
            email="contact@eventco.fr",
            phone="0143000000"
        )
        test_db.add(customer)
        test_db.commit()

        assert customer.id is not None
        assert customer.display_name == "EventCo SAS"

    def test_customer_type_invalid(self, test_db):
        """Test contrainte CHECK customer_type valide."""
        customer = Customer(
            tenant_id=1,
            customer_type="autre",  # Invalide
            company_name="Test Company",  # Fournir company_name pour éviter check_data_coherence
            email="test@example.com"
        )
        test_db.add(customer)

        # Accepte check_customer_type_valid OU check_customer_data_coherence (ordre indéterminé)
        with pytest.raises(IntegrityError, match="(check_customer_type_valid|check_customer_data_coherence)"):
            test_db.commit()

    def test_customer_data_coherence_individual(self, test_db):
        """Test contrainte CHECK cohérence données individual."""
        customer = Customer(
            tenant_id=1,
            customer_type="individual",
            # Manque first_name et last_name
            email="test@example.com"
        )
        test_db.add(customer)

        with pytest.raises(IntegrityError, match="check_customer_data_coherence"):
            test_db.commit()

    def test_customer_data_coherence_company(self, test_db):
        """Test contrainte CHECK cohérence données company."""
        customer = Customer(
            tenant_id=1,
            customer_type="company",
            # Manque company_name
            email="test@example.com"
        )
        test_db.add(customer)

        with pytest.raises(IntegrityError, match="check_customer_data_coherence"):
            test_db.commit()

    def test_customer_email_unique_per_tenant(self, test_db):
        """Test contrainte UNIQUE email par tenant."""
        customer1 = Customer(
            tenant_id=1,
            customer_type="individual",
            first_name="Alice",
            last_name="Martin",
            email="alice@example.com"
        )
        test_db.add(customer1)
        test_db.commit()

        # Même email, même tenant → erreur
        customer2 = Customer(
            tenant_id=1,
            customer_type="individual",
            first_name="Bob",
            last_name="Durand",
            email="alice@example.com"
        )
        test_db.add(customer2)

        with pytest.raises(IntegrityError, match="uq_customer_tenant_email"):
            test_db.commit()

    def test_customer_soft_delete(self, test_db):
        """Test suppression logique."""
        customer = Customer(
            tenant_id=1,
            customer_type="individual",
            first_name="Test",
            last_name="Delete",
            email="delete@example.com"
        )
        test_db.add(customer)
        test_db.commit()

        assert customer.is_active is True

        customer.soft_delete()
        test_db.commit()

        assert customer.is_active is False

        customer.restore()
        test_db.commit()

        assert customer.is_active is True


class TestProductModel:
    """Tests du modèle Product."""

    def test_create_product(self, test_db):
        """Test création produit."""
        product = Product(
            tenant_id=1,
            name="Assiette plate blanche 28cm",
            sku="ASS-PLATE-28-WHI",
            category="assiette",
            price_per_day=250,  # 2.50€
            deposit_amount=500,  # 5€
            stock_quantity=100,
            available_quantity=100,
            condition="neuf"
        )
        test_db.add(product)
        test_db.commit()

        assert product.id is not None
        assert product.price_per_day == 250
        assert product.deposit_amount == 500

    def test_product_category_invalid(self, test_db):
        """Test contrainte CHECK category valide."""
        product = Product(
            tenant_id=1,
            name="Test",
            sku="TEST-001",
            category="invalide",  # Invalide
            price_per_day=100,
            stock_quantity=10,
            available_quantity=10
        )
        test_db.add(product)

        with pytest.raises(IntegrityError, match="check_product_category_valid"):
            test_db.commit()

    def test_product_available_lte_stock(self, test_db):
        """Test contrainte CHECK available_quantity <= stock_quantity."""
        product = Product(
            tenant_id=1,
            name="Test Product",
            sku="TEST-002",
            category="verre",
            price_per_day=100,
            stock_quantity=50,
            available_quantity=60  # > stock_quantity → erreur
        )
        test_db.add(product)

        with pytest.raises(IntegrityError, match="check_product_available_lte_stock"):
            test_db.commit()

    def test_product_price_positive(self, test_db):
        """Test contrainte CHECK price_per_day >= 0."""
        product = Product(
            tenant_id=1,
            name="Test",
            sku="TEST-003",
            category="couvert",
            price_per_day=-100,  # Négatif → erreur
            stock_quantity=10,
            available_quantity=10
        )
        test_db.add(product)

        with pytest.raises(IntegrityError, match="check_product_price_positive"):
            test_db.commit()

    def test_product_sku_unique_per_tenant(self, test_db):
        """Test contrainte UNIQUE sku par tenant."""
        product1 = Product(
            tenant_id=1,
            name="Produit 1",
            sku="UNIQUE-SKU",
            category="nappe",
            price_per_day=100,
            stock_quantity=10,
            available_quantity=10
        )
        test_db.add(product1)
        test_db.commit()

        # Même SKU, même tenant → erreur
        product2 = Product(
            tenant_id=1,
            name="Produit 2",
            sku="UNIQUE-SKU",
            category="deco",
            price_per_day=200,
            stock_quantity=5,
            available_quantity=5
        )
        test_db.add(product2)

        with pytest.raises(IntegrityError, match="uq_product_tenant_sku"):
            test_db.commit()


class TestReservationModel:
    """Tests du modèle Reservation."""

    def test_create_reservation(self, test_db):
        """Test création réservation complète."""
        # Créer customer
        customer = Customer(
            tenant_id=1,
            customer_type="individual",
            first_name="Jean",
            last_name="Pierre",
            email="jean.pierre@example.com"
        )
        test_db.add(customer)
        test_db.flush()

        # Créer réservation
        today = date.today()
        reservation = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="RES-2026-0001",
            event_date=today + timedelta(days=7),
            delivery_date=today + timedelta(days=6),
            return_date=today + timedelta(days=8),
            event_location="Salle des Fêtes Paris",
            total_amount=15000,  # 150€
            deposit_amount=5000  # 50€
        )
        test_db.add(reservation)
        test_db.commit()

        assert reservation.id is not None
        assert reservation.status == "draft"
        assert reservation.deposit_paid is False

    def test_reservation_delivery_before_event(self, test_db):
        """Test contrainte CHECK delivery_date <= event_date."""
        customer = Customer(
            tenant_id=1,
            customer_type="individual",
            first_name="Test",
            last_name="User",
            email="test@example.com"
        )
        test_db.add(customer)
        test_db.flush()

        today = date.today()
        reservation = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="RES-TEST-001",
            event_date=today,
            delivery_date=today + timedelta(days=1),  # Après event → erreur
            return_date=today + timedelta(days=2)
        )
        test_db.add(reservation)

        with pytest.raises(IntegrityError, match="check_reservation_delivery_before_event"):
            test_db.commit()

    def test_reservation_return_after_event(self, test_db):
        """Test contrainte CHECK return_date >= event_date."""
        customer = Customer(
            tenant_id=1,
            customer_type="individual",
            first_name="Test",
            last_name="User",
            email="test2@example.com"
        )
        test_db.add(customer)
        test_db.flush()

        today = date.today()
        reservation = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="RES-TEST-002",
            event_date=today + timedelta(days=5),
            delivery_date=today,
            return_date=today + timedelta(days=2)  # Avant event → erreur
        )
        test_db.add(reservation)

        with pytest.raises(IntegrityError, match="check_reservation_return_after_event"):
            test_db.commit()


class TestReservationLineModel:
    """Tests du modèle ReservationLine."""

    def test_create_reservation_line(self, test_db):
        """Test création ligne de réservation."""
        # Setup customer, product, reservation
        customer = Customer(
            tenant_id=1,
            customer_type="individual",
            first_name="Line",
            last_name="Test",
            email="line.test@example.com"
        )
        test_db.add(customer)
        test_db.flush()

        product = Product(
            tenant_id=1,
            name="Verre à vin",
            sku="VERRE-VIN-001",
            category="verre",
            price_per_day=150,
            stock_quantity=200,
            available_quantity=200
        )
        test_db.add(product)
        test_db.flush()

        today = date.today()
        reservation = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="RES-LINE-001",
            event_date=today + timedelta(days=10),
            delivery_date=today + timedelta(days=9),
            return_date=today + timedelta(days=11)
        )
        test_db.add(reservation)
        test_db.flush()

        # Créer ligne
        line = ReservationLine(
            tenant_id=1,
            reservation_id=reservation.id,
            product_id=product.id,
            quantity=50,
            unit_price=150,
            subtotal=7500  # 50 × 150
        )
        test_db.add(line)
        test_db.commit()

        assert line.id is not None
        assert line.quantity == 50
        assert line.subtotal == 7500

    def test_reservation_line_quantity_positive(self, test_db):
        """Test contrainte CHECK quantity > 0."""
        customer = Customer(
            tenant_id=1,
            customer_type="individual",
            first_name="Qty",
            last_name="Test",
            email="qty.test@example.com"
        )
        test_db.add(customer)
        test_db.flush()

        product = Product(
            tenant_id=1,
            name="Test Product",
            sku="QTY-001",
            category="autre",
            price_per_day=100,
            stock_quantity=10,
            available_quantity=10
        )
        test_db.add(product)
        test_db.flush()

        today = date.today()
        reservation = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="RES-QTY-001",
            event_date=today + timedelta(days=5),
            delivery_date=today + timedelta(days=4),
            return_date=today + timedelta(days=6)
        )
        test_db.add(reservation)
        test_db.flush()

        line = ReservationLine(
            tenant_id=1,
            reservation_id=reservation.id,
            product_id=product.id,
            quantity=0,  # Invalid
            unit_price=100,
            subtotal=0
        )
        test_db.add(line)

        with pytest.raises(IntegrityError, match="check_reservation_line_quantity_positive"):
            test_db.commit()


class TestInvoiceModel:
    """Tests du modèle Invoice."""

    def test_create_invoice(self, test_db):
        """Test création facture."""
        customer = Customer(
            tenant_id=1,
            customer_type="company",
            company_name="Test Company",
            email="invoice.test@example.com"
        )
        test_db.add(customer)
        test_db.flush()

        today = date.today()
        reservation = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="RES-INV-001",
            event_date=today + timedelta(days=14),
            delivery_date=today + timedelta(days=13),
            return_date=today + timedelta(days=15),
            total_amount=25000
        )
        test_db.add(reservation)
        test_db.flush()

        invoice = Invoice(
            tenant_id=1,
            reservation_id=reservation.id,
            invoice_number="INV-2026-0001",
            issue_date=today,
            due_date=today + timedelta(days=30),
            total_amount=25000
        )
        test_db.add(invoice)
        test_db.commit()

        assert invoice.id is not None
        assert invoice.is_paid is False
        assert invoice.remaining_amount == 25000

    def test_invoice_is_paid_property(self, test_db):
        """Test property is_paid."""
        customer = Customer(
            tenant_id=1,
            customer_type="individual",
            first_name="Paid",
            last_name="Test",
            email="paid.test@example.com"
        )
        test_db.add(customer)
        test_db.flush()

        today = date.today()
        reservation = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="RES-PAID-001",
            event_date=today + timedelta(days=7),
            delivery_date=today + timedelta(days=6),
            return_date=today + timedelta(days=8)
        )
        test_db.add(reservation)
        test_db.flush()

        invoice = Invoice(
            tenant_id=1,
            reservation_id=reservation.id,
            invoice_number="INV-PAID-001",
            issue_date=today,
            due_date=today + timedelta(days=15),
            total_amount=10000,
            paid_amount=10000  # Payé en totalité
        )
        test_db.add(invoice)
        test_db.commit()

        assert invoice.is_paid is True
        assert invoice.remaining_amount == 0

    def test_invoice_paid_lte_total(self, test_db):
        """Test contrainte CHECK paid_amount <= total_amount."""
        customer = Customer(
            tenant_id=1,
            customer_type="individual",
            first_name="Over",
            last_name="Paid",
            email="over.paid@example.com"
        )
        test_db.add(customer)
        test_db.flush()

        today = date.today()
        reservation = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="RES-OVER-001",
            event_date=today + timedelta(days=7),
            delivery_date=today + timedelta(days=6),
            return_date=today + timedelta(days=8)
        )
        test_db.add(reservation)
        test_db.flush()

        invoice = Invoice(
            tenant_id=1,
            reservation_id=reservation.id,
            invoice_number="INV-OVER-001",
            issue_date=today,
            due_date=today + timedelta(days=15),
            total_amount=10000,
            paid_amount=15000  # > total → erreur
        )
        test_db.add(invoice)

        with pytest.raises(IntegrityError, match="check_invoice_paid_lte_total"):
            test_db.commit()

    def test_invoice_due_after_issue(self, test_db):
        """Test contrainte CHECK due_date >= issue_date."""
        customer = Customer(
            tenant_id=1,
            customer_type="individual",
            first_name="Date",
            last_name="Test",
            email="date.test@example.com"
        )
        test_db.add(customer)
        test_db.flush()

        today = date.today()
        reservation = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="RES-DATE-001",
            event_date=today + timedelta(days=7),
            delivery_date=today + timedelta(days=6),
            return_date=today + timedelta(days=8)
        )
        test_db.add(reservation)
        test_db.flush()

        invoice = Invoice(
            tenant_id=1,
            reservation_id=reservation.id,
            invoice_number="INV-DATE-001",
            issue_date=today,
            due_date=today - timedelta(days=10),  # Avant issue → erreur
            total_amount=5000
        )
        test_db.add(invoice)

        with pytest.raises(IntegrityError, match="check_invoice_due_after_issue"):
            test_db.commit()
