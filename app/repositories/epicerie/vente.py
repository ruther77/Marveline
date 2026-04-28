"""Repository EpicerieVente + EpicerieVenteLigne."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.epicerie.vente import EpicerieVente, EpicerieVenteLigne


class AsyncEpicerieVenteRepository:
    """Repository async pour EpicerieVente et EpicerieVenteLigne."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, vente_id: int, tenant_id: int) -> Optional[EpicerieVente]:
        result = await self._db.execute(
            select(EpicerieVente).where(
                EpicerieVente.id == vente_id,
                EpicerieVente.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_numero(self, numero: str, tenant_id: int) -> Optional[EpicerieVente]:
        result = await self._db.execute(
            select(EpicerieVente).where(
                EpicerieVente.numero_ticket == numero,
                EpicerieVente.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def next_sequence_today(self, tenant_id: int) -> int:
        """Retourne le prochain numéro séquentiel journalier."""
        today = date.today()
        prefix = f"VTE-{today.strftime('%Y%m%d')}-"
        result = await self._db.execute(
            select(func.count()).select_from(EpicerieVente).where(
                EpicerieVente.tenant_id == tenant_id,
                EpicerieVente.numero_ticket.like(f"{prefix}%"),
            )
        )
        return (result.scalar_one() or 0) + 1

    async def generate_numero_ticket(self, tenant_id: int) -> str:
        seq = await self.next_sequence_today(tenant_id)
        today = date.today()
        return f"VTE-{today.strftime('%Y%m%d')}-{seq:04d}"

    async def list_paginated(
        self,
        tenant_id: int,
        limit: int = 25,
        offset: int = 0,
        statut: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[tuple[EpicerieVente, int]], int]:
        """Retourne (vente, nb_articles) pour l'historique. Pas de N+1 : nb_articles
        est calculé via sous-requête corrélée dans la même requête SQL."""
        filters = [EpicerieVente.tenant_id == tenant_id]
        if statut:
            filters.append(EpicerieVente.statut == statut)
        if search:
            term = f"%{search}%"
            filters.append(or_(
                EpicerieVente.numero_ticket.ilike(term),
                EpicerieVente.client_nom.ilike(term),
            ))

        total = (await self._db.execute(
            select(func.count()).select_from(EpicerieVente).where(*filters)
        )).scalar_one()

        nb_lignes_sq = (
            select(func.count(EpicerieVenteLigne.id))
            .where(EpicerieVenteLigne.vente_id == EpicerieVente.id)
            .correlate(EpicerieVente)
            .scalar_subquery()
        )

        rows = (await self._db.execute(
            select(EpicerieVente, nb_lignes_sq.label("nb_articles"))
            .where(*filters)
            .order_by(EpicerieVente.date_vente.desc())
            .offset(offset)
            .limit(limit)
        )).all()

        return [(row[0], row[1]) for row in rows], total

    async def counts_by_statut(self, tenant_id: int) -> dict[str, int]:
        """Compte les ventes par statut pour les badges de tabs."""
        rows = (await self._db.execute(
            select(EpicerieVente.statut, func.count())
            .where(EpicerieVente.tenant_id == tenant_id)
            .group_by(EpicerieVente.statut)
        )).all()
        return {row[0]: row[1] for row in rows}

    async def create_vente(
        self,
        tenant_id: int,
        date_vente: datetime,
        mode_paiement: str,
        total_ht: int,
        total_tva: int,
        total_ttc: int,
        remise_pct: float = 0,
        remise_montant: int = 0,
        montant_especes: int = 0,
        montant_cb: int = 0,
        montant_rendu: int = 0,
        client_nom: Optional[str] = None,
        client_email: Optional[str] = None,
        vendeur_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> EpicerieVente:
        numero = await self.generate_numero_ticket(tenant_id)
        vente = EpicerieVente(
            tenant_id=tenant_id,
            numero_ticket=numero,
            date_vente=date_vente,
            statut="EN_COURS",
            mode_paiement=mode_paiement,
            total_ht=total_ht,
            total_tva=total_tva,
            total_ttc=total_ttc,
            remise_pct=remise_pct,
            remise_montant=remise_montant,
            montant_especes=montant_especes,
            montant_cb=montant_cb,
            montant_rendu=montant_rendu,
            client_nom=client_nom,
            client_email=client_email,
            vendeur_id=vendeur_id,
            notes=notes,
        )
        self._db.add(vente)
        await self._db.flush()
        return vente

    async def create_ligne(
        self,
        tenant_id: int,
        vente_id: int,
        produit_id: int,
        quantite: float,
        prix_unitaire_ht: int,
        taux_tva: int,
        montant_ht: int,
        montant_tva: int,
        montant_ttc: int,
        remise_pct: float = 0,
    ) -> EpicerieVenteLigne:
        ligne = EpicerieVenteLigne(
            tenant_id=tenant_id,
            vente_id=vente_id,
            produit_id=produit_id,
            quantite=quantite,
            prix_unitaire_ht=prix_unitaire_ht,
            taux_tva=taux_tva,
            montant_ht=montant_ht,
            montant_tva=montant_tva,
            montant_ttc=montant_ttc,
            remise_pct=remise_pct,
        )
        self._db.add(ligne)
        await self._db.flush()
        return ligne

    async def list_lignes(self, vente_id: int) -> list[EpicerieVenteLigne]:
        result = await self._db.execute(
            select(EpicerieVenteLigne)
            .where(EpicerieVenteLigne.vente_id == vente_id)
            .order_by(EpicerieVenteLigne.id)
        )
        return list(result.scalars().all())

    async def update_statut(
        self, vente: EpicerieVente, statut: str, invoice_id: Optional[int] = None
    ) -> EpicerieVente:
        vente.statut = statut
        if invoice_id is not None:
            vente.invoice_id = invoice_id
        await self._db.flush()
        return vente
