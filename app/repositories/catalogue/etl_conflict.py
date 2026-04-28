"""Repository pour EtlConflict — log déduplication Jaro-Winkler (M04).

Table sans tenant_id : log de déduplication partagé entre tous les imports.
Async only : consommé par le pipeline ETL (Celery, ADR-08) et le tableau
de bord résolution opérateur.

Références :
    §6.4   : schéma SQL validé
    ADR-07 : déduplication Jaro-Winkler, seuils ETL_SEUIL_MATCH / CONFLIT
    ADR-15 : etl_import_id nullable (SET NULL si import supprimé)
"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue.etl_conflict import EtlConflict

# Constantes locales
_MAX_LIST_LIMIT = 500
_RESOLUTION_PENDING = "PENDING"


class AsyncEtlConflictRepository:
    """Repository async pour les conflits de déduplication ETL.

    Pas de BaseRepository : EtlConflict n'a pas de tenant_id ni is_active.
    Log append-only — pas de delete. La résolution se fait via `resolve()`.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, conflict_obj: EtlConflict) -> EtlConflict:
        """Persiste un nouveau conflit de déduplication.

        Args:
            conflict_obj: Instance EtlConflict à créer

        Returns:
            EtlConflict avec id assigné
        """
        self.db.add(conflict_obj)
        await self.db.flush()
        await self.db.refresh(conflict_obj)
        return conflict_obj

    async def create_many(
        self, conflicts: list[EtlConflict]
    ) -> list[EtlConflict]:
        """Persiste plusieurs conflits en une seule opération (batch ETL).

        Args:
            conflicts: Liste d'instances EtlConflict à créer

        Returns:
            Liste d'EtlConflict avec ids assignés
        """
        for conflict in conflicts:
            self.db.add(conflict)
        await self.db.flush()
        for conflict in conflicts:
            await self.db.refresh(conflict)
        return conflicts

    async def get_by_id(self, conflict_id: int) -> Optional[EtlConflict]:
        """Récupère un conflit par son identifiant.

        Args:
            conflict_id: PK du conflit

        Returns:
            EtlConflict ou None si introuvable
        """
        return await self.db.get(EtlConflict, conflict_id)

    async def list_pending(self, limit: int = 100) -> list[EtlConflict]:
        """Liste les conflits en attente de résolution (tableau de bord opérateur).

        Triés par score de similarité décroissant pour prioriser les cas
        les plus ambigus.

        Args:
            limit: Nombre max de résultats (plafonné à _MAX_LIST_LIMIT)

        Returns:
            Liste d'EtlConflict PENDING triée par score DESC
        """
        effective_limit = min(limit, _MAX_LIST_LIMIT)
        stmt = (
            select(EtlConflict)
            .where(EtlConflict.resolution == _RESOLUTION_PENDING)
            .order_by(EtlConflict.score_similarite.desc().nulls_last())
            .limit(effective_limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_import(
        self,
        import_id: int,
        resolution: Optional[str] = None,
    ) -> list[EtlConflict]:
        """Liste les conflits liés à un import ETL, avec filtre résolution optionnel.

        Args:
            import_id: ID de l'import (etl_import_id)
            resolution: Filtre sur la résolution (None = tous)

        Returns:
            Liste d'EtlConflict triée par created_at ASC
        """
        stmt = (
            select(EtlConflict)
            .where(EtlConflict.etl_import_id == import_id)
            .order_by(EtlConflict.created_at.asc())
        )
        if resolution is not None:
            stmt = stmt.where(EtlConflict.resolution == resolution)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def resolve(
        self, conflict_obj: EtlConflict, resolution: str
    ) -> EtlConflict:
        """Résout un conflit (PENDING → MERGED | KEPT_SEPARATE).

        Args:
            conflict_obj: Instance EtlConflict à résoudre
            resolution: Nouvelle résolution (MERGED | KEPT_SEPARATE)

        Returns:
            EtlConflict mis à jour
        """
        conflict_obj.resolution = resolution
        await self.db.flush()
        await self.db.refresh(conflict_obj)
        return conflict_obj

    async def list_all(
        self,
        filter_resolution: Optional[str] = None,
        import_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[EtlConflict], int]:
        """Liste tous les conflits avec filtre optionnel sur la résolution.

        Args:
            filter_resolution: "PENDING" | "resolved" (MERGED + KEPT_SEPARATE) | None = tous
            import_id: Filtre par import ETL spécifique
            limit: Nombre max de résultats
            offset: Décalage pour la pagination

        Returns:
            (liste de conflits, total correspondant aux filtres)
        """
        stmt = select(EtlConflict)
        if filter_resolution == _RESOLUTION_PENDING:
            stmt = stmt.where(EtlConflict.resolution == _RESOLUTION_PENDING)
        elif filter_resolution == "resolved":
            stmt = stmt.where(EtlConflict.resolution != _RESOLUTION_PENDING)
        if import_id is not None:
            stmt = stmt.where(EtlConflict.etl_import_id == import_id)

        total = (await self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()

        rows = (await self.db.execute(
            stmt.order_by(EtlConflict.created_at.desc()).offset(offset).limit(limit)
        )).scalars().all()

        return list(rows), total

    async def count_stats(self) -> dict[str, int]:
        """Agrège les compteurs par résolution et par type pour la barre de KPIs."""
        rows = (await self.db.execute(
            select(EtlConflict.resolution, func.count())
            .group_by(EtlConflict.resolution)
        )).all()
        by_res = {row[0]: row[1] for row in rows}

        type_rows = (await self.db.execute(
            select(EtlConflict.type_conflit, func.count())
            .group_by(EtlConflict.type_conflit)
        )).all()
        by_type = {(row[0] or "INCONNU"): row[1] for row in type_rows}

        total = sum(by_res.values())
        return {
            "total": total,
            "pending": by_res.get(_RESOLUTION_PENDING, 0),
            "merged": by_res.get("MERGED", 0),
            "kept_separate": by_res.get("KEPT_SEPARATE", 0),
            "by_type": by_type,
        }

    async def resolve_many(self, ids: list[int], resolution: str) -> int:
        """Résout plusieurs conflits en une fois (action groupée opérateur).

        Args:
            ids: Liste de PKs de conflits PENDING à résoudre
            resolution: MERGED | KEPT_SEPARATE

        Returns:
            Nombre de conflits effectivement résolus
        """
        resolved_count = 0
        for conflict_id in ids:
            conflict = await self.get_by_id(conflict_id)
            if conflict is not None and conflict.resolution == _RESOLUTION_PENDING:
                conflict.resolution = resolution
                resolved_count += 1
        if resolved_count:
            await self.db.flush()
        return resolved_count

    async def get_existing_pending(
        self,
        designation_entrante: str,
        catalogue_produit_id: Optional[int],
    ) -> Optional[EtlConflict]:
        """Retourne un conflit PENDING identique s'il existe déjà (anti-doublon).

        Args:
            designation_entrante: Désignation de la ligne entrante
            catalogue_produit_id: ID du produit catalogue candidat (peut être None)

        Returns:
            EtlConflict PENDING existant, ou None si absent
        """
        stmt = (
            select(EtlConflict)
            .where(
                EtlConflict.resolution == _RESOLUTION_PENDING,
                EtlConflict.designation_entrante == designation_entrante,
                EtlConflict.catalogue_produit_id == catalogue_produit_id,
            )
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def count_pending_by_import(self, import_id: int) -> int:
        """Compte les conflits PENDING d'un import (indicateur PARTIEL).

        Args:
            import_id: ID de l'import

        Returns:
            Nombre de conflits non résolus pour cet import
        """
        stmt = (
            select(func.count())
            .select_from(EtlConflict)
            .where(
                EtlConflict.etl_import_id == import_id,
                EtlConflict.resolution == _RESOLUTION_PENDING,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0
