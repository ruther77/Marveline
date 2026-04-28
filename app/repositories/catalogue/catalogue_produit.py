"""Repository pour CatalogueProduit — référentiel alimentaire partagé (M01).

Table sans tenant_id : catalogue ETL partagé (ADR-01).
Async only : consommé par import_pipeline.py (Celery, ADR-08).

Références :
    §6.1   : schéma SQL validé
    ADR-07 : déduplication Jaro-Winkler — get_by_ean + get_all_candidates
    ADR-08 : pipeline ETL, parsers, Celery
"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue.catalogue_produit import CatalogueProduit
from app.models.catalogue.catalogue_produit_colisage import CatalogueProduitColisage
from app.models.catalogue.catalogue_produit_ean import CatalogueProduitEan


class AsyncCatalogueProduitRepository:
    """Repository async pour le catalogue produits alimentaires.

    Pas de BaseRepository : CatalogueProduit n'a pas de tenant_id ni is_active.
    Pas de delete : le catalogue est un log ETL append-only.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, produit: CatalogueProduit) -> CatalogueProduit:
        """Persiste un nouveau produit catalogue et retourne l'objet avec ID.

        Args:
            produit: Instance CatalogueProduit à créer.

        Returns:
            CatalogueProduit avec id assigné.
        """
        self.db.add(produit)
        await self.db.flush()
        await self.db.refresh(produit)
        return produit

    async def get_by_id(self, produit_id: int) -> Optional[CatalogueProduit]:
        """Récupère un produit par son identifiant.

        Args:
            produit_id: PK du produit.

        Returns:
            CatalogueProduit ou None si introuvable.
        """
        return await self.db.get(CatalogueProduit, produit_id)

    async def get_by_ean(self, ean: str) -> Optional[CatalogueProduit]:
        """Cherche un produit par EAN principal OU secondaire.

        Un produit peut avoir plusieurs EANs (cross-pays, cross-packaging). Cette
        méthode cherche d'abord dans le champ principal (catalogue_produits.ean),
        puis dans la table catalogue_produit_eans (EANs secondaires).

        Args:
            ean: Code EAN-8 ou EAN-13 à rechercher.

        Returns:
            CatalogueProduit ou None si aucun produit avec cet EAN.
        """
        stmt = select(CatalogueProduit).where(CatalogueProduit.ean == ean)
        result = await self.db.execute(stmt)
        found = result.scalar_one_or_none()
        if found is not None:
            return found

        # Fallback : EAN secondaire
        stmt2 = (
            select(CatalogueProduit)
            .join(CatalogueProduitEan, CatalogueProduitEan.catalogue_produit_id == CatalogueProduit.id)
            .where(CatalogueProduitEan.ean == ean)
        )
        result2 = await self.db.execute(stmt2)
        return result2.scalar_one_or_none()

    async def add_secondary_ean(
        self, produit_id: int, ean: str, source_fournisseur: Optional[str] = None,
    ) -> Optional[CatalogueProduitEan]:
        """Ajoute un EAN secondaire à un produit catalogue existant.

        Idempotent : si l'EAN existe déjà (principal ou secondaire), no-op.

        Args:
            produit_id: ID du produit catalogue cible.
            ean: Nouvel EAN à ajouter.
            source_fournisseur: Fournisseur source (METRO, TAIYAT, ...).

        Returns:
            CatalogueProduitEan créé, ou None si déjà présent.
        """
        # Vérifier que l'EAN n'existe pas déjà
        existing = await self.get_by_ean(ean)
        if existing is not None:
            return None
        entry = CatalogueProduitEan(
            catalogue_produit_id=produit_id,
            ean=ean,
            source_fournisseur=source_fournisseur,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def record_colisage(
        self, produit_id: int, colisage: int, source_fournisseur: Optional[str] = None,
    ) -> None:
        """Enregistre un colisage observé pour un produit (upsert).

        Idempotent sur (produit_id, colisage, source_fournisseur) : si déjà vu,
        ne fait que rafraîchir last_seen_at.
        """
        if not colisage or colisage <= 0:
            return
        stmt = pg_insert(CatalogueProduitColisage).values(
            catalogue_produit_id=produit_id,
            colisage=colisage,
            source_fournisseur=source_fournisseur,
        ).on_conflict_do_update(
            constraint='uq_cat_prod_colisage_source',
            set_={'last_seen_at': func.now()},
        )
        await self.db.execute(stmt)

    async def list_colisages(self, produit_id: int) -> list[tuple[int, Optional[str]]]:
        """Retourne les colisages observés pour un produit, triés croissants."""
        stmt = (
            select(CatalogueProduitColisage.colisage, CatalogueProduitColisage.source_fournisseur)
            .where(CatalogueProduitColisage.catalogue_produit_id == produit_id)
            .order_by(CatalogueProduitColisage.colisage.asc())
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def list_eans(self, produit_id: int) -> list[str]:
        """Retourne tous les EANs (principal + secondaires) d'un produit."""
        produit = await self.get_by_id(produit_id)
        eans: list[str] = []
        if produit and produit.ean:
            eans.append(produit.ean)
        stmt = select(CatalogueProduitEan.ean).where(
            CatalogueProduitEan.catalogue_produit_id == produit_id
        )
        result = await self.db.execute(stmt)
        eans.extend(row[0] for row in result.all())
        return eans

    async def get_all_candidates(self) -> list[tuple[int, str]]:
        """Retourne tous les produits avec une désignation normalisée (ADR-07 §2).

        Fournit les candidats au calcul Jaro-Winkler lors d'un import ETL.
        Seuls les produits ayant une designation_norm non nulle sont retournés.

        Returns:
            Liste de (catalogue_produit_id, designation_norm) triée par id ASC.
        """
        stmt = (
            select(CatalogueProduit.id, CatalogueProduit.designation_norm)
            .where(CatalogueProduit.designation_norm.is_not(None))
            .order_by(CatalogueProduit.id.asc())
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def count(self) -> int:
        """Compte le nombre total de produits dans le catalogue.

        Returns:
            Nombre d'entrées dans catalogue_produits.
        """
        stmt = select(func.count()).select_from(CatalogueProduit)
        result = await self.db.execute(stmt)
        return result.scalar() or 0
