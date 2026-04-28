#!/usr/bin/env python3
"""Seed données démo Marveline — idempotent, dates relatives à l'exécution.

Usage (Docker) :
    docker compose exec -T api python scripts/demo/seed_marveline_demo.py

Usage (local) :
    python3 scripts/demo/seed_marveline_demo.py

Crée 4 clients, 4 réservations, 3 factures, cautions, paiements et StockItems
pour la démo commerciale Marveline Mobile.

Script idempotent : les clients et produits démo sont créés ou récupérés,
les réservations démo sont supprimées et recréées à chaque exécution pour
maintenir des dates relatives fraîches.
"""

import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.database import get_db_context
from app.core.security import get_password_hash
from app.models.account import Account
from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership
from app.models.customer import Customer
from app.models.product import Product
from app.models.reservation import Reservation, ReservationLine
from app.models.invoice import Invoice
from app.models.invoice_charge import InvoiceCharge
from app.models.payment import Payment
from app.models.deposit import Deposit
from app.models.stock_item import StockItem

TENANT_ID = 1
TODAY = date.today()

DEMO_USER_EMAIL = "demo@marveline.fr"
DEMO_USER_PASSWORD = "DemoMarveline2026!"

DEMO_REFS = ["DEMO-EV001", "DEMO-EV002", "DEMO-EV003", "DEMO-EV004"]
DEMO_INV_NUMBERS = ["DEMO-INV001", "DEMO-INV002", "DEMO-INV003"]

DEMO_SKU_COUVERT = "DEMO-COV-LUX"
DEMO_SKU_CHAISE = "DEMO-CHR-CHV"
DEMO_SKU_SONO = "DEMO-SON-PRO"


def _eur(eur: float) -> int:
    return int(round(eur * 100))


def _rental_days(delivery_date: date, return_date: date) -> int:
    """Jours de location inclusifs : départ + retour compris (même convention
    que le frontend `rental_days`)."""
    return max((return_date - delivery_date).days + 1, 1)


def _line_subtotal(quantity: int, unit_price_cents: int, days: int) -> int:
    """Sous-total d'une ligne = quantité × prix unitaire × jours de location."""
    return quantity * unit_price_cents * days


def _cleanup_demo(db) -> None:
    """Supprime les données démo existantes dans le bon ordre FK."""
    demo_reservations = (
        db.query(Reservation)
        .filter(Reservation.tenant_id == TENANT_ID, Reservation.reference.in_(DEMO_REFS))
        .all()
    )
    if not demo_reservations:
        print("  -> Aucune donnée démo existante.")
        return

    res_ids = [r.id for r in demo_reservations]
    demo_invoices = db.query(Invoice).filter(Invoice.reservation_id.in_(res_ids)).all()
    inv_ids = [i.id for i in demo_invoices]

    # 1. Paiements et charges (FK sur factures)
    if inv_ids:
        db.query(Payment).filter(
            Payment.invoice_id.in_(inv_ids)
        ).delete(synchronize_session=False)
        db.query(InvoiceCharge).filter(
            InvoiceCharge.invoice_id.in_(inv_ids)
        ).delete(synchronize_session=False)

    # 2. Factures
    for inv in demo_invoices:
        db.delete(inv)
    db.flush()

    # 3. Cautions (FK RESTRICT sur reservation)
    db.query(Deposit).filter(
        Deposit.reservation_id.in_(res_ids)
    ).delete(synchronize_session=False)
    db.flush()

    # 4. Réservations (cascade sur reservation_lines)
    for res in demo_reservations:
        db.delete(res)
    db.flush()

    print(f"  -> Nettoyage : {len(demo_reservations)} réservations, {len(demo_invoices)} factures supprimées.")


def _get_or_create_user(db) -> None:
    """Crée le compte démo (Account + TenantMembership IAM v2) si absent."""
    import uuid

    # S'assurer que le tenant existe
    tenant = db.query(Tenant).filter(Tenant.id == TENANT_ID).first()
    if not tenant:
        tenant = Tenant(
            external_id=str(uuid.uuid4()),
            name="Marveline Demo",
            domain="marveline.fr",
            contact_email=DEMO_USER_EMAIL,
            app_code="marveline",
            status="active",
            is_active=True,
        )
        db.add(tenant)
        db.flush()

    account = db.query(Account).filter(Account.email == DEMO_USER_EMAIL).first()
    if account:
        print(f"  -> User démo existant : {DEMO_USER_EMAIL}")
        return

    account = Account(
        email=DEMO_USER_EMAIL,
        hashed_password=get_password_hash(DEMO_USER_PASSWORD),
        first_name="Demo",
        last_name="Marveline",
        is_active=True,
    )
    db.add(account)
    db.flush()

    membership = TenantMembership(
        account_id=account.id,
        tenant_id=tenant.id,
        role_name="tenant_admin",
        status="active",
    )
    db.add(membership)
    db.flush()
    print(f"  -> User démo créé : {DEMO_USER_EMAIL} / {DEMO_USER_PASSWORD}")


