"""Schemas Pydantic pour le dashboard (KPIs)."""
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
