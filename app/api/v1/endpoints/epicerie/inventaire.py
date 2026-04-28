"""Endpoints Inventaire épicerie — stock, ajustements, mouvements, produits."""
import logging
import os
import uuid as uuid_lib
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.errors import ErrorMessages
from app.core.config import settings
from app.core.database import get_async_db
from app.core.deps import require_scope
from app.core.exceptions import NotFound
from app.core.permissions import Scope
from app.repositories.epicerie.produit import AsyncEpicerieProduitRepository
from app.repositories.epicerie.stock import AsyncEpicerieStockRepository
from app.repositories.finance.vendor import AsyncFinanceVendorRepository
from app.schemas.epicerie.produit import (
    EpicerieEanAdd,
    EpicerieEanRead,
    EpicerieProduitEansResponse,
    EpicerieProduitRead,
)

logger = logging.getLogger(__name__)

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 Mo
_MAX_DIM = 512  # px thumbnail
from app.schemas.epicerie.stock import (
    AjustementCreate,
    AjustementResponse,
    ComptageRequest,
    ComptageResponse,
    EpicerieStockListResponse,
    EpicerieStockRead,
    EpicerieStockSummary,
    SeuilUpdate,
    StockMovementsListResponse,
    StockMovementRead,
)
from app.services.epicerie.inventaire import ajuster_stock, comptage_inventaire, set_seuil_alerte

router = APIRouter(prefix="/epicerie/stock", tags=["Épicerie — Inventaire"])
produits_router = APIRouter(prefix="/epicerie/produits", tags=["Épicerie — Produits"])


def _stock_badge(quantite: float, seuil: float) -> str:
    if quantite <= 0:
        return "rupture"
    if quantite <= seuil:
        return "bas"
    return "ok"


def _to_stock_read(stock, produit, vendor_name: str | None = None) -> EpicerieStockRead:
    """Construit EpicerieStockRead — stock peut être None (LEFT JOIN, produit sans entrée stock)."""
    quantite = float(stock.quantite) if stock else 0.0
    seuil = float(stock.seuil_alerte) if stock else 0.0
    return EpicerieStockRead(
        id=stock.id if stock else None,
        produit_id=produit.id,
        designation=produit.designation_clean,
        categorie=produit.categorie,
        fournisseur_source=vendor_name,
        image_url=produit.image_url,
        quantite=quantite,
        seuil_alerte=seuil,
        prix_achat_cts=produit.prix_achat_cts,
        prix_unitaire_cts=produit.prix_unitaire_cts,
        unite_vente=produit.unite_vente,
        unite_base=produit.unite_base,
        colisage=produit.colisage,
        volume_unitaire_ml=produit.volume_unitaire_ml,
        conditionnement=produit.description,
        statut_badge=_stock_badge(quantite, seuil),
        derniere_mise_a_jour=stock.updated_at if stock else None,
        actif=produit.actif,
    )


async def _build_vendors_dict(db: AsyncSession) -> dict[int, str]:
    """Charge {vendor_id: vendor_name} en une seule requête."""
    repo = AsyncFinanceVendorRepository(db)
    vendors = await repo.list_all()
    return {v.id: v.name for v in vendors}


@router.get("", response_model=EpicerieStockListResponse)
async def list_stock(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=500),
    search: Optional[str] = Query(default=None),
    categorie: Optional[str] = Query(default=None),
    vendor_id: Optional[int] = Query(default=None),
    is_low: Optional[bool] = Query(default=None),
    is_empty: Optional[bool] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Liste paginée du stock épicerie avec indicateurs."""
    repo = AsyncEpicerieStockRepository(db)
    items, total = await repo.list_with_produit(
        tenant_id=current_user.tenant_id,
        page=page,
        per_page=per_page,
        search=search,
        categorie=categorie,
        vendor_id=vendor_id,
        is_low=is_low,
        is_empty=is_empty,
    )
    vendors = await _build_vendors_dict(db)
    return EpicerieStockListResponse(
        items=[_to_stock_read(s, p, vendors.get(p.vendor_id)) for p, s in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/stats", response_model=EpicerieStockSummary)
async def stock_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Résumé global du stock (ruptures, bas, valeur)."""
    repo = AsyncEpicerieStockRepository(db)
    summary = await repo.summary(current_user.tenant_id)
    return EpicerieStockSummary(**summary)


