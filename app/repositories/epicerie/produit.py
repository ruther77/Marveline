"""Repository EpicerieProduit — CRUD produits épicerie."""
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.epicerie.produit import EpicerieProduit


class AsyncEpicerieProduitRepository:
    """Repository async pour EpicerieProduit."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, produit_id: int, tenant_id: int) -> Optional[EpicerieProduit]:
        result = await self._db.execute(
            select(EpicerieProduit).where(
                EpicerieProduit.id == produit_id,
                EpicerieProduit.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_ids(
        self, produit_ids: list[int], tenant_id: int
    ) -> dict[int, EpicerieProduit]:
        """Charge plusieurs produits en une seule requête. Retourne {id: produit}."""
        if not produit_ids:
            return {}
        result = await self._db.execute(
            select(EpicerieProduit).where(
                EpicerieProduit.id.in_(produit_ids),
                EpicerieProduit.tenant_id == tenant_id,
            )
        )
        return {p.id: p for p in result.scalars().all()}

    async def get_by_ean(self, ean: str, tenant_id: int) -> Optional[EpicerieProduit]:
        result = await self._db.execute(
            select(EpicerieProduit).where(
                EpicerieProduit.ean == ean,
                EpicerieProduit.tenant_id == tenant_id,
                EpicerieProduit.actif.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        tenant_id: int,
        page: int = 1,
        per_page: int = 20,
        search: Optional[str] = None,
        categorie: Optional[str] = None,
        vendor_id: Optional[int] = None,
        actif_only: bool = True,
    ) -> tuple[list[EpicerieProduit], int]:
        q = select(EpicerieProduit).where(EpicerieProduit.tenant_id == tenant_id)
        if actif_only:
            q = q.where(EpicerieProduit.actif.is_(True))
        if search:
            like = f"%{search}%"
            q = q.where(or_(
                EpicerieProduit.designation_clean.ilike(like),
                EpicerieProduit.nom_court.ilike(like),
                EpicerieProduit.ean.ilike(like),
            ))
        if categorie:
            q = q.where(EpicerieProduit.categorie == categorie)
        if vendor_id is not None:
            q = q.where(EpicerieProduit.vendor_id == vendor_id)

        total_result = await self._db.execute(
            select(func.count()).select_from(q.subquery())
        )
        total = total_result.scalar_one()

        items_result = await self._db.execute(
            q.order_by(EpicerieProduit.designation_clean)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(items_result.scalars().all()), total

    async def create(
        self,
        tenant_id: int,
        designation_clean: str,
        prix_unitaire_cts: int,
        ean: Optional[str] = None,
        nom_court: Optional[str] = None,
        description: Optional[str] = None,
        categorie: Optional[str] = None,
        unite_vente: str = "U",
        taux_tva: int = 2000,
        vendor_id: Optional[int] = None,
    ) -> EpicerieProduit:
        produit = EpicerieProduit(
            tenant_id=tenant_id,
            ean=ean,
            designation_clean=designation_clean,
            nom_court=nom_court,
            description=description,
            categorie=categorie,
            unite_vente=unite_vente,
            prix_unitaire_cts=prix_unitaire_cts,
            taux_tva=taux_tva,
            vendor_id=vendor_id,
            actif=True,
        )
        self._db.add(produit)
        await self._db.flush()
        return produit

    async def update(self, produit: EpicerieProduit, **kwargs) -> EpicerieProduit:
        for key, value in kwargs.items():
            setattr(produit, key, value)
        await self._db.flush()
        return produit

    async def list_without_image(self, tenant_id: int, limit: int = 200) -> list[EpicerieProduit]:
        """Retourne les produits actifs sans image."""
        result = await self._db.execute(
            select(EpicerieProduit).where(
                EpicerieProduit.tenant_id == tenant_id,
                EpicerieProduit.actif.is_(True),
                or_(
                    EpicerieProduit.image_url.is_(None),
                    EpicerieProduit.image_url == "",
                ),
            ).limit(limit)
        )
        return list(result.scalars().all())

    async def list_categories(self, tenant_id: int) -> list[str]:
        """Retourne la liste distincte des catégories actives."""
        result = await self._db.execute(
            select(EpicerieProduit.categorie).distinct().where(
                EpicerieProduit.tenant_id == tenant_id,
                EpicerieProduit.actif.is_(True),
                EpicerieProduit.categorie.isnot(None),
            ).order_by(EpicerieProduit.categorie)
        )
        return [r for r in result.scalars().all() if r]

    # ── Multi-EAN ──────────────────────────────────────────────────────────

    async def get_by_ean_multi(
        self, ean: str, tenant_id: int,
    ) -> Optional[EpicerieProduit]:
        """Lookup par EAN : cherche EpicerieProduit.ean d'abord, puis la table pivot multi-EAN."""
        # Fast path : EAN principal
        produit = await self.get_by_ean(ean, tenant_id)
        if produit is not None:
            return produit
        # Slow path : EAN secondaire (table pivot)
        from app.models.epicerie.produit_ean import EpicerieProduitEan
        result = await self._db.execute(
            select(EpicerieProduit)
            .join(EpicerieProduitEan, EpicerieProduitEan.produit_id == EpicerieProduit.id)
            .where(
                EpicerieProduitEan.ean == ean,
                EpicerieProduitEan.tenant_id == tenant_id,
                EpicerieProduit.actif.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_secondary_eans(
        self, produit_id: int, tenant_id: int,
    ) -> list["EpicerieProduitEan"]:
        """Liste les EANs secondaires d'un produit (table pivot)."""
        from app.models.epicerie.produit_ean import EpicerieProduitEan
        result = await self._db.execute(
            select(EpicerieProduitEan).where(
                EpicerieProduitEan.produit_id == produit_id,
                EpicerieProduitEan.tenant_id == tenant_id,
            ).order_by(EpicerieProduitEan.created_at)
        )
        return list(result.scalars().all())

    async def add_secondary_ean(
        self,
        produit_id: int,
        ean: str,
        tenant_id: int,
        source_fournisseur: Optional[str] = None,
    ) -> "EpicerieProduitEan":
        """Ajoute un EAN secondaire a un produit (idempotent si deja existant)."""
        from app.models.epicerie.produit_ean import EpicerieProduitEan
        # Vérifier si l'EAN existe déjà pour ce tenant
        existing = await self._db.execute(
            select(EpicerieProduitEan).where(
                EpicerieProduitEan.ean == ean,
                EpicerieProduitEan.tenant_id == tenant_id,
            )
        )
        found = existing.scalar_one_or_none()
        if found is not None:
            return found
        entry = EpicerieProduitEan(
            produit_id=produit_id,
            ean=ean,
            tenant_id=tenant_id,
            source_fournisseur=source_fournisseur,
        )
        self._db.add(entry)
        await self._db.flush()
        return entry
