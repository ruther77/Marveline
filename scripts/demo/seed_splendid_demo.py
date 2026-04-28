#!/usr/bin/env python3
"""Seed démo Le Splendid Events — tenant multi-tenant isole + 182 produits.

Usage (Docker) :
    docker compose exec -T api python scripts/demo/seed_splendid_demo.py

Usage (local) :
    python3 scripts/demo/seed_splendid_demo.py

Lit /home/ruuuzer/Téléchargements/splendid-produits.csv (scrape Wix).
Cree :
  - Tenant "Le Splendid Events" (app_code=marveline pour cohabiter frontend)
  - Compte demo@lesplendidevent.fr / DemoSplendid2026! + tenant_admin
  - 182 produits avec stock/caution baremes identiques Marveline

Script idempotent : skip produits deja presents par SKU.
"""

import csv
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.database import get_db_context
from app.core.security import get_password_hash
from app.models.account import Account
from app.models.product import Product
from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership


CSV_PATH = Path(__file__).parent / "splendid-produits.csv"

SPLENDID_DOMAIN = "le-splendid.events"
SPLENDID_NAME = "Le Splendid Events"
SPLENDID_CONTACT = "contact@le-splendid.events"

DEMO_USER_EMAIL = "demo@lesplendidevent.fr"
DEMO_USER_PASSWORD = "DemoSplendid2026!"


def _stock_tiers(price_cents: int) -> tuple[int, int]:
    """Bareme Marveline : total, available."""
    price_eur = price_cents / 100
    if price_eur < 10:
        return 150, 130
    if price_eur < 50:
        return 60, 50
    return 3, 2


def _get_or_create_tenant(db) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.domain == SPLENDID_DOMAIN).first()
    if tenant:
        print(f"  -> Tenant existant : {tenant.name} (id={tenant.id})")
        return tenant

    tenant = Tenant(
        external_id=str(uuid.uuid4()),
        name=SPLENDID_NAME,
        domain=SPLENDID_DOMAIN,
        contact_email=SPLENDID_CONTACT,
        app_code="marveline",
        brand_code="lesplendid",
        status="active",
        is_active=True,
    )
    db.add(tenant)
    db.flush()
    print(f"  -> Tenant cree : {tenant.name} (id={tenant.id})")
    return tenant


def _get_or_create_user(db, tenant: Tenant) -> None:
    account = db.query(Account).filter(Account.email == DEMO_USER_EMAIL).first()
    if account:
        membership = (
            db.query(TenantMembership)
            .filter(
                TenantMembership.account_id == account.id,
                TenantMembership.tenant_id == tenant.id,
            )
            .first()
        )
        if not membership:
            db.add(
                TenantMembership(
                    account_id=account.id,
                    tenant_id=tenant.id,
                    role_name="tenant_admin",
                    status="active",
                )
            )
            db.flush()
            print(f"  -> Membership ajoute pour {DEMO_USER_EMAIL}")
        else:
            print(f"  -> User demo deja membre : {DEMO_USER_EMAIL}")
        return

    account = Account(
        email=DEMO_USER_EMAIL,
        hashed_password=get_password_hash(DEMO_USER_PASSWORD),
        first_name="Demo",
        last_name="Splendid",
        is_active=True,
    )
    db.add(account)
    db.flush()
    db.add(
        TenantMembership(
            account_id=account.id,
            tenant_id=tenant.id,
            role_name="tenant_admin",
            status="active",
        )
    )
    db.flush()
    print(f"  -> User demo cree : {DEMO_USER_EMAIL} / {DEMO_USER_PASSWORD}")


def _import_products(db, tenant: Tenant) -> None:
    if not CSV_PATH.exists():
        print(f"  !! CSV introuvable : {CSV_PATH}")
        sys.exit(1)

    created = 0
    skipped = 0
    skipped_service = 0

    with CSV_PATH.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["name"].strip()
            if not name:
                continue
            if "Père Noël" in name or "Prestation" in name:
                skipped_service += 1
                continue

            sku = row["sku"].strip()
            existing = (
                db.query(Product)
                .filter(Product.tenant_id == tenant.id, Product.sku == sku)
                .first()
            )
            if existing:
                skipped += 1
                continue

            try:
                price_cents = int(row["price_per_day_cents"])
            except (ValueError, TypeError):
                price_cents = 0
            if price_cents <= 0:
                skipped_service += 1
                continue

            category = row["category"].strip() or "decorations"
            description = (row.get("description") or "").strip()[:5000] or None
            image_url = (row.get("image_url") or "").strip() or None
            stock, avail = _stock_tiers(price_cents)
            deposit = price_cents * 3

            name_exists = (
                db.query(Product)
                .filter(Product.tenant_id == tenant.id, Product.name == name)
                .first()
            )
            final_name = name if not name_exists else f"{name} ({sku[-3:]})"

            db.add(
                Product(
                    tenant_id=tenant.id,
                    sku=sku,
                    name=final_name,
                    category=category,
                    price_per_day_cents=price_cents,
                    deposit_amount_cents=deposit,
                    stock_quantity=stock,
                    available_quantity=avail,
                    condition="bon",
                    image_url=image_url,
                    description=description,
                    short_description=(description[:200] if description else None),
                    tva_rate=0.20,
                )
            )
            created += 1

    db.flush()
    print(f"  -> Produits : {created} crees, {skipped} deja presents, {skipped_service} services ignores")


def seed(db) -> None:
    print("\n=== Seed Le Splendid Events Demo ===\n")
    tenant = _get_or_create_tenant(db)
    _get_or_create_user(db, tenant)
    _import_products(db, tenant)
    db.commit()
    print("\nOK - demo pret. Login : demo@lesplendidevent.fr / DemoSplendid2026!\n")


def main() -> None:
    with get_db_context() as db:
        seed(db)


if __name__ == "__main__":
    main()