@router.get("/mouvements", response_model=StockMovementsListResponse)
async def list_mouvements(
    produit_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=500),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Journal des mouvements de stock épicerie avec nom produit."""
    repo = AsyncEpicerieStockRepository(db)
    items, total = await repo.list_movements(
        tenant_id=current_user.tenant_id,
        produit_id=produit_id,
        page=page,
        per_page=per_page,
    )

    # Enrichir avec les noms produits
    produit_ids = list({m.produit_id for m in items})
    produit_repo = AsyncEpicerieProduitRepository(db)
    produits = await produit_repo.get_by_ids(produit_ids, current_user.tenant_id)
    produit_map = {p.id: p.designation_clean for p in produits}

    return StockMovementsListResponse(
        items=[
            StockMovementRead(
                id=m.id,
                produit_id=m.produit_id,
                type=m.type,
                quantite=float(m.quantite),
                signed_quantite=float(m.quantite),
                stock_apres=float(m.stock_apres),
                date_mouvement=m.date_mouvement,
                reference=getattr(m, "reference", None),
                notes=m.notes,
                created_by_id=m.created_by_id,
                produit_designation=produit_map.get(m.produit_id),
                created_by_name=None,
            )
            for m in items
        ],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.put("/{produit_id}/seuil", response_model=EpicerieStockRead)
async def update_seuil(
    produit_id: int,
    payload: SeuilUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_WRITE)),
):
    """Met à jour le seuil d'alerte d'un produit."""
    result = await set_seuil_alerte(db, current_user.tenant_id, produit_id, payload.seuil)
    stock = result["stock"]
    produit_repo = AsyncEpicerieProduitRepository(db)
    produit = await produit_repo.get_by_id(produit_id, current_user.tenant_id)
    vendors = await _build_vendors_dict(db)
    return _to_stock_read(stock, produit, vendors.get(produit.vendor_id) if produit else None)


@router.post("/ajustement", response_model=AjustementResponse, status_code=201)
async def ajustement(
    payload: AjustementCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_WRITE)),
):
    """Crée un ajustement de stock (entrée, sortie, perte, ajustement)."""
    return await ajuster_stock(db, current_user.tenant_id, payload, current_user.id)


@router.post("/comptage", response_model=ComptageResponse)
async def comptage(
    payload: ComptageRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_WRITE)),
):
    """Inventaire physique : ajuste le stock de chaque produit compté."""
    return await comptage_inventaire(db, current_user.tenant_id, payload, current_user.id)


@router.get("/{produit_id}", response_model=EpicerieStockRead)
async def get_stock_by_produit(
    produit_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Détail du stock pour un produit donné."""
    stock_repo = AsyncEpicerieStockRepository(db)
    produit_repo = AsyncEpicerieProduitRepository(db)
    stock = await stock_repo.get_by_produit(produit_id, current_user.tenant_id)
    if stock is None:
        raise NotFound(f"Stock introuvable pour le produit {produit_id}")
    produit = await produit_repo.get_by_id(produit_id, current_user.tenant_id)
    if produit is None:
        raise NotFound(f"Produit {produit_id} introuvable")
    vendors = await _build_vendors_dict(db)
    return _to_stock_read(stock, produit, vendors.get(produit.vendor_id))


# ── Produits ────────────────────────────────────────────────────────────────

