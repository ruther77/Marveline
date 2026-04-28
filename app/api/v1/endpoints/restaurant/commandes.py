"""Endpoints — Salle & Commandes restaurant.

Salle (tables) :
  GET    /restaurant/tables            → liste tables avec statut LIBRE/OCCUPEE
  GET    /restaurant/tables/{id}       → table + commande active
  PATCH  /restaurant/tables/{id}/statut → libérer table (annule commande OUVERTE)

Commandes :
  POST   /restaurant/commandes         → ouvrir commande (table optionnelle)
  GET    /restaurant/commandes/{id}    → détail commande active
  DELETE /restaurant/commandes/{id}   → annuler commande (statut OUVERTE requis)
  POST   /restaurant/commandes/{id}/payer → clôturer et encaisser

Lignes :
  POST   /restaurant/commandes/{id}/lignes            → ajouter ligne (atomique)
  PATCH  /restaurant/lignes-commande/{ligne_id}/statut → mise à jour statut ligne
  DELETE /restaurant/commandes/{id}/lignes/{ligne_id} → supprimer ligne
"""
import os
import uuid as uuid_lib
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.restaurant.commande import (
    CommandeCreate,
    CommandeDetail,
    CommandeDetailHistorique,
    CommandeResponse,
    PaiementRequest,
)
from app.schemas.restaurant.ligne_commande import (
    LigneCommandeCreate,
    LigneCommandeCreateResponse,
    LigneCommandeResponse,
    MarquerPretRequest,
    MarquerPretResponse,
    StatutLigneUpdate,
    TicketCuisineResponse,
)
from app.schemas.restaurant.side import SideCreate, SideResponse, SideUpdate
from app.schemas.restaurant.table import TableCreate, TableListResponse, TableResponse, TableUpdate
from app.schemas.restaurant.variante_plat import VariantePlatCreate, VariantePlatResponse, VariantePlatUpdate
from app.schemas.restaurant.variante_side import VarianteSideCreate, VarianteSideResponse, VarianteSideUpdate
from app.services.restaurant.commande import CommandeService
from app.services.restaurant.ligne_commande import LigneCommandeService
from app.services.restaurant.side import SideService
from app.services.restaurant.table import TableService
from app.services.restaurant.variante_plat import VariantePlatService
from app.services.restaurant.variante_side import VarianteSideService
from app.api.ws.manager import publish_event

router = APIRouter(prefix="/restaurant", tags=["Restaurant — Commandes"])

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 Mo


# ── Upload image ──────────────────────────────────────────────────────────────

@router.post("/uploads/image", status_code=201)
async def upload_restaurant_image(
    file: UploadFile = File(...),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> dict:
    """Upload une image (JPG/PNG/WebP, max 5 Mo) pour un plat ou boisson."""
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Format non supporté. JPG, PNG ou WebP uniquement.",
        )
    content = await file.read()
    if len(content) > _MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Image trop volumineuse (max 5 Mo).",
        )
    ext = "jpg" if file.content_type == "image/jpeg" else file.content_type.split("/")[-1]
    filename = f"{uuid_lib.uuid4().hex}.{ext}"
    upload_dir = f"/app/uploads/restaurant/{current_user.tenant_id}"
    os.makedirs(upload_dir, exist_ok=True)
    with open(os.path.join(upload_dir, filename), "wb") as out:
        out.write(content)
    return {"url": f"/uploads/restaurant/{current_user.tenant_id}/{filename}"}


# ── Catalogue plats ───────────────────────────────────────────────────────────

