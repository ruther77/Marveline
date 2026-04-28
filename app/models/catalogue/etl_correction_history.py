"""Historique des corrections manuelles ETL — auto-apprentissage (Phase 3).

Quand un opérateur corrige manuellement un champ (categorie_code, marque, ean)
lors de la révision d'un import, la correction est enregistrée ici.

Le système utilise ensuite cet historique pour suggérer les mêmes corrections
aux désignations similaires dans les imports futurs (layer 0 de classification).
"""
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class EtlCorrectionHistory(Base, TimestampMixin):
    """Correction manuelle enregistrée lors de la révision d'un import ETL."""

    __tablename__ = "etl_correction_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    designation_norm: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Désignation normalisée du produit corrigé.",
    )
    field_corrected: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Champ corrigé : 'categorie_code', 'marque', 'ean'.",
    )
    old_value: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Ancienne valeur (peut être NULL si champ était vide).",
    )
    new_value: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Nouvelle valeur choisie par l'opérateur.",
    )
    etl_import_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="ID de l'import ETL où la correction a été faite.",
    )

    __table_args__ = (
        Index("idx_etl_correction_designation", "designation_norm"),
        Index("idx_etl_correction_field", "field_corrected"),
    )
