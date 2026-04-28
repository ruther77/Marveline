"""Service métier pour la gestion des clients."""
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.customer import Customer
from app.repositories.customer import AsyncCustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.constants import ErrorMessages


logger = logging.getLogger(__name__)


class CustomerService:
    """Version async du service client — expand/contract (sync conservé pour Celery)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AsyncCustomerRepository(db)

    async def list_customers(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        search_query: Optional[str] = None,
        customer_type: Optional[str] = None,
        include_inactive: bool = False,
        has_scheduled_relances: bool = False,
    ) -> tuple[list[Customer], int]:
        if has_scheduled_relances:
            return await self.repo.list_with_pending_relances(
                tenant_id=tenant_id,
                skip=skip,
                limit=limit,
            )

        if search_query:
            return await self.repo.search(
                search_term=search_query,
                tenant_id=tenant_id,
                skip=skip,
                limit=limit,
                customer_type=customer_type,  # combinaison search + type désormais supportée
            )

        filters: dict = {}
        if customer_type:
            filters["customer_type"] = customer_type

        return await self.repo.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters=filters if filters else None,
            include_inactive=include_inactive,  # paramètre séparé, pas dans le dict filters
        )

    async def get_customer(self, customer_id: int, tenant_id: int) -> Customer:
        customer = await self.repo.get_by_id(customer_id, tenant_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.CUSTOMER_NOT_FOUND,
            )
        return customer

    async def create_customer(
        self,
        customer_data: CustomerCreate,
        tenant_id: int,
    ) -> Customer:
        if customer_data.email:
            if await self.repo.email_exists(customer_data.email, tenant_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Customer with email '{customer_data.email}' already exists",
                )

        customer = Customer(
            tenant_id=tenant_id,
            customer_type=customer_data.customer_type,
            first_name=customer_data.first_name,
            last_name=customer_data.last_name,
            email=customer_data.email,
            phone=customer_data.phone,
            address=customer_data.address,
            city=customer_data.city,
            postal_code=customer_data.postal_code,
            country=customer_data.country,
            company_name=customer_data.company_name,
            notes=customer_data.notes,
            is_active=True,
        )

        return await self.repo.create(customer)

    async def update_customer(
        self,
        customer_id: int,
        customer_data: CustomerUpdate,
        tenant_id: int,
    ) -> Customer:
        customer = await self.get_customer(customer_id, tenant_id)

        if customer_data.email and customer_data.email != customer.email:
            if await self.repo.email_exists(
                customer_data.email, tenant_id, exclude_id=customer_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email '{customer_data.email}' already used by another customer",
                )

        update_data = customer_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(customer, field, value)

        return await self.repo.update(customer)

    async def delete_customer(
        self,
        customer_id: int,
        tenant_id: int,
        hard_delete: bool = False,
    ) -> bool:
        if hard_delete:
            success = await self.repo.hard_delete(customer_id, tenant_id)
        else:
            success = await self.repo.soft_delete(customer_id, tenant_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.CUSTOMER_NOT_FOUND,
            )
        return True

    async def send_rfm_campaign(
        self,
        tenant_id: int,
        segment: str,
        subject: str,
        message: str,
        customer_emails: list[tuple[int, str, str]],
    ) -> dict[str, int]:
        """Envoie une campagne email aux clients d'un segment RFM.

        Args:
            tenant_id: ID du tenant
            segment: Segment RFM ciblé
            subject: Sujet de l'email
            message: Corps du message (texte brut)
            customer_emails: Liste de (customer_id, customer_name, email)

        Returns:
            Dict avec recipients_count, sent_count, failed_count
        """
        from app.services.notification import notification_service

        sent = 0
        failed = 0
        for _cid, name, email in customer_emails:
            try:
                await notification_service.send_plain_email(
                    to=email,
                    subject=subject,
                    body=f"Bonjour {name},\n\n{message}",
                )
                sent += 1
            except Exception:
                logger.warning("RFM campaign email failed for %s", email)
                failed += 1

        return {
            "recipients_count": len(customer_emails),
            "sent_count": sent,
            "failed_count": failed,
        }


# Backward-compat alias
AsyncCustomerService = CustomerService
