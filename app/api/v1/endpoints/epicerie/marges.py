"""Endpoints épicerie — Gestion des marges par catégorie.

CRUD pour définir le taux de marge par catégorie produit.
Le prix de vente = prix_achat × (1 + marge%) × (1 + TVA%).
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope
from app.core.permissions import Scope
from app.repositories.epicerie.marge import AsyncEpicerieMargeRepository
from app.repositories.epicerie.produit import AsyncEpicerieProduitRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/epicerie/marges", tags=["Épicerie — Marges"])

_EPICERIE_TENANT_ID = 2

# ── Marges par défaut par famille ─────────────────────────────────────────────

DEFAULT_MARGES: dict[str, int] = {
    # Alcools — marge élevée
    "ALC_BIERE": 4000, "ALC_VIN_RGE": 5000, "ALC_VIN_BLC": 5000,
    "ALC_VIN_ROSE": 5000, "ALC_SPIRITUEUX": 5000, "ALC_LIQUEUR": 5000,
    "ALC_APERO": 4500,
    # Boissons — marge moyenne-haute
    "BOIS_EAU": 3500, "BOIS_SODA": 4000, "BOIS_JUS": 3500,
    "BOIS_SIROP": 3500, "BOIS_ENERG": 4500, "BOIS_CAFE": 4000,
    "BOIS_THE": 4000, "BOIS_CHOCO": 3500,
    # Épicerie sèche — marge moyenne
    "EPIC_SEMOULE": 3000, "EPIC_LEGUM_SEC": 3000, "EPIC_PATE": 3000,
    "EPIC_RIZ": 3000,
    # Frais — marge basse
    "FRAIS_BOEUF": 2500, "FRAIS_PORC": 2500, "FRAIS_AGNEAU": 2500,
    "FRAIS_VOLAILLE": 2500, "FRAIS_POISSON": 2500,
    "FRAIS_CHARC": 3000, "FRAIS_SAUCISSE": 3000, "FRAIS_JAMBON": 3000,
    "FRAIS_LARDON": 3000, "FRAIS_OEUF": 2500, "FRAIS_CRUST": 3000,
    "FRAIS_COQUIL": 3000, "FRAIS_TRAIT": 3000,
    # Laitier
    "LAIT_CREME": 3000, "LAIT_BEURRE": 3000, "LAIT_FROMAGE": 3500,
    "LAIT_YAOURT": 3000, "LAIT_DESSERT": 3000, "LAIT_UHT": 2500,
    # Condiments
    "COND_BOUILLON": 3500, "COND_SEL": 3000, "COND_HUILE": 3000,
    "COND_VINAIGRE": 3500, "COND_SAUCE": 3500, "COND_EPICE": 4000,
    # Conserves
    "CONS_LEGUME": 3000, "CONS_PLAT": 3000, "CONS_POISSON": 3500,
    "CONS_SAUCE": 3000,
    # Surgelés
    "SURG_VIANDE": 3000, "SURG_POISSON": 3000, "SURG_GLACE": 4000,
    "SURG_PATISS": 3500, "SURG_LEGUME": 3000,
    # Sucré
    "SUCR_BONBON": 5000, "SUCR_CHOCO": 4500, "SUCR_BISC": 4000,
    "SUCR_GATEAU": 4000, "SUCR_CONF": 3500, "SUCR_SUCRE": 3000,
    "SUCR_FARINE": 2500, "SUCR_CEREAL": 3500, "SUCR_LEVURE": 3000,
    "SUCR_AROME": 4000, "SUCR_NAPPAGE": 4000, "SUCR_VIEN": 3500,
    # Snacking
    "SNACK_CHIPS": 5000, "SNACK_FRUIT_SEC": 4500, "SNACK_BISCUIT": 4500,
    # Boulangerie
    "BOUL_BRIOCHE": 3500, "BOUL_PAIN": 3000, "BOUL_VIEN": 3500,
    # Fruits & Légumes
    "FL_AROMATE": 4000, "FL_SALADE": 3000, "FL_LEGUME": 3000, "FL_FRUIT": 3500,
    # Hygiène / Entretien
    "HYG_CORPS": 4000, "HYG_PAPIER": 3500,
    "ENTR_LESSIVE": 3500, "ENTR_NETTOY": 3500, "ENTR_VAISS": 3500,
    # Pro
    "PRO_FILM": 3000, "PRO_PROTECT": 3500, "PRO_ETIQ": 3000,
    "PRO_EMBALL": 3000, "PRO_JETABLE": 3500,
    # Monde
    "MONDE_HALAL": 3500, "MONDE_ASIE": 3500, "MONDE_ORIENT": 3500,
    "MONDE_AMERIQUE": 3500, "MONDE_AFRIQUE": 3500,
    # Autre
    "AUTRE": 3000,
}


# ── Schemas ───────────────────────────────────────────────────────────────────


class MargeRead(BaseModel):
    categorie: str
    taux_marge_centieme: int
    taux_pct: float  # commodité : 3000 → 30.0

    model_config = {"from_attributes": True}


class MargesListResponse(BaseModel):
    marges: list[MargeRead]
    total: int


class MargeUpdate(BaseModel):
    categorie: str
    taux_marge_centieme: int = Field(..., ge=0, le=20000)


class MargesBatchUpdate(BaseModel):
    marges: list[MargeUpdate] = Field(..., min_length=1)


class MargeCreate(BaseModel):
    categorie: str = Field(..., min_length=1, max_length=100, pattern=r"^[A-Z0-9_]+$")
    taux_marge_centieme: int = Field(3000, ge=0, le=20000)


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", response_model=MargesListResponse)
async def list_marges(
    db: AsyncSession = Depends(get_async_db),
    _=Depends(require_scope(Scope.SETTINGS_READ)),
):
    """Liste toutes les marges par catégorie. Crée les défauts si vide."""
    repo = AsyncEpicerieMargeRepository(db)
    marges = await repo.get_all(_EPICERIE_TENANT_ID)

    # Init avec les défauts si table vide
    if not marges:
        await repo.upsert_batch(_EPICERIE_TENANT_ID, DEFAULT_MARGES)
        await db.commit()
        marges = await repo.get_all(_EPICERIE_TENANT_ID)

    items = [
        MargeRead(
            categorie=m.categorie,
            taux_marge_centieme=m.taux_marge_centieme,
            taux_pct=m.taux_marge_centieme / 100,
        )
        for m in marges
    ]
    return MargesListResponse(marges=items, total=len(items))


@router.put("", response_model=MargesListResponse)
async def update_marges(
    payload: MargesBatchUpdate,
    db: AsyncSession = Depends(get_async_db),
    _=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Met à jour les marges par catégorie (batch upsert)."""
    repo = AsyncEpicerieMargeRepository(db)
    for m in payload.marges:
        await repo.upsert(_EPICERIE_TENANT_ID, m.categorie, m.taux_marge_centieme)
    await db.commit()

    marges = await repo.get_all(_EPICERIE_TENANT_ID)
    items = [
        MargeRead(
            categorie=m.categorie,
            taux_marge_centieme=m.taux_marge_centieme,
            taux_pct=m.taux_marge_centieme / 100,
        )
        for m in marges
    ]
    return MargesListResponse(marges=items, total=len(items))


