"""Modèle LigneCommandeRestaurant — Lignes d'une commande restaurant.

Chaque ligne représente un article commandé (VariantePlat × quantité).

Cycle de vie `statut_plat` (UPPER_CASE) :
  ENVOYEE → LANCEE → PRETE → SERVIE

`prix_unitaire_cts` : snapshot du prix au moment de la commande
(prix peut changer dans le menu sans affecter les commandes historiques).

`instance_preparation_id` : FK vers la marmite prélevée lors du service.
Null jusqu'à ce que la ligne passe en PRETE (affectation côté cuisine).

`side_id` : accompagnement optionnel choisi par le client.

Atomicité POST /lignes (ADR-09) :
  1. Vérifie portions_restantes > 0 de l'InstancePreparation
  2. Décrémente portions_restantes
  3. Génère MouvementStockRestaurant (consommation)
  4. Insère LigneCommande avec statut ENVOYEE
  Tout ou rien — rollback en cas d'échec à n'importe quelle étape.

Références :
    V2_API_RESTAURANT.md §Page: Salle — Commandes (POST /lignes)
    FC_RESTAURANT_COMMANDES.md §4 (atomicité 7 étapes)
    ADR-09 (niveau 1 : décrément atomique portions_restantes)
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin

STATUTS_PLAT = ('ENVOYEE', 'LANCEE', 'PRETE', 'SERVIE')


class LigneCommandeRestaurant(Base, TenantMixin, TimestampMixin):
    """Ligne d'une commande restaurant — article × quantité × statut cuisine.

    Pas de SoftDeleteMixin : une ligne annulée passe par un mécanisme
    de statut ou suppression explicite avec audit.
    """

    __tablename__ = "restaurant_lignes_commande"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    commande_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_commandes.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers la commande parente (restaurant_commandes)"
    )
    variante_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_variantes_plat.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers l'article commandé (restaurant_variantes_plat)"
    )
    quantite: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="Quantité commandée (toujours ≥ 1)"
    )
    prix_unitaire_cts: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="Snapshot du prix unitaire au moment de la commande (centimes)"
    )
    statut_plat: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ENVOYEE",
        comment="Statut cuisine : ENVOYEE | LANCEE | PRETE | SERVIE"
    )
    instance_preparation_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_instances_preparation.id", ondelete="SET NULL"),
        nullable=True,
        comment="Marmite prélevée (affectée lors du passage en PRETE)"
    )
    side_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_sides.id", ondelete="SET NULL"),
        nullable=True,
        comment="Accompagnement choisi (optionnel)"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Note pour la cuisine. Ex: 'sans piment', 'bien cuit'"
    )
    # tenant_id hérite de TenantMixin (= 3 pour restaurant)
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            f"statut_plat IN {STATUTS_PLAT}",
            name="check_ligne_commande_resto_statut_valide"
        ),
        CheckConstraint(
            "quantite >= 1",
            name="check_ligne_commande_resto_quantite_positive"
        ),
        CheckConstraint(
            "prix_unitaire_cts >= 0",
            name="check_ligne_commande_resto_prix_positif"
        ),
        Index("idx_lignes_commande_resto_tenant", "tenant_id"),
        Index("idx_lignes_commande_resto_commande", "commande_id"),
        Index("idx_lignes_commande_resto_variante", "variante_id"),
        Index("idx_lignes_commande_resto_instance", "instance_preparation_id"),
        Index("idx_lignes_commande_resto_side", "side_id"),
        Index("idx_lignes_commande_resto_statut", "statut_plat"),
    )

    def __repr__(self) -> str:
        return (
            f"<LigneCommandeRestaurant id={self.id} "
            f"commande_id={self.commande_id} "
            f"variante_id={self.variante_id} "
            f"statut={self.statut_plat!r}>"
        )
