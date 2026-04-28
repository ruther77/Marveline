"""Service métier pour les réservations."""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ErrorMessages, Limits, MovementType, ReservationStatus
from app.constants.business import (
    ADVANCE_DUE_DAYS,
    DEPOSIT_RATE,
    EVENT_TYPE_MIN_DAYS,
    SELFIE_BOOTH_DEPOSIT_CENTS,
)
from app.models.reservation import Reservation, ReservationLine, ReservationPreCheckItem
from app.repositories.customer import AsyncCustomerRepository
from app.repositories.product import AsyncProductRepository
from app.repositories.product_variant import AsyncProductVariantRepository
from app.repositories.reservation import (
    AsyncReservationLineRepository,
    AsyncReservationRepository,
)
from app.repositories.bundle import AsyncBundleRepository
from app.repositories.stock_item import AsyncStockItemRepository
from app.schemas.invoice import InvoiceCreate
from app.schemas.reservation import ReservationCreate, ReservationLineCreate, ReservationUpdate
from app.services.product import AsyncProductService

logger = logging.getLogger(__name__)


# Champs opérationnels modifiables sans avenant (notes, livraison, contacts).
# Tout autre champ d'une résa convertie depuis un devis (lines, dates, pricing)
# doit passer par POST /reservations/{id}/amend qui crée une nouvelle version
# du devis source.
RESERVATION_OPERATIONAL_FIELDS: frozenset[str] = frozenset({
    "notes",
    "deposit_paid",
    "delivery_zone_id",
    "delivery_method",
    "delivery_instructions",
    "carrier_name",
    "carrier_code",
    "delivery_address",
    "delivery_city",
    "delivery_postal_code",
})


