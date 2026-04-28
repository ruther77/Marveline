"""Service métier pour les opérations terrain (départ, retour, dommages, QR)."""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from app.core.exceptions import NotFound

from app.constants import ReservationStatus
from app.constants.errors import ErrorMessages
from app.models.damage_type import DamageType
from app.models.invoice import Invoice
from app.models.invoice_charge import InvoiceCharge
from app.models.bundle import BundleItem, ProductBundle
from app.models.reservation import Reservation, ReservationLine, ReservationPreCheckItem
from app.models.stock_item import StockItem
from app.schemas.operations import (
    DamageReportResponse,
    DepartureLineItem,
    DepartureItem,
    DepartureState,
    QrResult,
    ReturnItem,
    ReturnLineItem,
    ReturnState,
)


async def _load_lines(reservation_id: int, tenant_id: int, db: AsyncSession) -> list[ReservationLine]:
    """Charge les lignes de réservation avec produit et bundle (+ items) pour la checklist."""
    result = await db.execute(
        select(ReservationLine)
        .options(
            selectinload(ReservationLine.product),
            selectinload(ReservationLine.bundle)
            .selectinload(ProductBundle.items)
            .selectinload(BundleItem.product),
            selectinload(ReservationLine.variant),
        )
        .where(
            ReservationLine.reservation_id == reservation_id,
            ReservationLine.tenant_id == tenant_id,
        )
    )
    return list(result.scalars().all())


_DAMAGE_TYPE_UI_TO_CANONICAL: dict[str, str] = {
    "scratch": "rayure",
    "break": "casse",
    "missing": "manquant",
    "malfunction": "dysfonctionnement",
    "other": "autre",
}


