"""Repository FinanceInvoice — CRUD factures finance."""
from datetime import date
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance.invoice import FinanceInvoice

# Statuts comptabilisant une dette active
STATUTS_DETTE = ('EN_ATTENTE', 'EN_RETARD')


class AsyncFinanceInvoiceRepository:
    """Repository async pour FinanceInvoice."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, invoice_id: int, tenant_id: int) -> Optional[FinanceInvoice]:
        result = await self._db.execute(
            select(FinanceInvoice).where(
                FinanceInvoice.id == invoice_id,
                FinanceInvoice.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_numero(self, numero: str, tenant_id: int) -> Optional[FinanceInvoice]:
        result = await self._db.execute(
            select(FinanceInvoice).where(
                FinanceInvoice.numero == numero,
                FinanceInvoice.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def next_sequence_today(self, tenant_id: int) -> int:
        """Retourne le prochain numéro séquentiel journalier (1-based)."""
        today = date.today()
        prefix = f"FAC-{today.strftime('%Y%m%d')}-"
        result = await self._db.execute(
            select(func.count()).select_from(FinanceInvoice).where(
                FinanceInvoice.tenant_id == tenant_id,
                FinanceInvoice.numero.like(f"{prefix}%"),
            )
        )
        return (result.scalar_one() or 0) + 1

    async def generate_numero(self, tenant_id: int) -> str:
        seq = await self.next_sequence_today(tenant_id)
        today = date.today()
        return f"FAC-{today.strftime('%Y%m%d')}-{seq:04d}"

    async def list_by_vendor(
        self,
        vendor_id: int,
        tenant_id: int,
        limit: int = 50,
    ) -> list[FinanceInvoice]:
        result = await self._db.execute(
            select(FinanceInvoice).where(
                FinanceInvoice.vendor_id == vendor_id,
                FinanceInvoice.tenant_id == tenant_id,
            ).order_by(FinanceInvoice.date_facture.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def sum_dette(self, vendor_id: int, tenant_id: int) -> int:
        """Somme des montants TTC des factures EN_ATTENTE et EN_RETARD pour un fournisseur."""
        result = await self._db.execute(
            select(func.coalesce(func.sum(FinanceInvoice.montant_ttc), 0)).where(
                FinanceInvoice.vendor_id == vendor_id,
                FinanceInvoice.tenant_id == tenant_id,
                FinanceInvoice.statut.in_(STATUTS_DETTE),
            )
        )
        return result.scalar_one()

    async def has_retard(self, vendor_id: int, tenant_id: int) -> bool:
        """Vrai si au moins une facture est EN_RETARD pour ce fournisseur."""
        result = await self._db.execute(
            select(func.count()).select_from(FinanceInvoice).where(
                FinanceInvoice.vendor_id == vendor_id,
                FinanceInvoice.tenant_id == tenant_id,
                FinanceInvoice.statut == "EN_RETARD",
            )
        )
        return (result.scalar_one() or 0) > 0

    async def sum_achats_mois(self, vendor_id: int, tenant_id: int) -> int:
        """Somme TTC de toutes les factures du mois courant pour ce fournisseur."""
        today = date.today()
        debut_mois = today.replace(day=1)
        result = await self._db.execute(
            select(func.coalesce(func.sum(FinanceInvoice.montant_ttc), 0)).where(
                FinanceInvoice.vendor_id == vendor_id,
                FinanceInvoice.tenant_id == tenant_id,
                FinanceInvoice.date_facture >= debut_mois,
            )
        )
        return result.scalar_one()

    async def create(
        self,
        tenant_id: int,
        type: str,
        date_facture: date,
        montant_ht: int = 0,
        montant_tva: int = 0,
        montant_ttc: int = 0,
        date_echeance: Optional[date] = None,
        vendor_id: Optional[int] = None,
        supply_order_id: Optional[int] = None,
        vente_id: Optional[int] = None,
        transfer_id: Optional[int] = None,
        reference: Optional[str] = None,
        etl_import_id: Optional[int] = None,
    ) -> FinanceInvoice:
        numero = await self.generate_numero(tenant_id)
        invoice = FinanceInvoice(
            tenant_id=tenant_id,
            type=type,
            numero=numero,
            date_facture=date_facture,
            date_echeance=date_echeance,
            montant_ht=montant_ht,
            montant_tva=montant_tva,
            montant_ttc=montant_ttc,
            statut="EN_ATTENTE",
            vendor_id=vendor_id,
            supply_order_id=supply_order_id,
            vente_id=vente_id,
            transfer_id=transfer_id,
            reference=reference,
            etl_import_id=etl_import_id,
        )
        self._db.add(invoice)
        await self._db.flush()
        return invoice

    async def get_by_etl_import_id(self, etl_import_id: int) -> Optional[FinanceInvoice]:
        """Récupère la facture ACTIVE (dernière non-ANNULEE) liée à un import ETL.

        Un import peut avoir plusieurs factures si le cycle reopen/revalidate
        a été joué : 1 ANNULEE (revert) + 1 nouvelle EN_ATTENTE. Cette méthode
        retourne la plus récente qui N'EST PAS annulée. Si toutes sont
        annulées (cas extrême : import reverté puis pas encore ré-validé),
        retourne la plus récente annulée en fallback.
        """
        result = await self._db.execute(
            select(FinanceInvoice)
            .where(
                FinanceInvoice.etl_import_id == etl_import_id,
                FinanceInvoice.statut != "ANNULEE",
            )
            .order_by(FinanceInvoice.created_at.desc())
            .limit(1)
        )
        active = result.scalar_one_or_none()
        if active is not None:
            return active
        # Fallback : toutes les factures sont ANNULEE → retourne la plus récente
        result = await self._db.execute(
            select(FinanceInvoice)
            .where(FinanceInvoice.etl_import_id == etl_import_id)
            .order_by(FinanceInvoice.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def ca_par_mois(
        self,
        vendor_id: int,
        tenant_id: int,
        nb_mois: int = 6,
    ) -> list[tuple[str, int]]:
        """CA mensuel TTC sur les nb_mois derniers (inclut le mois courant), trié chronologiquement."""
        today = date.today()
        m = today.month - (nb_mois - 1)
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        debut = date(y, m, 1)
        mois_label = func.to_char(FinanceInvoice.date_facture, 'YYYY-MM')
        result = await self._db.execute(
            select(
                mois_label.label('mois'),
                func.coalesce(func.sum(FinanceInvoice.montant_ttc), 0).label('total'),
            ).where(
                FinanceInvoice.vendor_id == vendor_id,
                FinanceInvoice.tenant_id == tenant_id,
                FinanceInvoice.date_facture >= debut,
            ).group_by(mois_label).order_by(mois_label)
        )
        return [(row.mois, int(row.total)) for row in result.all()]

    async def count_all_by_vendor(self, vendor_id: int, tenant_id: int) -> int:
        """Nombre total de factures pour un fournisseur (toutes statuts)."""
        result = await self._db.execute(
            select(func.count()).select_from(FinanceInvoice).where(
                FinanceInvoice.vendor_id == vendor_id,
                FinanceInvoice.tenant_id == tenant_id,
            )
        )
        return result.scalar_one()

    async def count_retard_by_vendor(self, vendor_id: int, tenant_id: int) -> int:
        """Nombre de factures EN_RETARD pour un fournisseur."""
        result = await self._db.execute(
            select(func.count()).select_from(FinanceInvoice).where(
                FinanceInvoice.vendor_id == vendor_id,
                FinanceInvoice.tenant_id == tenant_id,
                FinanceInvoice.statut == "EN_RETARD",
            )
        )
        return result.scalar_one()

    async def update_statut(self, invoice: FinanceInvoice, statut: str) -> FinanceInvoice:
        invoice.statut = statut
        await self._db.flush()
        return invoice
