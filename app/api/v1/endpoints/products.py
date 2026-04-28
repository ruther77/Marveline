"""Endpoints CRUD pour les produits (matériel de location)."""
import logging
import os
import uuid as uuid_lib
from typing import Optional
import csv
import io
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, and_, select, update, func
from sqlalchemy.exc import IntegrityError
from app.constants.errors import ErrorMessages
from app.core.exceptions import NotFound
from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.models.product import Product
from app.models.audit_log import AuditLog
from app.models.reservation import Reservation, ReservationLine
from app.schemas.audit import AuditLogResponse
from app.services.product import ProductService
from datetime import date
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductList,
    StockBatchResponse,
    StockDetail,
    StockItemRead,
    StockItemHistory,
    StockItemHistoryEntry,
    StockItemStatusUpdate,
    ProductAvailabilityResponse,
    ProductAvailabilitySlot,
    ProductImageResponse,
    ProductImageReorder,
)
from app.models.product_image import ProductImage
from app.services.stock_item import StockItemService
from app.repositories.stock_item import AsyncStockItemRepository
from app.services.product_maintenance import ProductMaintenanceService
from app.schemas.product_maintenance import MaintenanceCreate, MaintenanceUpdate, MaintenanceResponse
from app.schemas.common import PaginationParams, PaginatedResponse, ImportReport, ImportRowError
from app.constants import ErrorMessages
from app.constants.business import LOW_STOCK_THRESHOLD


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["Products"])

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 Mo
_UPLOADS_BASE = "/app/uploads/products"


def _build_stock_detail(product: Product, stock_items: list) -> StockDetail:
    """Construit un StockDetail à partir d'un produit et de ses stock_items éventuels."""
    if stock_items:
        counts = {
            "available": 0,
            "reserved": 0,
            "on_location": 0,
            "damaged": 0,
            "in_repair": 0,
            "retired": 0,
        }
        for item in stock_items:
            status = getattr(item, "status", None)
            if status in counts:
                counts[status] += 1

        return StockDetail(
            product_id=product.id,
            qty_available=counts["available"],
            qty_reserved=counts["reserved"],
            qty_on_location=counts["on_location"],
            qty_damaged=counts["damaged"],
            qty_in_repair=counts["in_repair"],
            qty_retired=counts["retired"],
            total=sum(counts.values()),
            items=[StockItemRead.model_validate(item) for item in stock_items],
        )

    reserved = product.stock_quantity - product.available_quantity
    return StockDetail(
        product_id=product.id,
        qty_available=product.available_quantity,
        qty_reserved=max(reserved, 0),
        qty_on_location=0,
        qty_damaged=0,
        qty_in_repair=0,
        qty_retired=0,
        total=product.stock_quantity,
        items=[],
    )


