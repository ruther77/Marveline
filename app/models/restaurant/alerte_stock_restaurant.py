"""Modèle AlerteStockRestaurant — Alertes stock du restaurant.

Enregistre les événements d'alerte déclenchés par le système :
  - entité de type 'ingredient' : stock_actuel <= stock_alerte ou = 0
  - entité de type 'instance_preparation' : portions_restantes = 0

`seuil_type` :
  - rupture : stock/portions = 0
  - alerte  : stock <= stock_alerte (ingrédients)
  - faible  : portions <= seuil_alerte_portions (instances)

`resolu_at` : null = alerte active. Renseigné lorsque le stock remonte
au-dessus du seuil (entree fournisseur, nouveau lancement marmite, etc.).

`entite_type` + `entite_id` : identifiant polymorphe de l'entité en alerte.
Pas de FK polymorphe en DB — intégrité garantie par le service.

Références :
    V2_API_RESTAURANT.md §Page: Dashboard (bandeau ruptures)
    FC_RESTAURANT_DASHBOARD.md §3 (bandeau instances_vides + ingredients_en_alerte)
    FC_RESTAURANT_INGREDIENTS.md §4 (badge statut ok/alerte/rupture)
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin

ENTITE_TYPES = ('ingredient', 'instance_preparation')
SEUIL_TYPES = ('bas', 'zero')


class AlerteStockRestaurant(Base, TenantMixin):
    """Événement d'alerte stock — journal des dépassements de seuil.

    Pas de TimestampMixin : `created_at` seul suffit (journal d'événements).
    Pas de SoftDeleteMixin : journal immuable (résolution via resolu_at).
    """

    __tablename__ = "restaurant_alertes_stock"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    entite_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="Type d'entité : ingredient | instance_preparation"
    )
    entite_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="ID de l'entité en alerte (polymorphe, intégrité côté service)"
    )
    seuil_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Type de seuil franchi : rupture | alerte | faible"
    )
    resolu_at: Mapped[Optional[object]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp de résolution (null = alerte encore active)"
    )
    resolu_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        comment="Compte ayant résolu l'alerte (null si résolution automatique)"
    )
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Date de création de l'alerte"
    )
    # tenant_id hérite de TenantMixin (= 3 pour restaurant)

    __table_args__ = (
        CheckConstraint(
            f"entite_type IN {ENTITE_TYPES}",
            name="check_alerte_stock_resto_entite_type_valide"
        ),
        CheckConstraint(
            "seuil_type IN ('bas', 'zero')",
            name="check_alerte_stock_resto_seuil_type_valide"
        ),
        Index("idx_alertes_stock_resto_tenant", "tenant_id"),
        Index("idx_alertes_stock_resto_entite", "entite_type", "entite_id"),
        Index("idx_alertes_stock_resto_resolu", "resolu_at"),
        Index("idx_alertes_stock_resto_resolu_by", "resolu_by_id"),
        Index(
            "idx_alertes_stock_resto_tenant_active",
            "tenant_id", "resolu_at"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AlerteStockRestaurant id={self.id} "
            f"entite={self.entite_type}:{self.entite_id} "
            f"seuil={self.seuil_type!r} "
            f"resolu={self.resolu_at is not None}>"
        )
