"""Modèle CommandeRestaurant — Commandes de table du restaurant.

Cycle de vie d'une commande :
  OUVERTE → SERVIE → PAYEE
  OUVERTE → ANNULEE

`statut` UPPER_CASE conforme V2_API_RESTAURANT.md.

Les montants (sous_total_cts, tva_cts, total_cts) sont calculés
et dénormalisés lors du paiement — null tant que la commande est ouverte.

`fractionnement` JSONB : tableau de fractions de paiement en cas de
partage de l'addition (ex: [{"parts": 3, "montant_cts": 50000}]).

`nb_couverts` : nombre de personnes à table — utilisé pour le calcul
de la formule boissons (multiple de 3 → suggestion bouteille).

Références :
    V2_API_RESTAURANT.md §Page: Salle — Commandes
    FC_RESTAURANT_COMMANDES.md §2 (statut cycle), §6 (fractionnement JSONB)
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin

STATUTS_COMMANDE = ('OUVERTE', 'SERVIE', 'PAYEE', 'ANNULEE')


class CommandeRestaurant(Base, TenantMixin, TimestampMixin):
    """Commande restaurant associée à une table.

    Pas de SoftDeleteMixin : les commandes annulées sont conservées
    avec statut ANNULEE pour l'historique et la comptabilité.
    """

    __tablename__ = "restaurant_commandes"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    table_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_tables.id", ondelete="SET NULL"),
        nullable=True,
        comment="Table physique (null pour commandes à emporter)"
    )
    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OUVERTE",
        comment="Statut : OUVERTE | SERVIE | PAYEE | ANNULEE"
    )
    nb_couverts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="Nombre de couverts — sert au calcul formule boissons"
    )
    sous_total_cts: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="Sous-total HT en centimes (calculé au paiement)"
    )
    tva_cts: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="Montant TVA en centimes (calculé au paiement)"
    )
    total_cts: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="Total TTC en centimes (calculé au paiement)"
    )
    pourboire_cts: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Pourboire en centimes (saisi par le serveur)"
    )
    mode_paiement: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="Mode de paiement : especes | carte | cheque | mix (renseigné au paiement)"
    )
    fractionnement: Mapped[Optional[object]] = mapped_column(
        JSON, nullable=True,
        comment="JSON : liste de fractions de paiement [{parts, montant_cts}]"
    )
    nom_client: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Nom du client ou groupe. Ex: 'M. Dupont', 'Anniversaire Julie'"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Note libre. Ex: 'Allergie noix', 'Anniversaire'"
    )
    date_fermeture: Mapped[Optional[object]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Date/heure de fermeture de la commande (PAYEE ou ANNULEE)"
    )
    created_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        comment="Serveur ayant ouvert la commande"
    )
    # tenant_id hérite de TenantMixin (= 3 pour restaurant)
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            f"statut IN {STATUTS_COMMANDE}",
            name="check_commande_resto_statut_valide"
        ),
        CheckConstraint(
            "nb_couverts >= 1",
            name="check_commande_resto_couverts_positif"
        ),
        CheckConstraint(
            "pourboire_cts >= 0",
            name="check_commande_resto_pourboire_positif"
        ),
        Index("idx_commandes_resto_tenant", "tenant_id"),
        Index("idx_commandes_resto_table", "table_id"),
        Index("idx_commandes_resto_statut", "statut"),
        Index("idx_commandes_resto_created_by", "created_by_id"),
        Index("idx_commandes_resto_tenant_statut", "tenant_id", "statut"),
    )

    def __repr__(self) -> str:
        return (
            f"<CommandeRestaurant id={self.id} "
            f"table_id={self.table_id} statut={self.statut!r}>"
        )
