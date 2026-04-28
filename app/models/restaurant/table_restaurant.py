"""Modèle TableRestaurant — Plan de salle du restaurant (tenant_id=3).

Le statut de la table est CALCULÉ côté service (pas stocké) :
  - LIBRE   : aucune commande en statut OUVERTE liée à cette table
  - OCCUPEE : commande OUVERTE avec ≥ 1 ligne non SERVIE
  - SERVIE  : tous les plats de la commande ouverte sont SERVIS

Références :
    V2_API_RESTAURANT.md §Page: Salle — Commandes
    FC_RESTAURANT_COMMANDES.md §2 (statut calculé)
"""
from sqlalchemy import BigInteger, CheckConstraint, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


class TableRestaurant(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """Table physique du restaurant.

    is_active=False → table retirée du plan de salle (ex: réservée pour
    travaux), non affichée dans l'UI.
    Le champ `numero` est affiché aux serveurs (ex: "5", "Terrasse 2").
    """

    __tablename__ = "restaurant_tables"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    numero: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Numéro ou nom affiché de la table. Ex: '5', 'Terrasse 2'"
    )
    capacite: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Nombre maximum de couverts"
    )
    # is_active hérite de SoftDeleteMixin (table active dans le plan de salle)
    # tenant_id hérite de TenantMixin (= 3 pour restaurant)
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint("capacite >= 1", name="check_table_resto_capacite_positive"),
        Index("idx_restaurant_tables_tenant", "tenant_id"),
        Index("uq_restaurant_tables_tenant_numero", "tenant_id", "numero", unique=True),
    )

    def __repr__(self) -> str:
        return f"<TableRestaurant id={self.id} numero={self.numero!r} capacite={self.capacite}>"