class ReservationService:
    """Service async pour la gestion des réservations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        # Flag activé temporairement par amend_reservation() pour bypasser
        # les guards devis_id sur update_reservation/add_line/remove_line.
        self._in_amend: bool = False
        self.repo = AsyncReservationRepository(db)
        self.line_repo = AsyncReservationLineRepository(db)
        self.customer_repo = AsyncCustomerRepository(db)
        self.product_repo = AsyncProductRepository(db)
        self.variant_repo = AsyncProductVariantRepository(db)
        self.product_service = AsyncProductService(db)
        self.bundle_repo = AsyncBundleRepository(db)
        self.stock_item_repo = AsyncStockItemRepository(db)

    async def _resolve_variant(
        self, product_id: int, variant_id: int, tenant_id: int
    ) -> "ProductVariant":
        """Charge et valide la variante. Retourne l'objet ProductVariant.

        Chaque produit a obligatoirement au moins 1 variante.
        variant_id est requis quand product_id est fourni.
        """
        from app.models.product_variant import ProductVariant

        variant = await self.variant_repo.get_by_id(variant_id, tenant_id)
        if not variant or variant.product_id != product_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.VARIANT_NOT_FOUND,
            )
        return variant

    async def _sync_product_stock_from_variants(
        self, product_id: int, tenant_id: int
    ) -> None:
        """Resynchronise le stock du produit parent depuis ses variantes."""
        from app.services.product_variant import ProductVariantService
        variant_service = ProductVariantService(self.db)
        await variant_service._sync_product_stock(product_id, tenant_id)

    async def _resolve_bundle_line(
        self, bundle_id: int, tenant_id: int
    ) -> tuple[int, int]:
        """Valide un bundle et retourne (prix unitaire, caution par unité).

        La caution est la somme des cautions des produits individuels
        pondérées par leur quantité dans le bundle.
        """
        bundle = await self.bundle_repo.get_with_items(bundle_id, tenant_id)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bundle with id {bundle_id} not found",
            )
        deposit_per_unit = sum(
            item.quantity * item.product.deposit_amount_cents
            for item in bundle.items
            if item.product
        )
        return bundle.bundle_price_cents, deposit_per_unit

    async def _reserve_stock_for_bundle(
        self, bundle_id: int, line_quantity: int,
        tenant_id: int, reservation_id: int,
    ) -> None:
        """Réserve le stock individuel pour chaque item d'un bundle.

        Source de vérité unique : stock_items.
        reserve_n + sync_available (pas de décrément direct sur product/variant).
        """
        bundle = await self.bundle_repo.get_with_items(bundle_id, tenant_id)
        if not bundle:
            return
        for item in bundle.items:
            qty = item.quantity * line_quantity
            await self.stock_item_repo.reserve_n(
                product_id=item.product_id,
                n=qty,
                tenant_id=tenant_id,
                reservation_id=reservation_id,
            )
            await self.product_repo.sync_available_from_variants(
                item.product_id, tenant_id,
            )

    async def _release_stock_for_bundle(
        self, bundle_id: int, line_quantity: int, tenant_id: int,
        reservation_id: int | None = None,
    ) -> None:
        """Libère le stock individuel pour chaque item d'un bundle.

        Source de vérité unique : stock_items.
        release_n + sync_available (pas d'incrément direct sur product/variant).
        """
        bundle = await self.bundle_repo.get_with_items(bundle_id, tenant_id)
        if not bundle:
            return
        for item in bundle.items:
            qty = item.quantity * line_quantity
            await self._release_stock(
                product_id=item.product_id,
                quantity=qty,
                tenant_id=tenant_id,
                product_name=getattr(item.product, "name", None),
                reservation_id=reservation_id,
            )

    async def _uses_stock_items(self, product_id: int, tenant_id: int) -> bool:
        counts = await self.stock_item_repo.count_by_statuses(product_id, tenant_id)
        return sum(counts.values()) > 0

    async def _reserve_stock(
        self,
        product_id: int,
        quantity: int,
        tenant_id: int,
        reservation_id: int,
        variant_id: int | None = None,
        product_name: str | None = None,
        variant_label: str | None = None,
    ) -> None:
        if await self._uses_stock_items(product_id, tenant_id):
            await self.stock_item_repo.reserve_n(
                product_id=product_id,
                n=quantity,
                tenant_id=tenant_id,
                reservation_id=reservation_id,
                variant_id=variant_id,
            )
            if variant_id is not None:
                await self.product_repo.sync_available_from_variants(product_id, tenant_id)
            return

        if variant_id is not None:
            success = await self.variant_repo.reserve_stock(variant_id, quantity, tenant_id)
            if success:
                await self.product_repo.sync_available_from_variants(product_id, tenant_id)
                return
            variant_suffix = f" (variante {variant_label})" if variant_label else ""
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Stock insuffisant pour {product_name or f'produit #{product_id}'}"
                    f"{variant_suffix}: {quantity} demande(s)."
                ),
            )

        success = await self.product_repo.reserve_stock(product_id, quantity, tenant_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Stock insuffisant pour {product_name or f'produit #{product_id}'}: "
                    f"{quantity} demande(s)."
                ),
            )

    async def _release_stock(
        self,
        product_id: int,
        quantity: int,
        tenant_id: int,
        variant_id: int | None = None,
        product_name: str | None = None,
        reservation_id: int | None = None,
    ) -> None:
        if await self._uses_stock_items(product_id, tenant_id):
            reserved_count = await self.stock_item_repo.count_by_status(
                product_id, "reserved", tenant_id
            )
            if reserved_count >= quantity:
                await self.stock_item_repo.release_n(
                    product_id=product_id,
                    n=quantity,
                    tenant_id=tenant_id,
                    variant_id=variant_id,
                    reservation_id=reservation_id,
                )
                if variant_id is not None:
                    await self.product_repo.sync_available_from_variants(product_id, tenant_id)
            return

        if variant_id is not None:
            await self.variant_repo.release_stock(variant_id, quantity, tenant_id)
            await self.product_repo.sync_available_from_variants(product_id, tenant_id)
            return

        released = await self.product_repo.release_stock(product_id, quantity, tenant_id)
        if not released:
            logger.warning(
                "Unable to release aggregate stock for %s (product_id=%s, qty=%s, tenant=%s)",
                product_name or f"produit #{product_id}",
                product_id,
                quantity,
                tenant_id,
            )

    async def release_stock_for_lines(
        self, lines: list, tenant_id: int, reservation_id: int | None = None,
    ) -> None:
        """Libère le stock réservé pour toutes les lignes d'une réservation.

        Appelé lors de l'annulation (stock en reserved → available).
        Source de vérité unique : stock_items.

        ``reservation_id`` doit être fourni pour ne libérer que les items
        de cette résa et éviter d'impacter une autre réservation concurrente
        sur le même produit.
        """
        for line in lines:
            if line.bundle_id:
                await self._release_stock_for_bundle(
                    line.bundle_id, line.quantity, tenant_id,
                    reservation_id=reservation_id,
                )
            else:
                await self._release_stock(
                    product_id=line.product_id,
                    quantity=line.quantity,
                    tenant_id=tenant_id,
                    variant_id=line.variant_id,
                    product_name=getattr(line.product, "name", None),
                    reservation_id=reservation_id,
                )

    async def list_reservations(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        customer_id: Optional[int] = None,
        assigned_user_id: Optional[int] = None,
    ) -> tuple[list[Reservation], int]:
        return await self.repo.list_for_display(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            status=status_filter,
            start_date=start_date,
            end_date=end_date,
            customer_id=customer_id,
            assigned_user_id=assigned_user_id,
        )

    async def get_reservation(self, reservation_id: int, tenant_id: int) -> Reservation:
        reservation = await self.repo.get_by_id_with_relations(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND,
            )
        return reservation

    async def generate_reference(self) -> str:
        from sqlalchemy import cast, func as sa_func, select, Integer

        year = datetime.now().year
        max_counter = await self.db.scalar(
            select(
                sa_func.max(cast(sa_func.split_part(Reservation.reference, "-", 3), Integer))
            ).where(Reservation.reference.like(f"RES-{year}-%"))
        ) or 0

        next_counter = max_counter + 1
        if next_counter > 9999:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=ErrorMessages.RESERVATION_REFERENCE_OVERFLOW,
            )
        return f"RES-{year}-{next_counter:0{Limits.RESERVATION_REFERENCE_PADDING}d}"

    async def create_reservation(
        self,
        reservation_data: ReservationCreate,
        tenant_id: int,
    ) -> Reservation:
        customer = await self.customer_repo.get_by_id(
            reservation_data.customer_id, tenant_id
        )
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.CUSTOMER_NOT_FOUND,
            )

        rental_days = (
            reservation_data.return_date - reservation_data.delivery_date
        ).days + 1

        if reservation_data.event_type:
            min_days = EVENT_TYPE_MIN_DAYS.get(reservation_data.event_type, 1)
            if rental_days < min_days:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Minimum {min_days} jour(s) de location pour un evenement {reservation_data.event_type}",
                )

        _MAX_REF_RETRIES = 3
        reservation = None
        for _attempt in range(_MAX_REF_RETRIES):
            reference = await self.generate_reference()
            _obj = Reservation(
                tenant_id=tenant_id,
                customer_id=reservation_data.customer_id,
                reference=reference,
                event_date=reservation_data.event_date,
                delivery_date=reservation_data.delivery_date,
                return_date=reservation_data.return_date,
                event_location=reservation_data.event_location,
                event_type=reservation_data.event_type,
                event_name=reservation_data.event_name,
                guest_count=reservation_data.guest_count,
                notes=reservation_data.notes,
                status=ReservationStatus.DRAFT,
                total_amount_cents=0,
                deposit_amount_cents=0,
                deposit_paid=False,
                delivery_zone_id=reservation_data.delivery_zone_id,
                delivery_method=reservation_data.delivery_method,
                delivery_fee_cents=reservation_data.delivery_fee_cents or 0,
                delivery_instructions=reservation_data.delivery_instructions,
                carrier_name=reservation_data.carrier_name,
                carrier_code=reservation_data.carrier_code,
                delivery_address=reservation_data.delivery_address,
                delivery_city=reservation_data.delivery_city,
                delivery_postal_code=reservation_data.delivery_postal_code,
            )
            try:
                async with self.db.begin_nested():
                    reservation = await self.repo.create(_obj)
                break
            except IntegrityError:
                logger.warning(
                    "Collision référence réservation %s (tentative %d/%d)",
                    reference,
                    _attempt + 1,
                    _MAX_REF_RETRIES,
                )
                if _attempt == _MAX_REF_RETRIES - 1:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=ErrorMessages.RESERVATION_REFERENCE_OVERFLOW,
                    )

        total_amount = 0
        deposit_amount = 0

        for line_data in reservation_data.lines:
            if line_data.bundle_id:
                unit_price, deposit_per_unit = await self._resolve_bundle_line(
                    line_data.bundle_id, tenant_id
                )
                subtotal = line_data.quantity * unit_price * rental_days
                line_deposit = line_data.quantity * deposit_per_unit
                line = ReservationLine(
                    tenant_id=tenant_id,
                    reservation_id=reservation.id,
                    bundle_id=line_data.bundle_id,
                    quantity=line_data.quantity,
                    unit_price_cents=unit_price,
                    subtotal_cents=subtotal,
                )
            else:
                product = await self.product_repo.get_by_id(line_data.product_id, tenant_id)
                if not product:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Product with id {line_data.product_id} not found",
                    )
                # Auto-résolution variante unique si non spécifiée
                resolved_variant_id = line_data.variant_id
                if resolved_variant_id is None:
                    variants = await self.variant_repo.list_by_product(
                        line_data.product_id, tenant_id
                    )
                    if len(variants) == 1:
                        resolved_variant_id = variants[0].id
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Le produit {product.name} a {len(variants)} variante(s). "
                                "Veuillez spécifier variant_id."
                            ),
                        )
                line_data.variant_id = resolved_variant_id  # persist resolved
                variant = await self._resolve_variant(
                    line_data.product_id, resolved_variant_id, tenant_id
                )
                if product.requires_advance_booking_days > 0:
                    min_delivery = date.today() + timedelta(days=product.requires_advance_booking_days)
                    if reservation_data.delivery_date < min_delivery:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=(
                                f"Le produit '{product.name}' nécessite une réservation au moins "
                                f"{product.requires_advance_booking_days} jours à l'avance "
                                f"(date de livraison minimum : {min_delivery.isoformat()})"
                            ),
                        )
                unit_price = variant.price_per_day_cents if variant.price_per_day_cents is not None else product.price_per_day_cents
                subtotal = line_data.quantity * unit_price * rental_days
                line_deposit = line_data.quantity * variant.deposit_amount_cents
                line = ReservationLine(
                    tenant_id=tenant_id,
                    reservation_id=reservation.id,
                    product_id=line_data.product_id,
                    variant_id=line_data.variant_id,
                    quantity=line_data.quantity,
                    unit_price_cents=unit_price,
                    subtotal_cents=subtotal,
                )
            await self.line_repo.create(line)
            total_amount += subtotal
            deposit_amount += line_deposit

        reservation.total_amount_cents = total_amount
        reservation.deposit_amount_cents = deposit_amount
        await self.repo.update(reservation)

        return reservation

    async def confirm_reservation(
        self,
        reservation_id: int,
        tenant_id: int,
    ) -> Reservation:
        reservation = await self.repo.get_by_id_with_relations(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND,
            )

        if reservation.status != ReservationStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm reservation with status '{reservation.status}'. Must be 'draft'.",
            )

        try:
            for line in reservation.lines:
                if line.bundle_id:
                    await self._reserve_stock_for_bundle(
                        line.bundle_id, line.quantity,
                        tenant_id, reservation.id,
                    )
                else:
                    # Auto-résolution variante si absente (produit mono-variante)
                    variant_id = line.variant_id
                    if not variant_id and line.product_id:
                        variants = await self.variant_repo.list_by_product(
                            line.product_id, tenant_id
                        )
                        if len(variants) == 1:
                            variant_id = variants[0].id
                            line.variant_id = variant_id

                    await self._reserve_stock(
                        product_id=line.product_id,
                        quantity=line.quantity,
                        tenant_id=tenant_id,
                        reservation_id=reservation.id,
                        variant_id=variant_id,
                        product_name=getattr(line.product, "name", None),
                        variant_label=getattr(line.variant, "label", None),
                    )
        except HTTPException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm reservation: {e.detail}",
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm reservation: {e}",
            ) from e

        # Ne pas ecraser deposit_amount_cents si un Deposit ORM existe deja (B1 — conversion devis)
        from app.services.deposit import DepositService
        deposit_svc = DepositService(self.db)
        existing_deposits = await deposit_svc.list_deposits(reservation.id, tenant_id)
        if not existing_deposits:
            reservation.deposit_amount_cents = await self._calculate_deposit(reservation, tenant_id)

        reservation.status = ReservationStatus.CONFIRMED
        await self.repo.update(reservation)

        self._notify_reservation_confirmed(reservation)
        await self._auto_generate_invoice(reservation, tenant_id)

        from app.services.reservation_workflow import AsyncReservationWorkflowService
        workflow = AsyncReservationWorkflowService(self.db)
        await workflow.auto_generate_departure_movement(reservation, tenant_id)

        # Générer les items de precheck (statut reste CONFIRMED)
        await self._generate_precheck_items(reservation, tenant_id)

        return reservation

    async def _auto_generate_invoice(
        self,
        reservation: Reservation,
        tenant_id: int,
    ) -> None:
        """Genere 1 facture unique (100% du total) a la confirmation.

        Le montant d'acompte (advance_rate depuis tenant_settings) est indicatif :
        il indique au client combien payer en premier versement via la table payments.
        La facture elle-meme porte le montant total ; les paiements partiels viennent
        mettre a jour paid_amount_cents sur cette facture unique.

        - due_date = today + ADVANCE_DUE_DAYS (delai premier versement)
        - Remplit reservation.advance_payment_amount_cents et balance_due_date
        """
        from app.services.invoice import AsyncInvoiceService

        invoice_service = AsyncInvoiceService(self.db)
        today = date.today()
        due_date = today + timedelta(days=ADVANCE_DUE_DAYS)

        # Calcul acompte indicatif depuis tenant_settings (configurable)
        settings = await self._get_tenant_settings(tenant_id)
        advance_rate = settings.advance_rate if settings else 0.40
        advance_cents = int(reservation.total_amount_cents * advance_rate)

        reservation.advance_payment_amount_cents = advance_cents
        reservation.balance_due_date = reservation.event_date

        invoice_data = InvoiceCreate(
            reservation_id=reservation.id,
            issue_date=today,
            due_date=due_date,
        )
        try:
            invoice = await invoice_service.generate_from_reservation(
                invoice_data,
                tenant_id,
                invoice_type="full",
            )
            logger.info(
                "Auto-generated invoice %s for reservation %s "
                "(tenant=%d, total=%d cents, advance=%d cents)",
                invoice.invoice_number,
                reservation.reference,
                tenant_id,
                reservation.total_amount_cents,
                advance_cents,
            )
            self._notify_invoice_created(invoice, reservation)
        except HTTPException as e:
            if e.status_code == 400:
                logger.warning(
                    "Invoice already exists for reservation %s (tenant=%d): %s",
                    reservation.reference,
                    tenant_id,
                    e.detail,
                )
            else:
                raise

    async def _generate_precheck_items(
        self,
        reservation: Reservation,
        tenant_id: int,
    ) -> None:
        """Crée les items de checklist sans changer le statut.

        Un item par ligne de réservation (type=product). Idempotent.
        """
        from app.models.reservation import ReservationPreCheckItem

        existing = await self.db.execute(
            select(func.count()).select_from(ReservationPreCheckItem).where(
                ReservationPreCheckItem.reservation_id == reservation.id,
                ReservationPreCheckItem.tenant_id == tenant_id,
            )
        )
        if existing.scalar() > 0:
            return

        sort_idx = 0
        for line in reservation.lines:
            if line.bundle_id and hasattr(line, "bundle") and line.bundle:
                bundle = line.bundle
                bundle_items = getattr(bundle, "items", None) or []
                if not bundle_items:
                    label = f"{bundle.name} × {line.quantity}"
                    self.db.add(ReservationPreCheckItem(
                        reservation_id=reservation.id,
                        tenant_id=tenant_id,
                        label=label,
                        type="product",
                        checked=False,
                        sort_order=sort_idx,
                    ))
                    sort_idx += 1
                else:
                    for bi in bundle_items:
                        prod = bi.product
                        prod_name = getattr(prod, "name", None) or f"Produit #{bi.product_id}"
                        qty = bi.quantity * line.quantity
                        label = f"{prod_name} × {qty} ({bundle.name})"
                        self.db.add(ReservationPreCheckItem(
                            reservation_id=reservation.id,
                            tenant_id=tenant_id,
                            label=label,
                            type="product",
                            checked=False,
                            sort_order=sort_idx,
                        ))
                        sort_idx += 1
            else:
                product_name = f"Produit #{line.product_id}"
                if line.product and hasattr(line.product, "name"):
                    product_name = line.product.name
                label = f"{product_name} × {line.quantity}"
                self.db.add(ReservationPreCheckItem(
                    reservation_id=reservation.id,
                    tenant_id=tenant_id,
                    label=label,
                    type="product",
                    checked=False,
                    sort_order=sort_idx,
                ))
                sort_idx += 1

        await self.db.flush()
        logger.info(
            "Generated %d pre-check items for reservation %s (tenant=%d)",
            sort_idx,
            reservation.reference,
            tenant_id,
        )

    async def start_precheck(
        self,
        reservation_id: int,
        tenant_id: int,
    ) -> Reservation:
        """Transition confirmed → pre_check apres validation des precheck items."""
        reservation = await self.repo.get_by_id_with_relations(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND,
            )
        # Idempotent : si deja en pre_check, juste valider les items
        if reservation.status not in (
            ReservationStatus.CONFIRMED,
            ReservationStatus.PRE_CHECK,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot start pre-check from status '{reservation.status}'. "
                    "Required: confirmed or pre_check."
                ),
            )
        unchecked = await self._count_unchecked_precheck(reservation_id, tenant_id)
        if unchecked > 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{unchecked} element(s) de pre-check non coche(s).",
            )
        reservation.status = ReservationStatus.PRE_CHECK
        await self.repo.update(reservation)
        return reservation

    async def _count_unchecked_precheck(
        self, reservation_id: int, tenant_id: int
    ) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(ReservationPreCheckItem).where(
                ReservationPreCheckItem.reservation_id == reservation_id,
                ReservationPreCheckItem.tenant_id == tenant_id,
                ReservationPreCheckItem.checked.is_(False),
            )
        )
        return result.scalar() or 0

    async def _calculate_deposit(self, reservation: Reservation, tenant_id: int) -> int:
        from sqlalchemy import select
        from app.models.product import Product

        product_ids = [line.product_id for line in reservation.lines if line.product_id]

        # Inclure les produits contenus dans les bundles
        for line in reservation.lines:
            if line.bundle_id:
                bundle = await self.bundle_repo.get_with_items(
                    line.bundle_id, tenant_id
                )
                if bundle:
                    product_ids.extend(
                        item.product_id for item in bundle.items
                    )

        if not product_ids:
            settings = await self._get_tenant_settings(tenant_id)
            multiplier = settings.deposit_multiplier if settings else DEPOSIT_RATE
            return int(reservation.total_amount_cents * multiplier)
        result = await self.db.scalars(
            select(Product).where(
                Product.id.in_(product_ids),
                Product.tenant_id == tenant_id,
            )
        )
        products = result.all()
        has_selfie_booth = any("SELFIE" in p.sku.upper() for p in products)

        if has_selfie_booth:
            return SELFIE_BOOTH_DEPOSIT_CENTS

        settings = await self._get_tenant_settings(tenant_id)
        multiplier = settings.deposit_multiplier if settings else DEPOSIT_RATE
        return int(reservation.total_amount_cents * multiplier)

    async def _get_tenant_settings(self, tenant_id: int):
        from sqlalchemy import select
        from app.models.tenant_settings import TenantSettings

        return await self.db.scalar(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
        )

    def _notify_reservation_confirmed(self, reservation: Reservation) -> None:
        """Best-effort : notification confirmation au client (async via Celery)."""
        try:
            from app.tasks.notifications import send_reservation_confirmed_email

            customer = reservation.customer
            if not customer or not customer.email:
                return
            send_reservation_confirmed_email.delay(
                email=customer.email,
                customer_name=customer.display_name,
                reference=reservation.reference,
                event_date_iso=str(reservation.event_date),
                delivery_date_iso=str(reservation.delivery_date),
                return_date_iso=str(reservation.return_date),
                event_location=reservation.event_location or "",
                total_cents=reservation.total_amount_cents,
                deposit_cents=reservation.deposit_amount_cents,
                tenant_id=reservation.tenant_id,
            )
        except Exception:
            logger.exception("Notification failed for reservation %s", reservation.reference)

    def _notify_invoice_created(self, invoice, reservation: Reservation) -> None:
        """Best-effort : notification facture au client (async via Celery)."""
        try:
            from app.tasks.notifications import send_invoice_created_email

            customer = reservation.customer
            if not customer or not customer.email:
                return
            send_invoice_created_email.delay(
                email=customer.email,
                customer_name=customer.display_name,
                invoice_number=invoice.invoice_number,
                reservation_reference=reservation.reference,
                total_cents=invoice.total_amount_cents,
                due_date_iso=str(invoice.due_date),
                issue_date_iso=str(invoice.issue_date),
                tenant_id=invoice.tenant_id,
            )
        except Exception:
            logger.exception("Notification failed for invoice %s", invoice.invoice_number)

    async def deliver_reservation(self, reservation_id: int, tenant_id: int) -> Reservation:
        """Marque une réservation comme livrée avec vérifications complètes.

        Vérifie : statut pre_check, precheck items tous cochés, caution encaissée,
        et complète le mouvement de départ si présent.
        """
        reservation = await self.repo.get_by_id_with_relations(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND,
            )
        if reservation.status != ReservationStatus.PRE_CHECK:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot deliver reservation with status '{reservation.status}'. "
                    "Required: pre_check. Utilisez le flow opérations/départ pour le contrôle complet."
                ),
            )

        # Vérifier que tous les precheck items sont cochés
        result = await self.db.execute(
            select(func.count()).select_from(ReservationPreCheckItem).where(
                ReservationPreCheckItem.reservation_id == reservation_id,
                ReservationPreCheckItem.tenant_id == tenant_id,
                ReservationPreCheckItem.checked.is_(False),
            )
        )
        unchecked = result.scalar() or 0
        if unchecked > 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Impossible de livrer : {unchecked} élément(s) de pré-check non coché(s).",
            )

        # Vérifier la caution (2 sources : flag + table deposits)
        from app.services.deposit import DepositService
        deposit_svc = DepositService(self.db)
        has_held = await deposit_svc.has_held_deposit(reservation.id, tenant_id)
        deposit_ok = (reservation.deposit_amount_cents or 0) == 0 or (reservation.deposit_paid and has_held)
        if not deposit_ok:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Impossible de livrer : caution non encaissée.",
            )

        # Guards business additionnels (acompte payé + signature contrat).
        # Configurables par tenant via tenant_settings.
        from app.services.reservation_workflow import assert_delivery_guards
        await assert_delivery_guards(self.db, reservation, tenant_id)

        # Compléter le mouvement de départ si présent
        from app.models.inventory_movement import InventoryMovement
        from app.constants import MovementStatus, MovementType
        from app.services.inventory_movement import MovementService

        mvt_result = await self.db.execute(
            select(InventoryMovement).where(
                InventoryMovement.reservation_id == reservation_id,
                InventoryMovement.tenant_id == tenant_id,
                InventoryMovement.movement_type == MovementType.DEPARTURE.value,
                InventoryMovement.is_active.is_(True),
            )
        )
        departure = mvt_result.scalar_one_or_none()
        if departure and departure.status != MovementStatus.COMPLETED.value:
            svc = MovementService(self.db)
            if departure.status == MovementStatus.SCHEDULED.value:
                await svc.update_movement(
                    departure.id, tenant_id, status=MovementStatus.IN_TRANSIT.value,
                )
            await svc.complete_movement(departure.id, tenant_id, _internal=True)

        reservation.status = ReservationStatus.DELIVERED
        await self.repo.update(reservation)
        return reservation

    async def cancel_reservation(self, reservation_id: int, tenant_id: int) -> Reservation:
        reservation = await self.repo.get_by_id_with_relations(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND,
            )
        if reservation.status in (
            ReservationStatus.RETURNED,
            ReservationStatus.RETURNED_DISPUTE,
            ReservationStatus.COMPLETED,
            ReservationStatus.CANCELLED,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel reservation with status '{reservation.status}'",
            )

        if reservation.status in (
            ReservationStatus.CONFIRMED,
            ReservationStatus.CONFIRMED_RISK,
            ReservationStatus.PRE_CHECK,
            ReservationStatus.DELIVERED,
            ReservationStatus.EXTENDED,
        ):
            await self.release_stock_for_lines(
                reservation.lines, tenant_id, reservation_id=reservation.id,
            )

        # Synchroniser les factures liées
        await self._cancel_linked_invoices(reservation)

        # Synchroniser le devis source (si converti depuis un devis)
        await self._revert_linked_devis(reservation, tenant_id)

        reservation.status = ReservationStatus.CANCELLED
        await self.repo.update(reservation)
        return reservation

    async def _cancel_linked_invoices(self, reservation: Reservation) -> None:
        """Annule les factures sans paiement liees a la reservation."""
        from sqlalchemy import select
        from app.models.invoice import Invoice
        from app.constants.business import InvoiceStatus
        from datetime import datetime

        result = await self.db.execute(
            select(Invoice).where(
                Invoice.reservation_id == reservation.id,
                Invoice.tenant_id == reservation.tenant_id,
                Invoice.status != InvoiceStatus.CANCELLED,
            )
        )
        invoices = list(result.scalars().all())

        for invoice in invoices:
            paid = getattr(invoice, "paid_amount_cents", 0) or 0
            if paid == 0 and invoice.status in (
                InvoiceStatus.DRAFT,
                InvoiceStatus.SENT,
                InvoiceStatus.OVERDUE,
            ):
                invoice.status = InvoiceStatus.CANCELLED
                invoice.cancelled_at = datetime.now()
            elif paid > 0:
                logger.warning(
                    "Invoice %s has %d cents paid — credit note needed "
                    "(reservation %s cancelled)",
                    invoice.invoice_number, paid, reservation.reference,
                )

    async def _revert_linked_devis(self, reservation: Reservation, tenant_id: int) -> None:
        """Remet le devis source en etat CANCELLED si la reservation annulee en etait issue."""
        devis_id = getattr(reservation, "devis_id", None)
        if not devis_id:
            return

        from sqlalchemy import select
        from app.models.devis import Devis
        from app.constants.business import DevisStatus

        result = await self.db.execute(
            select(Devis).where(
                Devis.id == devis_id,
                Devis.tenant_id == tenant_id,
            )
        )
        devis = result.scalar_one_or_none()
        if not devis or devis.status != DevisStatus.CONVERTED:
            return

        devis.status = DevisStatus.ACCEPTED
        devis.converted_reservation_id = None
        devis.notes = (
            f"{devis.notes or ''}\n"
            f"Reservation {reservation.reference} annulee — devis remis en accepte."
        ).strip()

    async def amend_reservation(
        self,
        reservation_id: int,
        payload,  # ReservationAmendRequest (import circulaire évité)
        tenant_id: int,
        user_id: int,
    ) -> Reservation:
        """Avenant à une réservation issue d'un devis.

        Procédure :
          1. Vérifie que la résa est issue d'un devis (sinon 400)
          2. Vérifie statut non terminal (sinon 400)
          3. Crée une nouvelle DevisVersion (snapshot pre-amend)
          4. Active ``_in_amend = True`` (bypass les guards)
          5. Applique : update dates → remove lines → add lines (dans cet ordre
             pour éviter les conflits de stock)
          6. Append la raison aux notes de la résa
          7. Désactive ``_in_amend`` (finally)

        Cette méthode est l'unique chemin légal pour modifier le périmètre
        d'une résa convertie. Elle préserve la traçabilité du devis original.
        """
        from app.constants import ReservationStatus
        from app.repositories.devis import AsyncDevisRepository
        from app.schemas.reservation import ReservationUpdate as RU

        reservation = await self.repo.get_by_id_with_relations(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND,
            )
        if reservation.devis_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cette réservation n'est pas issue d'un devis — "
                    "utilisez PATCH /reservations/{id} directement."
                ),
            )
        if reservation.status in (
            ReservationStatus.COMPLETED,
            ReservationStatus.CANCELLED,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Avenant impossible : statut '{reservation.status}'. "
                    "Une résa terminée/annulée ne peut plus être modifiée."
                ),
            )

        # 1. Snapshot pre-amend du devis source
        devis_repo = AsyncDevisRepository(self.db)
        devis = await devis_repo.get_by_id_full(reservation.devis_id, tenant_id)
        if devis is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Devis source introuvable (résa orpheline)",
            )
        await devis_repo.create_version_snapshot(devis, user_id)

        # 2. Apply modifications avec bypass des guards
        self._in_amend = True
        try:
            # Dates : update via update_reservation pour bénéficier du recalcul
            # de rental_days et de la cascade des mouvements d'inventaire.
            date_fields: dict = {}
            if payload.event_date is not None:
                date_fields["event_date"] = payload.event_date
            if payload.delivery_date is not None:
                date_fields["delivery_date"] = payload.delivery_date
            if payload.return_date is not None:
                date_fields["return_date"] = payload.return_date
            if date_fields:
                await self.update_reservation(
                    reservation_id, RU(**date_fields), tenant_id,
                )

            # Lignes à supprimer
            for line_id in payload.remove_line_ids or []:
                await self.remove_line(reservation_id, line_id, tenant_id)

            # Lignes à ajouter
            for line_data in payload.add_lines or []:
                await self.add_line(reservation_id, line_data, tenant_id)
        finally:
            self._in_amend = False

        # 3. Trace la raison dans les notes
        reservation = await self.repo.get_by_id(reservation_id, tenant_id)
        from datetime import datetime as _dt
        timestamp = _dt.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        reservation.notes = (
            f"{reservation.notes or ''}\n"
            f"[Avenant {timestamp}] {payload.reason}"
        ).strip()
        await self.repo.update(reservation)

        logger.info(
            "Reservation %s amended (devis_id=%s, user=%d, reason=%r)",
            reservation.reference, reservation.devis_id, user_id, payload.reason,
        )
        return await self.repo.get_by_id_with_relations(reservation_id, tenant_id)

    async def update_reservation(
        self,
        reservation_id: int,
        reservation_data: ReservationUpdate,
        tenant_id: int,
    ) -> Reservation:
        reservation = await self.repo.get_by_id(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND,
            )
        # Statuts terminaux : modification interdite
        terminal_statuses = {
            ReservationStatus.COMPLETED,
            ReservationStatus.CANCELLED,
        }
        if reservation.status in terminal_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.RESERVATION_NOT_DRAFT,
            )
        update_data = reservation_data.model_dump(exclude_unset=True)

        # Verrouillage périmétrique post-conversion : une résa issue d'un devis
        # ne peut être modifiée que sur les champs opérationnels (notes, livraison,
        # contact). Toute modif de dates / périmètre / pricing doit passer par
        # POST /reservations/{id}/amend qui crée une nouvelle version de devis
        # et active self._in_amend pour bypasser ce guard pendant le traitement.
        if (
            reservation.devis_id is not None
            and update_data
            and not self._in_amend
        ):
            forbidden = set(update_data.keys()) - RESERVATION_OPERATIONAL_FIELDS
            if forbidden:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"{ErrorMessages.RESERVATION_LOCKED_BY_DEVIS} "
                        f"(forbidden fields: {sorted(forbidden)})"
                    ),
                )

        # Détecter changement de dates AVANT d'appliquer les champs
        old_delivery = reservation.delivery_date
        old_return = reservation.return_date

        for field, value in update_data.items():
            setattr(reservation, field, value)

        # Cascade dates → mouvements d'inventaire + recalcul subtotaux
        delivery_changed = "delivery_date" in update_data and reservation.delivery_date != old_delivery
        return_changed = "return_date" in update_data and reservation.return_date != old_return

        if (delivery_changed or return_changed) and reservation.status != ReservationStatus.DRAFT:
            from app.models.inventory_movement import InventoryMovement

            if delivery_changed:
                departure = (await self.db.execute(
                    select(InventoryMovement).where(
                        InventoryMovement.reservation_id == reservation_id,
                        InventoryMovement.tenant_id == tenant_id,
                        InventoryMovement.movement_type == MovementType.DEPARTURE.value,
                        InventoryMovement.is_active.is_(True),
                    )
                )).scalar_one_or_none()
                if departure:
                    departure.scheduled_date = reservation.delivery_date

            if return_changed:
                return_mvt = (await self.db.execute(
                    select(InventoryMovement).where(
                        InventoryMovement.reservation_id == reservation_id,
                        InventoryMovement.tenant_id == tenant_id,
                        InventoryMovement.movement_type == MovementType.RETURN.value,
                        InventoryMovement.is_active.is_(True),
                    )
                )).scalar_one_or_none()
                if return_mvt:
                    return_mvt.scheduled_date = reservation.return_date

        # Recalcul rental_days + subtotaux si dates effectives changées
        if delivery_changed or return_changed:
            d_date = reservation.delivery_date
            r_date = reservation.return_date
            if d_date and r_date:
                d = d_date if isinstance(d_date, date) else date.fromisoformat(str(d_date))
                r = r_date if isinstance(r_date, date) else date.fromisoformat(str(r_date))
                rental_days = (r - d).days + 1
                if rental_days >= 1:
                    lines = await self.line_repo.list_by_reservation(reservation_id, tenant_id)
                    total = 0
                    for line in lines:
                        line.subtotal_cents = line.quantity * line.unit_price_cents * rental_days
                        total += line.subtotal_cents
                    reservation.total_amount_cents = total + (reservation.delivery_fee_cents or 0)

        return await self.repo.update(reservation)

    async def _create_version_snapshot(
        self,
        reservation: Reservation,
        change_type: str,
        change_summary: str,
        user_id: int | None = None,
    ) -> None:
        """Crée un snapshot immuable de la réservation (historique modifications).

        Le devis original reste figé après conversion. Cet historique
        trace chaque modification de ligne sur la réservation vivante.
        """
        from app.models.reservation_version import ReservationVersion

        # Charger les lignes si pas déjà chargées
        lines = await self.line_repo.list_by_reservation(reservation.id, reservation.tenant_id)

        # Prochain numéro de version
        result = await self.db.execute(
            select(func.max(ReservationVersion.version_number))
            .filter(ReservationVersion.reservation_id == reservation.id)
        )
        version_number = (result.scalar() or 0) + 1

        snapshot = {
            "reference": reservation.reference,
            "status": reservation.status,
            "total_amount_cents": reservation.total_amount_cents,
            "deposit_amount_cents": reservation.deposit_amount_cents,
            "lines": [
                {
                    "id": l.id,
                    "product_id": l.product_id,
                    "variant_id": l.variant_id,
                    "bundle_id": l.bundle_id,
                    "quantity": l.quantity,
                    "unit_price_cents": l.unit_price_cents,
                    "subtotal_cents": l.subtotal_cents,
                }
                for l in lines
            ],
        }

        version = ReservationVersion(
            tenant_id=reservation.tenant_id,
            reservation_id=reservation.id,
            version_number=version_number,
            change_type=change_type,
            change_summary=change_summary,
            snapshot_json=snapshot,
            created_by=user_id,
        )
        self.db.add(version)
        await self.db.flush()

    async def add_line(
        self,
        reservation_id: int,
        line_data: ReservationLineCreate,
        tenant_id: int,
    ) -> ReservationLine:
        reservation = await self.repo.get_by_id(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND,
            )
        if reservation.status != ReservationStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.RESERVATION_NOT_DRAFT,
            )

        # Verrouillage devis : ajout de ligne sur résa convertie = avenant requis
        # (bypass possible si self._in_amend, activé par amend_reservation()).
        if reservation.devis_id is not None and not self._in_amend:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorMessages.RESERVATION_LOCKED_BY_DEVIS,
            )

        return_d = reservation.return_date if isinstance(reservation.return_date, date) else date.fromisoformat(str(reservation.return_date))
        delivery_d = reservation.delivery_date if isinstance(reservation.delivery_date, date) else date.fromisoformat(str(reservation.delivery_date))
        rental_days = (return_d - delivery_d).days + 1

        if line_data.bundle_id:
            unit_price, deposit_per_unit = await self._resolve_bundle_line(
                line_data.bundle_id, tenant_id
            )
            subtotal = line_data.quantity * unit_price * rental_days
            line_deposit = line_data.quantity * deposit_per_unit
            line = ReservationLine(
                tenant_id=tenant_id,
                reservation_id=reservation_id,
                bundle_id=line_data.bundle_id,
                quantity=line_data.quantity,
                unit_price_cents=unit_price,
                subtotal_cents=subtotal,
            )
        else:
            product = await self.product_repo.get_by_id(line_data.product_id, tenant_id)
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product with id {line_data.product_id} not found",
                )

            # Stock live-check (G30)
            if line_data.variant_id is not None:
                variant = await self._resolve_variant(
                    line_data.product_id, line_data.variant_id, tenant_id
                )
                available = variant.available_quantity or 0
                if line_data.quantity > available:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Stock insuffisant pour {product.name} "
                            f"(variante {variant.label}): "
                            f"{available} dispo, {line_data.quantity} demande(s)."
                        ),
                    )
                unit_price = variant.price_per_day_cents if variant.price_per_day_cents is not None else product.price_per_day_cents
                line_deposit = line_data.quantity * variant.deposit_amount_cents
            else:
                available = product.available_quantity or 0
                if line_data.quantity > available:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Stock insuffisant pour {product.name}: "
                            f"{available} dispo, {line_data.quantity} demande(s)."
                        ),
                    )
                unit_price = product.price_per_day_cents
                line_deposit = line_data.quantity * (product.deposit_amount_cents or 0)
            subtotal = line_data.quantity * unit_price * rental_days
            line = ReservationLine(
                tenant_id=tenant_id,
                reservation_id=reservation_id,
                product_id=line_data.product_id,
                variant_id=line_data.variant_id,
                quantity=line_data.quantity,
                unit_price_cents=unit_price,
                subtotal_cents=subtotal,
            )

        try:
            await self.line_repo.create(line)
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ce produit ou bundle est deja present dans la reservation.",
            )
        reservation.total_amount_cents += subtotal
        reservation.deposit_amount_cents += line_deposit
        await self.repo.update(reservation)

        # Eager-load product relation pour serialisation Pydantic (évite MissingGreenlet)
        await self.db.flush()
        await self.db.refresh(line, attribute_names=["product", "variant"])

        product_name = line.product.name if line.product else f"bundle #{line.bundle_id}"
        await self._create_version_snapshot(
            reservation,
            change_type="line_added",
            change_summary=f"+{line.quantity}x {product_name}",
        )

        return line

    async def remove_line(
        self,
        reservation_id: int,
        line_id: int,
        tenant_id: int,
    ) -> None:
        reservation = await self.repo.get_by_id(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND,
            )
        if reservation.status != ReservationStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.RESERVATION_NOT_DRAFT,
            )

        # Verrouillage devis : suppression de ligne sur résa convertie = avenant requis
        # (bypass possible si self._in_amend, activé par amend_reservation()).
        if reservation.devis_id is not None and not self._in_amend:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorMessages.RESERVATION_LOCKED_BY_DEVIS,
            )

        line = await self.line_repo.get_by_id(line_id, tenant_id)
        if not line or line.reservation_id != reservation_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation line not found",
            )

        reservation.total_amount_cents = max(0, reservation.total_amount_cents - line.subtotal_cents)

        if line.bundle_id:
            _, deposit_per_unit = await self._resolve_bundle_line(
                line.bundle_id, tenant_id
            )
            reservation.deposit_amount_cents = max(
                0,
                reservation.deposit_amount_cents - line.quantity * deposit_per_unit,
            )
        elif line.variant_id:
            variant = await self.variant_repo.get_by_id(line.variant_id, tenant_id)
            if variant:
                reservation.deposit_amount_cents = max(
                    0,
                    reservation.deposit_amount_cents - line.quantity * variant.deposit_amount_cents,
                )
        await self.repo.update(reservation)

        # Snapshot avant suppression (la ligne est encore en DB)
        product_name = line.product.name if line.product else f"bundle #{line.bundle_id}"
        summary = f"-{line.quantity}x {product_name}"

        await self.db.delete(line)
        await self.db.flush()

        await self._create_version_snapshot(
            reservation,
            change_type="line_removed",
            change_summary=summary,
        )

    async def complete_reservation(
        self, reservation_id: int, tenant_id: int
    ) -> Reservation:
        """Clôture définitive d'une réservation retournée (RETURNED → COMPLETED).

        Bloque si des factures actives restent impayées.
        """
        reservation = await self.repo.get_by_id_with_relations(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND,
            )
        if reservation.status != ReservationStatus.RETURNED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot complete reservation with status '{reservation.status}'. "
                    "Expected: returned."
                ),
            )

        # Vérifier que toutes les factures liées sont réglées ou annulées
        from app.models.invoice import Invoice
        from app.constants.business import InvoiceStatus

        result = await self.db.execute(
            select(Invoice).where(
                Invoice.reservation_id == reservation_id,
                Invoice.tenant_id == tenant_id,
                Invoice.status.notin_([
                    InvoiceStatus.PAID,
                    InvoiceStatus.CANCELLED,
                ]),
            )
        )
        unpaid_invoices = list(result.scalars().all())
        if unpaid_invoices:
            refs = ", ".join(
                getattr(inv, "invoice_number", None) or f"#{inv.id}"
                for inv in unpaid_invoices
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Impossible de clôturer : {len(unpaid_invoices)} facture(s) "
                    f"non réglée(s) ({refs}). Réglez ou annulez les factures avant de clôturer."
                ),
            )

        reservation.status = ReservationStatus.COMPLETED
        await self.repo.update(reservation)
        return reservation

    async def close_dispute(
        self, reservation_id: int, tenant_id: int, resolution_notes: str
    ) -> Reservation:
        """Résout un litige et repasse en RETURNED (RETURNED_DISPUTE → RETURNED)."""
        reservation = await self.repo.get_by_id_with_relations(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND,
            )
        if reservation.status != ReservationStatus.RETURNED_DISPUTE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot close dispute on reservation with status '{reservation.status}'. "
                    "Expected: returned_dispute."
                ),
            )
        reservation.notes = (
            f"{reservation.notes or ''}\n"
            f"[Litige résolu] {resolution_notes}"
        ).strip()
        reservation.status = ReservationStatus.RETURNED
        await self.repo.update(reservation)
        return reservation

    async def remind_deposit(self, reservation_id: int, tenant_id: int) -> None:
        """Envoie un rappel d'acompte pour une réservation confirmée."""
        reservation = await self.repo.get_by_id_with_relations(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND,
            )
        if reservation.status not in (
            ReservationStatus.CONFIRMED,
            ReservationStatus.CONFIRMED_RISK,
            ReservationStatus.PRE_CHECK,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Deposit reminder can only be sent for confirmed or pre-check reservations.",
            )
        customer = reservation.customer
        if not customer or not getattr(customer, "email", None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer email not available.",
            )
        advance_cents = (
            reservation.advance_payment_amount_cents
            if reservation.advance_payment_amount_cents is not None
            else int(reservation.total_amount_cents * 0.40)
        )
        self._notify_deposit_reminder(
            email=customer.email,
            customer_name=getattr(customer, "display_name", customer.email),
            reservation_reference=reservation.reference,
            event_date=reservation.event_date,
            amount_cents=advance_cents,
            tenant_id=reservation.tenant_id,
        )

    def _notify_deposit_reminder(
        self,
        email: str,
        customer_name: str,
        reservation_reference: str,
        event_date,
        amount_cents: int,
        tenant_id: int | None = None,
    ) -> None:
        """Déclenche la tâche Celery de rappel d'acompte (best-effort)."""
        try:
            from app.tasks.notifications import send_deposit_reminder_email
            send_deposit_reminder_email.delay(
                email=email,
                customer_name=customer_name,
                reservation_reference=reservation_reference,
                event_date_iso=(
                    event_date.isoformat()
                    if hasattr(event_date, "isoformat")
                    else str(event_date)
                ),
                amount_cents=amount_cents,
                tenant_id=tenant_id,
            )
        except Exception:
            logger.warning(
                "Failed to enqueue deposit reminder for reservation %s",
                reservation_reference,
            )


    async def delete_reservation(self, reservation_id: int, tenant_id: int) -> None:
        """Supprime une réservation brouillon (hard delete).

        Seules les réservations en statut 'draft' peuvent être supprimées.
        Les lignes, dépôts, risques et items pre-check sont supprimés en cascade.
        """
        reservation = await self.repo.get_by_id(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND,
            )
        if reservation.status != ReservationStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot delete reservation with status '{reservation.status}'. "
                    "Only 'draft' reservations can be deleted."
                ),
            )
        await self.db.delete(reservation)

    async def archive_reservation(self, reservation_id: int, tenant_id: int) -> Reservation:
        """Archive une réservation terminée ou annulée.

        Seules les réservations en statut 'completed' ou 'cancelled' peuvent être archivées.
        L'archivage masque la réservation des listes courantes sans suppression.
        """
        reservation = await self.repo.get_by_id_with_relations(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND,
            )
        archivable_statuses = {ReservationStatus.COMPLETED, ReservationStatus.CANCELLED}
        if reservation.status not in archivable_statuses:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot archive reservation with status '{reservation.status}'. "
                    "Only 'completed' or 'cancelled' reservations can be archived."
                ),
            )
        if reservation.is_archived:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reservation is already archived.",
            )
        reservation.is_archived = True
        return reservation


# Backward-compat alias
AsyncReservationService = ReservationService