def _normalize_damage_type_name(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        return "autre"
    lowered = raw.lower()
    return _DAMAGE_TYPE_UI_TO_CANONICAL.get(lowered, raw)


def _explode_line(line: ReservationLine) -> list[dict]:
    """Éclate une ligne de réservation en items individuels.

    - Produit simple → 1 item avec product_id, product_name, image, sku.
    - Bundle → N items (un par BundleItem), chaque item a le product réel
      + bundle_id/bundle_name pour regroupement frontend.
    """
    if line.bundle_id is not None and line.bundle:
        bundle = line.bundle
        bundle_items = getattr(bundle, "items", None) or []
        if not bundle_items:
            return [{
                "line_id": line.id,
                "product_id": -int(line.bundle_id),
                "product_name": bundle.name,
                "quantity_expected": line.quantity,
                "image_url": getattr(bundle, "image_url", None),
                "sku": None,
                "bundle_id": int(line.bundle_id),
                "bundle_name": bundle.name,
                "is_bundle_item": False,
            }]
        result = []
        for bi in bundle_items:
            product = bi.product
            product_name = getattr(product, "name", None) or f"Produit #{bi.product_id}"
            result.append({
                "line_id": line.id,
                "product_id": int(bi.product_id),
                "product_name": product_name,
                "quantity_expected": bi.quantity * line.quantity,
                "image_url": getattr(product, "image_url", None),
                "sku": getattr(product, "sku", None),
                "bundle_id": int(line.bundle_id),
                "bundle_name": bundle.name,
                "is_bundle_item": True,
            })
        return result

    product = line.product
    product_name = getattr(product, "name", None) if product else None
    variant = getattr(line, "variant", None)
    return [{
        "line_id": line.id,
        "product_id": int(line.product_id) if line.product_id else line.id,
        "product_name": (
            getattr(variant, "label", None)
            or product_name
            or f"Article #{line.product_id}"
        ),
        "quantity_expected": line.quantity,
        "image_url": getattr(product, "image_url", None) if product else None,
        "sku": (
            getattr(variant, "sku", None)
            or (getattr(product, "sku", None) if product else None)
        ),
        "bundle_id": None,
        "bundle_name": None,
        "is_bundle_item": False,
    }]


def _lines_to_departure_items(lines: list[ReservationLine]) -> list[DepartureItem]:
    items = []
    for line in lines:
        for data in _explode_line(line):
            items.append(DepartureItem(**data))
    return items


def _lines_to_return_items(lines: list[ReservationLine]) -> list[ReturnItem]:
    items = []
    for line in lines:
        for data in _explode_line(line):
            items.append(ReturnItem(**data))
    return items


async def _get_customer_name(customer_id: int | None, tenant_id: int, db: AsyncSession) -> str | None:
    """Récupère le display_name du client."""
    if not customer_id:
        return None
    from app.models.customer import Customer
    result = await db.execute(
        select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
    )
    customer = result.scalar_one_or_none()
    return customer.display_name if customer else None


async def get_reservation_or_404(reservation_id: int, tenant_id: int, db: AsyncSession) -> Reservation:
    """Récupère une réservation par ID + tenant ou lève 404."""
    result = await db.execute(
        select(Reservation).where(
            Reservation.id == reservation_id,
            Reservation.tenant_id == tenant_id,
        )
    )
    res = result.scalar_one_or_none()
    if not res:
        raise NotFound(ErrorMessages.RESERVATION_NOT_FOUND)
    return res


async def _count_prechecks(
    reservation_id: int, tenant_id: int, db: AsyncSession, checked: bool | None = None
) -> int:
    q = select(func.count()).select_from(ReservationPreCheckItem).where(
        ReservationPreCheckItem.reservation_id == reservation_id,
        ReservationPreCheckItem.tenant_id == tenant_id,
    )
    if checked is not None:
        q = q.where(ReservationPreCheckItem.checked == checked)  # noqa: E712
    result = await db.execute(q)
    return result.scalar() or 0


async def _complete_linked_movement(
    reservation_id: int,
    tenant_id: int,
    db: AsyncSession,
    *,
    movement_type: str,
) -> None:
    """Complète le mouvement lié à une réservation via complete_movement(_internal=True).

    Silencieux si aucun mouvement trouvé ou déjà complété.
    """
    from app.services.inventory_movement import MovementService
    from app.models.inventory_movement import InventoryMovement
    from app.constants import MovementStatus

    result = await db.execute(
        select(InventoryMovement).where(
            InventoryMovement.reservation_id == reservation_id,
            InventoryMovement.tenant_id == tenant_id,
            InventoryMovement.movement_type == movement_type,
            InventoryMovement.is_active.is_(True),
        )
    )
    movement = result.scalar_one_or_none()
    if not movement:
        return
    if movement.status == MovementStatus.COMPLETED.value:
        return

    # Passer en in_transit si encore scheduled (prérequis VALID_TRANSITIONS)
    svc = MovementService(db)
    if movement.status == MovementStatus.SCHEDULED.value:
        await svc.update_movement(
            movement.id, tenant_id, status=MovementStatus.IN_TRANSIT.value,
        )

    await svc.complete_movement(movement.id, tenant_id, _internal=True)


async def get_departure_state(reservation_id: int, tenant_id: int, db: AsyncSession) -> DepartureState:
    """Retourne l'état de la checklist de départ avec les lignes de réservation."""
    res = await get_reservation_or_404(reservation_id, tenant_id, db)
    lines = await _load_lines(reservation_id, tenant_id, db)
    total = await _count_prechecks(reservation_id, tenant_id, db)
    checked = await _count_prechecks(reservation_id, tenant_id, db, checked=True)
    prechecks_ok = res.status == ReservationStatus.PRE_CHECK and total > 0 and checked == total
    from app.services.deposit import DepositService
    deposit_svc = DepositService(db)
    has_held = await deposit_svc.has_held_deposit(reservation_id, tenant_id)
    deposit_ok = (res.deposit_amount_cents or 0) == 0 or (res.deposit_paid and has_held)
    can_depart = prechecks_ok and deposit_ok

    if not can_depart:
        blocked_reason: str | None = "pre_check_incomplete" if not prechecks_ok else "deposit_required"
    else:
        blocked_reason = None

    cust_name = await _get_customer_name(res.customer_id, tenant_id, db)
    return DepartureState(
        reservation_id=res.id,
        reference=res.reference,
        customer_name=cust_name,
        status=res.status,
        total_items=total,
        checked_items=checked,
        can_depart=can_depart,
        departure_blocked_reason=blocked_reason,
        items=_lines_to_departure_items(lines),
    )


async def validate_departure(
    reservation_id: int,
    tenant_id: int,
    db: AsyncSession,
    signature_url: str | None = None,
    items: list[DepartureLineItem] | None = None,
) -> DepartureState:
    """Valide le départ : transition pre_check → delivered."""
    res = await get_reservation_or_404(reservation_id, tenant_id, db)

    if res.status != ReservationStatus.PRE_CHECK:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot depart with status '{res.status}'. Required: pre_check.",
        )

    unchecked = await _count_prechecks(reservation_id, tenant_id, db, checked=False)
    if unchecked > 0:
        raise HTTPException(
            status_code=400,
            detail=ErrorMessages.RESERVATION_PRE_CHECK_INCOMPLETE,
        )

    # Vérification caution alignée sur ReservationService.deliver_reservation :
    # flag deposit_paid ET Deposit ORM en statut "held" requis
    from app.services.deposit import DepositService
    deposit_svc = DepositService(db)
    has_held = await deposit_svc.has_held_deposit(reservation_id, tenant_id)
    deposit_ok = (res.deposit_amount_cents or 0) == 0 or (res.deposit_paid and has_held)
    if not deposit_ok:
        raise HTTPException(
            status_code=400,
            detail=ErrorMessages.RESERVATION_DEPOSIT_REQUIRED,
        )

    # La signature passée en paramètre prime sur celle persistée (workflow operations).
    if signature_url:
        res.signature_url = signature_url

    # Guards business additionnels (acompte payé + signature obligatoire).
    # Configurables par tenant via tenant_settings.
    from app.services.reservation_workflow import assert_delivery_guards
    await assert_delivery_guards(db, res, tenant_id)

    if items:
        await _validate_departure_items(reservation_id, tenant_id, db, items)

    # Compléter le mouvement DEPARTURE lié (si existant)
    await _complete_linked_movement(reservation_id, tenant_id, db, movement_type="departure")

    res.status = ReservationStatus.DELIVERED
    # signature_url déjà appliquée avant les guards (cf. supra)
    await db.commit()
    await db.refresh(res)

    total = await _count_prechecks(reservation_id, tenant_id, db)
    return DepartureState(
        reservation_id=res.id,
        reference=res.reference,
        status=res.status,
        total_items=total,
        checked_items=total,
        can_depart=False,
    )


