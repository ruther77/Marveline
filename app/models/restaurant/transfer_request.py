"""Modèles TransferRequest — Demandes de transfert restaurant → épicerie (BACK-TRANSFER-RESTO-01).

Workflow MVP :
  1. Staff restaurant crée TransferRequest(status=PENDING) avec lignes désirées
  2. Gérant épicerie consulte les demandes (séparé, hors scope MVP backend)
  3. Conversion en InternalTransfer = future phase

Distinct de `app.models.epicerie.internal_transfer.InternalTransfer` :
  - InternalTransfer = transfert effectif (impacte le stock) initié par épicerie
  - TransferRequest = brouillon de demande émise par restaurant, sans impact stock

Multi-tenant strict : `tenant_id` = tenant restaurant émetteur, `target_tenant_id` = épicerie cible.
Filtre repository OBLIGATOIRE sur tenant_id pour toutes les opérations (A1).

Références :
    docs/plans/UX_RESTAURANT_V2.md §6.2
    BACK-TRANSFER-RESTO-01 (memory)
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin

STATUSES_TRANSFER_REQUEST = ('PENDING', 'APPROVED', 'FULFILLED', 'REJECTED', 'CANCELLED')

QTY_PRECISION = 10
QTY_SCALE = 3


class TransferRequest(Base, TenantMixin, SoftDeleteMixin, TimestampMixin):
    """Demande de transfert émise par le restaurant vers l'épicerie.

    `tenant_id`        : tenant restaurant émetteur (filtre obligatoire)
    `target_tenant_id` : tenant épicerie cible
    `status`           : PENDING (initial) → APPROVED → FULFILLED ou REJECTED ou CANCELLED
    """

    __tablename__ = "restaurant_transfer_requests"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    target_tenant_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="Tenant épicerie cible de la demande"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING",
        comment="État : PENDING | APPROVED | FULFILLED | REJECTED | CANCELLED"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Notes libres du demandeur (urgence, contexte)"
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="account_id du staff restaurant qui a créé la demande"
    )
    fulfilled_transfer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="FK internal_transfers — renseigné quand status=FULFILLED"
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Raison de rejet ou annulation"
    )

    lignes: Mapped[list["TransferRequestLine"]] = relationship(
        "TransferRequestLine",
        back_populates="request",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN {STATUSES_TRANSFER_REQUEST}",
            name="ck_transfer_request_status_valide"
        ),
        CheckConstraint(
            "tenant_id != target_tenant_id",
            name="ck_transfer_request_self_target"
        ),
        Index("ix_transfer_request_tenant_status", "tenant_id", "status"),
        Index("ix_transfer_request_target", "target_tenant_id", "status"),
        Index("ix_transfer_request_created_by", "created_by"),
    )

    def __repr__(self) -> str:
        return (
            f"<TransferRequest id={self.id} tenant={self.tenant_id} "
            f"target={self.target_tenant_id} status={self.status!r}>"
        )


class TransferRequestLine(Base, TimestampMixin):
    """Ligne d'une demande de transfert (un produit/quantité demandé).

    Pas de TenantMixin direct — hérite de la demande parente via FK.
    Le service vérifie l'isolation via `request.tenant_id`.

    Note : on n'utilise pas FK vers `restaurant_ingredients` ni vers
    `epicerie_catalogue_produits` car la demande peut être saisie en texte
    libre (designation) sans correspondance catalogue stricte.
    """

    __tablename__ = "restaurant_transfer_request_lines"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    request_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_transfer_requests.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK demande parente"
    )
    designation: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Libellé produit demandé (texte libre, ex 'Tomates')"
    )
    quantity: Mapped[float] = mapped_column(
        Numeric(QTY_PRECISION, QTY_SCALE), nullable=False,
        comment="Quantité demandée"
    )
    unit: Mapped[str] = mapped_column(
        String(20), nullable=False, default="kg",
        comment="Unité (kg, L, pièce, etc.)"
    )
    ingredient_restaurant_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="FK restaurant_ingredients — renseigné si lien stock resto identifié"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Notes par ligne (marque préférée, alternative)"
    )

    request: Mapped["TransferRequest"] = relationship(
        "TransferRequest", back_populates="lignes"
    )

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_transfer_request_line_qty_positive"
        ),
        Index("ix_transfer_request_line_request", "request_id"),
        Index("ix_transfer_request_line_ingredient", "ingredient_restaurant_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<TransferRequestLine id={self.id} request={self.request_id} "
            f"designation={self.designation!r} qty={self.quantity}>"
        )
