"""Service Dashboard épicerie — agrégation des KPIs."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.epicerie.vente import EpicerieVente
from app.models.epicerie.supply_order import SupplyOrder
from app.repositories.epicerie.stock import AsyncEpicerieStockRepository
from app.repositories.finance.invoice import AsyncFinanceInvoiceRepository
from app.schemas.epicerie.dashboard import (
    EpicerieDashboard,
    EpicerieKpiVentes,
    EpicerieKpiStock,
    EpicerieKpiAchats,
)

_STATUTS_VENTE_VALIDE = ("VALIDEE",)
_STATUTS_COMMANDE_EN_COURS = ("en_attente", "confirmee", "expediee")


async def get_dashboard(
    db: AsyncSession,
    tenant_id: int,
) -> EpicerieDashboard:
    """Calcule tous les KPIs du dashboard épicerie."""
    kpi_ventes = await _kpi_ventes(db, tenant_id)
    kpi_stock = await _kpi_stock(db, tenant_id)
    kpi_achats = await _kpi_achats(db, tenant_id)

    return EpicerieDashboard(
        ventes=kpi_ventes,
        stock=kpi_stock,
        achats=kpi_achats,
    )


async def _kpi_ventes(db: AsyncSession, tenant_id: int) -> EpicerieKpiVentes:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    ca_jour = await _sum_ventes(db, tenant_id, today_start, now)
    ca_semaine = await _sum_ventes(db, tenant_id, week_start, now)
    ca_mois = await _sum_ventes(db, tenant_id, month_start, now)
    nb_tickets_jour = await _count_ventes(db, tenant_id, today_start, now)

    panier_moyen = (ca_jour // nb_tickets_jour) if nb_tickets_jour > 0 else 0

    return EpicerieKpiVentes(
        ca_jour_cts=ca_jour,
        ca_semaine_cts=ca_semaine,
        ca_mois_cts=ca_mois,
        nb_tickets_jour=nb_tickets_jour,
        panier_moyen_cts=panier_moyen,
    )


async def _kpi_stock(db: AsyncSession, tenant_id: int) -> EpicerieKpiStock:
    stock_repo = AsyncEpicerieStockRepository(db)
    summary = await stock_repo.summary(tenant_id)
    return EpicerieKpiStock(
        total_articles=summary["total_articles"],
        nb_ruptures=summary["nb_ruptures"],
        nb_stock_bas=summary["nb_stock_bas"],
        valeur_stock_cts=summary["valeur_stock_cts"],
    )


async def _kpi_achats(db: AsyncSession, tenant_id: int) -> EpicerieKpiAchats:
    # Commandes en cours
    result = await db.execute(
        select(
            func.count().label("nb"),
            func.coalesce(func.sum(SupplyOrder.montant_ttc), 0).label("total"),
        )
        .where(
            SupplyOrder.tenant_id == tenant_id,
            SupplyOrder.statut.in_(_STATUTS_COMMANDE_EN_COURS),
        )
    )
    row = result.one()
    nb_commandes = row.nb
    montant_commandes = int(row.total)

    # Dette fournisseurs (toutes factures FOURNISSEUR non payées)
    invoice_repo = AsyncFinanceInvoiceRepository(db)
    # Sum des dettes sur tous les vendors de ce tenant
    from app.models.finance.invoice import FinanceInvoice
    dette_result = await db.execute(
        select(func.coalesce(func.sum(FinanceInvoice.montant_ttc), 0)).where(
            FinanceInvoice.tenant_id == tenant_id,
            FinanceInvoice.type == "FOURNISSEUR",
            FinanceInvoice.statut.in_(("EN_ATTENTE", "EN_RETARD")),
        )
    )
    dette = int(dette_result.scalar_one())

    # Livraisons cette semaine
    now = datetime.now(timezone.utc)
    week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = week_start - timedelta(days=week_start.weekday())
    livraisons_result = await db.execute(
        select(func.count()).select_from(SupplyOrder).where(
            SupplyOrder.tenant_id == tenant_id,
            SupplyOrder.statut == "livree",
            SupplyOrder.date_livraison_reelle >= week_start.date(),
        )
    )
    livraisons = livraisons_result.scalar_one() or 0

    return EpicerieKpiAchats(
        commandes_en_cours=nb_commandes,
        montant_commandes_cts=montant_commandes,
        dette_fournisseurs_cts=dette,
        livraisons_semaine=livraisons,
    )


async def _sum_ventes(
    db: AsyncSession,
    tenant_id: int,
    debut: datetime,
    fin: datetime,
) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(EpicerieVente.total_ttc), 0)).where(
            EpicerieVente.tenant_id == tenant_id,
            EpicerieVente.statut.in_(_STATUTS_VENTE_VALIDE),
            EpicerieVente.date_vente >= debut,
            EpicerieVente.date_vente <= fin,
        )
    )
    return int(result.scalar_one())


async def _count_ventes(
    db: AsyncSession,
    tenant_id: int,
    debut: datetime,
    fin: datetime,
) -> int:
    result = await db.execute(
        select(func.count()).select_from(EpicerieVente).where(
            EpicerieVente.tenant_id == tenant_id,
            EpicerieVente.statut.in_(_STATUTS_VENTE_VALIDE),
            EpicerieVente.date_vente >= debut,
            EpicerieVente.date_vente <= fin,
        )
    )
    return result.scalar_one() or 0
