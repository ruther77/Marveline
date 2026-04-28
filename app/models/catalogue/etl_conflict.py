"""Modèle EtlConflict — Log de déduplication Jaro-Winkler (M04).

Table sans tenant_id : log de déduplication partagé entre tous les imports.
Chaque ligne représente un conflit détecté lors d'un import ETL, en attente
de résolution manuelle par un opérateur.

Références :
    §6.4    : schéma SQL validé
    ADR-07  : déduplication Jaro-Winkler (seuils ETL_SEUIL_MATCH / ETL_SEUIL_CONFLIT_ALERTE)
    ADR-15  : etl_import_id BIGINT nullable (pas ON DELETE CASCADE)
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class EtlConflict(Base, TimestampMixin):
    """Conflit de déduplication à résoudre manuellement par un opérateur.

    Un conflit est créé quand le score Jaro-Winkler d'une désignation entrante
    se situe dans la plage d'alerte (ADR-07 : [0.75, 0.85[) par rapport à une
    entrée existante dans catalogue_produits.

    Cycle de résolution : PENDING → (MERGED | KEPT_SEPARATE).
    Pas de SoftDeleteMixin : log append-only.
    """

    __tablename__ = "etl_conflicts"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    etl_import_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="FK nullable vers etl_imports.id. SET NULL si l'import est supprimé (ADR-15)."
    )
    catalogue_produit_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="FK nullable vers catalogue_produits.id. NULL si l'entrée n'existe pas encore."
    )
    designation_entrante: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Désignation telle que reçue dans le fichier source à l'import."
    )
    designation_existante: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Désignation de l'entrée catalogue candidate au merge."
    )
    score_similarite: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 3), nullable=True,
        comment="Score Jaro-Winkler calculé. NULL pour EAN_COLLISION (pas de score texte)."
    )
    type_conflit: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True,
        comment="Classification : EAN_COLLISION | DESIGNATION_PROCHE | CATEGORIE_INCONNUE"
    )
    resolution: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING",
        comment="État de résolution : PENDING | MERGED | KEPT_SEPARATE"
    )
    ean_a: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="EAN de l'entrée entrante (utile pour EAN_COLLISION)."
    )
    ean_b: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="EAN de l'entrée catalogue existante (utile pour EAN_COLLISION)."
    )
    suggestion: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="Suggestion automatique ETL : MERGED | KEPT_SEPARATE."
    )
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            "resolution IN ('PENDING','MERGED','KEPT_SEPARATE')",
            name="ck_etl_conflicts_resolution",
        ),
        # Index ADR-15 : retrouver rapidement les conflits en attente par import
        Index(
            "idx_etl_conflicts_import_pending",
            "etl_import_id",
            "resolution",
            postgresql_where=text("resolution = 'PENDING'"),
        ),
        # Index pour tableau de bord résolution opérateur (tous les PENDING)
        Index("idx_etl_conflicts_resolution", "resolution"),
        # Index pour jointure depuis catalogue_produits
        Index("idx_etl_conflicts_produit", "catalogue_produit_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<EtlConflict id={self.id} type={self.type_conflit!r} "
            f"resolution={self.resolution!r} score={self.score_similarite}>"
        )