@router.get("", response_model=PaginatedResponse[ProductList])
async def list_products(
    pagination: PaginationParams = Depends(),
    category: Optional[str] = Query(None, description="Filtrer par catégorie"),
    condition: Optional[str] = Query(None, description="Filtrer par état (neuf, bon, usé, etc.)"),
    supplier_id: Optional[int] = Query(None, description="Filtrer par fournisseur"),
    available_only: bool = Query(False, description="Ne retourner que les produits avec stock disponible (available_quantity > 0)"),
    is_active: bool = Query(True, description="Inclure uniquement les produits actifs"),
    search: Optional[str] = Query(None, description="Recherche par nom ou SKU (insensible à la casse)"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user)
) -> PaginatedResponse[ProductList]:
    """Liste tous les produits avec pagination et filtres.

    Args:
        pagination: Paramètres de pagination (skip, limit)
        category: Filtre optionnel par catégorie
        available_only: Si True, ne retourne que produits avec stock > 0
        is_active: Si True, ne retourne que produits actifs (défaut: True)
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Liste paginée de produits

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    service = ProductService(db)

    products, total = await service.list_products(
        tenant_id=current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
        category=category,
        condition=condition,
        supplier_id=supplier_id,
        available_only=available_only,
        include_inactive=not is_active,
        search=search or None,
    )

    # Fallback image_url depuis la galerie ProductImage pour les produits sans image
    products_without_image = [p for p in products if not p.image_url]
    if products_without_image:
        pids = [p.id for p in products_without_image]
        primary_images = (await db.execute(
            select(ProductImage.product_id, ProductImage.url)
            .where(
                ProductImage.product_id.in_(pids),
                ProductImage.tenant_id == current_user.tenant_id,
                ProductImage.is_primary == True,  # noqa: E712
            )
        )).all()
        primary_map = {row.product_id: row.url for row in primary_images}
        if len(primary_map) < len(pids):
            # Fallback : premiere image par sort_order pour les produits sans primary
            missing = [pid for pid in pids if pid not in primary_map]
            if missing:
                from sqlalchemy import distinct
                first_images = (await db.execute(
                    select(ProductImage.product_id, ProductImage.url)
                    .where(
                        ProductImage.product_id.in_(missing),
                        ProductImage.tenant_id == current_user.tenant_id,
                    )
                    .distinct(ProductImage.product_id)
                    .order_by(ProductImage.product_id, ProductImage.sort_order)
                )).all()
                for row in first_images:
                    if row.product_id not in primary_map:
                        primary_map[row.product_id] = row.url
        for p in products_without_image:
            if p.id in primary_map:
                p.image_url = primary_map[p.id]

    return PaginatedResponse(
        items=[ProductList.model_validate(p) for p in products],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )


@router.get("/low-stock", response_model=PaginatedResponse[ProductList])
async def list_low_stock_products(
    threshold: int = Query(
        LOW_STOCK_THRESHOLD,
        ge=0,
        description=f"Seuil d'alerte (défaut: {LOW_STOCK_THRESHOLD})",
    ),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user),
) -> PaginatedResponse[ProductList]:
    """Liste les produits en stock faible (Planning 4E — Alertes stock)."""
    base_filter = and_(
        Product.tenant_id == current_user.tenant_id,
        Product.is_active == True,  # noqa: E712
        Product.available_quantity < threshold,
    )
    total = (await db.execute(
        select(func.count()).select_from(Product).where(base_filter)
    )).scalar() or 0
    products = (await db.execute(
        select(Product)
        .where(base_filter)
        .order_by(Product.available_quantity.asc())
        .offset(pagination.skip)
        .limit(pagination.limit)
    )).scalars().all()
    return PaginatedResponse(
        items=[ProductList.model_validate(p) for p in products],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/inventory-summary")
async def inventory_summary(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user),
) -> dict:
    """KPIs stock agrégés — remplace les appels limit=1000 côté frontend."""
    tenant_filter = and_(
        Product.tenant_id == current_user.tenant_id,
        Product.is_active == True,  # noqa: E712
    )
    # Agrégats principaux en 1 requête
    row = (await db.execute(
        select(
            func.coalesce(func.sum(Product.available_quantity), 0).label("total_available"),
            func.coalesce(func.sum(Product.stock_quantity), 0).label("total_stock"),
            func.count().filter(Product.available_quantity == 0).label("out_of_stock"),
            func.count().filter(Product.available_quantity < LOW_STOCK_THRESHOLD).label("low_stock"),
        ).where(tenant_filter)
    )).one()
    # Catégories distinctes
    cats = (await db.execute(
        select(Product.category)
        .where(tenant_filter)
        .group_by(Product.category)
        .order_by(Product.category)
    )).scalars().all()
    return {
        "total_available": row.total_available,
        "total_stock": row.total_stock,
        "total_unavailable": row.total_stock - row.total_available,
        "out_of_stock": row.out_of_stock,
        "low_stock": row.low_stock,
        "categories": [c for c in cats if c],
    }


@router.get("/stock", response_model=StockBatchResponse)
async def get_products_stock_batch(
    ids: list[int] = Query(..., description="IDs produits. Répéter le paramètre: ?ids=1&ids=2"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_READ)),
) -> StockBatchResponse:
    """Retourne le détail stock de plusieurs produits en une seule requête."""
    product_ids = list(dict.fromkeys(ids))
    if len(product_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 100 product ids per request",
        )

    products = (await db.execute(
        select(Product).where(
            Product.tenant_id == current_user.tenant_id,
            Product.is_active == True,  # noqa: E712
            Product.id.in_(product_ids),
        )
    )).scalars().all()

    products_by_id = {product.id: product for product in products}
    missing_ids = [product_id for product_id in product_ids if product_id not in products_by_id]
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produits introuvables: {', '.join(str(product_id) for product_id in missing_ids)}",
        )

    stock_service = StockItemService(db)
    stock_items = await stock_service.list_by_products(product_ids, current_user.tenant_id)
    stock_items_by_product: dict[int, list] = {product_id: [] for product_id in product_ids}
    for stock_item in stock_items:
        stock_items_by_product.setdefault(stock_item.product_id, []).append(stock_item)

    return StockBatchResponse(
        items=[
            _build_stock_detail(products_by_id[product_id], stock_items_by_product.get(product_id, []))
            for product_id in product_ids
        ]
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user)
) -> ProductResponse:
    """Récupère les détails d'un produit.

    Args:
        product_id: ID du produit
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Détails complets du produit

    Raises:
        HTTPException 404: Si produit non trouvé

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id (404 si autre tenant)
    """
    service = ProductService(db)
    product = await service.get_product(product_id, current_user.tenant_id)

    # Enrichir avec les compteurs stock_items (si existants)
    stock_service = StockItemService(db)
    counts = await stock_service.get_counts(product_id, current_user.tenant_id)
    has_stock_items = sum(counts.values()) > 0

    data = {c.key: getattr(product, c.key) for c in product.__table__.columns}
    # Ajouter les relations chargées (images)
    if hasattr(product, "images"):
        data["images"] = product.images

    if has_stock_items:
        data["qty_reserved"] = counts.get("reserved", 0)
        data["qty_on_location"] = counts.get("on_location", 0)
        data["qty_damaged"] = counts.get("damaged", 0)
        data["qty_in_repair"] = counts.get("in_repair", 0)
    else:
        # Fallback : dériver depuis les agrégats produit
        reserved = product.stock_quantity - product.available_quantity
        data["qty_reserved"] = max(reserved, 0)
        data["qty_on_location"] = 0
        data["qty_damaged"] = 0
        data["qty_in_repair"] = 0

    return ProductResponse.model_validate(data)


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_data: ProductCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE))
) -> ProductResponse:
    """Crée un nouveau produit (products:write).

    Business Rules:
        - SKU unique par tenant
        - available_quantity <= stock_quantity (validé par service)
        - is_active = True par défaut

    Security:
        - Authentification JWT requise
        - Rôle admin obligatoire
        - tenant_id ajouté automatiquement depuis JWT
    """
    service = ProductService(db)

    try:
        product = await service.create_product(product_data, current_user.tenant_id)
        await db.commit()

        # Recharger avec images eagerly-loaded (évite MissingGreenlet async lazy-load)
        product_with_rel = await service.get_product(product.id, current_user.tenant_id)
        data = {c.key: getattr(product_with_rel, c.key) for c in product_with_rel.__table__.columns}
        if hasattr(product_with_rel, "images"):
            data["images"] = product_with_rel.images
        data.update({"qty_reserved": 0, "qty_on_location": 0, "qty_damaged": 0, "qty_in_repair": 0})
        return ProductResponse.model_validate(data)

    except HTTPException:
        raise
    except IntegrityError as e:
        # Race condition : SKU déjà créé par thread concurrent
        if "unique constraint" in str(e).lower() or "sku" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Product with SKU '{product_data.sku}' already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database integrity error: {str(e)}"
        )
    except Exception as e:
        logger.exception("Unexpected error in create_product")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating product: {str(e)}"
        )


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_data: ProductUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE))
) -> ProductResponse:
    """Met à jour un produit existant (products:write, PATCH partiel).

    Business Rules:
        - SKU immutable (ne peut pas être changé)
        - available_quantity <= stock_quantity
        - Seuls champs fournis sont mis à jour (PATCH partiel)

    Security:
        - Authentification JWT requise
        - Rôle admin obligatoire
        - Filtrage automatique par tenant_id
    """
    service = ProductService(db)

    try:
        product = await service.update_product(product_id, product_data, current_user.tenant_id)
        await db.commit()
        product_with_rel = await service.get_product(product.id, current_user.tenant_id)
        data = {c.key: getattr(product_with_rel, c.key) for c in product_with_rel.__table__.columns}
        if hasattr(product_with_rel, "images"):
            data["images"] = product_with_rel.images
        data.update({"qty_reserved": 0, "qty_on_location": 0, "qty_damaged": 0, "qty_in_repair": 0})
        return ProductResponse.model_validate(data)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in update_product")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating product: {str(e)}"
        )


@router.post("/{product_id}/image", response_model=ProductResponse)
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> ProductResponse:
    """Uploade une image pour un produit (products:write).

    Formats acceptés : JPG, PNG, WebP. Taille max : 5 Mo.
    L'ancienne image est supprimée si elle existait.

    Returns:
        Produit mis à jour avec le nouveau image_url

    Raises:
        HTTPException 415: Format non supporté
        HTTPException 413: Fichier trop volumineux
        HTTPException 404: Produit non trouvé
    """
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=ErrorMessages.IMAGE_FORMAT_INVALID,
        )

    content = file.file.read()
    if len(content) > _MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=ErrorMessages.IMAGE_SIZE_EXCEEDED,
        )

    service = ProductService(db)
    product = await service.get_product(product_id, current_user.tenant_id)

    ext = "jpg" if file.content_type == "image/jpeg" else file.content_type.split("/")[-1]
    filename = f"{uuid_lib.uuid4().hex}.{ext}"
    upload_dir = f"{_UPLOADS_BASE}/{current_user.tenant_id}"
    os.makedirs(upload_dir, exist_ok=True)

    # Supprime l'ancienne image si elle existe
    if product.image_url and product.image_url.startswith("/uploads/"):
        old_path = f"/app{product.image_url}"
        if os.path.isfile(old_path):
            os.remove(old_path)

    with open(os.path.join(upload_dir, filename), "wb") as out:
        out.write(content)

    product.image_url = f"/uploads/products/{current_user.tenant_id}/{filename}"
    await db.commit()
    product_with_rel = await service.get_product(product_id, current_user.tenant_id)
    data = {c.key: getattr(product_with_rel, c.key) for c in product_with_rel.__table__.columns}
    if hasattr(product_with_rel, "images"):
        data["images"] = product_with_rel.images
    data.update({"qty_reserved": 0, "qty_on_location": 0, "qty_damaged": 0, "qty_in_repair": 0})
    logger.info(
        "Product image uploaded: product=%s tenant=%s user=%s file=%s",
        product_id, current_user.tenant_id, current_user.id, filename,
    )
    return ProductResponse.model_validate(data)


@router.get("/{product_id}/images", response_model=list[ProductImageResponse])
async def list_product_images(
    product_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user),
) -> list[ProductImageResponse]:
    """Liste les images de la galerie d'un produit."""
    service = ProductService(db)
    await service.get_product(product_id, current_user.tenant_id)  # 404 si absent
    images = (await db.execute(
        select(ProductImage)
        .where(ProductImage.product_id == product_id, ProductImage.tenant_id == current_user.tenant_id)
        .order_by(ProductImage.sort_order)
    )).scalars().all()
    return [ProductImageResponse.model_validate(img) for img in images]


