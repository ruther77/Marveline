"""Seed script — Données de démonstration complémentaires Marveline.

Ajoute : variantes couleur, réservations, factures, mouvements de stock.

Usage (Docker) :
    docker compose exec api python scripts/seed_demo_data.py

Usage (local) :
    python3 scripts/seed_demo_data.py
"""
import sys
import os
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db_context
from app.models.product import Product
from app.models.customer import Customer
from app.models.product_variant import ProductVariant
from app.models.reservation import Reservation, ReservationLine
from app.models.invoice import Invoice
from app.models.inventory_movement import InventoryMovement, MovementItem

TENANT_ID = 1


def _eur(eur: float) -> int:
    return int(round(eur * 100))


def _dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 8, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Variantes couleur (nappes rondes + housses chaises)
# SKUs réels : NAP-RND-240, HOU-CHA-BLC, HOU-CHA-IVO
# ---------------------------------------------------------------------------

VARIANTS_TO_CREATE = [
    # Nappe ronde 240cm — plusieurs couleurs
    {"product_sku": "NAP-RND-240", "color": "blanc",    "sku": "NAP-RND-240-BLC", "stock": 80,  "available": 75},
    {"product_sku": "NAP-RND-240", "color": "ivoire",   "sku": "NAP-RND-240-IVO", "stock": 60,  "available": 55},
    {"product_sku": "NAP-RND-240", "color": "bordeaux", "sku": "NAP-RND-240-BOR", "stock": 40,  "available": 38},
    {"product_sku": "NAP-RND-240", "color": "noir",     "sku": "NAP-RND-240-NOI", "stock": 30,  "available": 28},
    # Nappe rectangulaire 140x240cm
    {"product_sku": "NAP-REC-140x240", "color": "blanc",   "sku": "NAP-REC-140-BLC", "stock": 100, "available": 95},
    {"product_sku": "NAP-REC-140x240", "color": "ivoire",  "sku": "NAP-REC-140-IVO", "stock": 70,  "available": 65},
    {"product_sku": "NAP-REC-140x240", "color": "taupe",   "sku": "NAP-REC-140-TAU", "stock": 40,  "available": 38},
    # Housse de chaise blanche — variantes couleurs supplémentaires
    {"product_sku": "HOU-CHA-BLC",  "color": "blanc",    "sku": "HOU-CHA-BLC-STD", "stock": 200, "available": 185},
    # Housse de chaise ivoire — variantes couleurs supplémentaires
    {"product_sku": "HOU-CHA-IVO",  "color": "ivoire",   "sku": "HOU-CHA-IVO-STD", "stock": 150, "available": 140},
]


def seed_variants(db):
    existing = db.query(ProductVariant).filter(ProductVariant.tenant_id == TENANT_ID).count()
    if existing > 0:
        print(f"  -> {existing} variantes déjà présentes, skip.")
        return

    products_by_sku = {
        p.sku: p for p in db.query(Product).filter(Product.tenant_id == TENANT_ID).all()
    }

    created = 0
    skipped = 0
    for v in VARIANTS_TO_CREATE:
        product = products_by_sku.get(v["product_sku"])
        if not product:
            print(f"  [WARN] Produit SKU {v['product_sku']} introuvable, variante ignorée.")
            skipped += 1
            continue
        variant = ProductVariant(
            tenant_id=TENANT_ID,
            product_id=product.id,
            color=v["color"],
            sku=v["sku"],
            stock_quantity=v["stock"],
            available_quantity=v["available"],
        )
        db.add(variant)
        created += 1

    db.commit()
    print(f"  -> {created} variantes créées, {skipped} ignorées (produit introuvable).")


# ---------------------------------------------------------------------------
# Réservations + lignes (SKUs réels de la DB)
# ---------------------------------------------------------------------------