@router.get("/variantes-plat", response_model=list[VariantePlatResponse])
async def list_variantes_plat(
    type: str | None = None,
    include_inactive: bool = Query(False, description="Inclure les variantes inactives"),
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> list[VariantePlatResponse]:
    """Liste les variantes de plat (plat|boisson|formule)."""
    if include_inactive:
        return await VariantePlatService(db).list_all(type)
    return await VariantePlatService(db).list_actives(type)


@router.post("/variantes-plat", response_model=VariantePlatResponse, status_code=201)
async def create_variante_plat(
    payload: VariantePlatCreate,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> VariantePlatResponse:
    """Crée un nouveau plat/boisson/formule."""
    result = await VariantePlatService(db).create(payload)
    await db.commit()
    return result


@router.patch("/variantes-plat/{variante_id}", response_model=VariantePlatResponse)
async def update_variante_plat(
    variante_id: int,
    payload: VariantePlatUpdate,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> VariantePlatResponse:
    """Met a jour une variante de plat (prix, TVA, catégorie, liaisons, is_active)."""
    result = await VariantePlatService(db).update(variante_id, payload)
    await db.commit()
    return result


# ── Sides par plat (liaisons avec supplément) ────────────────────────────────

@router.get("/variantes-plat/{variante_id}/sides", response_model=list[VarianteSideResponse])
async def list_variante_sides(
    variante_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> list[VarianteSideResponse]:
    """Liste les sides liés à un plat avec leur supplément."""
    return await VarianteSideService(db).list_sides(variante_id, current_user.tenant_id)


@router.post("/variantes-plat/{variante_id}/sides", response_model=VarianteSideResponse, status_code=201)
async def add_variante_side(
    variante_id: int,
    payload: VarianteSideCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> VarianteSideResponse:
    """Ajoute un side à un plat avec supplément."""
    result = await VarianteSideService(db).add_side(variante_id, current_user.tenant_id, payload)
    await db.commit()
    return result


@router.patch("/variantes-plat/{variante_id}/sides/{side_id}", response_model=VarianteSideResponse)
async def update_variante_side(
    variante_id: int,
    side_id: int,
    payload: VarianteSideUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> VarianteSideResponse:
    """Modifie le supplément ou le statut d'un side pour un plat."""
    result = await VarianteSideService(db).update_side(
        variante_id, side_id, current_user.tenant_id, payload
    )
    await db.commit()
    return result


@router.delete("/variantes-plat/{variante_id}/sides/{side_id}", status_code=204)
async def remove_variante_side(
    variante_id: int,
    side_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> None:
    """Retire un side d'un plat."""
    await VarianteSideService(db).remove_side(variante_id, side_id, current_user.tenant_id)
    await db.commit()


# ── Sides (accompagnements globaux) ──────────────────────────────────────────

@router.get("/sides", response_model=list[SideResponse])
async def list_sides(
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> list[SideResponse]:
    """Liste les accompagnements du tenant."""
    if include_inactive:
        return await SideService(db).list_all()
    return await SideService(db).list_actives()


@router.post("/sides", response_model=SideResponse, status_code=201)
async def create_side(
    payload: SideCreate,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> SideResponse:
    """Crée un nouvel accompagnement."""
    result = await SideService(db).create(payload)
    await db.commit()
    return result


@router.patch("/sides/{side_id}", response_model=SideResponse)
async def update_side(
    side_id: int,
    payload: SideUpdate,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> SideResponse:
    """Met à jour un accompagnement (nom, image, ingrédient, quantité, is_active)."""
    result = await SideService(db).update(side_id, payload)
    await db.commit()
    return result


# ── Tables ───────────────────────────────────────────────────────────────────

@router.post("/tables", response_model=TableResponse, status_code=201)
async def create_table(
    payload: TableCreate,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> TableResponse:
    """Crée une nouvelle table."""
    result = await TableService(db).create_table(payload)
    await db.commit()
    return result


@router.get("/tables", response_model=TableListResponse)
async def list_tables(
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> TableListResponse:
    """Liste toutes les tables avec statut LIBRE/OCCUPEE calculé en temps réel."""
    return await TableService(db).list_avec_statut()


@router.get("/tables/{table_id}", response_model=TableResponse)
async def get_table(
    table_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> TableResponse:
    """Détail d'une table avec statut et commande active."""
    return await TableService(db).get_avec_statut(table_id)


@router.patch("/tables/{table_id}", response_model=TableResponse)
async def update_table(
    table_id: int,
    payload: TableUpdate,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> TableResponse:
    """Met à jour une table (numéro, capacité, is_active)."""
    result = await TableService(db).update_table(table_id, payload)
    await db.commit()
    return result


@router.delete("/tables/{table_id}", status_code=204)
async def delete_table(
    table_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> None:
    """Désactive une table (soft delete) ; annule la commande OUVERTE si présente."""
    commande_id = await TableService(db).delete_table(table_id)
    if commande_id is not None:
        await CommandeService(db).annuler(commande_id)
    await db.commit()
    if commande_id is not None:
        await publish_event(current_user.tenant_id, "kds", "commande_annulee", {
            "commande_id": commande_id,
        })


@router.patch("/tables/{table_id}/statut", response_model=CommandeResponse)
async def liberer_table(
    table_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> CommandeResponse:
    """Libère une table en annulant la commande OUVERTE associée."""
    table = await TableService(db).get_avec_statut(table_id)
    if table.commande_active is None:
        return Response(status_code=204)  # type: ignore[return-value]
    result = await CommandeService(db).annuler(table.commande_active.commande_id)
    await db.commit()
    return result


# ── Commandes ─────────────────────────────────────────────────────────────────

@router.post("/commandes", response_model=CommandeResponse, status_code=201)
async def ouvrir_commande(
    payload: CommandeCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> CommandeResponse:
    """Ouvre une nouvelle commande sur une table (ou sans table pour emporter)."""
    result = await CommandeService(db).ouvrir(payload, created_by_id=current_user.id)
    await db.commit()
    await publish_event(current_user.tenant_id, "kds", "nouvelle_commande", {
        "commande_id": result.id, "table_numero": result.table_numero,
    })
    return result


@router.get("/commandes/tickets-cuisine", response_model=TicketCuisineResponse)
async def get_tickets_cuisine(
    date_cuisine: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> TicketCuisineResponse:
    """Ticket cuisine : lignes ENVOYEE / LANCEE à préparer."""
    return await LigneCommandeService(db).get_ticket_cuisine(date_cuisine)


@router.get("/commandes/{commande_id}", response_model=CommandeDetail)
async def get_commande(
    commande_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> CommandeDetail:
    """Détail d'une commande active avec ses lignes et total provisoire."""
    return await CommandeService(db).get_detail(commande_id)


@router.delete("/commandes/{commande_id}", response_model=CommandeResponse)
async def annuler_commande(
    commande_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> CommandeResponse:
    """Annule une commande OUVERTE (statut → ANNULEE)."""
    result = await CommandeService(db).annuler(commande_id)
    await db.commit()
    await publish_event(current_user.tenant_id, "kds", "commande_annulee", {
        "commande_id": commande_id,
    })
    return result


@router.post("/commandes/{commande_id}/payer", response_model=CommandeDetailHistorique)
async def payer_commande(
    commande_id: int,
    payload: PaiementRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> CommandeDetailHistorique:
    """Encaisse la commande : calcule TVA, enregistre paiement, clôture."""
    result = await CommandeService(db).payer(commande_id, payload)
    await db.commit()
    await publish_event(current_user.tenant_id, "salle", "commande_payee", {
        "commande_id": commande_id,
    })
    return result


# ── Lignes de commande ────────────────────────────────────────────────────────

@router.post(
    "/commandes/{commande_id}/lignes",
    response_model=LigneCommandeCreateResponse,
    status_code=201,
)
async def ajouter_ligne(
    commande_id: int,
    payload: LigneCommandeCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> LigneCommandeCreateResponse:
    """Ajoute une ligne à la commande (atomique : stock + portions décrémentés)."""
    result = await LigneCommandeService(db).create_ligne(
        commande_id, payload, created_by_id=current_user.id
    )
    await db.commit()
    await publish_event(current_user.tenant_id, "kds", "commande_modifiee", {
        "commande_id": commande_id, "action": "ligne_ajoutee",
    })
    return result


@router.patch(
    "/lignes-commande/{ligne_id}/statut",
    response_model=LigneCommandeResponse,
)
async def update_statut_ligne(
    ligne_id: int,
    payload: StatutLigneUpdate,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> LigneCommandeResponse:
    """Mise à jour du statut d'une ligne (LANCEE → PRETE → SERVIE)."""
    result = await LigneCommandeService(db).update_statut(ligne_id, payload)
    await db.commit()
    return result


@router.post(
    "/commandes/{commande_id}/marquer-pret",
    response_model=MarquerPretResponse,
)
async def marquer_pret(
    commande_id: int,
    payload: MarquerPretRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> MarquerPretResponse:
    """Marque des lignes comme PRETE (toutes ou seulement les ligne_ids fournis)."""
    result = await LigneCommandeService(db).marquer_pret(commande_id, payload)
    await db.commit()
    await publish_event(current_user.tenant_id, "salle", "commande_prete", {
        "commande_id": commande_id,
    })
    return result


@router.post(
    "/commandes/{commande_id}/marquer-servi",
    response_model=MarquerPretResponse,
)
async def marquer_servi(
    commande_id: int,
    payload: MarquerPretRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> MarquerPretResponse:
    """Marque les lignes PRETE comme SERVIE."""
    result = await LigneCommandeService(db).marquer_servi(commande_id, payload)
    await db.commit()
    await publish_event(current_user.tenant_id, "salle", "commande_servie", {
        "commande_id": commande_id,
    })
    return result


@router.delete("/commandes/{commande_id}/lignes/{ligne_id}", status_code=204)
async def supprimer_ligne(
    commande_id: int,
    ligne_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> None:
    """Supprime une ligne ENVOYEE (interdit si PRETE ou SERVIE)."""
    await LigneCommandeService(db).delete(ligne_id)
    await db.commit()
