"""Modèle InstancePreparation — Marmites cuisinées au quotidien.

Une InstancePreparation est une marmite physique créée à partir d'un
TypePreparation. Elle suit le stock de portions restantes (niveau 1 ADR-09).

`portions_restantes` est décrémenté atomiquement à chaque service
(POST /lignes décrémente portions_restantes + génère MouvementStockRestaurant).
ADR-14 : `portions_restantes` lu directement en DB, jamais depuis Redis.

`statut_badge` calculé côté service à partir de portions_restantes :
  - DISPO   : portions_restantes > seuil_alerte_portions du TypePreparation
  - FAIBLE  : 0 < portions_restantes <= seuil_alerte_portions
  - EPUISE  : portions_restantes = 0

Références :
    V2_API_RESTAURANT.md §Page: Cuisine (GET /instances, POST /lancer)
    FC_RESTAURANT_CUISINE.md §2, §4 (atomicité, décrément portions)
    ADR-09 (niveau 1 stock restaurant), ADR-14 (lecture directe DB)
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class InstancePreparation(Base, TenantMixin, TimestampMixin):
    """Marmite cuisinée — instance concrète d'un TypePreparation.

    Pas de SoftDeleteMixin : une marmite épuisée reste dans l'historique
    (utile pour les statistiques de production journalière).
    """

    __tablename__ = "restaurant_instances_preparation"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    type_preparation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_types_preparation.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers la recette template (restaurant_types_preparation)"
    )
    portions_initiales: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Nombre de portions au lancement (= portions_par_batch du type, ou ajusté)"
    )
    portions_restantes: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Portions disponibles actuellement — mis à jour atomiquement (ADR-14: direct DB)"
    )
    date_cuisine: Mapped[object] = mapped_column(
        Date, nullable=False,
        comment="Date de cuisson (jour J, sans heure)"
    )
    heure_lancement: Mapped[Optional[object]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp précis du lancement (optionnel)"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Note libre. Ex: 'Extra épicé', 'Batch réduit faute de poulet'"
    )
    created_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        comment="Compte ayant lancé la marmite (null si import ou automatique)"
    )
    # tenant_id hérite de TenantMixin (= 3 pour restaurant)
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            "portions_initiales >= 1",
            name="check_instance_prep_portions_initiales_positive"
        ),
        CheckConstraint(
            "portions_restantes >= 0",
            name="check_instance_prep_portions_restantes_positive"
        ),
        CheckConstraint(
            "portions_restantes <= portions_initiales",
            name="check_instance_prep_portions_coherentes"
        ),
        Index("idx_instances_prep_tenant", "tenant_id"),
        Index("idx_instances_prep_type", "type_preparation_id"),
        Index("idx_instances_prep_date", "date_cuisine"),
        Index("idx_instances_prep_created_by", "created_by_id"),
        Index("idx_instances_prep_tenant_date", "tenant_id", "date_cuisine"),
    )

    def __repr__(self) -> str:
        return (
            f"<InstancePreparation id={self.id} "
            f"type_preparation_id={self.type_preparation_id} "
            f"date={self.date_cuisine} "
            f"portions={self.portions_restantes}/{self.portions_initiales}>"
        )
