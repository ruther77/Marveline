"""Endpoints CRUD pour les clients (particuliers et entreprises)."""
import logging
from datetime import date, timedelta
from typing import Optional
import csv
import io
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.reservation import Reservation
from app.services.customer import CustomerService
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerList,
    CustomerHistory,
    CustomerHistoryReservation,
    CustomerHistoryInvoice,
    CustomerHistoryStats,
    CustomerRFMItem,
    CustomerRFMResponse,
    RFMCampaignRequest,
    RFMCampaignResponse,
)
from app.schemas.common import PaginationParams, PaginatedResponse, ImportReport, ImportRowError
from app.constants import ErrorMessages
from app.repositories.customer import AsyncCustomerRepository


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=PaginatedResponse[CustomerList])
async def list_customers(
    pagination: PaginationParams = Depends(),
    search_query: Optional[str] = Query(None, description="Rechercher par nom, prénom, raison sociale ou email"),
    customer_type: Optional[str] = Query(None, description="Filtrer par type: individual ou company"),
    is_active: bool = Query(True, description="Inclure uniquement les clients actifs"),
    has_scheduled_relances: bool = Query(False, description="Ne retourner que les clients ayant des relances planifiées"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CUSTOMERS_READ))
) -> PaginatedResponse[CustomerList]:
    """Liste tous les clients avec pagination et filtres.

    Args:
        pagination: Paramètres de pagination (skip, limit)
        search_query: Recherche textuelle sur nom/prénom/email/entreprise
        customer_type: Filtre par type (individual, company)
        is_active: Si True, ne retourne que clients actifs (défaut: True)
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Liste paginée de clients

    Example:
        GET /api/v1/customers?skip=0&limit=20&search_query=dupont&customer_type=individual

        Response:
        {
            "items": [
                {
                    "id": 1,
                    "customer_type": "individual",
                    "first_name": "Jean",
                    "last_name": "Dupont",
                    "email": "jean.dupont@example.com",
                    "phone": "+33612345678",
                    ...
                }
            ],
            "total": 12,
            "skip": 0,
            "limit": 20
        }

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    service = CustomerService(db)

    customers, total = await service.list_customers(
        tenant_id=current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
        search_query=search_query,
        customer_type=customer_type,
        include_inactive=not is_active,
        has_scheduled_relances=has_scheduled_relances,
    )

    return PaginatedResponse(
        items=[CustomerList.model_validate(c) for c in customers],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )


@router.get("/rfm", response_model=CustomerRFMResponse)
async def get_customers_rfm(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CUSTOMERS_READ)),
) -> CustomerRFMResponse:
    """Analyse RFM (Recency / Frequency / Monetary) pour tous les clients du tenant.

    - Recency  : jours depuis la dernière réservation completed
    - Frequency: nombre total de réservations completed
    - Monetary : somme des factures payées (centimes)
    - Segment  : Champions / Loyal / Potential / At Risk / Lost / New
    """
    today = date.today()

    # Agrégats par customer (réservations completed)
    res_agg = (
        await db.execute(
            select(
                Reservation.customer_id,
                func.count(Reservation.id).label("frequency"),
                func.max(Reservation.event_date).label("last_event_date"),
            ).filter(
                Reservation.tenant_id == current_user.tenant_id,
                Reservation.status == "returned",
            ).group_by(Reservation.customer_id)
        )
    ).all()

    # Index rapide
    res_by_customer = {
        row.customer_id: {"frequency": row.frequency, "last_event_date": row.last_event_date}
        for row in res_agg
    }

    # Montant payé par client (via factures paid)
    inv_agg = (await db.execute(
        select(
            Reservation.customer_id,
            func.sum(Invoice.total_amount_cents).label("monetary"),
        ).join(Invoice, Invoice.reservation_id == Reservation.id).filter(
            Reservation.tenant_id == current_user.tenant_id,
            Invoice.status == "paid",
        ).group_by(Reservation.customer_id)
    )).all()

    monetary_by_customer = {row.customer_id: int(row.monetary or 0) for row in inv_agg}

    # Tous les clients actifs
    customers = (await db.execute(
        select(Customer).filter(
            Customer.tenant_id == current_user.tenant_id,
            Customer.is_active == True,  # noqa: E712
        )
    )).scalars().all()

    items: list[CustomerRFMItem] = []
    for c in customers:
        res_data = res_by_customer.get(c.id)
        frequency = res_data["frequency"] if res_data else 0
        last_date: Optional[date] = res_data["last_event_date"] if res_data else None
        recency_days = (today - last_date).days if last_date else 9999
        monetary_cents = monetary_by_customer.get(c.id, 0)

        # Segmentation simple
        if frequency == 0:
            segment = "New"
        elif recency_days <= 30 and frequency >= 5:
            segment = "Champions"
        elif recency_days <= 90 and frequency >= 3:
            segment = "Loyal"
        elif recency_days <= 180:
            segment = "Potential"
        elif recency_days <= 365:
            segment = "At Risk"
        else:
            segment = "Lost"

        customer_name = (
            f"{c.first_name or ''} {c.last_name or ''}".strip()
            or c.company_name
            or f"Client #{c.id}"
        )

        items.append(CustomerRFMItem(
            customer_id=c.id,
            customer_name=customer_name,
            recency_days=recency_days,
            frequency=frequency,
            monetary_cents=monetary_cents,
            segment=segment,
        ))

    # Trier par monetary desc
    items.sort(key=lambda x: x.monetary_cents, reverse=True)

    return CustomerRFMResponse(items=items, total=len(items))


@router.post("/rfm/campaign", response_model=RFMCampaignResponse)
async def send_rfm_campaign(
    payload: RFMCampaignRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CUSTOMERS_WRITE)),
) -> RFMCampaignResponse:
    """Envoie une campagne email aux clients d'un segment RFM."""
    today = date.today()
    tenant_id = current_user.tenant_id

    # Agrégats réservations (même logique que get_customers_rfm)
    res_agg = (await db.execute(
        select(
            Reservation.customer_id,
            func.count(Reservation.id).label("frequency"),
            func.max(Reservation.event_date).label("last_event_date"),
        ).filter(
            Reservation.tenant_id == tenant_id,
            Reservation.status == "returned",
        ).group_by(Reservation.customer_id)
    )).all()
    res_by_customer = {
        r.customer_id: {"frequency": r.frequency, "last_event_date": r.last_event_date}
        for r in res_agg
    }

    # Tous les clients actifs avec email
    customers = (await db.execute(
        select(Customer).filter(
            Customer.tenant_id == tenant_id,
            Customer.is_active == True,  # noqa: E712
        )
    )).scalars().all()

    # Filtrer par segment
    customer_emails: list[tuple[int, str, str]] = []
    for c in customers:
        if not c.email:
            continue
        res_data = res_by_customer.get(c.id)
        frequency = res_data["frequency"] if res_data else 0
        last_date = res_data["last_event_date"] if res_data else None
        recency_days = (today - last_date).days if last_date else 9999

        if frequency == 0:
            segment = "New"
        elif recency_days <= 30 and frequency >= 5:
            segment = "Champions"
        elif recency_days <= 90 and frequency >= 3:
            segment = "Loyal"
        elif recency_days <= 180:
            segment = "Potential"
        elif recency_days <= 365:
            segment = "At Risk"
        else:
            segment = "Lost"

        if segment != payload.segment:
            continue

        name = f"{c.first_name or ''} {c.last_name or ''}".strip() or c.company_name or "Client"
        customer_emails.append((c.id, name, c.email))

    if not customer_emails:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Aucun client dans le segment '{payload.segment}'",
        )

    service = CustomerService(db)
    result = await service.send_rfm_campaign(
        tenant_id=tenant_id,
        segment=payload.segment,
        subject=payload.subject,
        message=payload.message,
        customer_emails=customer_emails,
    )

    return RFMCampaignResponse(segment=payload.segment, **result)


