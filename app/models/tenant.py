"""Modèle ORM Tenant — cycle de vie tenant (§10-MULTI-TENANT-OPS §S-13.1)."""
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    """Représente un tenant (client) dans la plateforme CaroCorp.

    State machine (§10 §S-13.1) :
        provisioning → active → suspended → offboarding → archived

    Règle : tenant_id est immuable (UUID string), jamais réutilisé.
    """

    __tablename__ = "tenants"
    __table_args__ = (
        Index("idx_tenants_status", "status"),
        Index("idx_tenants_domain", "domain", unique=True),
        Index("idx_tenants_app_code", "app_code"),
        Index("idx_tenants_brand_code", "brand_code"),
        CheckConstraint(
            "app_code IN ('marveline', 'epicerie', 'restaurant')",
            name="ck_tenants_app_code_valid",
        ),
    )

    APP_CODES: tuple[str, ...] = ("marveline", "epicerie", "restaurant")

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    """ID interne (BigInteger — clé FK dans les tables métier)."""

    external_id = Column(String(64), nullable=False, unique=True, index=True)
    """UUID v4 immutable — jamais réutilisé (§10 règle d'or)."""

    name = Column(String(200), nullable=False)
    domain = Column(String(200), nullable=False, unique=True)
    contact_email = Column(String(200), nullable=False)

    app_code = Column(String(20), nullable=False)
    """App rattachée : marveline | epicerie | restaurant. ISO-APP-01 enforcement."""

    brand_code = Column(String(30), nullable=False, default="marveline")
    """Code brand (habillage frontend) : marveline | lesplendid | ... Independant de app_code."""

    status = Column(String(20), nullable=False, default="provisioning", index=True)
    """Statut cycle de vie : provisioning | active | suspended | offboarding | archived."""

    plan = Column(String(50), nullable=False, default="standard")
    """Plan tarifaire : standard | premium | enterprise."""

    is_active = Column(Boolean, nullable=False, default=True)
    """Shortcut : True si status == 'active'."""

    # Timestamps de transition
    activated_at = Column(DateTime(timezone=True), nullable=True)
    suspended_at = Column(DateTime(timezone=True), nullable=True)
    offboarding_started_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Métadonnées provisioning
    provisioned_by = Column(Integer, nullable=True)
    """user_id du super_admin ayant provisionné le tenant."""

    notes = Column(Text, nullable=True)
    """Notes internes (ops, raisons de suspension, etc.)."""

    # Paramètres RGPD
    data_retention_days = Column(Integer, nullable=False, default=90)
    """Durée rétention données métier après offboarding (défaut 90 jours §10 §S-13.1)."""

    # Limites opérationnelles
    max_users = Column(Integer, nullable=False, default=50)
    max_sessions_per_user = Column(Integer, nullable=False, default=5)

    # Transitions légales (§10 state machine)
    TRANSITIONS: dict[str, list[str]] = {
        "provisioning": ["active"],
        "active":       ["suspended", "offboarding"],
        "suspended":    ["active", "offboarding"],
        "offboarding":  ["archived"],
        "archived":     [],  # état terminal
    }

    def can_transition_to(self, new_status: str) -> bool:
        """Vérifie si la transition est légale selon la state machine."""
        return new_status in self.TRANSITIONS.get(self.status, [])