def _get_or_create_customers(db) -> dict:
    """Crée les 4 clients démo si absents."""
    customers_data = [
        {
            "email": "marie.dupont@gmail.com",
            "customer_type": "individual",
            "first_name": "Marie",
            "last_name": "Dupont",
            "phone": "06 12 34 56 78",
            "address": "15 allée des Roses",
            "city": "Creil",
            "postal_code": "60100",
        },
        {
            "email": "rh@techcorp.fr",
            "customer_type": "company",
            "company_name": "TechCorp Solutions",
            "phone": "01 23 45 67 89",
            "city": "Paris",
            "postal_code": "75001",
        },
        {
            "email": "famille.lebrun@gmail.com",
            "customer_type": "individual",
            "first_name": "Jean-Pierre",
            "last_name": "Lebrun",
            "phone": "06 55 44 33 22",
            "city": "Senlis",
            "postal_code": "60300",
        },
        {
            "email": "cabinet@moreau-notaires.fr",
            "customer_type": "company",
            "company_name": "Cabinet Moreau Notaires",
            "phone": "03 44 55 66 77",
            "city": "Chantilly",
            "postal_code": "60500",
        },
    ]

    result = {}
    created = 0
    for data in customers_data:
        email = data["email"]
        customer = (
            db.query(Customer)
            .filter(Customer.tenant_id == TENANT_ID, Customer.email == email)
            .first()
        )
        if not customer:
            customer = Customer(tenant_id=TENANT_ID, **data)
            db.add(customer)
            db.flush()
            created += 1
        result[email] = customer

    print(f"  -> Clients démo : {created} créés, {len(result) - created} existants.")
    return result


def _get_or_create_products(db) -> dict:
    """Crée les 3 produits démo avec les quantités cibles pour le stock tracking."""
    products_data = [
        {
            "sku": DEMO_SKU_COUVERT,
            "name": "Couvert luxe élégance",
            "category": "couverts",
            "price_per_day_cents": _eur(0.30),
            "deposit_amount_cents": 0,
            "stock_quantity": 150,
            "available_quantity": 130,
            "condition": "bon",
            "short_description": "Set couvert luxe gamme élégance — 150 unités",
        },
        {
            "sku": DEMO_SKU_CHAISE,
            "name": "Chaise Chiavari dorée",
            "category": "chaises",
            "price_per_day_cents": _eur(1.20),
            "deposit_amount_cents": 0,
            "stock_quantity": 60,
            "available_quantity": 50,
            "condition": "bon",
            "short_description": "Chaise Chiavari finition dorée — 60 unités",
        },
        {
            "sku": DEMO_SKU_SONO,
            "name": "Système sono portable",
            "category": "machines",
            "price_per_day_cents": _eur(15.00),
            "deposit_amount_cents": 0,
            "stock_quantity": 2,
            "available_quantity": 1,
            "condition": "bon",
            "short_description": "Système sono portable Bluetooth — 2 unités",
        },
    ]

    result = {}
    for data in products_data:
        sku = data["sku"]
        product = (
            db.query(Product)
            .filter(Product.tenant_id == TENANT_ID, Product.sku == sku)
            .first()
        )
        if not product:
            product = Product(tenant_id=TENANT_ID, **data)
            db.add(product)
            db.flush()
            print(f"  -> Produit créé : {product.name}")
        else:
            product.stock_quantity = data["stock_quantity"]
            product.available_quantity = data["available_quantity"]
        result[sku] = product

    return result