async def _compute_rfm_for_customer(
    db: AsyncSession,
    customer: Customer,
    tenant_id: int,
    today: Optional[date] = None,
) -> CustomerRFMItem:
    """Calcule R/F/M + segment pour un client donné.

    Source de vérité unique pour la segmentation : utilisée par l'endpoint
    global ``GET /customers/rfm`` (par batch) et l'endpoint individuel
    ``GET /customers/{id}/rfm-profile``.
    """
    if today is None:
        today = date.today()

    # Réservations completed (= status returned)
    res_row = (await db.execute(
        select(
            func.count(Reservation.id).label("frequency"),
            func.max(Reservation.event_date).label("last_event_date"),
        ).filter(
            Reservation.customer_id == customer.id,
            Reservation.tenant_id == tenant_id,
            Reservation.status == "returned",
        )
    )).one()
    frequency = int(res_row.frequency or 0)
    last_date: Optional[date] = res_row.last_event_date
    recency_days = (today - last_date).days if last_date else 9999

    # Total payé via factures
    monetary_row = (await db.execute(
        select(func.sum(Invoice.total_amount_cents).label("monetary"))
        .join(Reservation, Invoice.reservation_id == Reservation.id)
        .filter(
            Reservation.customer_id == customer.id,
            Reservation.tenant_id == tenant_id,
            Invoice.status == "paid",
        )
    )).one()
    monetary_cents = int(monetary_row.monetary or 0)

    # Segmentation (alignée avec /customers/rfm)
    if frequency == 0:
        segment = "New"
    elif recency_days <= 30 and frequency >= 5:
        segment = "Champions"
    elif recency_days <= 90 and frequency >= 3:
        segment = "Loyal"
    elif recency_days <= 180:
        segment = "Potential"
    elif recency_days <= 365:
        segment = "At Risk"
    else:
        segment = "Lost"

    customer_name = (
        f"{customer.first_name or ''} {customer.last_name or ''}".strip()
        or customer.company_name
        or f"Client #{customer.id}"
    )
    return CustomerRFMItem(
        customer_id=customer.id,
        customer_name=customer_name,
        recency_days=recency_days,
        frequency=frequency,
        monetary_cents=monetary_cents,
        segment=segment,
    )


