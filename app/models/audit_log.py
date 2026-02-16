"""Modèle AuditLog pour conformité RGPD et traçabilité complète."""
from datetime import datetime
from sqlalchemy import BigInteger, String, Text, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class AuditLog(Base):
    """Log d'audit immuable append-only pour conformité RGPD/SOC2.

    Enregistre toutes les actions sensibles (mutations + lectures sensibles)
    pour traçabilité complète et conformité réglementaire.

    Architecture:
        - Append-only : Pas de UPDATE/DELETE autorisé
        - Trigger PostgreSQL empêche toute modification
        - Retention 7 ans minimum (conformité RGPD Art. 30)
        - Chiffrement au repos (DB encryption PostgreSQL)

    Attributes:
        id: Clé primaire auto-incrémentée
        user_id: ID utilisateur (NULL pour actions système)
        tenant_id: ID tenant (multi-tenant isolation)
        action: Type d'action (CREATE, UPDATE, DELETE, READ_SENSITIVE, LOGIN_SUCCESS, etc.)
        entity_type: Type d'entité (Customer, Reservation, Invoice, User, etc.)
        entity_id: ID de l'entité impactée (NULL pour actions globales)
        changes: JSONB avant/après pour UPDATE, données complètes pour CREATE/DELETE
        description: Description humaine de l'action
        ip_address: IP du client (IPv4/IPv6 ou valeur test, String(45))
        user_agent: User-Agent du navigateur/client
        request_id: UUID de requête pour corrélation logs applicatifs
        created_at: Timestamp immuable (server_default=now())

    Security:
        - Trigger prevent_audit_log_modification() interdit UPDATE/DELETE
        - Index composite pour queries performantes (tenant_id, user_id, dates)
        - JSONB pour flexibilité changes sans schema rigide
        - INET pour IPv4/IPv6 natif PostgreSQL

    Conformité:
        - RGPD Article 30 : Registre des activités de traitement
        - SOC 2 : Audit trail complet
        - ISO 27001 : Traçabilité accès données
        - PCI-DSS : Journalisation mutations données sensibles

    Example:
        >>> # Audit création customer
        >>> audit_log = AuditLog(
        ...     user_id=42,
        ...     tenant_id=1,
        ...     action="CREATE",
        ...     entity_type="Customer",
        ...     entity_id=123,
        ...     changes={"after": {"email": "john@example.com", ...}},
        ...     description="Created Customer #123",
        ...     ip_address="192.168.1.100",
        ...     user_agent="Mozilla/5.0...",
        ...     request_id="550e8400-e29b-41d4-a716-446655440000"
        ... )

        >>> # Audit modification réservation
        >>> audit_log = AuditLog(
        ...     user_id=42,
        ...     tenant_id=1,
        ...     action="UPDATE",
        ...     entity_type="Reservation",
        ...     entity_id=456,
        ...     changes={
        ...         "status": {"before": "draft", "after": "confirmed"},
        ...         "total_amount": {"before": 10000, "after": 12000}
        ...     },
        ...     description="Updated Reservation #456: status, total_amount",
        ...     ip_address="192.168.1.100",
        ...     user_agent="Mozilla/5.0...",
        ...     request_id="550e8400-e29b-41d4-a716-446655440001"
        ... )

        >>> # Audit lecture sensible
        >>> audit_log = AuditLog(
        ...     user_id=42,
        ...     tenant_id=1,
        ...     action="READ_SENSITIVE",
        ...     entity_type="Customer",
        ...     entity_id=123,
        ...     description="Accessed sensitive data Customer #123",
        ...     ip_address="192.168.1.100",
        ...     user_agent="Mozilla/5.0...",
        ...     request_id="550e8400-e29b-41d4-a716-446655440002"
        ... )
    """

    __tablename__ = "audit_logs"

    # ===== Clé primaire =====
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Clé primaire auto-incrémentée"
    )

    # ===== Acteur =====
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
        comment="ID utilisateur (NULL pour actions système automatiques ou API key)"
    )

    api_key_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
        comment="ID API key (NULL si action par utilisateur ou système)"
    )

    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="ID tenant (isolation multi-tenant stricte)"
    )

    # ===== Action =====
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type d'action: CREATE, UPDATE, DELETE, SOFT_DELETE, READ_SENSITIVE, LOGIN_SUCCESS, LOGIN_FAILED, LOGOUT"
    )

    # ===== Entité impactée =====
    entity_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Type d'entité: Customer, Reservation, Invoice, Product, User, etc."
    )

    entity_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="ID de l'entité impactée (NULL pour actions globales type LOGIN)"
    )

    # ===== Détails modifications =====
    changes: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="JSONB modifications: {'field': {'before': old, 'after': new}} pour UPDATE, {'after': data} pour CREATE, {'before': data} pour DELETE"
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description humaine de l'action pour lisibilité logs"
    )

    # ===== Contexte requête HTTP =====
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="Adresse IP du client (IPv4/IPv6) ou valeur test (max 45 chars)"
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="User-Agent du navigateur/client HTTP"
    )

    request_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="UUID de requête HTTP pour corrélation avec logs applicatifs"
    )

    # ===== Timestamp immuable =====
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("now()"),
        comment="Timestamp création (immuable, généré par PostgreSQL)"
    )

    # ===== Indexes composites pour queries fréquentes =====
    __table_args__ = (
        # Index composite pour queries par tenant + plage dates (query admin la plus fréquente)
        Index(
            "idx_audit_tenant_created",
            "tenant_id",
            "created_at",
            postgresql_using="btree"
        ),

        # Index composite pour queries par user + plage dates (historique utilisateur)
        Index(
            "idx_audit_user_created",
            "user_id",
            "created_at",
            postgresql_using="btree",
            postgresql_where=text("user_id IS NOT NULL")  # Partial index (exclu actions système)
        ),

        # Index composite pour queries par entité (traçabilité complète d'une entité)
        Index(
            "idx_audit_entity",
            "entity_type",
            "entity_id",
            "created_at",
            postgresql_using="btree",
            postgresql_where=text("entity_type IS NOT NULL AND entity_id IS NOT NULL")  # Partial index
        ),

        # Index composite pour queries par action + date (stats par type d'action)
        Index(
            "idx_audit_action_created",
            "action",
            "created_at",
            postgresql_using="btree"
        ),

        # Index sur request_id pour corrélation logs (queries ponctuelles)
        # Déjà défini via index=True dans mapped_column
    )

    def __repr__(self) -> str:
        """Représentation lisible pour debug logs."""
        return (
            f"<AuditLog("
            f"id={self.id}, "
            f"user={self.user_id}, "
            f"tenant={self.tenant_id}, "
            f"action={self.action}, "
            f"entity={self.entity_type}:{self.entity_id}, "
            f"created_at={self.created_at.isoformat() if self.created_at else None}"
            f")>"
        )