def _recreate_stock_items(db, products: dict, res_dupont: Reservation) -> None:
    """Supprime et recrée les StockItems des produits démo."""
    couvert = products[DEMO_SKU_COUVERT]
    chaise = products[DEMO_SKU_CHAISE]
    sono = products[DEMO_SKU_SONO]

    for prod in [couvert, chaise, sono]:
        db.query(StockItem).filter(
            StockItem.product_id == prod.id,
            StockItem.tenant_id == TENANT_ID,
        ).delete(synchronize_session=False)
    db.flush()

    # Couvert luxe : 130 available + 15 reserved (Dupont) + 5 damaged = 150
    for i in range(130):
        db.add(StockItem(
            tenant_id=TENANT_ID,
            product_id=couvert.id,
            serial_number=f"COV-LUX-{i + 1:04d}",
            status="available",
        ))
    for i in range(15):
        db.add(StockItem(
            tenant_id=TENANT_ID,
            product_id=couvert.id,
            serial_number=f"COV-LUX-{130 + i + 1:04d}",
            status="reserved",
            current_reservation_id=res_dupont.id,
        ))
    for i in range(5):
        db.add(StockItem(
            tenant_id=TENANT_ID,
            product_id=couvert.id,
            serial_number=f"COV-LUX-{145 + i + 1:04d}",
            status="damaged",
            notes="Endommagé lors d'un retour précédent",
        ))

    # Chaise Chiavari : 50 available + 10 reserved (Dupont) = 60
    for i in range(50):
        db.add(StockItem(
            tenant_id=TENANT_ID,
            product_id=chaise.id,
            serial_number=f"CHR-CHV-{i + 1:03d}",
            status="available",
        ))
    for i in range(10):
        db.add(StockItem(
            tenant_id=TENANT_ID,
            product_id=chaise.id,
            serial_number=f"CHR-CHV-{50 + i + 1:03d}",
            status="reserved",
            current_reservation_id=res_dupont.id,
        ))

    # Système sono : 1 available + 1 on_location = 2
    db.add(StockItem(
        tenant_id=TENANT_ID,
        product_id=sono.id,
        serial_number="SON-PRO-001",
        status="available",
    ))
    db.add(StockItem(
        tenant_id=TENANT_ID,
        product_id=sono.id,
        serial_number="SON-PRO-002",
        status="on_location",
        notes="Chez client Lebrun",
    ))
    db.flush()
    print(f"  -> StockItems recréés : 150 couvert + 60 chaises + 2 sono")


