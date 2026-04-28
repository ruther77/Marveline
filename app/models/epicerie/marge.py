"""Modèle EpicerieMargeCategorie — Taux de marge par catégorie produit.

Permet de calculer le prix de vente TTC à partir du prix d'achat HT :
  prix_vente_cts = prix_achat_cts × (1 + taux_marge / 10000)

Le taux est en centièmes de pourcent (3000 = 30%, 5000 = 50%).
"""
from sqlalchemy import BigInteger, Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class EpicerieMargeCategorie(Base, TenantMixin, TimestampMixin):
    """Taux de marge par catégorie pour un tenant épicerie."""

    __tablename__ = "epicerie_marges_categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    categorie: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Code catégorie (ALC_BIERE, BOIS_SODA, etc.)"
    )
    taux_marge_centieme: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3000,
        comment="Taux de marge en centièmes de % (3000 = 30%, 5000 = 50%)"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "categorie", name="uq_epicerie_marges_tenant_cat"),
        Index("idx_epicerie_marges_tenant", "tenant_id"),
    )

    def __repr__(self) -> str:
        return f"<EpicerieMargeCategorie cat={self.categorie!r} marge={self.taux_marge_centieme/100}%>"