@router.get("/{customer_id}/rfm-profile", response_model=CustomerRFMItem)
async def get_customer_rfm_profile(
    customer_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CUSTOMERS_READ)),
) -> CustomerRFMItem:
    """Profil RFM individuel d'un client (R, F, M, segment)."""
    customer = (await db.execute(
        select(Customer).filter(
            Customer.id == customer_id,
            Customer.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.CUSTOMER_NOT_FOUND,
        )
    return await _compute_rfm_for_customer(db, customer, current_user.tenant_id)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CUSTOMERS_READ))
) -> CustomerResponse:
    """Récupère les détails d'un client.

    Args:
        customer_id: ID du client
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Détails complets du client

    Raises:
        HTTPException 404: Si client non trouvé

    Example:
        GET /api/v1/customers/1

        Response:
        {
            "id": 1,
            "customer_type": "individual",
            "first_name": "Jean",
            "last_name": "Dupont",
            "email": "jean.dupont@example.com",
            "phone": "+33612345678",
            "address": "10 rue de la Paix",
            "city": "Paris",
            "postal_code": "75001",
            "company_name": null,
            "notes": "Client VIP",
            "is_active": true,
            "tenant_id": 1,
            "created_at": "2026-01-10T09:00:00Z",
            "updated_at": "2026-02-10T11:30:00Z"
        }

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id (404 si autre tenant)
    """
    service = CustomerService(db)
    customer = await service.get_customer(customer_id, current_user.tenant_id)
    return CustomerResponse.model_validate(customer)


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_data: CustomerCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CUSTOMERS_WRITE))
) -> CustomerResponse:
    """Crée un nouveau client.

    Args:
        customer_data: Données du client à créer
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Client créé

    Raises:
        HTTPException 400: Si email déjà existant ou données invalides

    Example:
        POST /api/v1/customers
        Content-Type: application/json

        {
            "customer_type": "individual",
            "first_name": "Marie",
            "last_name": "Martin",
            "email": "marie.martin@example.com",
            "phone": "+33687654321",
            "address": "25 avenue des Champs",
            "city": "Lyon",
            "postal_code": "69001"
        }

    Business Rules:
        - Type "individual": first_name + last_name obligatoires
        - Type "company": company_name + siret obligatoires
        - Email unique par tenant (optionnel)
        - is_active = True par défaut

    Security:
        - Authentification JWT requise
        - tenant_id ajouté automatiquement depuis JWT
    """
    service = CustomerService(db)

    try:
        customer = await service.create_customer(customer_data, current_user.tenant_id)
        await db.commit()
        await db.refresh(customer)
        return CustomerResponse.model_validate(customer)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in create_customer")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating customer: {str(e)}"
        )


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    customer_data: CustomerUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CUSTOMERS_WRITE))
) -> CustomerResponse:
    """Met à jour un client existant (PATCH partiel).

    Args:
        customer_id: ID du client
        customer_data: Données à mettre à jour (PATCH partiel)
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Client mis à jour

    Raises:
        HTTPException 404: Si client non trouvé
        HTTPException 400: Si validation échoue ou email déjà utilisé

    Example:
        PATCH /api/v1/customers/1
        Content-Type: application/json

        {
            "phone": "+33612345678",
            "address": "Nouvelle adresse",
            "notes": "Client fidèle"
        }

    Business Rules:
        - Validation cohérence customer_type si modifié
        - Email unique si modifié
        - Seuls champs fournis sont mis à jour (PATCH partiel)

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    service = CustomerService(db)

    try:
        customer = await service.update_customer(customer_id, customer_data, current_user.tenant_id)
        await db.commit()
        await db.refresh(customer)
        return CustomerResponse.model_validate(customer)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in update_customer")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating customer: {str(e)}"
        )


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: int,
    hard_delete: bool = Query(False, description="Si True, suppression physique (défaut: soft delete)"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CUSTOMERS_DELETE))
) -> None:
    """Supprime un client (soft delete par défaut).

    Args:
        customer_id: ID du client
        hard_delete: Si True, suppression physique, sinon is_active=False
        db: Session de base de données
        current_user: Utilisateur authentifié

    Raises:
        HTTPException 404: Si client non trouvé
        HTTPException 400: Si contraintes FK (hard delete avec réservations liées)

    Example:
        DELETE /api/v1/customers/1?hard_delete=false

        Response: 204 No Content

    Business Rules:
        - Soft delete par défaut (is_active=False)
        - Hard delete seulement si aucune réservation liée
        - Clients soft-deleted exclus des listes par défaut

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    service = CustomerService(db)

    try:
        await service.delete_customer(customer_id, current_user.tenant_id, hard_delete)
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in delete_customer")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting customer: {str(e)}"
        )