RESERVATIONS_DATA = [
    {
        "reference": "RES-2026-0001",
        "status": "returned",
        "event_date": date(2026, 1, 18),
        "delivery_date": date(2026, 1, 17),
        "return_date": date(2026, 1, 19),
        "event_location": "Salle des fêtes de Neuilly-sur-Marne",
        "deposit_paid": True,
        "lines": [
            {"sku": "ASS-RND-CLA-26",  "qty": 80,  "unit_price_cents": 0.50},
            {"sku": "VER-VR-CLA",      "qty": 80,  "unit_price_cents": 0.45},
            {"sku": "CHA-NAP3",        "qty": 80,  "unit_price_cents": 0.80},
            {"sku": "NAP-REC-140x240", "qty": 10,  "unit_price_cents": 4.50},
        ],
        "invoice": {
            "number": "FAC-2026-0001",
            "status": "paid",
            "payment_method": "transfer",
            "payment_date": date(2026, 1, 10),
            "issue_date": date(2026, 1, 5),
            "due_date": date(2026, 1, 15),
        },
        "movements": [
            {"type": "departure", "status": "completed", "date": date(2026, 1, 17)},
            {"type": "return",    "status": "completed", "date": date(2026, 1, 19)},
        ],
    },
    {
        "reference": "RES-2026-0002",
        "status": "confirmed",
        "event_date": date(2026, 2, 22),
        "delivery_date": date(2026, 2, 21),
        "return_date": date(2026, 2, 23),
        "event_location": "Château de Vincennes — Grande Salle",
        "deposit_paid": True,
        "lines": [
            {"sku": "ASS-CRS-CLA-22",  "qty": 120, "unit_price_cents": 0.55},
            {"sku": "ASS-RND-CLA-26",  "qty": 120, "unit_price_cents": 0.50},
            {"sku": "VER-FLU-ELG",     "qty": 120, "unit_price_cents": 0.55},
            {"sku": "VER-VR-ELG",      "qty": 120, "unit_price_cents": 0.45},
            {"sku": "CHA-NAP3",        "qty": 120, "unit_price_cents": 1.20},
            {"sku": "NAP-RND-240",     "qty": 15,  "unit_price_cents": 5.00},
            {"sku": "HOU-CHA-BLC",     "qty": 120, "unit_price_cents": 1.50},
        ],
        "invoice": {
            "number": "FAC-2026-0002",
            "status": "sent",
            "payment_method": None,
            "payment_date": None,
            "issue_date": date(2026, 2, 1),
            "due_date": date(2026, 2, 20),
        },
        "movements": [
            {"type": "departure", "status": "scheduled", "date": date(2026, 2, 21)},
            {"type": "return",    "status": "scheduled", "date": date(2026, 2, 23)},
        ],
    },
    {
        "reference": "RES-2026-0003",
        "status": "confirmed",
        "event_date": date(2026, 3, 8),
        "delivery_date": date(2026, 3, 7),
        "return_date": date(2026, 3, 9),
        "event_location": "Jardins de Bagatelle — Boulogne-Billancourt",
        "deposit_paid": True,
        "lines": [
            {"sku": "ASS-RND-CLA-26",  "qty": 60,  "unit_price_cents": 0.50},
            {"sku": "VER-EAU-ELG",     "qty": 60,  "unit_price_cents": 0.40},
            {"sku": "VER-VR-CLA",      "qty": 60,  "unit_price_cents": 0.45},
            {"sku": "CHA-BOIS-DC",     "qty": 60,  "unit_price_cents": 0.80},
            {"sku": "NAP-REC-200x240", "qty": 8,   "unit_price_cents": 4.50},
        ],
        "invoice": {
            "number": "FAC-2026-0003",
            "status": "draft",
            "payment_method": None,
            "payment_date": None,
            "issue_date": date(2026, 2, 10),
            "due_date": date(2026, 3, 5),
        },
        "movements": [
            {"type": "departure", "status": "scheduled", "date": date(2026, 3, 7)},
            {"type": "return",    "status": "scheduled", "date": date(2026, 3, 9)},
        ],
    },
    {
        "reference": "RES-2026-0004",
        "status": "draft",
        "event_date": date(2026, 4, 12),
        "delivery_date": date(2026, 4, 11),
        "return_date": date(2026, 4, 13),
        "event_location": "Domaine de Saint-Cloud",
        "deposit_paid": False,
        "lines": [
            {"sku": "ASS-RND-CLA-30",  "qty": 200, "unit_price_cents": 0.50},
            {"sku": "ASS-CRS-CLA-22",  "qty": 200, "unit_price_cents": 0.55},
            {"sku": "VER-VR-ELG",      "qty": 200, "unit_price_cents": 0.45},
            {"sku": "VER-FLU-CLA",     "qty": 200, "unit_price_cents": 0.50},
        ],
        "invoice": None,
        "movements": [],
    },
    {
        "reference": "RES-2026-0005",
        "status": "returned",
        "event_date": date(2026, 1, 25),
        "delivery_date": date(2026, 1, 24),
        "return_date": date(2026, 1, 26),
        "event_location": "Salle Pleyel — Paris 8ème",
        "deposit_paid": True,
        "lines": [
            {"sku": "CHA-NAP3",        "qty": 50,  "unit_price_cents": 1.20},
            {"sku": "ASS-RND-CLA-26",  "qty": 50,  "unit_price_cents": 0.50},
            {"sku": "VER-EAU-CLA",     "qty": 50,  "unit_price_cents": 0.40},
        ],
        "invoice": {
            "number": "FAC-2026-0005",
            "status": "paid",
            "payment_method": "card",
            "payment_date": date(2026, 1, 20),
            "issue_date": date(2026, 1, 15),
            "due_date": date(2026, 1, 22),
        },
        "movements": [
            {"type": "departure", "status": "completed", "date": date(2026, 1, 24)},
            {"type": "return",    "status": "completed", "date": date(2026, 1, 26)},
        ],
    },
]