async def _validate_departure_items(
    reservation_id: int,
    tenant_id: int,
    db: AsyncSession,
    items: list[DepartureLineItem],
) -> None:
    """Valide les saisies de départ envoyées par le front.

    Bloque la validation standard si au moins une ligne est incomplète/endommagée,
    pour forcer l'action explicite `departure/block`.
    """
    lines = await _load_lines(reservation_id, tenant_id, db)
    lines_by_id = {line.id: line for line in lines}

    # Construire le mapping (line_id, product_id) → quantité attendue
    # en décomposant les bundles comme le fait _explode_line.
    expected_qty: dict[tuple[int, int], int] = {}
    for line in lines:
        for data in _explode_line(line):
            key = (data["line_id"], data["product_id"])
            expected_qty[key] = data["quantity_expected"]

    risky_conditions = {"damaged", "missing"}

    blockers: list[str] = []
    for item in items:
        line = lines_by_id.get(item.line_id)
        if line is None:
            raise HTTPException(
                status_code=400,
                detail=ErrorMessages.DEPARTURE_LINE_NOT_FOUND,
            )

        if item.quantity_loaded < 0:
            raise HTTPException(
                status_code=400,
                detail=ErrorMessages.RESERVATION_LINE_QUANTITY_INVALID,
            )

        qty_expected = expected_qty.get(
            (item.line_id, item.product_id), line.quantity,
        )

        if item.quantity_loaded > qty_expected:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Quantité chargée ({item.quantity_loaded}) supérieure à la quantité attendue "
                    f"({qty_expected}) pour la ligne {item.line_id}"
                ),
            )

        if item.quantity_loaded < qty_expected:
            blockers.append(f"ligne {item.line_id}: quantité incomplète")
        if item.condition in risky_conditions:
            blockers.append(f"ligne {item.line_id}: état {item.condition}")

    if blockers:
        detail = (
            "Départ bloqué: contrôles terrain en anomalie ("
            + ", ".join(blockers)
            + "). Utilisez /operations/departure/{id}/block."
        )
        raise HTTPException(status_code=400, detail=detail)


