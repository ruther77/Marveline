"""Endpoints admin — Tableau de bord résolution conflits ETL.

Références :
    ADR-07 : déduplication Soft TF-IDF, plage alerte [0.75, 0.85[
    ADR-15 : etl_import_id nullable (SET NULL si import supprimé)
    §6.4   : schéma SQL etl_conflicts

Résolution MERGED :
  - Le catalogue_produit entrant reçoit merged_into_id vers le produit existant
  - Si EAN différents : EAN secondaire ajouté au produit épicerie existant (multi-EAN)

Auth : SETTINGS_READ (lecture) / SETTINGS_WRITE (résolution) — scope admin standard.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope
from app.core.permissions import Scope
from app.models.catalogue.catalogue_produit import CatalogueProduit
from app.repositories.catalogue.etl_conflict import AsyncEtlConflictRepository
from app.repositories.catalogue.etl_import import AsyncEtlImportRepository
from app.repositories.epicerie.produit import AsyncEpicerieProduitRepository
from app.schemas.catalogue.etl_conflict import (
    EtlConflictListResponse,
    EtlConflictRead,
    EtlConflictResolveRequest,
    EtlConflictResolveResponse,
    EtlConflictStats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/etl", tags=["Admin — ETL Conflits"])

_VALID_RESOLUTIONS = {"MERGED", "KEPT_SEPARATE"}
_VALID_FILTERS = {"all", "pending", "resolved"}
_STATUT_PREVIEW = "PREVIEW"
_STATUT_PARTIEL = "PARTIEL"
_STATUT_SUCCES = "SUCCES"


def _is_facture_import(import_obj) -> bool:
    return any((
        bool(import_obj.numero_facture),
        import_obj.date_facture is not None,
        import_obj.montant_ht_total is not None,
        import_obj.montant_ttc_total is not None,
        bool(import_obj.fichier_path),
    ))


async def _sync_parent_import_after_resolution(
    import_id: int,
    conflict_repo: AsyncEtlConflictRepository,
    import_repo: AsyncEtlImportRepository,
) -> bool:
    import_obj = await import_repo.get_by_id(import_id)
    if import_obj is None:
        return False

    pending = await conflict_repo.count_pending_by_import(import_id)
    total = import_obj.nb_lignes_total
    if total is None:
        total = len(import_obj.lignes_data or [])
        import_obj.nb_lignes_total = total

    errors = import_obj.nb_lignes_erreur or 0
    import_obj.nb_lignes_conflit = pending
    import_obj.nb_lignes_ok = max(total - errors - pending, 0)

    if pending == 0:
        import_obj.validation_step = None
        if _is_facture_import(import_obj):
            import_obj.statut = _STATUT_PREVIEW
        else:
            import_obj.statut = _STATUT_SUCCES if errors == 0 else _STATUT_PARTIEL

    return pending == 0


@router.get("/conflicts", response_model=EtlConflictListResponse)
async def list_conflicts(
    filter: Optional[str] = Query(default="all", description="all | pending | resolved"),
    import_id: Optional[int] = Query(default=None, description="Filtrer par import ETL"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_db),
    _=Depends(require_scope(Scope.SETTINGS_READ)),
):
    """Liste les conflits ETL avec filtre par état de résolution et/ou import."""
    if filter not in _VALID_FILTERS:
        raise HTTPException(status_code=422, detail=f"filter doit être dans {_VALID_FILTERS}")

    repo = AsyncEtlConflictRepository(db)
    resolution_filter = filter if filter != "all" else None
    if resolution_filter == "pending":
        resolution_filter = "PENDING"

    items, total = await repo.list_all(
        filter_resolution=resolution_filter,
        import_id=import_id,
        limit=limit,
        offset=offset,
    )
    return EtlConflictListResponse(
        items=[EtlConflictRead.model_validate(c) for c in items],
        total=total,
    )


@router.get("/conflicts/stats", response_model=EtlConflictStats)
async def get_conflict_stats(
    db: AsyncSession = Depends(get_async_db),
    _=Depends(require_scope(Scope.SETTINGS_READ)),
):
    """Agrégats pour la barre de KPIs du tableau de bord."""
    repo = AsyncEtlConflictRepository(db)
    counts = await repo.count_stats()
    return EtlConflictStats(**counts)


@router.post("/conflicts/resolve", response_model=EtlConflictResolveResponse)
async def resolve_conflicts(
    payload: EtlConflictResolveRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Résout plusieurs conflits ETL — MERGED fusionne les produits, KEPT_SEPARATE les sépare."""
    if payload.resolution not in _VALID_RESOLUTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"resolution doit être dans {_VALID_RESOLUTIONS}",
        )
    repo = AsyncEtlConflictRepository(db)
    import_repo = AsyncEtlImportRepository(db)
    produit_repo = AsyncEpicerieProduitRepository(db)

    epicerie_tenant_id = current_user.tenant_id
    affected_import_ids: set[int] = set()

    # Appliquer les effets de bord pour chaque conflit MERGED
    for conflict_id in payload.ids:
        conflict = await repo.get_by_id(conflict_id)
        if conflict is None:
            continue
        if conflict.etl_import_id:
            affected_import_ids.add(conflict.etl_import_id)
        if payload.resolution != "MERGED" or conflict.resolution != "PENDING":
            continue

        # Trouver le catalogue_produit entrant via ean_a + etl_import_id
        incoming = None
        if conflict.ean_a and conflict.etl_import_id:
            result = await db.execute(
                select(CatalogueProduit).where(
                    CatalogueProduit.ean == conflict.ean_a,
                ).limit(1)
            )
            incoming = result.scalar_one_or_none()

        if incoming is None and conflict.designation_entrante:
            # Fallback : chercher par designation exacte
            result = await db.execute(
                select(CatalogueProduit).where(
                    CatalogueProduit.designation == conflict.designation_entrante,
                ).limit(1)
            )
            incoming = result.scalar_one_or_none()

        if incoming is not None and conflict.catalogue_produit_id:
            # Marquer le produit entrant comme fusionné
            incoming.merged_into_id = conflict.catalogue_produit_id
            await db.flush()

            # Si EAN différents : ajouter l'EAN entrant comme alias
            if (
                conflict.ean_a
                and conflict.ean_b
                and conflict.ean_a != conflict.ean_b
            ):
                # Trouver le produit épicerie cible (celui qui existe déjà)
                target_produit = await produit_repo.get_by_ean(
                    conflict.ean_b, epicerie_tenant_id,
                )
                if target_produit is not None:
                    await produit_repo.add_secondary_ean(
                        produit_id=target_produit.id,
                        ean=conflict.ean_a,
                        tenant_id=epicerie_tenant_id,
                        source_fournisseur=incoming.source_fournisseur,
                    )
                    logger.info(
                        "Conflit %d MERGED : EAN %s ajouté comme alias de produit %d",
                        conflict_id, conflict.ean_a, target_produit.id,
                    )

    # Résoudre en batch (met à jour le statut)
    resolved = await repo.resolve_many(payload.ids, payload.resolution)

    # Recalculer l'import parent pour refléter les conflits encore ouverts.
    all_resolved = False
    etl_import_id = None
    if resolved > 0 and affected_import_ids:
        for affected_import_id in affected_import_ids:
            import_all_resolved = await _sync_parent_import_after_resolution(
                affected_import_id,
                repo,
                import_repo,
            )
            if etl_import_id is None:
                etl_import_id = affected_import_id
                all_resolved = import_all_resolved

    await db.commit()
    return EtlConflictResolveResponse(
        resolved=resolved,
        all_resolved=all_resolved,
        etl_import_id=etl_import_id,
    )