@router.post("/categories", response_model=MargeRead, status_code=201)
async def create_marge_categorie(
    payload: MargeCreate,
    db: AsyncSession = Depends(get_async_db),
    _=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Crée une nouvelle catégorie de marge (code unique par tenant)."""
    repo = AsyncEpicerieMargeRepository(db)
    existing = await repo.get_by_categorie(_EPICERIE_TENANT_ID, payload.categorie)
    if existing:
        raise HTTPException(status_code=409, detail=f"La catégorie '{payload.categorie}' existe déjà.")
    obj = await repo.upsert(_EPICERIE_TENANT_ID, payload.categorie, payload.taux_marge_centieme)
    await db.commit()
    return MargeRead(
        categorie=obj.categorie,
        taux_marge_centieme=obj.taux_marge_centieme,
        taux_pct=obj.taux_marge_centieme / 100,
    )


@router.delete("/categories/{categorie}", status_code=204)
async def delete_marge_categorie(
    categorie: str,
    db: AsyncSession = Depends(get_async_db),
    _=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Supprime une catégorie de marge (les produits associés gardent leur code)."""
    repo = AsyncEpicerieMargeRepository(db)
    deleted = await repo.remove(_EPICERIE_TENANT_ID, categorie)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Catégorie '{categorie}' introuvable.")
    await db.commit()


@router.post("/recalculate-prices")
async def recalculate_prices(
    db: AsyncSession = Depends(get_async_db),
    _=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Recalcule tous les prix de vente depuis prix_achat × marge × TVA."""
    from sqlalchemy import text

    marge_repo = AsyncEpicerieMargeRepository(db)
    marges = await marge_repo.get_marges_dict(_EPICERIE_TENANT_ID)

    if not marges:
        raise HTTPException(status_code=409, detail="Aucune marge définie.")

    # Fallback marge si catégorie pas dans la table
    default_marge = marges.get("AUTRE", 3000)

    produit_repo = AsyncEpicerieProduitRepository(db)
    result = await db.execute(
        text("SELECT id, categorie, prix_achat_cts, taux_tva FROM epicerie_produits WHERE tenant_id = :tid AND actif = true"),
        {"tid": _EPICERIE_TENANT_ID},
    )
    rows = result.fetchall()

    updated = 0
    for row in rows:
        pid, cat, achat, tva = row
        if not achat or achat <= 0:
            continue
        marge_taux = marges.get(cat or "AUTRE", default_marge)
        prix_ht = int(achat * (1 + marge_taux / 10000))
        prix_ttc = int(prix_ht * (1 + (tva or 2000) / 10000))
        await db.execute(
            text("UPDATE epicerie_produits SET prix_unitaire_cts = :prix WHERE id = :id"),
            {"prix": prix_ttc, "id": pid},
        )
        await db.execute(
            text(
                "INSERT INTO epicerie_prix_historique "
                "(tenant_id, produit_id, prix_achat_cts, prix_vente_cts, taux_marge_centieme, source, reference) "
                "VALUES (:tid, :pid, :achat, :vente, :marge, 'recalcul', 'Recalcul marges')"
            ),
            {"tid": _EPICERIE_TENANT_ID, "pid": pid, "achat": achat, "vente": prix_ttc, "marge": marge_taux},
        )
        updated += 1

    await db.commit()
    return {"updated": updated, "total": len(rows)}
