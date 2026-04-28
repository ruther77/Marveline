"""Schemas Pydantic pour le dashboard (KPIs)."""
from typing import List, Optional
from datetime import date as Date
from pydantic import Field
from app.schemas.base import BaseSchema


class DashboardStats(BaseSchema):
    """KPIs agrégés par tenant pour le tableau de bord."""

    # Reservations
    active_reservations: int = Field(
        ..., description="Réservations actives (confirmed + delivered)"
    )
    draft_reservations: int = Field(
        ..., description="Réservations en brouillon"
    )

    # Chiffre d'affaires du mois en cours (centimes)
    monthly_revenue_cents: int = Field(
        ..., description="CA du mois en cours (centimes), basé sur réservations confirmed+"
    )

    # Factures
    overdue_invoices: int = Field(
        ..., description="Nombre de factures en retard"
    )
    overdue_amount_cents: int = Field(
        ..., description="Montant total des factures en retard (centimes)"
    )
    unpaid_invoices: int = Field(
        ..., description="Nombre de factures envoyées non payées"
    )

    # Mouvements
    late_movements: int = Field(
        ..., description="Mouvements de stock en retard"
    )
    scheduled_departures: int = Field(
        ..., description="Départs programmés (scheduled)"
    )
    scheduled_returns: int = Field(
        ..., description="Retours programmés (scheduled)"
    )

    # Stock
    low_stock_products: int = Field(
        ..., description="Produits avec stock disponible < 5"
    )
    total_products: int = Field(
        ..., description="Nombre total de produits actifs"
    )


class UrgentAlertItem(BaseSchema):
    """Alerte urgente : retour à contrôler (1 seule, la plus critique)."""

    reservation_id: int
    reference: str
    customer_name: str
    return_date: Date


class TodayCard(BaseSchema):
    """Carte planning du jour (départ ou retour)."""

    reservation_id: int
    reference: str
    customer_name: str
    hour: Optional[str] = None
    articles_count: int
    deposit_paid: bool
    kind: str = Field(..., description="'departure' ou 'return'")


class TodayPlanning(BaseSchema):
    """Planning du jour : départs + retours."""

    departures: List[TodayCard]
    returns: List[TodayCard]


class ActivityItem(BaseSchema):
    """Élément du feed d'activité récente."""

    kind: str = Field(
        ...,
        description=(
            "Type : 'return_checked', 'invoice_paid', 'deposit_received', "
            "'quote_sent', 'low_stock', 'reservation_created'"
        ),
    )
    label: str
    sub_label: Optional[str] = None
    link: Optional[str] = None
    created_at: str = Field(..., description="ISO datetime")


class ActivityFeed(BaseSchema):
    """Feed activité récente (5 derniers événements cross-domaines)."""

    items: List[ActivityItem]


class FinancesMonthly(BaseSchema):
    """Données financières agrégées pour un mois donné."""

    month: int = Field(..., description="Numéro du mois (1-12)")
    revenue_cents: int = Field(..., description="CA encaissé dans le mois (centimes)")
    invoices_paid: int = Field(..., description="Nombre de factures payées dans le mois")
    invoices_overdue: int = Field(..., description="Nombre de factures passées en retard ce mois")


class FinancesTotals(BaseSchema):
    """Totaux annuels et KPIs globaux."""

    revenue_ytd_cents: int = Field(..., description="CA encaissé depuis le 1er janvier (centimes)")
    overdue_amount_cents: int = Field(..., description="Montant total factures en retard (centimes)")
    active_reservations: int = Field(..., description="Réservations actives (confirmed + delivered)")
    low_stock_products: int = Field(..., description="Produits avec stock faible")


class FinancesStats(BaseSchema):
    """Statistiques financières annuelles par mois."""

    year: int = Field(..., description="Année des données")
    monthly: List[FinancesMonthly] = Field(..., description="Données par mois (12 entrées)")
    totals: FinancesTotals = Field(..., description="Totaux et KPIs globaux")


# ── KPIs analytics ────────────────────────────────────────────────────────────


class TopProductItem(BaseSchema):
    """Produit du classement par fréquence de location."""

    product_id: int
    product_name: str
    category: Optional[str] = None
    rental_count: int = Field(..., description="Nombre de locations (lignes de réservation)")
    total_quantity: int = Field(..., description="Quantité totale louée")
    revenue_cents: int = Field(..., description="CA généré (centimes)")


class SeasonalityMonthly(BaseSchema):
    """Données mensuelles pour une année donnée (saisonnalité)."""

    year: int
    month: int
    revenue_cents: int
    reservation_count: int


class AnalyticsKpis(BaseSchema):
    """KPIs analytiques avancés : panier moyen, taux utilisation, top produits."""

    # Panier moyen
    avg_basket_cents: int = Field(..., description="Panier moyen par réservation (centimes)")
    total_reservations: int = Field(..., description="Nb réservations dans la période")
    total_revenue_cents: int = Field(..., description="CA total de la période (centimes)")

    # Taux d'utilisation
    utilization_rate: float = Field(..., description="Taux d'utilisation global du parc (%)")
    total_stock: int = Field(..., description="Stock total (unités)")
    total_rented: int = Field(..., description="Unités en location")

    # Top produits
    top_products: List[TopProductItem] = Field(
        default_factory=list,
        description="Top 10 produits par fréquence de location",
    )

    # Saisonnalité
    monthly_revenue: List[SeasonalityMonthly] = Field(
        default_factory=list,
        description="CA mensuel multi-années pour analyse saisonnalité",
    )
    seasonality_years: List[int] = Field(
        default_factory=list,
        description="Années incluses dans les données saisonnalité",
    )