@router.get("/{customer_id}/history", response_model=CustomerHistory)
async def get_customer_history(
    customer_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CUSTOMERS_READ)),
) -> CustomerHistory:
    """Retourne l'historique complet d'un client (réservations + factures + stats).

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id (404 si autre tenant)
    """
    service = CustomerService(db)
    customer = await service.get_customer(customer_id, current_user.tenant_id)

    repo = AsyncCustomerRepository(db)
    history = await repo.get_customer_history(customer_id, current_user.tenant_id)

    reservations = [
        CustomerHistoryReservation.model_validate(r)
        for r in history["reservations"]
    ]
    invoices = [
        CustomerHistoryInvoice.model_validate(i)
        for i in history["invoices"]
    ]
    stats = CustomerHistoryStats(**history["stats"])

    return CustomerHistory(
        customer=CustomerResponse.model_validate(customer),
        reservations=reservations,
        invoices=invoices,
        stats=stats,
    )


# ---------------------------------------------------------------------------
# Import CSV (L-08)
# ---------------------------------------------------------------------------

_CUSTOMER_CSV_REQUIRED = {"customer_type", "email"}
_CUSTOMER_CSV_FIELDS = {
    "customer_type", "email", "first_name", "last_name",
    "phone", "address", "city", "postal_code", "country",
}


