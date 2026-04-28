"""Modèle Relance — relances planifiées liées aux factures."""
from datetime import datetime
from typing import Optional
from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TenantMixin


class Relance(Base, TenantMixin):
    """Relance planifiée associée à une facture.

    Statuts :
        scheduled : Relance planifiée, en attente d'envoi
        sent      : Relance envoyée avec succès
        cancelled : Relance annulée avant envoi

    Attributes:
        invoice_id: FK vers la facture concernée
        scheduled_at: Date/heure planifiée d'envoi
        sent_at: Date/heure effective d'envoi (NULL si pas encore envoyée)
        cancelled_at: Date/heure d'annulation (NULL si non annulée)
        status: État de la relance (scheduled/sent/cancelled)
        channel: Canal d'envoi (email/sms/push)
        created_at: Timestamp de création (immuable)
    """

    __tablename__ = "relances"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK vers la facture à relancer"
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="Date/heure planifiée d'envoi"
    )

    sent_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Date/heure effective d'envoi"
    )

    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Date/heure d'annulation"
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="scheduled",
        comment="Statut : scheduled, sent, cancelled"
    )

    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="email",
        comment="Canal : email, sms, push"
    )

    message: Mapped[Optional[str]] = mapped_column(
        nullable=True,
        comment="Message personnalisé (optionnel, sinon template par défaut)"
    )

    email_send_error: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="F1058 — message d'erreur si l'envoi gateway a échoué (status='failed')"
    )

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="Timestamp de création"
    )

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="relances")

    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled', 'sent', 'cancelled', 'failed')",
            name="check_relance_status_valid"
        ),
        CheckConstraint(
            "channel IN ('email', 'sms', 'push')",
            name="check_relance_channel_valid"
        ),
        Index("ix_relances_tenant_id_composite", "tenant_id", "id"),
        Index("ix_relances_tenant_invoice", "tenant_id", "invoice_id"),
        Index("ix_relances_tenant_status", "tenant_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Relance(id={self.id}, invoice={self.invoice_id}, "
            f"status='{self.status}', scheduled='{self.scheduled_at}')>"
        )
