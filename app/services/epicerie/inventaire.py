"""Service Inventaire épicerie — ajustements, comptage, seuils."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound, BadRequest
from app.repositories.epicerie.produit import AsyncEpicerieProduitRepository
from app.repositories.epicerie.stock import AsyncEpicerieStockRepository
from app.schemas.epicerie.stock import (
    AjustementCreate,
    AjustementResponse,
    ComptageLineResult,
    ComptageRequest,
    ComptageResponse,
)


# Types de mouvement entraînant une entrée de stock
_TYPES_ENTREE = frozenset({"ENTREE", "AJUSTEMENT"})
# Types de mouvement entraînant une sortie de stock
_TYPES_SORTIE = frozenset({"SORTIE", "PERTE"})


def _delta_pour_type(type_ajustement: str, quantite: float) -> float:
    """Retourne le delta signé pour un type d'ajustement."""
    if type_ajustement in _TYPES_ENTREE:
        return quantite
    if type_ajustement in _TYPES_SORTIE:
        return -quantite
    raise BadRequest(f"Type d'ajustement inconnu : {type_ajustement}")


def _ecart_pct(ecart: float, ancien_stock: float) -> float | None:
    """Retourne le pourcentage d'écart, ou None si ancien stock = 0."""
    if ancien_stock == 0:
        return None
    return round(ecart / ancien_stock * 100, 1)


async def ajuster_stock(
    db: AsyncSession,
    tenant_id: int,
    payload: AjustementCreate,
    user_id: int,
) -> AjustementResponse:
    """Crée un ajustement de stock et le mouvement associé (FC_EPICERIE_INVENTAIRE §ajustement)."""
    produit_repo = AsyncEpicerieProduitRepository(db)
    stock_repo = AsyncEpicerieStockRepository(db)

    produit = await produit_repo.get_by_id(payload.produit_id, tenant_id)
    if produit is None:
        raise NotFound(f"Produit {payload.produit_id} introuvable")

    stock = await stock_repo.get_or_create(payload.produit_id, tenant_id)
    ancien_stock = float(stock.quantite)
    delta = _delta_pour_type(payload.type_ajustement, payload.quantite)
    nouvelle_quantite = ancien_stock + delta

    if nouvelle_quantite < 0:
        raise BadRequest(
            f"Stock insuffisant : disponible {stock.quantite}, demandé {payload.quantite}"
        )

    await stock_repo.update_quantite(stock, delta)
    mvt = await stock_repo.create_movement(
        tenant_id=tenant_id,
        produit_id=payload.produit_id,
        type=payload.type_ajustement,
        quantite=delta,
        stock_apres=nouvelle_quantite,
        notes=payload.raison,
        created_by_id=user_id,
    )
    return AjustementResponse(
        success=True,
        ancien_stock=ancien_stock,
        nouveau_stock=nouvelle_quantite,
        quantite_ajustee=abs(delta),
        mouvement_id=mvt.id,
    )


async def comptage_inventaire(
    db: AsyncSession,
    tenant_id: int,
    payload: ComptageRequest,
    user_id: int,
) -> ComptageResponse:
    """Inventaire physique : ajuste le stock de chaque produit compté (FC_EPICERIE_INVENTAIRE §comptage).

    Batch-load produits + stocks en 2 requêtes (anti-N+1), puis itère en mémoire.
    """
    produit_repo = AsyncEpicerieProduitRepository(db)
    stock_repo = AsyncEpicerieStockRepository(db)

    # ── Batch load (2 requêtes au lieu de 2N) ──
    all_produit_ids = [item.produit_id for item in payload.lignes]
    produits_map = await produit_repo.get_by_ids(all_produit_ids, tenant_id)
    stocks_map = await stock_repo.get_or_create_batch(
        [pid for pid in all_produit_ids if pid in produits_map],
        tenant_id,
    )

    nb_ajustements = 0
    lignes: list[ComptageLineResult] = []

    for item in payload.lignes:
        produit = produits_map.get(item.produit_id)
        if produit is None:
            continue

        stock = stocks_map[item.produit_id]
        ancien_stock = float(stock.quantite)
        ecart = item.quantite_comptee - ancien_stock
        ajustement_cree = abs(ecart) >= 0.001

        if ajustement_cree:
            await stock_repo.update_quantite(stock, ecart)
            await stock_repo.create_movement(
                tenant_id=tenant_id,
                produit_id=item.produit_id,
                type="AJUSTEMENT",
                quantite=ecart,
                stock_apres=item.quantite_comptee,
                notes=item.notes or payload.notes,
                created_by_id=user_id,
            )
            nb_ajustements += 1

        lignes.append(ComptageLineResult(
            produit_id=item.produit_id,
            designation=produit.designation_clean,
            ancien_stock=ancien_stock,
            nouveau_stock=item.quantite_comptee,
            ecart=ecart,
            ecart_pct=_ecart_pct(ecart, ancien_stock),
            ajustement_cree=ajustement_cree,
        ))

    return ComptageResponse(
        nb_lignes=len(payload.lignes),
        nb_ajustements=nb_ajustements,
        message=f"Inventaire traité : {nb_ajustements} ajustements sur {len(payload.lignes)} articles.",
        lignes=lignes,
    )


async def set_seuil_alerte(
    db: AsyncSession,
    tenant_id: int,
    produit_id: int,
    seuil: float,
) -> dict:
    """Met à jour le seuil d'alerte d'un produit."""
    produit_repo = AsyncEpicerieProduitRepository(db)
    stock_repo = AsyncEpicerieStockRepository(db)

    produit = await produit_repo.get_by_id(produit_id, tenant_id)
    if produit is None:
        raise NotFound(f"Produit {produit_id} introuvable")

    stock = await stock_repo.get_or_create(produit_id, tenant_id)
    await stock_repo.set_seuil(stock, seuil)
    return {"stock": stock}