@router.post("/{product_id}/images", response_model=ProductImageResponse, status_code=status.HTTP_201_CREATED)
async def add_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> ProductImageResponse:
    """Ajoute une image à la galerie d'un produit."""
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=ErrorMessages.IMAGE_FORMAT_INVALID)

    content = file.file.read()
    if len(content) > _MAX_IMAGE_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=ErrorMessages.IMAGE_SIZE_EXCEEDED)

    service = ProductService(db)
    await service.get_product(product_id, current_user.tenant_id)

    ext = "jpg" if file.content_type == "image/jpeg" else file.content_type.split("/")[-1]
    filename = f"{uuid_lib.uuid4().hex}.{ext}"
    upload_dir = f"{_UPLOADS_BASE}/{current_user.tenant_id}"
    os.makedirs(upload_dir, exist_ok=True)
    with open(os.path.join(upload_dir, filename), "wb") as out:
        out.write(content)

    # Détermine sort_order (nombre d'images existantes)
    existing_count = (await db.scalar(
        select(func.count(ProductImage.id)).where(
            ProductImage.product_id == product_id,
            ProductImage.tenant_id == current_user.tenant_id,
        )
    )) or 0

    # Première image = primaire + sync Product.image_url
    is_first = existing_count == 0
    image_url = f"/uploads/products/{current_user.tenant_id}/{filename}"
    img = ProductImage(
        tenant_id=current_user.tenant_id,
        product_id=product_id,
        url=image_url,
        sort_order=existing_count,
        is_primary=is_first,
    )
    db.add(img)
    if is_first:
        product = await service.get_product(product_id, current_user.tenant_id)
        if not product.image_url:
            product.image_url = image_url
    await db.commit()
    await db.refresh(img)
    return ProductImageResponse.model_validate(img)


