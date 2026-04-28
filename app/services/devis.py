"""Service Devis — logique métier et transitions d'état."""
import logging
from datetime import date as date_type, datetime, timedelta, timezone
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.core.exceptions import NotFound

from app.models.devis import (
    Devis, DevisLine, DevisModule, DevisPhase,
    DevisNegotiation, DevisChangeRequest, DevisCoverageItem, DevisVersion,
)
from app.models.deposit import Deposit
from app.models.reservation import Reservation, ReservationLine
from app.repositories.devis import AsyncDevisRepository
from app.repositories.customer import AsyncCustomerRepository
from app.schemas.devis import (
    DevisCreate, DevisUpdate, DevisConvert,
    DevisModuleCreate, DevisModuleUpdate,
    DevisPhaseCreate, DevisPhaseUpdate,
    DevisNegotiationCreate,
    DevisChangeRequestCreate, DevisChangeRequestUpdate,
    DevisCoverageItemCreate, DevisCoverageItemUpdate,
)
from app.constants import DevisStatus, ReservationStatus
from app.constants.errors import ErrorMessages

logger = logging.getLogger(__name__)

# Transitions autorisées par statut
DEVIS_TRANSITIONS: dict[str, list[str]] = {
    DevisStatus.DRAFT:          [DevisStatus.SENT, DevisStatus.CANCELLED],
    DevisStatus.SENT:           [DevisStatus.NEGOTIATION, DevisStatus.ACCEPTED,
                                  DevisStatus.REFUSED, DevisStatus.EXPIRED],
    DevisStatus.NEGOTIATION:    [DevisStatus.ACCEPTED, DevisStatus.REFUSED,
                                  DevisStatus.EXPIRED, DevisStatus.VERSION_PENDING],
    DevisStatus.VERSION_PENDING: [DevisStatus.SENT, DevisStatus.NEGOTIATION,
                                   DevisStatus.ACCEPTED, DevisStatus.REFUSED,
                                   DevisStatus.CANCELLED],
    DevisStatus.ACCEPTED:       [DevisStatus.CONVERTED, DevisStatus.CANCELLED],
    DevisStatus.REFUSED:        [DevisStatus.DRAFT],   # duplicate() crée un nouveau DRAFT
    DevisStatus.EXPIRED:        [DevisStatus.DRAFT],
    DevisStatus.CONVERTED:      [],
    DevisStatus.CANCELLED:      [],
}


def _assert_transition(devis: Devis, new_status: str) -> None:
    """Valide une transition de statut ou lève HTTPException 400.

    Args:
        devis: Instance Devis actuelle
        new_status: Nouveau statut demandé

    Raises:
        HTTPException 400 si la transition est invalide
    """
    allowed = DEVIS_TRANSITIONS.get(devis.status, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Transition '{devis.status}' → '{new_status}' invalide. "
                f"Transitions autorisées : {allowed or 'aucune'}"
            ),
        )


