"""Modèle ReservationVersion — historique des modifications de lignes."""

from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class ReservationVersion(Base):
    """Snapshot immuable d'une réservation à un instant T.

    Créé automatiquement lors de chaque modification significative
    (ajout/suppression/modification de ligne, changement de statut).
    Le devis original reste figé après conversion — ceci est l'historique vivant.
    """

    __tablename__ = "reservation_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reservation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    change_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="line_added, line_removed, line_updated, status_changed",
    )
    change_summary: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="Description lisible du changement",
    )
    snapshot_json: Mapped[dict] = mapped_column(
        JSON, nullable=False,
        comment="Snapshot complet lignes + totaux",
    )
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
