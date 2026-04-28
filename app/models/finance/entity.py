"""Modèle FinanceEntity — Entités finance pour transferts internes.

Référentiel partagé identifiant les parties d'un transfert interne
(Épicerie = 1, Restaurant = 2). Sans tenant_id : partagé globalement.

ADR-03 : isolation via FK entity_source_id / entity_dest_id sur InternalTransfer.
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

TYPES_ENTITY = ('EPICERIE', 'RESTAURANT', 'EXTERNE')


class FinanceEntity(Base, TimestampMixin):
    """Entité finance (épicerie, restaurant, externe) pour les transferts internes.

    Pas de TenantMixin : référentiel partagé global.
    Pas de SoftDeleteMixin : les entités sont stables.
    """

    __tablename__ = "finance_entities"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    nom: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Nom lisible de l'entité (ex: Épicerie, Restaurant)"
    )
    type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Type : EPICERIE | RESTAURANT | EXTERNE"
    )
    code: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, unique=True,
        comment="Code court unique (ex: EPICERIE, RESTO)"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Description optionnelle de l'entité"
    )
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            f"type IN {TYPES_ENTITY}",
            name="check_finance_entity_type_valide"
        ),
        Index("idx_finance_entity_code", "code"),
        Index("idx_finance_entity_type", "type"),
    )

    def __repr__(self) -> str:
        return f"<FinanceEntity id={self.id} code={self.code!r} type={self.type!r}>"