@router.delete("/{product_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_image(
    product_id: int,
    image_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> None:
    """Supprime une image de la galerie."""
    img = (await db.execute(
        select(ProductImage).where(
            ProductImage.id == image_id,
            ProductImage.product_id == product_id,
            ProductImage.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorMessages.IMAGE_NOT_FOUND)
    if img.url.startswith("/uploads/"):
        path = f"/app{img.url}"
        if os.path.isfile(path):
            os.remove(path)
    await db.delete(img)
    await db.commit()


@router.patch("/{product_id}/images/{image_id}/set-primary", response_model=ProductImageResponse)
async def set_primary_image(
    product_id: int,
    image_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> ProductImageResponse:
    """Définit une image comme principale."""
    img = (await db.execute(
        select(ProductImage).where(
            ProductImage.id == image_id,
            ProductImage.product_id == product_id,
            ProductImage.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorMessages.IMAGE_NOT_FOUND)
    # Retire le flag primaire des autres
    await db.execute(
        update(ProductImage)
        .where(
            ProductImage.product_id == product_id,
            ProductImage.tenant_id == current_user.tenant_id,
        )
        .values(is_primary=False)
    )
    img.is_primary = True
    # Sync Product.image_url avec l'image primaire
    product = (await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if product:
        product.image_url = img.url
    await db.commit()
    await db.refresh(img)
    return ProductImageResponse.model_validate(img)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    hard_delete: bool = Query(False, description="Si True, suppression physique (défaut: soft delete)"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_DELETE))
) -> None:
    """Supprime un produit (products:delete, soft delete par défaut).

    Business Rules:
        - Soft delete par défaut (is_active=False)
        - Hard delete seulement si aucune réservation liée
        - Produits soft-deleted exclus des listes par défaut

    Security:
        - Authentification JWT requise
        - Rôle admin obligatoire
        - Filtrage automatique par tenant_id
    """
    service = ProductService(db)

    try:
        await service.delete_product(product_id, current_user.tenant_id, hard_delete=hard_delete)
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in delete_product")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting product: {str(e)}"
        )


@router.get("/{product_id}/stock", response_model=StockDetail)
async def get_product_stock(
    product_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_READ)),
) -> StockDetail:
    """Retourne le détail du stock physique d'un produit (products:read).

    Returns:
        StockDetail: compteurs par statut + liste des unités physiques

    Raises:
        HTTPException 404: Si produit non trouvé
    """
    product_service = ProductService(db)
    product = await product_service.get_product(product_id, current_user.tenant_id)

    stock_service = StockItemService(db)
    items = await stock_service.list_by_product(product_id, current_user.tenant_id)
    return _build_stock_detail(product, items)


@router.patch("/{product_id}/stock-items/{item_id}", response_model=StockItemRead)
async def update_stock_item_status(
    product_id: int,
    item_id: int,
    body: StockItemStatusUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> StockItemRead:
    """Met à jour le statut d'une unité physique de stock (inventory:write)."""
    product_service = ProductService(db)
    await product_service.get_product(product_id, current_user.tenant_id)

    stock_service = StockItemService(db)
    item = await stock_service.transition_status(item_id, body.status, current_user.tenant_id)
    return StockItemRead.model_validate(item)


@router.get("/{product_id}/stock-items/{item_id}/history", response_model=StockItemHistory)
async def get_stock_item_history(
    product_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_READ)),
) -> StockItemHistory:
    """Retourne l'historique complet d'une unité physique de stock (products:read)."""
    product_service = ProductService(db)
    await product_service.get_product(product_id, current_user.tenant_id)

    repo = AsyncStockItemRepository(db)
    stock_item = await repo.get_by_id(item_id, product_id, current_user.tenant_id)
    if not stock_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock item {item_id} not found for product {product_id}",
        )

    units = await repo.get_item_history(item_id, current_user.tenant_id)
    entries = []
    for unit in units:
        mv_item = unit.movement_item
        mv = mv_item.movement
        entries.append(
            StockItemHistoryEntry(
                movement_id=mv.id,
                movement_type=mv.movement_type,
                scheduled_date=mv.scheduled_date,
                actual_date=mv.actual_date,
                movement_status=mv.status,
                reservation_id=mv.reservation_id,
                status_before=unit.status_before,
                status_after=unit.status_after,
                condition=unit.condition,
                condition_notes=unit.condition_notes,
            )
        )

    return StockItemHistory(
        stock_item_id=stock_item.id,
        product_id=product_id,
        serial_number=stock_item.serial_number,
        current_status=stock_item.status,
        entries=entries,
    )


