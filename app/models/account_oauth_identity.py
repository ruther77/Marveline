"""Modèle AccountOAuthIdentity — Identités OAuth liées à un compte global."""
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class AccountOAuthIdentity(Base):
    """Identité OAuth liée à un compte global CaroCorp.

    Un compte peut avoir plusieurs identités OAuth (Google, GitHub, Facebook).
    Un (provider, provider_subject) est unique globalement — jamais deux comptes
    ne peuvent pointer vers le même provider_subject.

    Règles :
        - provider_subject est l'identifiant stable côté provider (claim 'sub')
        - email_at_provider est informatif uniquement (snapshot)
        - Auto-link par email uniquement si vérifié + compte unique (flow OAuth)
    """

    __tablename__ = "account_oauth_identities"

    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_oauth_provider_subject"),
        Index("idx_oauth_account_id", "account_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        comment="Compte global associé",
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Provider OAuth : google | github | facebook",
    )

    provider_subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="ID stable chez le provider (claim 'sub')",
    )

    email_at_provider: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Email snapshot chez le provider (informatif uniquement)",
    )

    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Date de liaison du compte OAuth",
    )

    account: Mapped["Account"] = relationship("Account", lazy="noload")

    def __repr__(self) -> str:
        return f"<AccountOAuthIdentity(account={self.account_id}, provider='{self.provider}')>"
