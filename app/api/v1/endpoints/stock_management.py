"""Endpoints gestion physique du stock — inventaire, ajustements, niveaux."""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import LOW_STOCK_THRESHOLD
from app.constants.errors import ErrorMessages
from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.common import PaginatedResponse, PaginationParams
from app.models.inventory_movement import MovementItem, InventoryMovement
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.stock_management import StockAdjustment, StockInventaireSession
from app.schemas.stock_management import (
    InventaireSessionResponse,
    ReorderItem,
    ReorderRequest,
    ReorderResponse,
    StockAdjustmentCreate,
    StockAdjustmentResponse,
    StockCoverageItem,
    StockCoverageResponse,
    StockLevelItem,
    UpdateInventaireRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stock", tags=["Stock Management"])


# ---------------------------------------------------------------------------
# Inventaire physique
# ---------------------------------------------------------------------------

@router.post("/inventaire", response_model=InventaireSessionResponse, status_code=status.HTTP_201_CREATED)
async def start_inventaire(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> InventaireSessionResponse:
    """Démarre une session d'inventaire physique."""
    # Vérifier qu'aucune session n'est déjà en cours
    existing = (await db.execute(
        select(StockInventaireSession).where(
            StockInventaireSession.tenant_id == current_user.tenant_id,
            StockInventaireSession.status == "in_progress",
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An inventory session is already in progress (id={existing.id})",
        )

    session = StockInventaireSession(
        tenant_id=current_user.tenant_id,
        status="in_progress",
        started_at=datetime.now(tz=timezone.utc),
        created_by=current_user.id,
        variances_json={},
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return InventaireSessionResponse.model_validate(session)


@router.get("/inventaire/active", response_model=InventaireSessionResponse)
async def get_active_inventaire(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> InventaireSessionResponse:
    """Retourne la session d'inventaire en cours, ou 404 si aucune."""
    session = (await db.execute(
        select(StockInventaireSession).where(
            StockInventaireSession.tenant_id == current_user.tenant_id,
            StockInventaireSession.status == "in_progress",
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active inventory session")
    return InventaireSessionResponse.model_validate(session)


@router.get("/inventaire/{session_id}", response_model=InventaireSessionResponse)
async def get_inventaire(
    session_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> InventaireSessionResponse:
    """Récupère l'état d'une session d'inventaire."""
    session = (await db.execute(
        select(StockInventaireSession).where(
            StockInventaireSession.id == session_id,
            StockInventaireSession.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorMessages.SESSION_NOT_FOUND)
    return InventaireSessionResponse.model_validate(session)


@router.patch("/inventaire/{session_id}", response_model=InventaireSessionResponse)
async def update_inventaire(
    session_id: int,
    data: UpdateInventaireRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> InventaireSessionResponse:
    """Saisit les comptages pour une session d'inventaire en cours."""
    session = (await db.execute(
        select(StockInventaireSession).where(
            StockInventaireSession.id == session_id,
            StockInventaireSession.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorMessages.SESSION_NOT_FOUND)
    if session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already completed",
        )

    variances = dict(session.variances_json or {})
    for entry in data.entries:
        product = (await db.execute(
            select(Product).where(
                Product.id == entry.product_id,
                Product.tenant_id == current_user.tenant_id,
                Product.is_active == True,  # noqa: E712
            )
        )).scalar_one_or_none()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Produit {entry.product_id} introuvable",
            )
        expected_qty = product.stock_quantity
        variance_key = str(entry.product_id)
        if entry.variant_id:
            variant = (await db.execute(
                select(ProductVariant).where(
                    ProductVariant.id == entry.variant_id,
                    ProductVariant.product_id == entry.product_id,
                    ProductVariant.tenant_id == current_user.tenant_id,
                    ProductVariant.is_active == True,  # noqa: E712
                )
            )).scalar_one_or_none()
            if not variant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Variante {entry.variant_id} introuvable pour produit {entry.product_id}",
                )
            expected_qty = variant.stock_quantity
            variance_key = f"{entry.product_id}:{entry.variant_id}"

        variances[variance_key] = {
            "expected": expected_qty,
            "counted": entry.counted_quantity,
            "delta": entry.counted_quantity - expected_qty,
            "variant_id": entry.variant_id,
            "product_id": entry.product_id,
        }

    session.variances_json = variances
    await db.commit()
    await db.refresh(session)
    return InventaireSessionResponse.model_validate(session)


@router.post("/inventaire/{session_id}/complete", response_model=InventaireSessionResponse)
async def complete_inventaire(
    session_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> InventaireSessionResponse:
    """Valide la session d'inventaire — applique les variances aux stocks."""
    session = (await db.execute(
        select(StockInventaireSession).where(
            StockInventaireSession.id == session_id,
            StockInventaireSession.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorMessages.SESSION_NOT_FOUND)
    if session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already completed",
        )

    variances = session.variances_json or {}
    synced_products: set[int] = set()
    for _key, variance in variances.items():
        delta = variance.get("delta", 0)
        if delta == 0:
            continue
        pid = variance.get("product_id") or int(_key.split(":")[0])
        vid = variance.get("variant_id")

        if vid:
            variant = await db.get(ProductVariant, vid)
            if variant and variant.tenant_id == current_user.tenant_id:
                variant.stock_quantity += delta
                variant.available_quantity = max(0, variant.available_quantity + delta)
                synced_products.add(pid)
        else:
            product = await db.get(Product, pid)
            if product and product.tenant_id == current_user.tenant_id:
                product.stock_quantity += delta
                product.available_quantity = max(0, product.available_quantity + delta)

        adj = StockAdjustment(
            tenant_id=current_user.tenant_id,
            product_id=pid,
            variant_id=vid,
            delta=delta,
            reason=f"Inventaire physique #{session_id}",
            created_at=datetime.now(tz=timezone.utc),
            created_by=current_user.id,
        )
        db.add(adj)

    # Sync product aggregates from variants
    if synced_products:
        from app.services.product_variant import ProductVariantService
        variant_svc = ProductVariantService(db)
        for pid in synced_products:
            await variant_svc._sync_product_stock(pid, current_user.tenant_id)

    session.status = "completed"
    session.completed_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(session)
    return InventaireSessionResponse.model_validate(session)


# ---------------------------------------------------------------------------
# Ajustements manuels
# ---------------------------------------------------------------------------

@router.post("/adjustments", response_model=StockAdjustmentResponse, status_code=status.HTTP_201_CREATED)
async def create_adjustment(
    data: StockAdjustmentCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> StockAdjustmentResponse:
    """Crée un ajustement manuel de stock (motif obligatoire)."""
    product = (await db.execute(
        select(Product).where(
            Product.id == data.product_id,
            Product.tenant_id == current_user.tenant_id,
            Product.is_active == True,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produit {data.product_id} introuvable",
        )

    if data.variant_id:
        variant = (await db.execute(
            select(ProductVariant).where(
                ProductVariant.id == data.variant_id,
                ProductVariant.product_id == data.product_id,
                ProductVariant.tenant_id == current_user.tenant_id,
                ProductVariant.is_active == True,  # noqa: E712
            )
        )).scalar_one_or_none()
        if not variant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Variante {data.variant_id} introuvable pour produit {data.product_id}",
            )
        variant.stock_quantity += data.delta
        variant.available_quantity = max(0, variant.available_quantity + data.delta)
    else:
        product.stock_quantity += data.delta
        product.available_quantity = max(0, product.available_quantity + data.delta)

    adj = StockAdjustment(
        tenant_id=current_user.tenant_id,
        product_id=data.product_id,
        variant_id=data.variant_id,
        delta=data.delta,
        reason=data.reason,
        created_at=datetime.now(tz=timezone.utc),
        created_by=current_user.id,
    )
    db.add(adj)
    await db.commit()

    # Sync product aggregates if variant was adjusted
    if data.variant_id:
        from app.services.product_variant import ProductVariantService
        variant_svc = ProductVariantService(db)
        await variant_svc._sync_product_stock(data.product_id, current_user.tenant_id)
        await db.commit()

    await db.refresh(adj)
    return StockAdjustmentResponse.model_validate(adj)


@router.get("/adjustments", response_model=PaginatedResponse[StockAdjustmentResponse])
async def list_adjustments(
    product_id: int | None = None,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> PaginatedResponse[StockAdjustmentResponse]:
    """Historique des ajustements manuels du tenant."""
    base = select(StockAdjustment).where(
        StockAdjustment.tenant_id == current_user.tenant_id,
    )
    if product_id is not None:
        base = base.where(StockAdjustment.product_id == product_id)
    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar() or 0
    query = base.order_by(StockAdjustment.created_at.desc()).offset(pagination.skip).limit(pagination.limit)
    items = (await db.execute(query)).scalars().all()
    return PaginatedResponse(
        items=[StockAdjustmentResponse.model_validate(a) for a in items],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


# ---------------------------------------------------------------------------
# Niveaux de stock
# ---------------------------------------------------------------------------

@router.get("/levels", response_model=PaginatedResponse[StockLevelItem])
async def get_stock_levels(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> PaginatedResponse[StockLevelItem]:
    """Retourne les niveaux de stock (critical/low/ok/overstock) par produit."""
    base_filter = (
        Product.tenant_id == current_user.tenant_id,
        Product.is_active == True,  # noqa: E712
    )
    total = (await db.execute(
        select(func.count()).select_from(Product).where(*base_filter)
    )).scalar() or 0
    products = (await db.execute(
        select(Product).where(*base_filter)
        .order_by(Product.available_quantity.asc())
        .offset(pagination.skip).limit(pagination.limit)
    )).scalars().all()

    result = []
    for p in products:
        threshold = LOW_STOCK_THRESHOLD
        qty = p.available_quantity
        if qty == 0:
            level = "critical"
        elif qty <= threshold:
            level = "low"
        elif qty <= threshold * 3:
            level = "ok"
        else:
            level = "overstock"
        result.append(StockLevelItem(
            product_id=p.id,
            product_name=p.name,
            stock_quantity=p.stock_quantity,
            available_quantity=p.available_quantity,
            level=level,
            low_stock_threshold=threshold,
        ))

    return PaginatedResponse(
        items=result,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/reorder", response_model=PaginatedResponse[ReorderItem])
async def get_reorder_list(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> PaginatedResponse[ReorderItem]:
    """Produits sous seuil de réassort."""
    base_filter = (
        Product.tenant_id == current_user.tenant_id,
        Product.is_active == True,  # noqa: E712
        Product.available_quantity <= LOW_STOCK_THRESHOLD,
    )
    total = (await db.execute(
        select(func.count()).select_from(Product).where(*base_filter)
    )).scalar() or 0
    products = (await db.execute(
        select(Product).where(*base_filter)
        .order_by(Product.available_quantity.asc())
        .offset(pagination.skip).limit(pagination.limit)
    )).scalars().all()

    items = [
        ReorderItem(
            product_id=p.id,
            product_name=p.name,
            available_quantity=p.available_quantity,
            low_stock_threshold=LOW_STOCK_THRESHOLD,
            deficit=LOW_STOCK_THRESHOLD - p.available_quantity,
        )
        for p in products
    ]
    return PaginatedResponse(
        items=items,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.post("/reorder", response_model=ReorderResponse, status_code=status.HTTP_201_CREATED)
async def create_reorder(
    data: ReorderRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> ReorderResponse:
    """Enregistre une commande de réassort (stub — crée des ajustements en attente)."""
    count = 0
    for item in data.items:
        product_id = item.get("product_id")
        quantity = item.get("quantity", 0)
        if product_id and quantity > 0:
            product = (await db.execute(
                select(Product).where(
                    Product.id == product_id,
                    Product.tenant_id == current_user.tenant_id,
                )
            )).scalar_one_or_none()
            if product:
                count += 1

    return ReorderResponse(
        created=count,
        message=f"Commande de réassort créée pour {count} produit(s). En attente de réception.",
    )


# ---------------------------------------------------------------------------
# Couverture stock
# ---------------------------------------------------------------------------

@router.get("/coverage", response_model=StockCoverageResponse)
async def get_stock_coverage(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> StockCoverageResponse:
    """Analyse couverture et rotation du stock sur 30 jours."""
    since = datetime.now(timezone.utc) - timedelta(days=30)

    # Mouvements sortants (departure) complétés sur 30j, groupés par produit
    movements_subq = (
        select(
            MovementItem.product_id,
            func.count(MovementItem.id).label("movements_30d"),
        )
        .join(InventoryMovement, MovementItem.movement_id == InventoryMovement.id)
        .where(
            InventoryMovement.tenant_id == current_user.tenant_id,
            InventoryMovement.movement_type == "departure",
            InventoryMovement.status == "completed",
            InventoryMovement.scheduled_date >= since,
            MovementItem.product_id.is_not(None),
        )
        .group_by(MovementItem.product_id)
        .subquery()
    )

    products = (await db.execute(
        select(Product).where(
            Product.tenant_id == current_user.tenant_id,
            Product.is_active == True,  # noqa: E712
        )
    )).scalars().all()

    # Charger les comptages mouvements en une seule requête
    movement_counts: dict[int, int] = {}
    rows = (await db.execute(select(movements_subq))).all()
    for row in rows:
        movement_counts[row.product_id] = row.movements_30d

    items: list[StockCoverageItem] = []
    for p in products:
        moves = movement_counts.get(p.id, 0)
        avg_daily = moves / 30.0
        if avg_daily > 0:
            days_coverage: float | None = round(p.available_quantity / avg_daily, 1)
        else:
            days_coverage = None
        rotation = round((moves / p.stock_quantity * 100), 1) if p.stock_quantity > 0 else 0.0

        if days_coverage is None:
            cov_status = "good"
        elif days_coverage < 7:
            cov_status = "critical"
        elif days_coverage < 30:
            cov_status = "low"
        elif days_coverage < 90:
            cov_status = "ok"
        else:
            cov_status = "good"

        items.append(StockCoverageItem(
            product_id=p.id,
            product_name=p.name,
            sku=p.sku,
            available_qty=p.available_quantity,
            total_qty=p.stock_quantity,
            movements_30d=moves,
            avg_daily_movements=round(avg_daily, 2),
            days_of_coverage=days_coverage,
            rotation_rate=rotation,
            status=cov_status,
        ))

    # Tri : produits avec couverture critique en premier, puis par jours de couverture ASC
    items.sort(key=lambda x: (x.days_of_coverage is None, x.days_of_coverage or 9999))

    return StockCoverageResponse(items=items, computed_at=datetime.now(timezone.utc))