def seed(db) -> None:
    print("\n=== Seed Marveline Démo ===\n")

    _get_or_create_user(db)

    customers = _get_or_create_customers(db)
    dupont = customers["marie.dupont@gmail.com"]
    techcorp = customers["rh@techcorp.fr"]
    lebrun = customers["famille.lebrun@gmail.com"]
    moreau = customers["cabinet@moreau-notaires.fr"]

    products = _get_or_create_products(db)
    couvert = products[DEMO_SKU_COUVERT]
    chaise = products[DEMO_SKU_CHAISE]
    sono = products[DEMO_SKU_SONO]

    # Nettoyage avant recréation (dates fraîches)
    _cleanup_demo(db)

    # ── EV-001 : Dupont — Mariage J+7, Confirmée ──────────────────────────
    ev1_delivery = TODAY + timedelta(days=6)
    ev1_return = TODAY + timedelta(days=8)
    ev1_days = _rental_days(ev1_delivery, ev1_return)
    ev1_line1 = _line_subtotal(120, _eur(0.30), ev1_days)   # couverts
    ev1_line2 = _line_subtotal(30, _eur(1.20), ev1_days)    # chaises
    ev1_total = ev1_line1 + ev1_line2

    res_dupont = Reservation(
        tenant_id=TENANT_ID,
        customer_id=dupont.id,
        reference="DEMO-EV001",
        event_date=TODAY + timedelta(days=7),
        delivery_date=ev1_delivery,
        return_date=ev1_return,
        event_location="Domaine des Roses, Creil",
        event_type="mariage",
        event_name="Dupont - Le Grand Jour",
        guest_count=180,
        status="confirmed",
        total_amount_cents=ev1_total,
        deposit_amount_cents=_eur(500),
        deposit_paid=True,
    )
    db.add(res_dupont)
    db.flush()

    db.add(ReservationLine(
        tenant_id=TENANT_ID,
        reservation_id=res_dupont.id,
        product_id=couvert.id,
        quantity=120,
        unit_price_cents=_eur(0.30),
        subtotal_cents=ev1_line1,
    ))
    db.add(ReservationLine(
        tenant_id=TENANT_ID,
        reservation_id=res_dupont.id,
        product_id=chaise.id,
        quantity=30,
        unit_price_cents=_eur(1.20),
        subtotal_cents=ev1_line2,
    ))
    db.flush()

    # Facture DEMO-INV001 : acompte 40% déjà payé
    ev1_paid = int(round(ev1_total * 0.40))
    inv_dupont = Invoice(
        tenant_id=TENANT_ID,
        reservation_id=res_dupont.id,
        invoice_number="DEMO-INV001",
        issue_date=TODAY - timedelta(days=5),
        due_date=TODAY + timedelta(days=14),
        total_amount_cents=ev1_total,
        paid_amount_cents=ev1_paid,
        status="sent",
    )
    db.add(inv_dupont)
    db.flush()

    db.add(Payment(
        tenant_id=TENANT_ID,
        invoice_id=inv_dupont.id,
        amount_cents=ev1_paid,
        payment_method="transfer",
        payment_date=TODAY - timedelta(days=3),
        notes="Acompte 40% — virement bancaire",
    ))
    db.add(Deposit(
        tenant_id=TENANT_ID,
        reservation_id=res_dupont.id,
        amount_cents=_eur(500),
        status="held",
        collection_date=TODAY - timedelta(days=5),
        notes="Caution mariage encaissée par virement",
    ))
    db.flush()

    # ── EV-002 : TechCorp — Séminaire J+21, Brouillon ─────────────────────
    ev2_delivery = TODAY + timedelta(days=20)
    ev2_return = TODAY + timedelta(days=22)
    ev2_days = _rental_days(ev2_delivery, ev2_return)
    ev2_line1 = _line_subtotal(50, _eur(1.20), ev2_days)    # chaises
    ev2_total = ev2_line1

    res_techcorp = Reservation(
        tenant_id=TENANT_ID,
        customer_id=techcorp.id,
        reference="DEMO-EV002",
        event_date=TODAY + timedelta(days=21),
        delivery_date=ev2_delivery,
        return_date=ev2_return,
        event_location="Hôtel Novotel, Paris",
        event_type="entreprise",
        event_name="TechCorp — Séminaire Q1 2026",
        guest_count=50,
        status="draft",
        total_amount_cents=ev2_total,
        deposit_amount_cents=0,
        deposit_paid=False,
    )
    db.add(res_techcorp)
    db.flush()

    db.add(ReservationLine(
        tenant_id=TENANT_ID,
        reservation_id=res_techcorp.id,
        product_id=chaise.id,
        quantity=50,
        unit_price_cents=_eur(1.20),
        subtotal_cents=ev2_line1,
    ))
    db.flush()

    # ── EV-003 : Lebrun — Anniversaire J-30, Retournée, Soldée ───────────
    ev3_delivery = TODAY - timedelta(days=31)
    ev3_return = TODAY - timedelta(days=29)
    ev3_days = _rental_days(ev3_delivery, ev3_return)
    ev3_line1 = _line_subtotal(1, _eur(15.00), ev3_days)    # sono
    ev3_total = ev3_line1
    ev3_half = ev3_total // 2

    res_lebrun = Reservation(
        tenant_id=TENANT_ID,
        customer_id=lebrun.id,
        reference="DEMO-EV003",
        event_date=TODAY - timedelta(days=30),
        delivery_date=ev3_delivery,
        return_date=ev3_return,
        event_location="Salle des Fêtes, Senlis",
        event_type="anniversaire",
        event_name="Anniversaire Lebrun — 50 ans",
        guest_count=30,
        status="returned",
        total_amount_cents=ev3_total,
        deposit_amount_cents=_eur(200),
        deposit_paid=True,
    )
    db.add(res_lebrun)
    db.flush()

    db.add(ReservationLine(
        tenant_id=TENANT_ID,
        reservation_id=res_lebrun.id,
        product_id=sono.id,
        quantity=1,
        unit_price_cents=_eur(15.00),
        subtotal_cents=ev3_line1,
    ))
    db.flush()

    inv_lebrun = Invoice(
        tenant_id=TENANT_ID,
        reservation_id=res_lebrun.id,
        invoice_number="DEMO-INV002",
        issue_date=TODAY - timedelta(days=40),
        due_date=TODAY - timedelta(days=25),
        total_amount_cents=ev3_total,
        paid_amount_cents=ev3_total,
        status="paid",
        payment_method="cash",
        payment_date=TODAY - timedelta(days=20),
    )
    db.add(inv_lebrun)
    db.flush()

    db.add(Payment(
        tenant_id=TENANT_ID,
        invoice_id=inv_lebrun.id,
        amount_cents=ev3_half,
        payment_method="transfer",
        payment_date=TODAY - timedelta(days=38),
        notes="Acompte 50%",
    ))
    db.add(Payment(
        tenant_id=TENANT_ID,
        invoice_id=inv_lebrun.id,
        amount_cents=ev3_total - ev3_half,
        payment_method="cash",
        payment_date=TODAY - timedelta(days=20),
        notes="Solde 50% — espèces",
    ))
    db.add(Deposit(
        tenant_id=TENANT_ID,
        reservation_id=res_lebrun.id,
        amount_cents=_eur(200),
        status="released",
        collection_date=TODAY - timedelta(days=40),
        release_date=TODAY - timedelta(days=25),
        notes="Caution restituée — aucun dommage constaté",
    ))
    db.flush()

    # ── EV-004 : Moreau — Cocktail J-60, Retournée, Frais Dommage ────────
    ev4_delivery = TODAY - timedelta(days=61)
    ev4_return = TODAY - timedelta(days=59)
    ev4_days = _rental_days(ev4_delivery, ev4_return)
    ev4_line1 = _line_subtotal(60, _eur(0.30), ev4_days)    # couverts
    ev4_damage = _eur(80)                                    # frais dommage
    ev4_total_resa = ev4_line1                               # total réservation = lignes uniquement
    ev4_total_inv = ev4_line1 + ev4_damage                   # total facture inclut le dommage
    ev4_half = ev4_total_inv // 2

    res_moreau = Reservation(
        tenant_id=TENANT_ID,
        customer_id=moreau.id,
        reference="DEMO-EV004",
        event_date=TODAY - timedelta(days=60),
        delivery_date=ev4_delivery,
        return_date=ev4_return,
        event_location="Étude Moreau, Chantilly",
        event_type="cocktail",
        event_name="Cocktail Cabinet Moreau",
        guest_count=60,
        status="returned",
        total_amount_cents=ev4_total_resa,
        deposit_amount_cents=_eur(200),
        deposit_paid=True,
    )
    db.add(res_moreau)
    db.flush()

    db.add(ReservationLine(
        tenant_id=TENANT_ID,
        reservation_id=res_moreau.id,
        product_id=couvert.id,
        quantity=60,
        unit_price_cents=_eur(0.30),
        subtotal_cents=ev4_line1,
    ))
    db.flush()

    inv_moreau = Invoice(
        tenant_id=TENANT_ID,
        reservation_id=res_moreau.id,
        invoice_number="DEMO-INV003",
        issue_date=TODAY - timedelta(days=70),
        due_date=TODAY - timedelta(days=55),
        total_amount_cents=ev4_total_inv,
        paid_amount_cents=ev4_total_inv,
        status="paid",
        payment_method="check",
        payment_date=TODAY - timedelta(days=50),
    )
    db.add(inv_moreau)
    db.flush()

    db.add(Payment(
        tenant_id=TENANT_ID,
        invoice_id=inv_moreau.id,
        amount_cents=ev4_half,
        payment_method="transfer",
        payment_date=TODAY - timedelta(days=68),
        notes="Acompte 50%",
    ))
    db.add(Payment(
        tenant_id=TENANT_ID,
        invoice_id=inv_moreau.id,
        amount_cents=ev4_total_inv - ev4_half,
        payment_method="check",
        payment_date=TODAY - timedelta(days=50),
        notes="Solde 50% — chèque",
    ))
    db.add(InvoiceCharge(
        tenant_id=TENANT_ID,
        invoice_id=inv_moreau.id,
        charge_type="DAMAGE",
        amount_cents=ev4_damage,
        description="2 verres brisés",
    ))
    db.add(Deposit(
        tenant_id=TENANT_ID,
        reservation_id=res_moreau.id,
        amount_cents=_eur(200),
        status="retained",
        retained_amount_cents=ev4_damage,
        collection_date=TODAY - timedelta(days=70),
        release_date=TODAY - timedelta(days=55),
        notes="Caution partiellement retenue — 2 verres brisés (80 €)",
    ))
    db.flush()

    # StockItems (après création des réservations pour les FK current_reservation_id)
    _recreate_stock_items(db, products, res_dupont)

    db.commit()
    print(f"\n✓ Seed terminé :")
    print(f"  → 4 clients | 4 réservations | 3 factures | 4 cautions | 5 paiements | 1 frais dommage")
    print(f"  → 212 StockItems (150 couverts + 60 chaises + 2 sono)")
    print(f"  → Login démo : {DEMO_USER_EMAIL} / {DEMO_USER_PASSWORD}")


if __name__ == "__main__":
    with get_db_context() as db:
        seed(db)
