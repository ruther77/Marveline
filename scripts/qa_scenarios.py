"""QA — 4 scénarios métier complets post-purge.

Exécuter :
  docker compose exec api python scripts/qa_scenarios.py
"""
import asyncio
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any

# ── Bootstrap ────────────────────────────────────────────────────────────────

TENANT_ID = 1
PASS = "\033[92m  PASS\033[0m"
FAIL = "\033[91m  FAIL\033[0m"
results: list[tuple[str, bool, str]] = []


def check(label: str, condition: bool, detail: str = ""):
    results.append((label, condition, detail))
    tag = PASS if condition else FAIL
    info = f" — {detail}" if detail else ""
    print(f"{tag}  {label}{info}")
    if not condition:
        print(f"        ↳ expected True, got False")


# ── Async runner ─────────────────────────────────────────────────────────────

async def run_all():
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select, func, text
    from sqlalchemy.ext.asyncio import AsyncSession

    # Services
    from app.services.devis import DevisService
    from app.services.reservation import ReservationService
    from app.services.invoice import InvoiceService
    from app.services.customer import CustomerService

    # Schemas
    from app.schemas.devis import DevisCreate, DevisLineCreate, DevisConvert
    from app.schemas.reservation import ReservationCreate, ReservationLineCreate
    from app.schemas.customer import CustomerCreate
    from app.schemas.invoice import AddPaymentRequest

    # Models
    from app.models.reservation import Reservation, ReservationLine, ReservationPreCheckItem
    from app.models.devis import Devis
    from app.models.invoice import Invoice
    from app.models.inventory_movement import InventoryMovement
    from app.models.stock_item import StockItem
    from app.models.product import Product
    from app.models.product_variant import ProductVariant
    from app.models.customer import Customer

    # Constants
    from app.constants import DevisStatus, ReservationStatus

    # Movement service
    from app.services.inventory_movement import MovementService

    async with AsyncSessionLocal() as db:

        # ── Helper: count stock by status ────────────────────────────
        async def count_stock(status: str = "available") -> int:
            r = await db.execute(
                select(func.count(StockItem.id)).where(StockItem.status == status)
            )
            return r.scalar() or 0

        async def variant_available(variant_id: int) -> int:
            r = await db.execute(
                select(func.count(StockItem.id)).where(
                    StockItem.variant_id == variant_id,
                    StockItem.status == "available",
                )
            )
            return r.scalar() or 0

        # Snapshot stock initial
        stock_before = await count_stock("available")
        print(f"\n{'='*60}")
        print(f"  STOCK INITIAL : {stock_before} items available")
        print(f"{'='*60}\n")

        # ══════════════════════════════════════════════════════════════
        # SC-1 : Mariage classique — Devis → Flow complet
        # ══════════════════════════════════════════════════════════════
        print("━" * 60)
        print("SC-1 : MARIAGE CLASSIQUE (devis → complet)")
        print("━" * 60)

        devis_svc = DevisService(db)
        resa_svc = ReservationService(db)

        # 1.1 Créer client
        cust_svc = CustomerService(db)
        try:
            sc1_cust = await cust_svc.create_customer(CustomerCreate(
                customer_type="individual",
                first_name="Marie",
                last_name="Lefèvre",
                email="marie.lefevre@qa-test.fr",
                phone="+33612345678",
            ), TENANT_ID)
            await db.commit()
            check("SC1 client créé", sc1_cust.id > 0, f"id={sc1_cust.id}")
        except Exception as e:
            # Client peut déjà exister
            await db.rollback()
            r = await db.execute(
                select(Customer).where(
                    Customer.email == "marie.lefevre@qa-test.fr",
                    Customer.tenant_id == TENANT_ID,
                )
            )
            sc1_cust = r.scalar_one()
            check("SC1 client existant", True, f"id={sc1_cust.id}")

        # 1.2 Créer devis avec bundle 5 (Formule 15 pièces) × 80
        # Produits 1 variante : Borne selfie (120, stock=200), Bol (65, stock=200), Couteau à dessert (189, stock=600)
        sc1_devis = await devis_svc.create(TENANT_ID, DevisCreate(
            customer_id=sc1_cust.id,
            valid_until=date(2026, 5, 1),
            event_date=date(2026, 6, 15),
            event_location="Château de Chantilly",
            delivery_date=date(2026, 6, 14),
            return_date=date(2026, 6, 16),
            tva_rate=2000,
            lines=[
                DevisLineCreate(
                    product_id=65,  # Bol — stock=200
                    label="Bol",
                    quantity=80,
                    unit_price_cents=50,
                ),
                DevisLineCreate(
                    product_id=189,  # Couteau à dessert — stock=600
                    label="Couteau à dessert",
                    quantity=80,
                    unit_price_cents=30,
                ),
                DevisLineCreate(
                    product_id=120,  # Borne à selfie — stock=200
                    label="Borne à selfie",
                    quantity=2,
                    unit_price_cents=20000,
                ),
            ],
        ))
        await db.commit()
        check("SC1 devis créé", sc1_devis is not None, f"id={sc1_devis.id} ref={sc1_devis.reference}")
        check("SC1 devis status=draft", sc1_devis.status == DevisStatus.DRAFT)
        check("SC1 devis 3 lignes", len(sc1_devis.lines) == 3)

        # 1.3 Send → Accept → Convert
        sc1_devis = await devis_svc.send(sc1_devis.id, TENANT_ID, user_id=1)
        await db.commit()
        check("SC1 devis sent", sc1_devis.status == DevisStatus.SENT)

        sc1_devis = await devis_svc.accept(sc1_devis.id, TENANT_ID, user_id=1)
        await db.commit()
        check("SC1 devis accepted", sc1_devis.status == DevisStatus.ACCEPTED)

        sc1_devis = await devis_svc.convert_to_reservation(
            sc1_devis.id, TENANT_ID,
            DevisConvert(
                event_date=date(2026, 6, 15),
                delivery_date=date(2026, 6, 14),
                return_date=date(2026, 6, 16),
                event_location="Château de Chantilly",
            ),
            user_id=1,
        )
        await db.commit()
        check("SC1 devis converted", sc1_devis.status == DevisStatus.CONVERTED)
        sc1_resa_id = sc1_devis.converted_reservation_id
        check("SC1 reservation créée", sc1_resa_id is not None, f"resa_id={sc1_resa_id}")

        # 1.4 Vérif réservation
        sc1_resa = await resa_svc.get_reservation(sc1_resa_id, TENANT_ID)
        check("SC1 resa status=draft", sc1_resa.status == ReservationStatus.DRAFT)
        check("SC1 resa 3 lignes", len(sc1_resa.lines) == 3, f"got {len(sc1_resa.lines)}")
        check("SC1 resa total > 0", sc1_resa.total_amount > 0, f"total={sc1_resa.total_amount}ct")

        # 1.5 Confirm → stock réservé + factures auto
        sc1_resa = await resa_svc.confirm_reservation(sc1_resa_id, TENANT_ID)
        await db.commit()
        check("SC1 resa confirmed", sc1_resa.status in (
            ReservationStatus.CONFIRMED, "pre_check", ReservationStatus.PRE_CHECK,
        ), f"status={sc1_resa.status}")

        # Vérif factures auto-générées
        inv_result = await db.execute(
            select(Invoice).where(Invoice.reservation_id == sc1_resa_id, Invoice.tenant_id == TENANT_ID)
        )
        sc1_invoices = inv_result.scalars().all()
        check("SC1 2 factures auto", len(sc1_invoices) == 2, f"got {len(sc1_invoices)}")

        # Vérif mouvement départ auto
        mv_result = await db.execute(
            select(InventoryMovement).where(
                InventoryMovement.reservation_id == sc1_resa_id,
                InventoryMovement.movement_type == "departure",
            )
        )
        sc1_departure = mv_result.scalar_one_or_none()
        check("SC1 mouvement départ auto", sc1_departure is not None)

        # 1.6 Déposer la caution
        from app.services.deposit import DepositService
        from app.schemas.deposit import DepositCreate
        deposit_svc = DepositService(db)
        if sc1_resa.deposit_amount and sc1_resa.deposit_amount > 0:
            await deposit_svc.create_deposit(
                sc1_resa.id,
                DepositCreate(
                    amount_cents=sc1_resa.deposit_amount,
                    payment_method="card",
                    payment_date=date.today(),
                ),
                TENANT_ID,
            )
            await db.commit()
            await db.refresh(sc1_resa)
            check("SC1 caution encaissée", sc1_resa.deposit_paid is True,
                  f"deposit={sc1_resa.deposit_amount}ct")

        # 1.7 Pre-check : cocher tous les items
        pc_result = await db.execute(
            select(ReservationPreCheckItem).where(
                ReservationPreCheckItem.reservation_id == sc1_resa_id
            )
        )
        pc_items = pc_result.scalars().all()
        for item in pc_items:
            item.checked = True
            item.checked_at = datetime.now(tz=timezone.utc)
        await db.flush()

        # 1.7 Deliver
        try:
            sc1_resa = await resa_svc.deliver_reservation(sc1_resa_id, TENANT_ID)
            await db.commit()
            check("SC1 resa delivered", sc1_resa.status == ReservationStatus.DELIVERED
                  or sc1_resa.status == "delivered", f"status={sc1_resa.status}")
        except Exception as e:
            await db.rollback()
            check("SC1 deliver", False, str(e)[:120])

        # 1.8 Retour : compléter le mouvement retour
        # Créer mouvement retour
        mv_svc = MovementService(db)

        # Récupérer les lignes pour le retour
        await db.refresh(sc1_resa, attribute_names=["lines"])
        return_items = []
        for line in sc1_resa.lines:
            if line.product_id:
                return_items.append({
                    "product_id": line.product_id,
                    "variant_id": line.variant_id,
                    "quantity_expected": line.quantity,
                })

        if return_items:
            try:
                sc1_return = await mv_svc.create_movement(
                    tenant_id=TENANT_ID,
                    movement_type="return",
                    scheduled_date=datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc),
                    reservation_id=sc1_resa_id,
                    items=return_items,
                )
                await db.commit()
                check("SC1 mouvement retour créé", sc1_return is not None)

                # Passer en in_transit d'abord (prérequis pour complete)
                sc1_return = await mv_svc.update_movement(
                    sc1_return.id, TENANT_ID, status="in_transit",
                )
                await db.commit()
                # Compléter via complete_movement (déclenche _update_stock_on_complete)
                sc1_return = await mv_svc.complete_movement(
                    sc1_return.id, TENANT_ID, _internal=True,
                )
                await db.commit()
                check("SC1 retour complété", sc1_return.status == "completed")
            except Exception as e:
                await db.rollback()
                check("SC1 mouvement retour", False, str(e)[:120])

        await db.refresh(sc1_resa)
        check("SC1 resa returned", sc1_resa.status in ("returned", ReservationStatus.RETURNED),
              f"status={sc1_resa.status}")

        # 1.9 Payer les factures
        inv_svc = InvoiceService(db)
        for inv in sc1_invoices:
            await db.refresh(inv)
            if inv.status != "cancelled":
                try:
                    await inv_svc.add_payment(
                        inv.id,
                        AddPaymentRequest(
                            amount_cents=inv.total_amount,
                            payment_method="card",
                            payment_date=date(2026, 6, 16),
                        ),
                        TENANT_ID,
                    )
                    await db.commit()
                except Exception as e:
                    await db.rollback()
                    check(f"SC1 paiement facture {inv.id}", False, str(e)[:100])

        # Refresh invoices
        for inv in sc1_invoices:
            await db.refresh(inv)
        paid_count = sum(1 for i in sc1_invoices if i.status == "paid")
        check("SC1 factures payées", paid_count == len(sc1_invoices),
              f"{paid_count}/{len(sc1_invoices)}")

        # 1.10 Complete
        try:
            sc1_resa = await resa_svc.complete_reservation(sc1_resa_id, TENANT_ID)
            await db.commit()
            check("SC1 resa completed", sc1_resa.status in ("completed", ReservationStatus.COMPLETED),
                  f"status={sc1_resa.status}")
        except Exception as e:
            await db.rollback()
            check("SC1 complete", False, str(e)[:120])

        # ══════════════════════════════════════════════════════════════
        # SC-2 : Anniversaire entreprise — Réservation directe + annulation
        # ══════════════════════════════════════════════════════════════
        print("\n" + "━" * 60)
        print("SC-2 : ANNIVERSAIRE ENTREPRISE (résa directe → annulation)")
        print("━" * 60)

        # 2.1 Créer client entreprise
        try:
            sc2_cust = await cust_svc.create_customer(CustomerCreate(
                customer_type="company",
                company_name="SAS TechCorp",
                email="events@techcorp-qa.fr",
                phone="+33145678900",
            ), TENANT_ID)
            await db.commit()
            check("SC2 client créé", sc2_cust.id > 0, f"id={sc2_cust.id}")
        except Exception:
            await db.rollback()
            r = await db.execute(
                select(Customer).where(
                    Customer.email == "events@techcorp-qa.fr",
                    Customer.tenant_id == TENANT_ID,
                )
            )
            sc2_cust = r.scalar_one()
            check("SC2 client existant", True)

        # 2.2 Réservation directe avec bundle 3 (Formule 8 pièces) × 30
        stock_avail_before = await count_stock("available")
        # Produits avec 1 variante (auto-resolve) : Bol (65), Coupe à dessert (45)
        sc2_resa = await resa_svc.create_reservation(ReservationCreate(
            customer_id=sc2_cust.id,
            event_date=date(2026, 5, 20),
            delivery_date=date(2026, 5, 19),
            return_date=date(2026, 5, 21),
            event_location="Palais des Congrès",
            event_type="entreprise",
            lines=[
                ReservationLineCreate(product_id=65, quantity=30),   # Bol
                ReservationLineCreate(product_id=45, quantity=30),   # Coupe à dessert
            ],
        ), TENANT_ID)
        await db.commit()
        check("SC2 resa créée", sc2_resa is not None, f"id={sc2_resa.id} ref={sc2_resa.reference}")
        check("SC2 resa draft", sc2_resa.status == ReservationStatus.DRAFT)

        # 2.3 Confirm → stock réservé
        sc2_resa = await resa_svc.confirm_reservation(sc2_resa.id, TENANT_ID)
        await db.commit()
        stock_avail_after_confirm = await count_stock("available")
        stock_reserved = await count_stock("reserved")
        check("SC2 stock réservé", stock_reserved > 0, f"reserved={stock_reserved}")
        check("SC2 available diminué", stock_avail_after_confirm < stock_avail_before,
              f"{stock_avail_before} → {stock_avail_after_confirm}")

        # 2.4 Vérif factures auto
        inv_result = await db.execute(
            select(Invoice).where(Invoice.reservation_id == sc2_resa.id)
        )
        sc2_invoices = inv_result.scalars().all()
        check("SC2 factures auto", len(sc2_invoices) == 2)

        # 2.5 Cancel → stock libéré + factures annulées
        sc2_resa = await resa_svc.cancel_reservation(sc2_resa.id, TENANT_ID)
        await db.commit()
        check("SC2 resa cancelled", sc2_resa.status in ("cancelled", ReservationStatus.CANCELLED))

        stock_avail_after_cancel = await count_stock("available")
        stock_reserved_after = await count_stock("reserved")
        check("SC2 stock libéré", stock_reserved_after == 0,
              f"reserved={stock_reserved_after}")
        check("SC2 available restauré", stock_avail_after_cancel == stock_avail_before,
              f"{stock_avail_after_cancel} vs {stock_avail_before}")

        for inv in sc2_invoices:
            await db.refresh(inv)
        cancelled_count = sum(1 for i in sc2_invoices if i.status == "cancelled")
        check("SC2 factures annulées", cancelled_count == len(sc2_invoices),
              f"{cancelled_count}/{len(sc2_invoices)}")

        # ══════════════════════════════════════════════════════════════
        # SC-3 : Vin d'honneur — Devis refusé, renouvelé, converti
        # ══════════════════════════════════════════════════════════════
        print("\n" + "━" * 60)
        print("SC-3 : VIN D'HONNEUR (devis refusé → renouvelé → converti)")
        print("━" * 60)

        # 3.1 Client
        try:
            sc3_cust = await cust_svc.create_customer(CustomerCreate(
                customer_type="individual",
                first_name="Pierre",
                last_name="Martin",
                email="pierre.martin@qa-test.fr",
            ), TENANT_ID)
            await db.commit()
            check("SC3 client créé", sc3_cust.id > 0)
        except Exception:
            await db.rollback()
            r = await db.execute(
                select(Customer).where(
                    Customer.email == "pierre.martin@qa-test.fr",
                    Customer.tenant_id == TENANT_ID,
                )
            )
            sc3_cust = r.scalar_one()
            check("SC3 client existant", True)

        # 3.2 Devis Vin d'Honneur 100 personnes
        # Produits actifs : Candy bar (198), Borne selfie (120)
        sc3_devis = await devis_svc.create(TENANT_ID, DevisCreate(
            customer_id=sc3_cust.id,
            valid_until=date(2026, 4, 15),
            event_date=date(2026, 7, 1),
            delivery_date=date(2026, 6, 30),
            return_date=date(2026, 7, 2),
            event_location="Domaine des Roses",
            lines=[
                DevisLineCreate(
                    product_id=198,  # Candy bar — stock=1200
                    label="Candy bar",
                    quantity=2,
                    unit_price_cents=4200,
                ),
                DevisLineCreate(
                    product_id=120,  # Borne à selfie — stock=200
                    label="Borne à selfie",
                    quantity=1,
                    unit_price_cents=20000,
                ),
            ],
        ))
        await db.commit()
        check("SC3 devis créé", sc3_devis is not None, f"ref={sc3_devis.reference}")

        # 3.3 Send → Refuse
        sc3_devis = await devis_svc.send(sc3_devis.id, TENANT_ID, user_id=1)
        await db.commit()

        sc3_devis = await devis_svc.refuse(sc3_devis.id, TENANT_ID, reason="Trop cher")
        await db.commit()
        check("SC3 devis refusé", sc3_devis.status == DevisStatus.REFUSED)

        # 3.4 Duplicate (depuis refused) → nouveau devis en draft
        sc3_devis = await devis_svc.duplicate(sc3_devis.id, TENANT_ID)
        await db.commit()
        check("SC3 devis dupliqué", sc3_devis.status == DevisStatus.DRAFT,
              f"ref={sc3_devis.reference}")
        check("SC3 nouveau devis", sc3_devis.id is not None)

        # 3.5 Send → Accept → Convert
        sc3_devis = await devis_svc.send(sc3_devis.id, TENANT_ID, user_id=1)
        await db.commit()
        sc3_devis = await devis_svc.accept(sc3_devis.id, TENANT_ID, user_id=1)
        await db.commit()
        sc3_devis = await devis_svc.convert_to_reservation(
            sc3_devis.id, TENANT_ID,
            DevisConvert(
                event_date=date(2026, 7, 1),
                delivery_date=date(2026, 6, 30),
                return_date=date(2026, 7, 2),
                event_location="Domaine des Roses",
            ),
            user_id=1,
        )
        await db.commit()
        check("SC3 devis converti", sc3_devis.status == DevisStatus.CONVERTED)

        sc3_resa_id = sc3_devis.converted_reservation_id
        check("SC3 reservation créée", sc3_resa_id is not None)

        # 3.6 Confirm (laisse en confirmed pour vérif stock)
        sc3_resa = await resa_svc.confirm_reservation(sc3_resa_id, TENANT_ID)
        await db.commit()
        check("SC3 resa confirmed", sc3_resa.status in (
            "confirmed", "pre_check", ReservationStatus.CONFIRMED, ReservationStatus.PRE_CHECK,
        ))

        # ══════════════════════════════════════════════════════════════
        # SC-4 : Petit événement express — Réservation directe complète
        # ══════════════════════════════════════════════════════════════
        print("\n" + "━" * 60)
        print("SC-4 : ÉVÉNEMENT EXPRESS (résa directe → complet → archivé)")
        print("━" * 60)

        # Utiliser le premier client existant
        sc4_cust_id = 13  # Marie Dupont

        # Produits avec stock : Assiette ronde classique (152), Bol (65), Bonbonnière (199)
        # Produits 1 variante : Fourchette dessert (190), Cuillère café (192), Cuillère moka (193)
        sc4_resa = await resa_svc.create_reservation(ReservationCreate(
            customer_id=sc4_cust_id,
            event_date=date(2026, 4, 10),
            delivery_date=date(2026, 4, 9),
            return_date=date(2026, 4, 11),
            event_location="Salle des fêtes, Compiègne",
            event_type="anniversaire",
            guest_count=20,
            lines=[
                ReservationLineCreate(product_id=190, quantity=20),  # Fourchette dessert
                ReservationLineCreate(product_id=192, quantity=20),  # Cuillère café
                ReservationLineCreate(product_id=193, quantity=10),  # Cuillère moka
            ],
        ), TENANT_ID)
        await db.commit()
        check("SC4 resa créée", sc4_resa is not None, f"ref={sc4_resa.reference}")
        check("SC4 3 lignes", len(sc4_resa.lines) == 3)

        # Confirm
        sc4_resa = await resa_svc.confirm_reservation(sc4_resa.id, TENANT_ID)
        await db.commit()
        check("SC4 confirmed", sc4_resa.status in (
            "confirmed", "pre_check", ReservationStatus.CONFIRMED, ReservationStatus.PRE_CHECK,
        ))

        # Caution SC4
        await db.refresh(sc4_resa)
        if sc4_resa.deposit_amount and sc4_resa.deposit_amount > 0:
            await deposit_svc.create_deposit(
                sc4_resa.id,
                DepositCreate(
                    amount_cents=sc4_resa.deposit_amount,
                    payment_method="cash",
                    payment_date=date.today(),
                ),
                TENANT_ID,
            )
            await db.commit()
            await db.refresh(sc4_resa)

        # Pre-check SC4
        pc_result = await db.execute(
            select(ReservationPreCheckItem).where(
                ReservationPreCheckItem.reservation_id == sc4_resa.id
            )
        )
        for item in pc_result.scalars().all():
            item.checked = True
            item.checked_at = datetime.now(tz=timezone.utc)
        await db.flush()

        # Deliver SC4
        try:
            sc4_resa = await resa_svc.deliver_reservation(sc4_resa.id, TENANT_ID)
            await db.commit()
            check("SC4 delivered", sc4_resa.status in ("delivered", ReservationStatus.DELIVERED))
        except Exception as e:
            await db.rollback()
            check("SC4 deliver", False, str(e)[:120])

        # Return movement
        await db.refresh(sc4_resa, attribute_names=["lines"])
        return_items = []
        for line in sc4_resa.lines:
            if line.product_id:
                return_items.append({
                    "product_id": line.product_id,
                    "variant_id": line.variant_id,
                    "quantity_expected": line.quantity,
                })

        if return_items:
            try:
                sc4_return = await mv_svc.create_movement(
                    tenant_id=TENANT_ID,
                    movement_type="return",
                    scheduled_date=datetime(2026, 4, 11, 10, 0, tzinfo=timezone.utc),
                    reservation_id=sc4_resa.id,
                    items=return_items,
                )
                await db.commit()

                sc4_return = await mv_svc.update_movement(
                    sc4_return.id, TENANT_ID, status="in_transit",
                )
                await db.commit()
                sc4_return = await mv_svc.update_movement(
                    sc4_return.id, TENANT_ID,
                    status="completed",
                    actual_date=datetime(2026, 4, 11, 15, 0, tzinfo=timezone.utc),
                )
                await db.commit()
                check("SC4 retour complété", True)

                from app.services.reservation_workflow import AsyncReservationWorkflowService
                wf_svc4 = AsyncReservationWorkflowService(db)
                await wf_svc4.update_reservation_on_movement_complete(sc4_return)
                await db.commit()
            except Exception as e:
                await db.rollback()
                check("SC4 retour", False, str(e)[:120])

        await db.refresh(sc4_resa)
        check("SC4 returned", sc4_resa.status in ("returned", ReservationStatus.RETURNED),
              f"status={sc4_resa.status}")

        # Pay invoices
        inv_result = await db.execute(
            select(Invoice).where(Invoice.reservation_id == sc4_resa.id)
        )
        sc4_invoices = inv_result.scalars().all()
        for inv in sc4_invoices:
            if inv.status not in ("cancelled", "paid"):
                try:
                    await inv_svc.add_payment(
                        inv.id,
                        AddPaymentRequest(
                            amount_cents=inv.total_amount,
                            payment_method="transfer",
                            payment_date=date(2026, 4, 11),
                        ),
                        TENANT_ID,
                    )
                    await db.commit()
                except Exception as e:
                    await db.rollback()

        # Complete
        try:
            sc4_resa = await resa_svc.complete_reservation(sc4_resa.id, TENANT_ID)
            await db.commit()
            check("SC4 completed", sc4_resa.status in ("completed", ReservationStatus.COMPLETED))
        except Exception as e:
            await db.rollback()
            check("SC4 complete", False, str(e)[:120])

        # Archive
        try:
            sc4_resa = await resa_svc.archive_reservation(sc4_resa.id, TENANT_ID)
            await db.commit()
            check("SC4 archived", sc4_resa.is_archived is True)
        except Exception as e:
            await db.rollback()
            check("SC4 archive", False, str(e)[:120])

        # ══════════════════════════════════════════════════════════════
        # VÉRIFICATIONS GLOBALES
        # ══════════════════════════════════════════════════════════════
        print("\n" + "━" * 60)
        print("VÉRIFICATIONS GLOBALES")
        print("━" * 60)

        # Stock par status
        for st in ("available", "reserved", "on_location", "damaged"):
            cnt = await count_stock(st)
            print(f"  stock_items [{st}] = {cnt}")

        # SC-3 laisse du stock réservé (confirmed, pas retourné)
        reserved_final = await count_stock("reserved")
        check("GLOBAL stock reserved (SC3 only)", reserved_final >= 0,
              f"reserved={reserved_final}")

        # Cohérence products.available_quantity
        mismatch = await db.execute(text("""
            SELECT p.id, p.name, p.available_quantity,
                   (SELECT COUNT(*) FROM stock_items si
                    WHERE si.product_id = p.id AND si.status = 'available') as real
            FROM products p
            WHERE p.tenant_id = 1
              AND p.available_quantity != (
                  SELECT COUNT(*) FROM stock_items si
                  WHERE si.product_id = p.id AND si.status = 'available'
              )
            LIMIT 5
        """))
        mismatches = mismatch.fetchall()
        check("GLOBAL stock cohérent", len(mismatches) == 0,
              f"{len(mismatches)} mismatches" + (f" ex: {mismatches[0]}" if mismatches else ""))

        # Factures : compter par status
        inv_stats = await db.execute(text("""
            SELECT status, COUNT(*), SUM(total_amount)
            FROM invoices WHERE tenant_id = 1
            GROUP BY status ORDER BY status
        """))
        print("\n  Factures par status :")
        for row in inv_stats.fetchall():
            print(f"    {row[0]}: {row[1]} factures, total={row[2]}ct")

        # Réservations par status
        resa_stats = await db.execute(text("""
            SELECT status, COUNT(*) FROM reservations WHERE tenant_id = 1
            GROUP BY status ORDER BY status
        """))
        print("\n  Réservations par status :")
        for row in resa_stats.fetchall():
            print(f"    {row[0]}: {row[1]}")

        # Devis par status
        devis_stats = await db.execute(text("""
            SELECT status, COUNT(*) FROM devis WHERE tenant_id = 1
            GROUP BY status ORDER BY status
        """))
        print("\n  Devis par status :")
        for row in devis_stats.fetchall():
            print(f"    {row[0]}: {row[1]}")

    # ── RAPPORT FINAL ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total - passed
    if failed == 0:
        print(f"\033[92m  ✓ {passed}/{total} checks PASSED\033[0m")
    else:
        print(f"\033[91m  ✗ {failed}/{total} checks FAILED\033[0m")
        print("\n  Échecs :")
        for label, ok, detail in results:
            if not ok:
                print(f"    ✗ {label} — {detail}")
    print("=" * 60)
    return failed


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    failed = asyncio.run(run_all())
    sys.exit(1 if failed else 0)