async def block_departure(
    reservation_id: int,
    tenant_id: int,
    db: AsyncSession,
    reason: str | None = None,
) -> DepartureState:
    """Bloque le départ : transition confirmed/pre_check → confirmed_risk."""
    res = await get_reservation_or_404(reservation_id, tenant_id, db)

    if res.status not in (ReservationStatus.CONFIRMED, ReservationStatus.PRE_CHECK):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot block departure with status '{res.status}'. Allowed: confirmed, pre_check.",
        )

    res.status = ReservationStatus.CONFIRMED_RISK
    if reason:
        existing_notes = res.notes or ""
        block_note = f"[BLOCAGE DEPART] {reason}"
        res.notes = f"{existing_notes}\n{block_note}".strip() if existing_notes else block_note
    await db.commit()
    await db.refresh(res)

    total = await _count_prechecks(reservation_id, tenant_id, db)
    checked = await _count_prechecks(reservation_id, tenant_id, db, checked=True)
    return DepartureState(
        reservation_id=res.id,
        reference=res.reference,
        status=res.status,
        total_items=total,
        checked_items=checked,
        can_depart=False,
    )


async def get_return_state(reservation_id: int, tenant_id: int, db: AsyncSession) -> ReturnState:
    """Retourne l'état du retour avec les lignes de réservation."""
    res = await get_reservation_or_404(reservation_id, tenant_id, db)
    lines = await _load_lines(reservation_id, tenant_id, db)
    cust_name = await _get_customer_name(res.customer_id, tenant_id, db)
    return ReturnState(
        reservation_id=res.id,
        reference=res.reference,
        customer_name=cust_name,
        status=res.status,
        delivery_date=res.delivery_date,
        return_date=res.return_date,
        can_return=(res.status in (ReservationStatus.DELIVERED, ReservationStatus.EXTENDED)),
        items=_lines_to_return_items(lines),
    )


async def validate_return(
    reservation_id: int,
    tenant_id: int,
    db: AsyncSession,
    signature_url: str | None = None,
    items: list[ReturnLineItem] | None = None,
) -> ReturnState:
    """Valide le retour : transition delivered/extended → returned.

    Si des items avec dommages sont fournis :
    - Crée/récupère le DamageType
    - Crée un InventoryMovementDamage
    - Auto-crée une InvoiceCharge sur la facture de la réservation (si fee > 0)
    - Passe la réservation en returned_dispute si des dommages sont déclarés
    """
    res = await get_reservation_or_404(reservation_id, tenant_id, db)

    if res.status not in (ReservationStatus.DELIVERED, ReservationStatus.EXTENDED):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Retour impossible depuis le statut '{res.status}'. "
                "Statut requis : delivered ou extended."
            ),
        )

    has_damages = False
    if items:
        has_damages = await _process_return_items(reservation_id, tenant_id, db, items)
        # Persister quantity_actual et condition sur les MovementItem du retour
        await _persist_return_quantities(reservation_id, tenant_id, db, items)

    # Compléter le mouvement RETURN lié (si existant)
    # _complete_linked_movement → complete_movement → _update_stock_on_complete
    # qui fait on_location → available (restitution du matériel prêté)
    # _update_stock_on_complete lit quantity_actual et condition depuis MovementItem
    await _complete_linked_movement(reservation_id, tenant_id, db, movement_type="return")
    # Note: release_stock_for_lines (reserved → available) n'est PAS appelé ici.
    # Au retour, le stock est en on_location (pas reserved). La restitution
    # est gérée par _update_stock_on_complete dans complete_movement.
    # release_stock_for_lines est réservé aux annulations (cancel_reservation).

    if has_damages:
        res.status = ReservationStatus.RETURNED_DISPUTE
    else:
        res.status = ReservationStatus.RETURNED
    if signature_url:
        res.signature_url = signature_url
    await db.commit()
    await db.refresh(res)

    # D — Solde restant après retour (warning non bloquant côté UI).
    invoice_q = await db.execute(
        select(Invoice)
        .where(
            Invoice.reservation_id == reservation_id,
            Invoice.tenant_id == tenant_id,
            Invoice.status != "cancelled",
        )
        .order_by(Invoice.id.desc())
        .limit(1)
    )
    invoice = invoice_q.scalar_one_or_none()
    balance_due = 0
    if invoice is not None:
        balance_due = max(
            0,
            (invoice.total_amount_cents or 0) - (invoice.paid_amount_cents or 0),
        )

    return ReturnState(
        reservation_id=res.id,
        reference=res.reference,
        status=res.status,
        delivery_date=res.delivery_date,
        return_date=res.return_date,
        can_return=False,
        balance_due_cents=balance_due,
    )