@router.get("/{product_id}/audit", response_model=list[AuditLogResponse])
async def get_product_audit(
    product_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_READ)),
) -> list[AuditLogResponse]:
    """Retourne l'historique d'audit d'un produit (products:read)."""
    product_service = ProductService(db)
    await product_service.get_product(product_id, current_user.tenant_id)

    logs = (await db.execute(
        select(AuditLog)
        .where(
            AuditLog.tenant_id == current_user.tenant_id,
            AuditLog.entity_type == "Product",
            AuditLog.entity_id == product_id,
        )
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )).scalars().all()
    return [AuditLogResponse.model_validate(log) for log in logs]


# ── Maintenances ────────────────────────────────────────────────────────────


@router.get("/{product_id}/maintenances", response_model=list[MaintenanceResponse])
async def list_maintenances(
    product_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_READ)),
) -> list[MaintenanceResponse]:
    """Liste les maintenances d'un produit (products:read)."""
    svc = ProductMaintenanceService(db)
    items = await svc.list_maintenances(current_user.tenant_id, product_id)
    return [MaintenanceResponse.model_validate(m) for m in items]


@router.post(
    "/{product_id}/maintenances",
    response_model=MaintenanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_maintenance(
    product_id: int,
    data: MaintenanceCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> MaintenanceResponse:
    """Crée une maintenance pour un produit (products:write)."""
    svc = ProductMaintenanceService(db)
    maintenance = await svc.create_maintenance(current_user.tenant_id, product_id, data)
    await db.commit()
    await db.refresh(maintenance)
    return MaintenanceResponse.model_validate(maintenance)


@router.patch("/{product_id}/maintenances/{maintenance_id}", response_model=MaintenanceResponse)
async def update_maintenance(
    product_id: int,
    maintenance_id: int,
    data: MaintenanceUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> MaintenanceResponse:
    """Met à jour une maintenance (products:write)."""
    svc = ProductMaintenanceService(db)
    maintenance = await svc.update_maintenance(current_user.tenant_id, maintenance_id, data)
    await db.commit()
    await db.refresh(maintenance)
    return MaintenanceResponse.model_validate(maintenance)


@router.delete(
    "/{product_id}/maintenances/{maintenance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_maintenance(
    product_id: int,
    maintenance_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> None:
    """Supprime (soft) une maintenance (products:write)."""
    svc = ProductMaintenanceService(db)
    await svc.delete_maintenance(current_user.tenant_id, maintenance_id)
    await db.commit()


@router.get("/{product_id}/availability", response_model=ProductAvailabilityResponse)
async def get_product_availability(
    product_id: int,
    date_from: date = Query(..., description="Date de début (YYYY-MM-DD)"),
    date_to: date = Query(..., description="Date de fin (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_READ)),
) -> ProductAvailabilityResponse:
    """Retourne les créneaux d'indisponibilité d'un produit sur une plage de dates."""
    if date_to < date_from:
        raise HTTPException(status_code=400, detail=ErrorMessages.INVALID_DATE_RANGE)

    product = (await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == current_user.tenant_id,
            Product.is_active == True,
        )
    )).scalar_one_or_none()
    if not product:
        raise NotFound(ErrorMessages.PRODUCT_NOT_FOUND)

    active_statuses = ["confirmed", "pre_check", "confirmed_risk", "delivered", "extended"]
    rows = (await db.execute(
        select(
            ReservationLine.quantity,
            ReservationLine.reservation_id,
            Reservation.reference,
            Reservation.delivery_date,
            Reservation.return_date,
        )
        .join(Reservation, and_(
            Reservation.id == ReservationLine.reservation_id,
            Reservation.tenant_id == current_user.tenant_id,
        ))
        .where(
            ReservationLine.product_id == product_id,
            ReservationLine.tenant_id == current_user.tenant_id,
            Reservation.status.in_(active_statuses),
            Reservation.delivery_date <= date_to,
            Reservation.return_date >= date_from,
        )
    )).all()

    busy_slots = [
        ProductAvailabilitySlot(
            date_from=row.delivery_date,
            date_to=row.return_date,
            reserved_quantity=row.quantity,
            reservation_id=row.reservation_id,
            reservation_ref=row.reference,
        )
        for row in rows
    ]

    return ProductAvailabilityResponse(
        product_id=product_id,
        total_quantity=product.stock_quantity,
        date_from=date_from,
        date_to=date_to,
        busy_slots=busy_slots,
    )


# ---------------------------------------------------------------------------
# Import CSV (L-09)
# ---------------------------------------------------------------------------

_PRODUCT_CSV_REQUIRED = {"name", "sku", "category", "price_per_day_cents"}
_PRODUCT_CSV_INT_FIELDS = {"price_per_day_cents", "deposit_amount_cents", "stock_quantity", "available_quantity"}


@router.post("/import", response_model=ImportReport, status_code=status.HTTP_200_OK)
async def import_products_csv(
    file: UploadFile = File(..., description="Fichier CSV produits (UTF-8, séparateur virgule)"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> ImportReport:
    """Importe des produits depuis un fichier CSV.

    Colonnes supportées : name (required), sku (required), category (required),
    price_per_day_cents (required), deposit_amount_cents, stock_quantity,
    available_quantity, condition, image_url.

    Règles :
    - Lignes avec SKU déjà existant dans le tenant → skipped
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
        text = content.decode("utf-8-sig")
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

    missing_required = _PRODUCT_CSV_REQUIRED - set(reader.fieldnames)
    if missing_required:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Colonnes obligatoires manquantes : {', '.join(sorted(missing_required))}",
        )

    report = ImportReport()

    for row_idx, row in enumerate(reader, start=1):
        name = row.get("name", "").strip()
        sku = row.get("sku", "").strip()
        if not name and not sku:
            report.skipped += 1
            continue

        if not name:
            report.errors.append(ImportRowError(row=row_idx, field="name", message="name est obligatoire"))
            continue
        if not sku:
            report.errors.append(ImportRowError(row=row_idx, field="sku", message="sku est obligatoire"))
            continue

        # Vérifier doublon SKU dans le tenant
        existing = (await db.execute(
            select(Product).where(
                Product.tenant_id == current_user.tenant_id,
                Product.sku == sku,
            )
        )).scalar_one_or_none()
        if existing:
            report.skipped += 1
            continue

        # Convertir les champs entiers
        int_values: dict = {}
        parse_error = False
        for int_field in _PRODUCT_CSV_INT_FIELDS:
            raw = row.get(int_field, "").strip()
            if not raw:
                continue
            try:
                int_values[int_field] = int(raw)
            except ValueError:
                report.errors.append(ImportRowError(
                    row=row_idx,
                    field=int_field,
                    message=f"Valeur entière attendue, reçu: {raw!r}",
                ))
                parse_error = True
                break
        if parse_error:
            continue

        payload = {
            "name": name,
            "sku": sku,
            "category": row.get("category", "").strip(),
            "price_per_day_cents": int_values.get("price_per_day_cents", 0),
            "deposit_amount_cents": int_values.get("deposit_amount_cents", 0),
            "stock_quantity": int_values.get("stock_quantity", 0),
            "available_quantity": int_values.get("available_quantity") or int_values.get("stock_quantity", 0),
            "condition": row.get("condition", "").strip() or "bon",
            "image_url": row.get("image_url", "").strip() or None,
        }

        try:
            validated = ProductCreate(**payload)
        except Exception as exc:
            report.errors.append(ImportRowError(row=row_idx, message=str(exc)))
            continue

        try:
            product_svc = ProductService(db)
            await product_svc.create_product(validated, current_user.tenant_id)
            await db.commit()
            report.created += 1
        except Exception as exc:
            await db.rollback()
            logger.warning("CSV import product row %d failed: %s", row_idx, exc)
            report.errors.append(ImportRowError(row=row_idx, message=str(exc)))

    return report
