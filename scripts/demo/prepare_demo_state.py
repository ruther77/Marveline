#!/usr/bin/env python3
"""Prepare l'etat seed pour la demo Loom 90s du Splendid Events.

Idempotent : cree (ou recupere) :
  - Devis "DEV-DEMO-2026-A" (Anniversaire Lea 30 ans), status=accepted
    -> filme l'Acte 2 (conversion en reservation, 1 clic)
  - Reservation "RES-DEMO-2026-D" (Mariage Mai 2026), status=delivered
    -> filme l'Acte 4 (constat de retour + dispute log)

Tenant : Le Splendid Events (id=5, brand_code=lesplendid).

Usage :
    docker compose run --rm --entrypoint "" api python scripts/demo/prepare_demo_state.py
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.orm import Session

from app.core.database import get_db_context
from app.models.customer import Customer
from app.models.devis import Devis, DevisLine
from app.models.product import Product
from app.models.reservation import Reservation, ReservationLine
from app.models.tenant import Tenant
from app.constants import CustomerType, ReservationStatus

TENANT_BRAND = "lesplendid"

DEVIS_REF = "DEV-DEMO-2026-A"
RESA_DEMO_REF = "RES-DEMO-2026-D"

DEMO_CUSTOMER_BIRTHDAY = {
    "first_name": "Lea",
    "last_name": "Martin",
    "email": "lea.martin.demo@splendid.local",
    "phone": "+33611223344",
}
DEMO_CUSTOMER_WEDDING = {
    "first_name": "Caroline",
    "last_name": "Dubois",
    "email": "caroline.dubois.demo@splendid.local",
    "phone": "+33611223345",
}


def _get_tenant(db: Session) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.brand_code == TENANT_BRAND).first()
    if not tenant:
        raise SystemExit(
            f"Tenant brand_code={TENANT_BRAND} introuvable. "
            "Lance d'abord scripts/demo/seed_splendid_demo.py."
        )
    return tenant


def _get_or_create_customer(db: Session, tenant: Tenant, info: dict) -> Customer:
    cust = (
        db.query(Customer)
        .filter(
            Customer.tenant_id == tenant.id,
            Customer.email == info["email"],
        )
        .first()
    )
    if cust:
        return cust
    cust = Customer(
        tenant_id=tenant.id,
        customer_type=CustomerType.INDIVIDUAL,
        first_name=info["first_name"],
        last_name=info["last_name"],
        email=info["email"],
        phone=info["phone"],
        is_active=True,
    )
    db.add(cust)
    db.flush()
    db.refresh(cust)
    return cust


def _find_product(db: Session, tenant: Tenant, name_substring: str) -> Product:
    p = (
        db.query(Product)
        .filter(
            Product.tenant_id == tenant.id,
            Product.is_active.is_(True),
            Product.name.ilike(f"%{name_substring}%"),
        )
        .order_by(Product.stock_quantity.desc())
        .first()
    )
    if not p:
        raise SystemExit(f"Produit introuvable pour '{name_substring}' tenant={tenant.id}")
    return p


def _ensure_devis_accepted(db: Session, tenant: Tenant) -> Devis:
    """Devis "Anniversaire Lea 30 ans", status=accepted, non converti."""
    existing = (
        db.query(Devis)
        .filter(Devis.tenant_id == tenant.id, Devis.reference == DEVIS_REF)
        .first()
    )
    if existing:
        if existing.status != "accepted" or existing.converted_reservation_id is not None:
            existing.status = "accepted"
            existing.converted_reservation_id = None
            db.flush()
        print(f"  -> Devis {DEVIS_REF} existant (status={existing.status})")
        return existing

    customer = _get_or_create_customer(db, tenant, DEMO_CUSTOMER_BIRTHDAY)
    chaise = _find_product(db, tenant, "Chaise Napoleon Blanche")
    nappe = _find_product(db, tenant, "Nappe ronde blanche")
    arche = _find_product(db, tenant, "Arche hexagonale")

    today = date.today()
    event_d = today + timedelta(days=21)

    lines_spec = [
        (chaise, 80, "Chaise Napoleon blanche - location"),
        (nappe, 12, "Nappe ronde blanche 280cm - location"),
        (arche, 1, "Arche hexagonale - decor entree - location"),
    ]
    subtotal = sum(
        p.price_per_day_cents * qty for (p, qty, _) in lines_spec
    )
    tva_rate = 20
    tva_cents = int(subtotal * tva_rate / 100)
    total_cents = subtotal + tva_cents
    caution = sum(p.deposit_amount_cents * qty for (p, qty, _) in lines_spec)

    devis = Devis(
        tenant_id=tenant.id,
        reference=DEVIS_REF,
        customer_id=customer.id,
        status="accepted",
        event_date=event_d,
        event_location="Salle des Fetes - Marseille",
        delivery_date=event_d - timedelta(days=1),
        return_date=event_d + timedelta(days=1),
        valid_until=today + timedelta(days=15),
        tva_rate=tva_rate,
        subtotal_cents=subtotal,
        tva_cents=tva_cents,
        total_cents=total_cents,
        discount_pct=0,
        caution_required=True,
        caution_amount_cents=caution,
        notes="Anniversaire 30 ans Lea - 80 invites - theme blanc.",
    )
    db.add(devis)
    db.flush()
    db.refresh(devis)

    for sort_order, (product, qty, label) in enumerate(lines_spec):
        line_subtotal = product.price_per_day_cents * qty
        db.add(
            DevisLine(
                tenant_id=tenant.id,
                devis_id=devis.id,
                product_id=product.id,
                label=label,
                quantity=qty,
                unit_price_cents=product.price_per_day_cents,
                discount_pct=0,
                subtotal_cents=line_subtotal,
                sort_order=sort_order,
            )
        )

    db.flush()
    print(f"  -> Devis {DEVIS_REF} cree (status=accepted, total={total_cents/100:.2f}€)")
    return devis


def _ensure_resa_delivered(db: Session, tenant: Tenant) -> Reservation:
    """Reservation "Mariage" status=delivered, prete pour constat retour."""
    existing = (
        db.query(Reservation)
        .filter(Reservation.tenant_id == tenant.id, Reservation.reference == RESA_DEMO_REF)
        .first()
    )
    if existing:
        if existing.status != ReservationStatus.DELIVERED.value:
            existing.status = ReservationStatus.DELIVERED.value
            db.flush()
        print(f"  -> Resa {RESA_DEMO_REF} existante (status={existing.status})")
        return existing

    customer = _get_or_create_customer(db, tenant, DEMO_CUSTOMER_WEDDING)
    chaise = _find_product(db, tenant, "Chaise Napoleon Blanche")
    nappe = _find_product(db, tenant, "Nappe rectangulaire blanche")

    today = date.today()
    event_d = today - timedelta(days=2)

    lines_spec = [
        (chaise, 100, "Chaise Napoleon blanche", chaise.price_per_day_cents, chaise.deposit_amount_cents),
        (nappe, 10, "Nappe rectangulaire blanche", nappe.price_per_day_cents, nappe.deposit_amount_cents),
    ]
    total_cents = sum(unit * qty for (_, qty, _, unit, _) in lines_spec)
    deposit = sum(dep * qty for (_, qty, _, _, dep) in lines_spec)

    res = Reservation(
        tenant_id=tenant.id,
        customer_id=customer.id,
        reference=RESA_DEMO_REF,
        event_date=event_d,
        delivery_date=event_d - timedelta(days=1),
        return_date=event_d + timedelta(days=1),
        event_location="Domaine du Mas - Aix-en-Provence",
        status=ReservationStatus.DELIVERED.value,
        total_amount_cents=total_cents,
        deposit_amount_cents=deposit,
        deposit_paid=True,
        notes="Mariage Caroline & Thomas - 100 invites.",
    )
    db.add(res)
    db.flush()
    db.refresh(res)

    for product, qty, label, unit, _dep in lines_spec:
        db.add(
            ReservationLine(
                tenant_id=tenant.id,
                reservation_id=res.id,
                product_id=product.id,
                quantity=qty,
                unit_price_cents=unit,
                subtotal_cents=unit * qty,
                tva_rate=20.0,
            )
        )
    db.flush()
    print(f"  -> Resa {RESA_DEMO_REF} creee (status=delivered, total={total_cents/100:.2f}€)")
    return res


def main() -> None:
    print("Preparation etat demo Splendid Events...")
    with get_db_context() as db:
        tenant = _get_tenant(db)
        print(f"Tenant: {tenant.name} (id={tenant.id})")
        _ensure_devis_accepted(db, tenant)
        _ensure_resa_delivered(db, tenant)
        db.commit()
    print("Etat demo pret.")
    print("")
    print("Acte 2 (conversion devis): DEV-DEMO-2026-A")
    print("Acte 4 (constat retour) : RES-DEMO-2026-D")


if __name__ == "__main__":
    main()