async def _persist_return_quantities(
    reservation_id: int,
    tenant_id: int,
    db: AsyncSession,
    items: list[ReturnLineItem],
) -> None:
    """Persiste quantity_actual et condition sur les MovementItem du retour.

    Cherche le mouvement retour lié à la réservation et met à jour chaque
    MovementItem avec les données terrain (quantités réellement retournées,
    état du matériel). Ces valeurs sont ensuite lues par
    _update_stock_on_complete pour les transitions stock.
    """
    from app.models.inventory_movement import InventoryMovement, MovementItem

    result = await db.execute(
        select(InventoryMovement)
        .options(selectinload(InventoryMovement.items))
        .where(
            InventoryMovement.reservation_id == reservation_id,
            InventoryMovement.tenant_id == tenant_id,
            InventoryMovement.movement_type == "return",
            InventoryMovement.is_active.is_(True),
        )
    )
    movement = result.scalar_one_or_none()
    if not movement:
        return

    items_by_line = {it.line_id: it for it in items}

    # Matcher via event_item_id (= line.id) — fonctionne pour produits simples ET bundles.
    # Un bundle produit N MovementItem pour le même event_item_id.
    line_to_movement_items: dict[int, list[MovementItem]] = {}
    for mi in movement.items:
        if mi.event_item_id is not None:
            line_to_movement_items.setdefault(mi.event_item_id, []).append(mi)

    for line_id, return_item in items_by_line.items():
        mis = line_to_movement_items.get(line_id, [])
        for mi in mis:
            mi.quantity_actual = return_item.quantity_returned
            mi.condition = return_item.condition

    await db.flush()


async def _process_return_items(
    reservation_id: int,
    tenant_id: int,
    db: AsyncSession,
    items: list[ReturnLineItem],
) -> bool:
    """Traite les items du retour — crée dommages + InvoiceCharge si applicable.

    Retourne True si au moins un dommage a été déclaré.
    """
    from app.models.invoice import Invoice
    from app.models.invoice_charge import InvoiceCharge
    from app.models.movement_damage import InventoryMovementDamage

    has_damages = False

    # Trouver la facture associée à la réservation (prendre la plus récente active)
    invoice_result = await db.execute(
        select(Invoice)
        .where(
            Invoice.reservation_id == reservation_id,
            Invoice.tenant_id == tenant_id,
        )
        .order_by(Invoice.id.desc())
        .limit(1)
    )
    invoice = invoice_result.scalar_one_or_none()

    for item in items:
        if not item.damages:
            continue
        has_damages = True

        for dmg in item.damages:
            # Crée ou réutilise le DamageType
            damage_type = await _get_or_create_damage_type(
                db, tenant_id, dmg.damage_type_name, dmg.fee_cents
            )

            # Auto-création InvoiceCharge si fee > 0 et facture disponible
            charge_id: int | None = None
            if dmg.fee_cents > 0 and invoice is not None:
                charge = InvoiceCharge(
                    tenant_id=tenant_id,
                    invoice_id=invoice.id,
                    charge_type="DAMAGE",
                    description=dmg.description or dmg.damage_type_name,
                    amount_cents=dmg.fee_cents,
                    damage_type_id=damage_type.id,
                )
                db.add(charge)
                await db.flush()
                charge_id = charge.id
                # Mettre à jour total HT + TVA de la facture
                from app.services.invoice import update_invoice_after_charge
                await update_invoice_after_charge(invoice, dmg.fee_cents, db)

            # Enregistrement du dommage
            movement_damage = InventoryMovementDamage(
                tenant_id=tenant_id,
                movement_item_unit_id=item.line_id,
                damage_type_id=damage_type.id,
                description=dmg.description or dmg.damage_type_name,
                fee_cents=dmg.fee_cents,
                photo_urls=dmg.photo_urls or None,
                invoice_charge_id=charge_id,
            )
            db.add(movement_damage)

    await db.flush()

    # Auto-retenir la caution si des dommages sont declares
    if has_damages:
        from app.services.deposit import DepositService
        deposit_service = DepositService(db)
        await deposit_service.auto_retain_from_damages(reservation_id, tenant_id)

    return has_damages