@router.post("/import", response_model=ImportReport, status_code=status.HTTP_200_OK)
async def import_customers_csv(
    file: UploadFile = File(..., description="Fichier CSV clients (UTF-8, séparateur virgule)"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CUSTOMERS_WRITE)),
) -> ImportReport:
    """Importe des clients depuis un fichier CSV.

    Colonnes supportées : customer_type (required), email (required),
    first_name, last_name, phone, address, city, postal_code, country.

    Règles :
    - Lignes avec email déjà existant dans le tenant → skipped
    - Lignes avec erreurs de validation → errors (sans interruption)
    - Import partiel : les lignes valides sont créées même si d'autres échouent
    """
    if file.content_type not in ("text/csv", "text/plain", "application/octet-stream"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=ErrorMessages.INVALID_FILE_TYPE,
        )

    content = file.file.read()
    try:
        text = content.decode("utf-8-sig")  # gère BOM Excel
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Encodage invalide — utiliser UTF-8",
        )

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Empty CSV file or missing header",
        )

    missing_required = _CUSTOMER_CSV_REQUIRED - set(reader.fieldnames)
    if missing_required:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Colonnes obligatoires manquantes : {', '.join(sorted(missing_required))}",
        )

    report = ImportReport()

    for row_idx, row in enumerate(reader, start=1):
        # Colonnes vides → skip silencieux
        if not row.get("email", "").strip() and not row.get("customer_type", "").strip():
            report.skipped += 1
            continue

        email = row.get("email", "").strip().lower()
        if not email:
            report.errors.append(ImportRowError(row=row_idx, field="email", message="email est obligatoire"))
            continue

        customer_type_raw = row.get("customer_type", "").strip().lower()
        if not customer_type_raw:
            report.errors.append(ImportRowError(row=row_idx, field="customer_type", message="customer_type est obligatoire"))
            continue

        # Vérifier doublon dans le tenant
        existing = (await db.execute(
            select(Customer).where(
                Customer.tenant_id == current_user.tenant_id,
                Customer.email == email,
            )
        )).scalar_one_or_none()
        if existing:
            report.skipped += 1
            continue

        # Construire le payload et valider via CustomerCreate
        payload = {
            "customer_type": customer_type_raw,
            "email": email,
            "first_name": row.get("first_name", "").strip() or None,
            "last_name": row.get("last_name", "").strip() or None,
            "phone": row.get("phone", "").strip() or None,
            "address": row.get("address", "").strip() or None,
            "city": row.get("city", "").strip() or None,
            "postal_code": row.get("postal_code", "").strip() or None,
            "country": row.get("country", "").strip() or "France",
        }

        try:
            validated = CustomerCreate(**payload)
        except Exception as exc:
            # Extraire le premier message d'erreur lisible (Pydantic ou autre)
            try:
                from pydantic import ValidationError as PydanticValidationError
                if isinstance(exc, PydanticValidationError):
                    first = exc.errors()[0]
                    field_loc = first.get("loc", ())
                    field = str(field_loc[-1]) if field_loc else None
                    message = first.get("msg", str(exc))
                else:
                    field = None
                    message = str(exc)
            except Exception:
                field = None
                message = str(exc)
            report.errors.append(ImportRowError(row=row_idx, field=field, message=message))
            continue

        try:
            await CustomerService(db).create_customer(validated, current_user.tenant_id)
            await db.commit()
            report.created += 1
        except Exception as exc:
            await db.rollback()
            logger.warning("CSV import customer row %d failed: %s", row_idx, exc)
            report.errors.append(ImportRowError(row=row_idx, message=str(exc)))

    return report
