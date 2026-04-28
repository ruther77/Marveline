"""Repository pour EtlImport — log technique des imports ETL (M03).

Table sans tenant_id : log opérationnel partagé entre tous les imports.
Async only : consommé uniquement par Celery tasks (ADR-08) et endpoints admin.

Références :
    §6.3   : schéma SQL validé
    ADR-08 : parsers ETL fournisseurs, déclenché via Celery
"""
from typing import Optional

from sqlalchemy import case, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue.etl_import import EtlImport
from app.models.finance.invoice import FinanceInvoice

# Constantes locales (pas de magic string)
_MAX_LIST_LIMIT = 200


class AsyncEtlImportRepository:
    """Repository async pour les logs d'import ETL.

    Pas de BaseRepository : EtlImport n'a pas de tenant_id ni is_active.
    Log append-only — pas de delete, pas de filtre actif.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _visible_for_tenant_clause(tenant_id: int):
        """Retourne la clause de visibilité tenant-aware pour un import ETL.

        `etl_imports` n'a pas de `tenant_id`. Quand une facture finance liée
        existe, son `tenant_id` devient la source de vérité d'accès. Les
        imports legacy sans facture restent visibles à tous les tenants tant
        qu'ils ne portent pas encore leur propre rattachement.
        """
        has_any_invoice = exists(
            select(FinanceInvoice.id).where(
                FinanceInvoice.etl_import_id == EtlImport.id
            )
        )
        has_tenant_invoice = exists(
            select(FinanceInvoice.id).where(
                FinanceInvoice.etl_import_id == EtlImport.id,
                FinanceInvoice.tenant_id == tenant_id,
            )
        )
        return or_(~has_any_invoice, has_tenant_invoice)

    async def create(self, import_obj: EtlImport) -> EtlImport:
        """Persiste un nouvel import en base et retourne l'objet avec ID.

        Args:
            import_obj: Instance EtlImport à créer (statut PENDING par défaut)

        Returns:
            EtlImport avec id assigné
        """
        self.db.add(import_obj)
        await self.db.flush()
        await self.db.refresh(import_obj)
        return import_obj

    async def get_by_id(self, import_id: int) -> Optional[EtlImport]:
        """Récupère un import par son identifiant.

        Args:
            import_id: PK de l'import

        Returns:
            EtlImport ou None si introuvable
        """
        return await self.db.get(EtlImport, import_id)

    async def get_by_id_for_tenant(
        self,
        import_id: int,
        tenant_id: int,
    ) -> Optional[EtlImport]:
        """Récupère un import visible pour un tenant donné.

        Retourne `None` si l'import n'existe pas ou s'il est lié à une facture
        d'un autre tenant. Le caller peut alors répondre `404` pour éviter tout
        info leakage cross-tenant.
        """
        stmt = (
            select(EtlImport)
            .where(EtlImport.id == import_id)
            .where(self._visible_for_tenant_clause(tenant_id))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_statut(
        self,
        import_obj: EtlImport,
        statut: str,
        erreur_detail: Optional[str] = None,
    ) -> EtlImport:
        """Met à jour le statut d'un import (PENDING→RUNNING→SUCCES|PARTIEL|ECHEC).

        Args:
            import_obj: Instance EtlImport à modifier
            statut: Nouveau statut (PENDING|RUNNING|SUCCES|PARTIEL|ECHEC)
            erreur_detail: Détail erreur si statut=ECHEC, None sinon

        Returns:
            EtlImport mis à jour
        """
        import_obj.statut = statut
        if erreur_detail is not None:
            import_obj.erreur_detail = erreur_detail
        await self.db.flush()
        await self.db.refresh(import_obj)
        return import_obj

    async def list_by_statut(
        self,
        statut: str,
        limit: int = 50,
    ) -> list[EtlImport]:
        """Liste les imports filtrés par statut, triés par date de création desc.

        Args:
            statut: Valeur à filtrer (ex: 'PENDING', 'ECHEC')
            limit: Nombre max de résultats (plafonné à _MAX_LIST_LIMIT)

        Returns:
            Liste d'EtlImport triée par created_at DESC
        """
        effective_limit = min(limit, _MAX_LIST_LIMIT)
        stmt = (
            select(EtlImport)
            .where(EtlImport.statut == statut)
            .order_by(EtlImport.created_at.desc())
            .limit(effective_limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_statut(self, statut: str) -> int:
        """Compte les imports d'un statut donné (monitoring ETL).

        Args:
            statut: Statut à compter

        Returns:
            Nombre d'imports avec ce statut
        """
        stmt = select(func.count()).select_from(EtlImport).where(
            EtlImport.statut == statut
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def list_paginated(
        self,
        statut_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EtlImport], int]:
        """Liste paginée des imports avec filtre statut optionnel.

        Args:
            statut_filter: Si non-None, filtre par ce statut exact.
            limit: Nombre max de résultats (plafonné à _MAX_LIST_LIMIT).
            offset: Offset pour pagination.

        Returns:
            Tuple (items, total_count).
        """
        effective_limit = min(limit, _MAX_LIST_LIMIT)
        base = select(EtlImport)
        count_base = select(func.count()).select_from(EtlImport)

        if statut_filter is not None:
            base = base.where(EtlImport.statut == statut_filter)
            count_base = count_base.where(EtlImport.statut == statut_filter)

        count_result = await self.db.execute(count_base)
        total = count_result.scalar() or 0

        stmt = base.order_by(EtlImport.created_at.desc()).offset(offset).limit(effective_limit)
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def list_paginated_for_tenant(
        self,
        tenant_id: int,
        statut_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EtlImport], int]:
        """Liste paginée des imports visibles pour un tenant.

        Les imports liés à une facture d'un autre tenant sont exclus. Les
        imports sans facture restent listés pour compatibilité legacy.
        """
        effective_limit = min(limit, _MAX_LIST_LIMIT)
        visibility = self._visible_for_tenant_clause(tenant_id)
        base = select(EtlImport).where(visibility)
        count_base = select(func.count()).select_from(EtlImport).where(visibility)

        if statut_filter is not None:
            base = base.where(EtlImport.statut == statut_filter)
            count_base = count_base.where(EtlImport.statut == statut_filter)

        count_result = await self.db.execute(count_base)
        total = count_result.scalar() or 0

        if statut_filter is None:
            # Sans filtre : PREVIEW en tête (attente d'action), puis par date desc
            priority = case((EtlImport.statut == "PREVIEW", 0), else_=1)
            order = [priority, EtlImport.created_at.desc()]
        else:
            order = [EtlImport.created_at.desc()]

        stmt = (
            base.order_by(*order)
            .offset(offset)
            .limit(effective_limit)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total