class DevisService:
    """Service pour la gestion des devis commerciaux."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AsyncDevisRepository(db)

    async def _track_line_change(
        self, devis_id: int, tenant_id: int, line_id: int | None,
        action: str, old_values: dict | None, new_values: dict | None,
        changed_by: int | None = None,
    ) -> None:
        """Enregistre une modification de ligne dans l'historique (G28)."""
        from app.models.devis import DevisLineHistory
        entry = DevisLineHistory(
            tenant_id=tenant_id,
            devis_id=devis_id,
            devis_line_id=line_id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            changed_by=changed_by,
        )
        self.db.add(entry)

    def _line_to_dict(self, line: DevisLine) -> dict:
        """Serialise une DevisLine en dict pour l'historique."""
        return {
            "label": line.label,
            "product_id": line.product_id,
            "bundle_id": line.bundle_id,
            "variant_id": line.variant_id,
            "quantity": line.quantity,
            "unit_price_cents": line.unit_price_cents,
            "discount_pct": line.discount_pct,
            "subtotal_cents": line.subtotal_cents,
            "sort_order": line.sort_order,
        }

    async def _get_or_404(self, devis_id: int, tenant_id: int) -> Devis:
        devis = await self.repo.get_by_id_full(devis_id, tenant_id)
        if not devis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.DEVIS_NOT_FOUND
            )
        return devis

    async def _get_customer_or_404(self, customer_id: int, tenant_id: int):
        repo = AsyncCustomerRepository(self.db)
        customer = await repo.get_by_id(customer_id, tenant_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.CUSTOMER_NOT_FOUND
            )
        return customer

    # ── CRUD ─────────────────────────────────────────────────────────────────

    async def create(self, tenant_id: int, data: DevisCreate) -> Devis:
        """Crée un devis avec ses lignes et génère la référence.

        Args:
            tenant_id: ID du tenant
            data: Données de création du devis

        Returns:
            Devis créé avec référence DEV-YYYY-NNNN
        """
        await self._get_customer_or_404(data.customer_id, tenant_id)
        reference = await self.repo.generate_reference(tenant_id)
        devis_data = data.model_dump(exclude={"lines"})
        lines_data = [line.model_dump() for line in data.lines]
        devis = await self.repo.create_with_lines(tenant_id, devis_data, lines_data, reference)
        await self.db.commit()
        await self.db.refresh(devis)
        logger.info("Devis %d créé (ref=%s, tenant=%d)", devis.id, reference, tenant_id)
        return await self.repo.get_by_id_full(devis.id, tenant_id)

    async def get(self, devis_id: int, tenant_id: int) -> Devis:
        return await self._get_or_404(devis_id, tenant_id)

    async def list(
        self,
        tenant_id: int,
        status: Optional[str] = None,
        customer_id: Optional[int] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[Devis], int]:
        items = await self.repo.list_by_tenant(
            tenant_id, status=status, customer_id=customer_id,
            search=search, skip=skip, limit=limit,
        )
        total = await self.repo.count_by_tenant(
            tenant_id, status=status, customer_id=customer_id, search=search,
        )
        return items, total

    async def update(self, devis_id: int, tenant_id: int, data: DevisUpdate) -> Devis:
        """Met à jour un devis en brouillon uniquement.

        Args:
            devis_id: ID du devis
            tenant_id: ID du tenant
            data: Champs à modifier

        Returns:
            Devis mis à jour

        Raises:
            HTTPException 400 si le devis n'est pas en statut 'draft'
        """
        devis = await self._get_or_404(devis_id, tenant_id)
        editable_statuses = (DevisStatus.DRAFT, DevisStatus.VERSION_PENDING)
        if devis.status not in editable_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Le devis ne peut etre modifie qu'en statut draft ou version_pending "
                       f"(statut actuel : {devis.status}).",
            )
        update_data = data.model_dump(exclude_unset=True)
        lines_data = update_data.pop("lines", None)

        for field, value in update_data.items():
            setattr(devis, field, value)

        if lines_data is not None:
            existing_lines = list(devis.lines)
            # Compatibilité défensive: certains écrans envoient des lignes sans refs produit/bundle.
            # Si l'index correspond à une ligne existante référencée, on conserve la référence.
            for i, line_data in enumerate(lines_data):
                if line_data.get("product_id") is None and line_data.get("bundle_id") is None:
                    if i < len(existing_lines):
                        prev_line = existing_lines[i]
                        if prev_line.product_id is not None or prev_line.bundle_id is not None:
                            line_data["product_id"] = prev_line.product_id
                            line_data["bundle_id"] = prev_line.bundle_id

            # G28 : tracker les suppressions
            for existing_line in existing_lines:
                await self._track_line_change(
                    devis.id, tenant_id, existing_line.id,
                    "delete", self._line_to_dict(existing_line), None,
                )
                await self.db.delete(existing_line)
            await self.db.flush()

            subtotal = 0
            for i, line_data in enumerate(lines_data):
                qty = line_data["quantity"]
                price = line_data["unit_price_cents"]
                discount = line_data.get("discount_pct", 0)
                line_subtotal = qty * price * (10000 - discount) // 10000
                new_line = DevisLine(
                    tenant_id=tenant_id,
                    devis_id=devis.id,
                    product_id=line_data.get("product_id"),
                    bundle_id=line_data.get("bundle_id"),
                    variant_id=line_data.get("variant_id"),
                    label=line_data["label"],
                    quantity=qty,
                    unit_price_cents=price,
                    discount_pct=discount,
                    subtotal_cents=line_subtotal,
                    sort_order=line_data.get("sort_order", i),
                )
                self.db.add(new_line)
                await self.db.flush()
                # G28 : tracker la creation
                await self._track_line_change(
                    devis.id, tenant_id, new_line.id,
                    "create", None, self._line_to_dict(new_line),
                )
                subtotal += line_subtotal

            global_discount_pct = devis.discount_pct or 0
            if global_discount_pct:
                subtotal = subtotal * (10000 - global_discount_pct) // 10000
            tva = subtotal * devis.tva_rate // 10000
            devis.subtotal_cents = subtotal
            devis.tva_cents = tva
            devis.total_cents = subtotal + tva + (devis.delivery_fee_cents or 0)
        elif any(k in update_data for k in ("discount_pct", "tva_rate")):
            # Sans remplacement des lignes, les montants dépendent toujours de discount_pct/tva_rate.
            self.repo.recalculate_amounts(devis)

        await self.db.commit()
        await self.db.refresh(devis)
        return await self.repo.get_by_id_full(devis_id, tenant_id)

    async def delete(self, devis_id: int, tenant_id: int) -> None:
        """Suppression logique d'un devis (soft delete).

        Seuls les devis en draft ou cancelled peuvent être supprimés.
        Nettoie aussi les fichiers physiques des pièces jointes.
        """
        import os
        import shutil
        devis = await self._get_or_404(devis_id, tenant_id)
        if devis.status not in (DevisStatus.DRAFT, DevisStatus.CANCELLED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.DEVIS_NOT_DRAFT
            )
        # Nettoyage fichiers physiques des pièces jointes
        upload_dir = f"/app/uploads/devis/{devis_id}"
        if os.path.isdir(upload_dir):
            try:
                shutil.rmtree(upload_dir)
                logger.info("Fichiers attachments supprimés : %s", upload_dir)
            except OSError as e:
                logger.warning("Impossible de supprimer %s : %s", upload_dir, e)
        devis.soft_delete()
        await self.db.commit()

    # ── Transitions d'état ───────────────────────────────────────────────────

    async def send(self, devis_id: int, tenant_id: int, user_id: int) -> Devis:
        """Passe le devis de 'draft' à 'sent' et crée un snapshot v1."""
        devis = await self._get_or_404(devis_id, tenant_id)
        _assert_transition(devis, DevisStatus.SENT)
        devis.status = DevisStatus.SENT
        await self.repo.create_version_snapshot(devis, user_id)
        await self.db.commit()
        logger.info("Devis %d envoyé (tenant=%d)", devis_id, tenant_id)
        return await self.repo.get_by_id_full(devis_id, tenant_id)

    async def start_negotiation(self, devis_id: int, tenant_id: int) -> Devis:
        """Passe le devis en négociation.

        Transitions autorisées :
        - sent -> negotiation
        - version_pending -> negotiation
        """
        devis = await self._get_or_404(devis_id, tenant_id)
        _assert_transition(devis, DevisStatus.NEGOTIATION)
        devis.status = DevisStatus.NEGOTIATION
        await self.db.commit()
        return await self.repo.get_by_id_full(devis_id, tenant_id)

    async def mark_version_pending(self, devis_id: int, tenant_id: int) -> Devis:
        """Marque le devis en attente d'une nouvelle version (negotiation -> version_pending)."""
        devis = await self._get_or_404(devis_id, tenant_id)
        _assert_transition(devis, DevisStatus.VERSION_PENDING)
        devis.status = DevisStatus.VERSION_PENDING
        await self.db.commit()
        return await self.repo.get_by_id_full(devis_id, tenant_id)

    async def accept(self, devis_id: int, tenant_id: int, user_id: int) -> Devis:
        """Accepte un devis et fige une version (snapshot du contrat signé).

        La version créée ici matérialise l'état exact accepté par le client.
        Si une modification est ensuite demandée, elle passera par un avenant
        (POST /reservations/{id}/amend) qui créera une version supplémentaire.
        """
        devis = await self._get_or_404(devis_id, tenant_id)
        _assert_transition(devis, DevisStatus.ACCEPTED)
        devis.status = DevisStatus.ACCEPTED
        await self.repo.create_version_snapshot(devis, user_id)
        await self.db.commit()
        logger.info("Devis %d accepté (tenant=%d, user=%d) — snapshot version créé", devis_id, tenant_id, user_id)
        return await self.repo.get_by_id_full(devis_id, tenant_id)

    async def refuse(
        self, devis_id: int, tenant_id: int, reason: Optional[str] = None,
    ) -> Devis:
        """Refuse un devis avec raison optionnelle."""
        devis = await self._get_or_404(devis_id, tenant_id)
        _assert_transition(devis, DevisStatus.REFUSED)
        devis.status = DevisStatus.REFUSED
        devis.refusal_reason = reason
        await self.db.commit()
        return await self.repo.get_by_id_full(devis_id, tenant_id)

    async def cancel(self, devis_id: int, tenant_id: int) -> Devis:
        """Annule un devis."""
        devis = await self._get_or_404(devis_id, tenant_id)
        _assert_transition(devis, DevisStatus.CANCELLED)
        devis.status = DevisStatus.CANCELLED
        await self.db.commit()
        return await self.repo.get_by_id_full(devis_id, tenant_id)

    async def expire(self, devis_id: int, tenant_id: int) -> Devis:
        """Marque un devis comme expiré."""
        devis = await self._get_or_404(devis_id, tenant_id)
        _assert_transition(devis, DevisStatus.EXPIRED)
        devis.status = DevisStatus.EXPIRED
        await self.db.commit()
        return await self.repo.get_by_id_full(devis_id, tenant_id)

    async def list_versions(self, devis_id: int, tenant_id: int) -> list:
        """Retourne les snapshots de versions du devis enrichis du nom auteur.

        Chaque version expose un champ ``created_by_name`` (concaténation
        first_name + last_name de l'Account) en plus du ``created_by`` brut,
        pour éviter d'afficher l'ID utilisateur dans l'UI ("par 13").
        """
        await self._get_or_404(devis_id, tenant_id)
        result = await self.db.execute(
            select(DevisVersion)
            .filter(DevisVersion.devis_id == devis_id, DevisVersion.tenant_id == tenant_id)
            .order_by(DevisVersion.version_number)
        )
        versions = list(result.scalars().all())

        # Enrichissement noms (1 query batch sur les ids uniques)
        author_ids = {v.created_by for v in versions if v.created_by}
        names_by_id: dict[int, str] = {}
        if author_ids:
            from app.models.account import Account
            authors = await self.db.execute(
                select(Account.id, Account.first_name, Account.last_name)
                .filter(Account.id.in_(author_ids))
            )
            names_by_id = {
                row.id: f"{row.first_name} {row.last_name}".strip()
                for row in authors.all()
            }
        for v in versions:
            # Attribut dynamique consommé par DevisVersionResponse.created_by_name
            v.created_by_name = names_by_id.get(v.created_by)
        return versions

    async def list_change_requests(self, devis_id: int, tenant_id: int) -> list:
        """Liste les demandes de modification du devis."""
        await self._get_or_404(devis_id, tenant_id)
        result = await self.db.execute(
            select(DevisChangeRequest)
            .filter(DevisChangeRequest.devis_id == devis_id, DevisChangeRequest.tenant_id == tenant_id)
            .order_by(DevisChangeRequest.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_modules(self, devis_id: int, tenant_id: int) -> list:
        """Liste les modules du devis."""
        await self._get_or_404(devis_id, tenant_id)
        result = await self.db.execute(
            select(DevisModule)
            .filter(
                DevisModule.devis_id == devis_id,
                DevisModule.tenant_id == tenant_id,
                DevisModule.is_active == True,  # noqa: E712
            )
            .order_by(DevisModule.id)
        )
        return list(result.scalars().all())

    async def list_phases(self, devis_id: int, tenant_id: int) -> list:
        """Liste les phases du devis triées par sort_order."""
        await self._get_or_404(devis_id, tenant_id)
        result = await self.db.execute(
            select(DevisPhase)
            .filter(
                DevisPhase.devis_id == devis_id,
                DevisPhase.tenant_id == tenant_id,
                DevisPhase.is_active == True,  # noqa: E712
            )
            .order_by(DevisPhase.sort_order, DevisPhase.id)
        )
        return list(result.scalars().all())

    async def renew(self, devis_id: int, tenant_id: int, new_valid_until: str) -> Devis:
        """Renouvelle un devis expiré en créant un nouveau brouillon.

        Args:
            devis_id: ID du devis expiré
            tenant_id: ID du tenant
            new_valid_until: Nouvelle date de validité (ISO date string)

        Returns:
            Nouveau devis en statut 'draft'
        """
        devis = await self._get_or_404(devis_id, tenant_id)
        if devis.status != DevisStatus.EXPIRED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"renew n'est disponible que depuis 'expired' (statut actuel : '{devis.status}')",
            )

        reference = await self.repo.generate_reference(tenant_id)
        new_valid_until_date = date_type.fromisoformat(new_valid_until)
        lines_data = [
            {
                "label": l.label,
                "product_id": l.product_id,
                "bundle_id": l.bundle_id,
                "variant_id": l.variant_id,
                "quantity": l.quantity,
                "unit_price_cents": l.unit_price_cents,
                "discount_pct": l.discount_pct,
                "sort_order": l.sort_order,
            }
            for l in devis.lines
        ]
        new_data = {
            "customer_id": devis.customer_id,
            "event_date": devis.event_date,
            "event_location": devis.event_location,
            "delivery_date": devis.delivery_date,
            "return_date": devis.return_date,
            "valid_until": new_valid_until_date,
            "tva_rate": devis.tva_rate,
            "discount_pct": devis.discount_pct,
            "caution_required": devis.caution_required,
            "caution_amount_cents": devis.caution_amount_cents,
            "notes": devis.notes,
            "conditions_paiement": devis.conditions_paiement,
        }
        new_devis = await self.repo.create_with_lines(
            tenant_id, new_data, lines_data, reference
        )
        # Le devis source reste 'expired' — l'historique est préservé
        await self.db.commit()
        logger.info("Devis %d renouvelé → %d (tenant=%d)", devis_id, new_devis.id, tenant_id)
        return await self.repo.get_by_id_full(new_devis.id, tenant_id)

    async def convert_to_reservation(
        self, devis_id: int, tenant_id: int, data: DevisConvert, user_id: int
    ) -> Devis:
        """Convertit un devis accepté en réservation.

        Avant la conversion, fige une version finale (snapshot de l'état
        précis qui a généré la réservation). Combinée à la version créée à
        l'acceptation, ça donne une traçabilité complète : draft → V1 (send)
        → V2 (accept) → V3 (convert) → résa.

        Args:
            devis_id: ID du devis
            tenant_id: ID du tenant
            data: Dates et lieu de l'événement
            user_id: ID de l'utilisateur qui convertit (audit version)

        Returns:
            Devis converti avec converted_reservation_id renseigné

        Raises:
            HTTPException 400 si le devis n'est pas 'accepted'
        """
        # Charge le devis avec toutes les relations necessaires pour la conversion
        from sqlalchemy.orm import selectinload
        from app.models.devis import DevisLine
        from app.models.bundle import ProductBundle, BundleItem
        stmt = (
            select(Devis)
            .options(
                selectinload(Devis.lines).selectinload(DevisLine.bundle).selectinload(ProductBundle.items),
            )
            .where(Devis.id == devis_id, Devis.tenant_id == tenant_id)
        )
        result = await self.db.execute(stmt)
        devis = result.unique().scalar_one_or_none()
        if not devis:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorMessages.DEVIS_NOT_FOUND)
        _assert_transition(devis, DevisStatus.CONVERTED)

        # Snapshot version finale avant conversion : trace l'état exact qui a
        # généré la réservation (différent de la V acceptation si modif intermédiaire).
        await self.repo.create_version_snapshot(devis, user_id)

        from sqlalchemy import Integer
        from sqlalchemy.sql.functions import func as sa_func

        async def _generate_res_reference() -> str:
            year = datetime.now(tz=timezone.utc).year
            prefix = f"RES-{year}-"
            try:
                last_counter = await self.db.scalar(
                    select(
                        sa_func.max(sa_func.cast(sa_func.split_part(Reservation.reference, '-', 3), Integer))
                    ).where(Reservation.reference.like(f"{prefix}%"), Reservation.tenant_id == tenant_id)
                ) or 0
            except Exception:
                last_counter = await self.db.scalar(
                    select(sa_func.count(Reservation.id)).where(
                        Reservation.reference.like(f"{prefix}%"),
                        Reservation.tenant_id == tenant_id,
                    )
                ) or 0
            return f"{prefix}{last_counter + 1:04d}"

        # Résolution des dates : payload > devis (fallback)
        resolved_delivery = data.delivery_date or devis.delivery_date
        resolved_return = data.return_date or devis.return_date
        resolved_location = data.event_location or devis.event_location

        if not resolved_delivery or not resolved_return:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "delivery_date et return_date sont requis pour la conversion. "
                    "Renseignez-les dans le devis ou dans la requête de conversion."
                ),
            )

        # event_date : payload > devis > delivery_date (fallback)
        resolved_event = data.event_date or devis.event_date or resolved_delivery

        rental_days = (resolved_return - resolved_delivery).days + 1
        if rental_days < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.RESERVATION_DATES_INVALID,
            )

        lines_with_ref = [
            l for l in devis.lines if l.product_id or l.bundle_id
        ]
        if not lines_with_ref:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Ce devis ne contient aucune ligne avec un produit ou bundle référencé. "
                    "Ajoutez au moins un produit ou bundle du catalogue avant de convertir."
                ),
            )

        # Recalcul des subtotaux en fonction des rental_days reels
        # Applique discount_pct par ligne + discount_pct global du devis
        global_discount = devis.discount_pct or 0
        computed_lines = []
        total_amount = 0
        for line in lines_with_ref:
            line_discount = line.discount_pct or 0
            subtotal = line.quantity * line.unit_price_cents * rental_days
            if line_discount:
                subtotal = subtotal * (10000 - line_discount) // 10000
            if global_discount:
                subtotal = subtotal * (10000 - global_discount) // 10000
            total_amount += subtotal
            computed_lines.append((line, subtotal))

        # Résolution livraison : payload > devis (fallback)
        resolved_delivery_method = data.delivery_method or devis.delivery_method
        resolved_delivery_fee = (
            data.delivery_fee_cents
            if data.delivery_fee_cents is not None
            else devis.delivery_fee_cents
        )
        total_amount += resolved_delivery_fee or 0
        resolved_carrier_name = data.carrier_name or devis.carrier_name
        resolved_carrier_code = data.carrier_code or devis.carrier_code
        resolved_delivery_address = data.delivery_address or devis.delivery_address
        resolved_delivery_city = data.delivery_city or devis.delivery_city
        resolved_delivery_postal = data.delivery_postal_code or devis.delivery_postal_code
        resolved_delivery_zone = data.delivery_zone_id or devis.delivery_zone_id
        resolved_delivery_instructions = data.delivery_instructions or devis.delivery_instructions

        _MAX_REF_RETRIES = 3
        reservation = None
        for _attempt in range(_MAX_REF_RETRIES):
            reference = await _generate_res_reference()
            reservation = Reservation(
                tenant_id=tenant_id,
                customer_id=devis.customer_id,
                reference=reference,
                event_date=resolved_event,
                delivery_date=resolved_delivery,
                return_date=resolved_return,
                event_location=resolved_location,
                status=ReservationStatus.DRAFT,
                total_amount_cents=total_amount,
                deposit_amount_cents=devis.caution_amount_cents or 0,
                devis_id=devis.id,
                notes=devis.notes,
                signature_url=devis.signature_url,
                signed_at=devis.signed_at,
                delivery_method=resolved_delivery_method,
                delivery_fee_cents=resolved_delivery_fee,
                carrier_name=resolved_carrier_name,
                carrier_code=resolved_carrier_code,
                delivery_address=resolved_delivery_address,
                delivery_city=resolved_delivery_city,
                delivery_postal_code=resolved_delivery_postal,
                delivery_zone_id=resolved_delivery_zone,
                delivery_instructions=resolved_delivery_instructions,
            )
            try:
                self.db.add(reservation)
                async with self.db.begin_nested():
                    await self.db.flush()
                break
            except IntegrityError:
                logger.warning(
                    "Collision référence réservation %s depuis devis (tentative %d/%d)",
                    reference, _attempt + 1, _MAX_REF_RETRIES,
                )
                await self.db.rollback()
                reservation = None
        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Impossible de générer une référence unique pour la réservation.",
            )

        for line, subtotal in computed_lines:
            self.db.add(ReservationLine(
                tenant_id=tenant_id,
                reservation_id=reservation.id,
                product_id=line.product_id if not line.bundle_id else None,
                bundle_id=line.bundle_id if line.bundle_id else None,
                variant_id=line.variant_id if not line.bundle_id else None,
                quantity=line.quantity,
                unit_price_cents=line.unit_price_cents,
                subtotal_cents=subtotal,
                tva_rate=devis.tva_rate / 10000 if devis.tva_rate else 0.20,
            ))

        # Auto-créer la caution si demandée dans le devis
        if devis.caution_required and devis.caution_amount_cents:
            deposit = Deposit(
                tenant_id=tenant_id,
                reservation_id=reservation.id,
                amount_cents=devis.caution_amount_cents,
                status="held",
                collection_date=None,
                notes=f"Caution auto-creee depuis devis {devis.reference}",
            )
            self.db.add(deposit)

        devis.status = DevisStatus.CONVERTED
        devis.converted_reservation_id = reservation.id
        await self.db.flush()
        logger.info(
            "Devis %d converti en réservation %d (tenant=%d)",
            devis_id, reservation.id, tenant_id
        )
        return await self.repo.get_by_id_full(devis_id, tenant_id)

    # ── Modules ──────────────────────────────────────────────────────────────

    async def add_module(
        self, devis_id: int, tenant_id: int, data: DevisModuleCreate
    ) -> DevisModule:
        devis = await self._get_or_404(devis_id, tenant_id)
        module = DevisModule(
            tenant_id=tenant_id,
            devis_id=devis.id,
            **data.model_dump(),
        )
        self.db.add(module)
        await self.db.commit()
        await self.db.refresh(module)
        return module

    async def update_module(
        self, devis_id: int, module_id: int, tenant_id: int, data: DevisModuleUpdate
    ) -> DevisModule:
        await self._get_or_404(devis_id, tenant_id)
        result = await self.db.execute(
            select(DevisModule).filter(
                DevisModule.id == module_id,
                DevisModule.devis_id == devis_id,
                DevisModule.tenant_id == tenant_id,
            )
        )
        module = result.scalars().first()
        if not module:
            raise NotFound("Quote module not found")
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(module, field, value)
        await self.db.commit()
        await self.db.refresh(module)
        return module

    async def delete_module(
        self, devis_id: int, module_id: int, tenant_id: int
    ) -> None:
        await self._get_or_404(devis_id, tenant_id)
        result = await self.db.execute(
            select(DevisModule).filter(
                DevisModule.id == module_id,
                DevisModule.devis_id == devis_id,
                DevisModule.tenant_id == tenant_id,
            )
        )
        module = result.scalars().first()
        if not module:
            raise NotFound("Quote module not found")
        await self.db.delete(module)
        await self.db.commit()

    # ── Phases ───────────────────────────────────────────────────────────────

    async def add_phase(
        self, devis_id: int, tenant_id: int, data: DevisPhaseCreate
    ) -> DevisPhase:
        devis = await self._get_or_404(devis_id, tenant_id)
        phase = DevisPhase(
            tenant_id=tenant_id,
            devis_id=devis.id,
            **data.model_dump(),
        )
        self.db.add(phase)
        await self.db.commit()
        await self.db.refresh(phase)
        return phase

    async def update_phase(
        self, devis_id: int, phase_id: int, tenant_id: int, data: DevisPhaseUpdate
    ) -> DevisPhase:
        await self._get_or_404(devis_id, tenant_id)
        result = await self.db.execute(
            select(DevisPhase).filter(
                DevisPhase.id == phase_id,
                DevisPhase.devis_id == devis_id,
                DevisPhase.tenant_id == tenant_id,
            )
        )
        phase = result.scalars().first()
        if not phase:
            raise NotFound("Quote phase not found")
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(phase, field, value)
        await self.db.commit()
        await self.db.refresh(phase)
        return phase

    async def delete_phase(
        self, devis_id: int, phase_id: int, tenant_id: int
    ) -> None:
        await self._get_or_404(devis_id, tenant_id)
        result = await self.db.execute(
            select(DevisPhase).filter(
                DevisPhase.id == phase_id,
                DevisPhase.devis_id == devis_id,
                DevisPhase.tenant_id == tenant_id,
            )
        )
        phase = result.scalars().first()
        if not phase:
            raise NotFound("Quote phase not found")
        await self.db.delete(phase)
        await self.db.commit()

    # ── Négociations ──────────────────────────────────────────────────────────

    async def add_negotiation(
        self, devis_id: int, tenant_id: int, user_id: int, data: DevisNegotiationCreate
    ) -> DevisNegotiation:
        devis = await self._get_or_404(devis_id, tenant_id)
        if devis.status != DevisStatus.NEGOTIATION:
            raise HTTPException(
                status_code=400,
                detail=ErrorMessages.DEVIS_INVALID_STATUS_TRANSITION
            )
        neg = DevisNegotiation(
            tenant_id=tenant_id,
            devis_id=devis.id,
            author_id=user_id,
            message=data.message,
            proposed_amount_cents=data.proposed_amount_cents,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        self.db.add(neg)
        await self.db.commit()
        await self.db.refresh(neg)
        return neg

    # ── Change requests ───────────────────────────────────────────────────────

    async def add_change_request(
        self, devis_id: int, tenant_id: int, user_id: int, data: DevisChangeRequestCreate
    ) -> DevisChangeRequest:
        devis = await self._get_or_404(devis_id, tenant_id)
        cr = DevisChangeRequest(
            tenant_id=tenant_id,
            devis_id=devis.id,
            author_id=user_id,
            description=data.description,
        )
        self.db.add(cr)
        await self.db.commit()
        await self.db.refresh(cr)
        return cr

    async def update_change_request(
        self,
        devis_id: int,
        cr_id: int,
        tenant_id: int,
        data: DevisChangeRequestUpdate,
    ) -> DevisChangeRequest:
        await self._get_or_404(devis_id, tenant_id)
        result = await self.db.execute(
            select(DevisChangeRequest).filter(
                DevisChangeRequest.id == cr_id,
                DevisChangeRequest.devis_id == devis_id,
                DevisChangeRequest.tenant_id == tenant_id,
            )
        )
        cr = result.scalars().first()
        if not cr:
            raise NotFound("Quote change request not found")
        cr.status = data.status
        await self.db.commit()
        await self.db.refresh(cr)
        return cr

    # ── Couverture fonctionnelle ───────────────────────────────────────────────

    async def list_coverage_items(self, devis_id: int, tenant_id: int) -> List[DevisCoverageItem]:
        await self._get_or_404(devis_id, tenant_id)
        result = await self.db.execute(
            select(DevisCoverageItem)
            .filter(
                DevisCoverageItem.devis_id == devis_id,
                DevisCoverageItem.tenant_id == tenant_id,
            )
            .order_by(DevisCoverageItem.sort_order, DevisCoverageItem.id)
        )
        return list(result.scalars().all())

    async def add_coverage_item(
        self, devis_id: int, tenant_id: int, data: DevisCoverageItemCreate
    ) -> DevisCoverageItem:
        await self._get_or_404(devis_id, tenant_id)
        item = DevisCoverageItem(
            tenant_id=tenant_id,
            devis_id=devis_id,
            title=data.title,
            description=data.description,
            status=data.status,
            sort_order=data.sort_order,
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def update_coverage_item(
        self, devis_id: int, item_id: int, tenant_id: int, data: DevisCoverageItemUpdate
    ) -> DevisCoverageItem:
        await self._get_or_404(devis_id, tenant_id)
        result = await self.db.execute(
            select(DevisCoverageItem).filter(
                DevisCoverageItem.id == item_id,
                DevisCoverageItem.devis_id == devis_id,
                DevisCoverageItem.tenant_id == tenant_id,
            )
        )
        item = result.scalars().first()
        if not item:
            raise NotFound("Quote coverage item not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def delete_coverage_item(self, devis_id: int, item_id: int, tenant_id: int) -> None:
        await self._get_or_404(devis_id, tenant_id)
        result = await self.db.execute(
            select(DevisCoverageItem).filter(
                DevisCoverageItem.id == item_id,
                DevisCoverageItem.devis_id == devis_id,
                DevisCoverageItem.tenant_id == tenant_id,
            )
        )
        item = result.scalars().first()
        if not item:
            raise NotFound("Quote coverage item not found")
        await self.db.delete(item)
        await self.db.commit()

    # ── Duplication ───────────────────────────────────────────────────────────

    async def duplicate(self, devis_id: int, tenant_id: int) -> Devis:
        """Duplique un devis existant en brouillon avec une nouvelle référence.

        Args:
            devis_id: ID du devis source
            tenant_id: ID du tenant

        Returns:
            Nouveau Devis DRAFT avec les mêmes lignes que l'original
        """
        original = await self._get_or_404(devis_id, tenant_id)
        new_reference = await self.repo.generate_reference(tenant_id)
        now = datetime.now(tz=timezone.utc)

        # Recalculer valid_until si la date source est deja passee (G2)
        fresh_valid_until = original.valid_until
        if fresh_valid_until and fresh_valid_until < date_type.today():
            fresh_valid_until = date_type.today() + timedelta(days=30)

        new_devis = Devis(
            tenant_id=tenant_id,
            reference=new_reference,
            customer_id=original.customer_id,
            status=DevisStatus.DRAFT,
            event_date=original.event_date,
            event_location=original.event_location,
            delivery_date=original.delivery_date,
            return_date=original.return_date,
            valid_until=fresh_valid_until,
            tva_rate=original.tva_rate,
            subtotal_cents=original.subtotal_cents,
            tva_cents=original.tva_cents,
            total_cents=original.total_cents,
            discount_pct=original.discount_pct,
            caution_required=original.caution_required,
            caution_amount_cents=original.caution_amount_cents,
            notes=original.notes,
            conditions_paiement=original.conditions_paiement,
            created_at=now,
            updated_at=now,
        )
        self.db.add(new_devis)
        await self.db.flush()

        for line in original.lines:
            new_line = DevisLine(
                tenant_id=tenant_id,
                devis_id=new_devis.id,
                product_id=line.product_id,
                bundle_id=line.bundle_id,
                variant_id=line.variant_id,
                label=line.label,
                quantity=line.quantity,
                unit_price_cents=line.unit_price_cents,
                discount_pct=line.discount_pct,
                subtotal_cents=line.subtotal_cents,
                sort_order=line.sort_order,
            )
            self.db.add(new_line)

        await self.db.commit()
        logger.info(
            "Devis %d dupliqué → %d (ref=%s, tenant=%d)",
            devis_id, new_devis.id, new_reference, tenant_id,
        )
        return await self.repo.get_by_id_full(new_devis.id, tenant_id)

    async def add_signature(self, devis_id: int, tenant_id: int, signature_data: str) -> Devis:
        """Enregistre la signature électronique d'un devis (statut 'sent' requis).

        Args:
            devis_id: ID du devis à signer.
            tenant_id: Tenant courant.
            signature_data: Données base64 de la signature PNG.

        Returns:
            Devis mis à jour avec signature_url et signed_at.

        Raises:
            HTTPException 400: Statut invalide (pas 'sent').
            HTTPException 404: Devis introuvable.
        """
        devis = await self._get_or_404(devis_id, tenant_id)
        if devis.status not in (DevisStatus.SENT, DevisStatus.ACCEPTED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.DEVIS_SIGNATURE_REQUIRED
            )
        # `signed_at` est stocké en TIMESTAMP WITHOUT TIME ZONE.
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        devis.signature_url = signature_data
        devis.signed_at = now
        await self.db.commit()
        await self.db.refresh(devis)
        logger.info("Devis %d signé électroniquement (tenant=%d)", devis_id, tenant_id)
        return devis

    async def suggest_formula(
        self,
        tenant_id: int,
        guest_count: int,
        event_type: str | None = None,
    ):
        """Suggere la formule la plus adaptee selon le nombre d'invites.

        Retourne la formule featured en priorite, sinon la premiere par sort_order.
        """
        from app.models.formula import Formula

        query = (
            select(Formula)
            .filter(
                Formula.tenant_id == tenant_id,
                Formula.is_active == True,  # noqa: E712
            )
            .order_by(Formula.featured.desc(), Formula.sort_order)
        )
        result = await self.db.execute(query)
        formulas = result.scalars().all()

        if not formulas:
            return None

        for f in formulas:
            if f.featured:
                return f

        return formulas[0] if formulas else None