async def declare_damage(
    reservation_id: int,
    tenant_id: int,
    db: AsyncSession,
    damage_type_name: str,
    description: str,
    fee_cents: int,
) -> DamageReportResponse:
    """Déclare un dommage lors du retour. Crée ou réutilise un DamageType."""
    res = await get_reservation_or_404(reservation_id, tenant_id, db)

    if res.status not in (
        ReservationStatus.DELIVERED,
        ReservationStatus.EXTENDED,
        ReservationStatus.RETURNED,
        ReservationStatus.RETURNED_DISPUTE,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot declare damage with status '{res.status}'.",
        )

    damage_type = await _get_or_create_damage_type(
        db, tenant_id, damage_type_name, fee_cents
    )

    if res.status == ReservationStatus.RETURNED:
        res.status = ReservationStatus.RETURNED_DISPUTE
        await db.flush()

    # Créer InvoiceCharge si fee_cents > 0 et une facture active existe
    invoice_charge_id: int | None = None
    if fee_cents and fee_cents > 0:
        inv_result = await db.execute(
            select(Invoice).where(
                Invoice.reservation_id == reservation_id,
                Invoice.tenant_id == tenant_id,
                Invoice.status.notin_(["cancelled"]),
            ).limit(1)
        )
        active_invoice = inv_result.scalar_one_or_none()
        if active_invoice:
            charge = InvoiceCharge(
                tenant_id=tenant_id,
                invoice_id=active_invoice.id,
                charge_type="DAMAGE",
                description=description or f"Dommage : {damage_type_name}",
                amount_cents=fee_cents,
                damage_type_id=damage_type.id,
            )
            db.add(charge)
            await db.flush()
            invoice_charge_id = charge.id
            # Mettre à jour total HT + TVA de la facture
            from app.services.invoice import update_invoice_after_charge
            await update_invoice_after_charge(active_invoice, fee_cents, db)

    # Auto-retenir la caution si des dommages sont factures
    from app.services.deposit import DepositService
    deposit_service = DepositService(db)
    await deposit_service.auto_retain_from_damages(reservation_id, tenant_id)

    await db.commit()
    await db.refresh(damage_type)

    return DamageReportResponse(
        reservation_id=reservation_id,
        damage_type_id=damage_type.id,
        damage_type_name=damage_type.name,
        description=description,
        fee_cents=fee_cents,
        invoice_charge_id=invoice_charge_id,
    )


async def _get_or_create_damage_type(
    db: AsyncSession,
    tenant_id: int,
    damage_type_name: str,
    default_fee_cents: int,
) -> DamageType:
    """Récupère un type de dommage en normalisant les catégories UI frontend."""
    normalized_name = _normalize_damage_type_name(damage_type_name)

    dt_result = await db.execute(
        select(DamageType).where(
            func.lower(DamageType.name) == normalized_name.lower(),
            DamageType.tenant_id == tenant_id,
            DamageType.is_active == True,  # noqa: E712
        ).limit(1)
    )
    damage_type = dt_result.scalar_one_or_none()
    if damage_type:
        return damage_type

    damage_type = DamageType(
        tenant_id=tenant_id,
        name=normalized_name,
        default_fee_cents=default_fee_cents,
    )
    db.add(damage_type)
    await db.flush()
    return damage_type


async def resolve_qr(code: str, tenant_id: int, db: AsyncSession) -> QrResult:
    """Résout un code QR / numéro de série → product_id + stock_item_id."""
    result = await db.execute(
        select(StockItem)
        .options(selectinload(StockItem.product))
        .where(
            StockItem.serial_number == code,
            StockItem.tenant_id == tenant_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFound(ErrorMessages.STOCK_ITEM_NOT_FOUND)

    return QrResult(
        product_id=item.product_id,
        product_name=item.product.name if item.product else "",
        stock_item_id=item.id,
        serial_number=item.serial_number,
        stock_status=item.status,
    )