@router.get("/{produit_id}/prix-historique")
async def prix_historique(
    produit_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Historique des changements de prix d'un produit.

    `date` = effective_date (date facture pour ETL) si présente, sinon created_at.
    `recorded_at` = created_at (timestamp d'enregistrement, pour traçabilité).
    """
    from sqlalchemy import text
    result = await db.execute(
        text(
            "SELECT prix_achat_cts, prix_vente_cts, taux_marge_centieme, source, "
            "reference, source_fournisseur, etl_import_id, effective_date, created_at "
            "FROM epicerie_prix_historique "
            "WHERE tenant_id = :tid AND produit_id = :pid "
            "ORDER BY COALESCE(effective_date, created_at::date) DESC, id DESC LIMIT 500"
        ),
        {"tid": current_user.tenant_id, "pid": produit_id},
    )
    rows = result.fetchall()
    return [
        {
            "prix_achat_cts": r[0],
            "prix_vente_cts": r[1],
            "taux_marge_pct": (r[2] or 0) / 100,
            "source": r[3],
            "reference": r[4],
            "source_fournisseur": r[5],
            "etl_import_id": r[6],
            "date": r[7].isoformat() if r[7] else (r[8].date().isoformat() if r[8] else None),
            "recorded_at": r[8].isoformat() if r[8] else None,
        }
        for r in rows
    ]


@produits_router.get("", response_model=list[EpicerieProduitRead])
async def list_produits(
    search: Optional[str] = Query(default=None),
    categorie: Optional[str] = Query(default=None),
    actif_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Liste des produits épicerie avec filtres."""
    repo = AsyncEpicerieProduitRepository(db)
    page = (offset // limit) + 1
    items, _ = await repo.list_paginated(
        tenant_id=current_user.tenant_id,
        page=page,
        per_page=limit,
        search=search,
        categorie=categorie,
        actif_only=actif_only,
    )
    return [EpicerieProduitRead.model_validate(p) for p in items]


@produits_router.get("/ean/{ean}", response_model=EpicerieProduitRead)
async def get_produit_by_ean(
    ean: str,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Lookup d'un produit par code EAN (scan caisse). Cherche EAN principal puis multi-EAN."""
    repo = AsyncEpicerieProduitRepository(db)
    produit = await repo.get_by_ean_multi(ean, current_user.tenant_id)
    if produit is None:
        raise NotFound(f"Produit EAN '{ean}' introuvable")
    return EpicerieProduitRead.model_validate(produit)


def _products_img_dir() -> str:
    """Répertoire persistant partagé avec l'auto-fetcher."""
    base = settings.UPLOAD_DIR or "uploads"
    if not os.path.isabs(base):
        base = os.path.abspath(base)
    img_dir = os.path.join(base, "products", "epicerie")
    os.makedirs(img_dir, exist_ok=True)
    return img_dir


def _optimize_and_save(content: bytes, dest_path: str) -> None:
    """Redimensionne à 512px max et sauve en JPEG q85."""
    img = Image.open(BytesIO(content))
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    img.thumbnail((_MAX_DIM, _MAX_DIM), Image.LANCZOS)
    img.save(dest_path, "JPEG", quality=85, optimize=True)


@produits_router.post("/{produit_id}/image", response_model=EpicerieProduitRead)
async def upload_produit_image(
    produit_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_WRITE)),
):
    """Upload une photo produit (JPG/PNG/WebP, max 5 Mo).

    Remplace l'image existante (auto-fetchée ou précédemment uploadée).
    Le fichier est redimensionné à 512px et converti en JPEG.
    """
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=ErrorMessages.IMAGE_FORMAT_INVALID,
        )
    content = await file.read()
    if len(content) > _MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=ErrorMessages.IMAGE_SIZE_EXCEEDED,
        )

    repo = AsyncEpicerieProduitRepository(db)
    produit = await repo.get_by_id(produit_id, current_user.tenant_id)
    if produit is None:
        raise NotFound(f"Produit {produit_id} introuvable")

    img_dir = _products_img_dir()
    filename = f"{produit_id}_{uuid_lib.uuid4().hex[:8]}.jpg"
    dest_path = os.path.join(img_dir, filename)

    try:
        _optimize_and_save(content, dest_path)
    except Exception as exc:
        logger.warning("Image optimize failed produit=%s: %s", produit_id, exc)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=ErrorMessages.IMAGE_FORMAT_INVALID,
        )

    # Supprime l'ancien fichier si c'était un path local connu
    old = produit.image_url
    if old and old.startswith("products/epicerie/"):
        old_filename = os.path.basename(old)
        if old_filename != filename:
            old_path = os.path.join(img_dir, old_filename)
            if os.path.isfile(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass

    produit.image_url = f"products/epicerie/{filename}"
    await db.commit()
    await db.refresh(produit)
    logger.info(
        "Epicerie product image uploaded: produit=%s tenant=%s user=%s file=%s",
        produit_id, current_user.tenant_id, current_user.id, filename,
    )
    return EpicerieProduitRead.model_validate(produit)


@produits_router.get(
    "/{produit_id}/eans",
    response_model=EpicerieProduitEansResponse,
)
async def list_produit_eans(
    produit_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Retourne l'EAN principal + tous les EANs secondaires d'un produit."""
    repo = AsyncEpicerieProduitRepository(db)
    produit = await repo.get_by_id(produit_id, current_user.tenant_id)
    if produit is None:
        raise NotFound(f"Produit {produit_id} introuvable")
    eans = await repo.list_secondary_eans(produit_id, current_user.tenant_id)
    return EpicerieProduitEansResponse(
        produit_id=produit.id,
        ean_principal=produit.ean,
        eans_secondaires=[EpicerieEanRead.model_validate(e) for e in eans],
    )


@produits_router.post(
    "/{produit_id}/eans",
    response_model=EpicerieEanRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_produit_ean(
    produit_id: int,
    payload: EpicerieEanAdd,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_WRITE)),
):
    """Ajoute un EAN secondaire à un produit (idempotent par produit).

    Conflit 409 si l'EAN appartient déjà à un autre produit du même tenant.
    """
    repo = AsyncEpicerieProduitRepository(db)
    produit = await repo.get_by_id(produit_id, current_user.tenant_id)
    if produit is None:
        raise NotFound(f"Produit {produit_id} introuvable")

    if produit.ean == payload.ean:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="EAN identique à l'EAN principal du produit",
        )

    existing = await repo.get_by_ean_multi(payload.ean, current_user.tenant_id)
    if existing is not None and existing.id != produit_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"EAN déjà attribué au produit {existing.id} ({existing.designation_clean})",
        )

    entry = await repo.add_secondary_ean(
        produit_id=produit_id,
        ean=payload.ean,
        tenant_id=current_user.tenant_id,
        source_fournisseur=payload.source_fournisseur,
    )
    await db.commit()
    await db.refresh(entry)
    logger.info(
        "Epicerie EAN added: produit=%s tenant=%s user=%s ean=%s",
        produit_id, current_user.tenant_id, current_user.id, payload.ean,
    )
    return EpicerieEanRead.model_validate(entry)
