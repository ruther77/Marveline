"""Modèle FournisseurAlim — Référentiel fournisseurs alimentaires partagé (M02).

Table sans tenant_id : les fournisseurs (METRO, TAIYAT, EUROCIEL, ETHAN, GNANAM)
approvisionnent à la fois l'épicerie (tenant_id=2) et le restaurant (tenant_id=3).
Dupliquer par tenant créerait une désynchronisation des EAN.

Références :
    ADR-02  : fournisseurs_alim sans tenant_id
    §6.2    : schéma SQL validé
"""
from typing import Optional

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FournisseurAlim(Base, TimestampMixin):
    """Fournisseur alimentaire du référentiel partagé.

    Un fournisseur peut être référencé par l'épicerie et le restaurant
    via leurs commandes respectives (commandes_fournisseurs.tenant_id).
    Pas de SoftDeleteMixin : le référentiel fournisseur est stable —
    la désactivation se gère par absence de nouvelles commandes.
    """

    __tablename__ = "fournisseurs_alim"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    nom: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True,
        comment="Raison sociale complète. Ex: 'Metro Cash & Carry France'"
    )
    code_fournisseur: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, unique=True,
        comment="Code court unique. Ex: 'METRO', 'TAIYAT', 'EUROCIEL'. "
                "Correspond aux valeurs SourceFournisseur (constants/approvisionnement.py)"
    )
    type_facturation: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Format de facturation pour le parser ETL. Ex: 'pdf', 'xlsx', 'email'"
    )
    # created_at / updated_at hérités de TimestampMixin

    def __repr__(self) -> str:
        return f"<FournisseurAlim code={self.code_fournisseur!r} nom={self.nom!r}>"
