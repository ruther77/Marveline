"""Modèle DamageType — Types de dommages pour les charges de facture."""
from sqlalchemy import BigInteger, CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin


class DamageType(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Type de dommage prédéfini pour les charges additionnelles sur facture.

    Attributes:
        name: Libellé du type de dommage (ex: "Assiette cassée")
        default_fee_cents: Tarif par défaut en centimes (peut être surchargé)
    """

    __tablename__ = "damage_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Libellé du type de dommage"
    )

    default_fee_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Tarif par défaut en centimes (0 = montant à saisir)"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_damage_type_tenant_name"),
        CheckConstraint(
            "default_fee_cents >= 0",
            name="check_damage_type_fee_positive"
        ),
    )

    def __repr__(self) -> str:
        return f"<DamageType(id={self.id}, name='{self.name}')>"