def seed_reservations(db):
    existing = db.query(Reservation).filter(Reservation.tenant_id == TENANT_ID).count()
    if existing > 0:
        print(f"  -> {existing} réservations déjà présentes, skip.")
        return

    products_by_sku = {
        p.sku: p for p in db.query(Product).filter(Product.tenant_id == TENANT_ID).all()
    }
    customers = db.query(Customer).filter(Customer.tenant_id == TENANT_ID).all()
    if not customers:
        print("  [WARN] Aucun client trouvé ! Lancez d'abord seed_data.py.")
        return

    res_count = 0
    inv_count = 0
    mov_count = 0

    for i, res_data in enumerate(RESERVATIONS_DATA):
        customer = customers[i % len(customers)]

        # Calcul montant total à partir des lignes
        total = 0
        lines_ok = []
        for line_data in res_data["lines"]:
            product = products_by_sku.get(line_data["sku"])
            if not product:
                print(f"  [WARN] Produit {line_data['sku']} introuvable, ligne ignorée.")
                continue
            unit_cents = _eur(line_data["unit_price"])
            subtotal = unit_cents * line_data["qty"]
            total += subtotal
            lines_ok.append({
                "product": product,
                "qty": line_data["qty"],
                "unit_price_cents": unit_cents,
                "subtotal_cents": subtotal,
            })

        if not lines_ok:
            print(f"  [WARN] Réservation {res_data['reference']} ignorée (aucune ligne valide).")
            continue

        deposit = int(total * 0.30)  # 30% caution

        res = Reservation(
            tenant_id=TENANT_ID,
            customer_id=customer.id,
            reference=res_data["reference"],
            status=res_data["status"],
            event_date=res_data["event_date"],
            delivery_date=res_data["delivery_date"],
            return_date=res_data["return_date"],
            event_location=res_data["event_location"],
            total_amount_cents=total,
            deposit_amount_cents=deposit,
            deposit_paid=res_data["deposit_paid"],
        )
        db.add(res)
        db.flush()

        for line in lines_ok:
            db.add(ReservationLine(
                tenant_id=TENANT_ID,
                reservation_id=res.id,
                product_id=line["product"].id,
                quantity=line["qty"],
                unit_price_cents=line["unit_price"],
                subtotal_cents=line["subtotal"],
            ))

        res_count += 1

        # Facture
        if res_data["invoice"]:
            inv_data = res_data["invoice"]
            invoice = Invoice(
                tenant_id=TENANT_ID,
                reservation_id=res.id,
                invoice_number=inv_data["number"],
                issue_date=inv_data["issue_date"],
                due_date=inv_data["due_date"],
                total_amount_cents=total,
                paid_amount_cents=total if inv_data["status"] == "paid" else 0,
                status=inv_data["status"],
                payment_method=inv_data["payment_method"],
                payment_date=inv_data["payment_date"],
            )
            db.add(invoice)
            inv_count += 1

        # Mouvements de stock
        for mov_data in res_data["movements"]:
            mov = InventoryMovement(
                tenant_id=TENANT_ID,
                reservation_id=res.id,
                movement_type=mov_data["type"],
                scheduled_date=_dt(mov_data["date"]),
                actual_date=_dt(mov_data["date"]) if mov_data["status"] == "completed" else None,
                status=mov_data["status"],
                delivery_method="delivery",
                delivery_address=res_data["event_location"],
            )
            db.add(mov)
            db.flush()

            for line in lines_ok:
                qty_actual = line["qty"] if mov_data["status"] == "completed" else None
                cond = "good" if mov_data["status"] == "completed" else None
                db.add(MovementItem(
                    tenant_id=TENANT_ID,
                    movement_id=mov.id,
                    product_id=line["product"].id,
                    quantity_expected=line["qty"],
                    quantity_actual=qty_actual,
                    condition=cond,
                ))
            mov_count += 1

    db.commit()
    print(f"  -> {res_count} réservations créées")
    print(f"  -> {inv_count} factures créées")
    print(f"  -> {mov_count} mouvements de stock créés")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== Marveline — Seed données de démonstration ===\n")

    with get_db_context() as db:
        print("1. Variantes couleur...")
        seed_variants(db)

        print("2. Réservations, factures & mouvements...")
        seed_reservations(db)

    print("\n=== Terminé ===")


if __name__ == "__main__":
    main()
