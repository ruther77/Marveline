"""Modele FeatureFlag - Feature flags avec ciblage par tenant."""
from typing import Optional
from sqlalchemy import CheckConstraint, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class FeatureFlag(Base, TimestampMixin):
    """Feature flag avec ciblage par tenant et rollout progressif.

    Pas de TenantMixin (les flags sont globaux, le ciblage se fait via target_tenants).
    Pas de SoftDeleteMixin (suppression directe).

    Attributes:
        name: Identifiant unique du flag (ex: "mfa_enabled", "stripe_payments")
        description: Description humaine du flag
        is_enabled: Master switch global (False = desactive pour tous)
        target_tenants: Liste de tenant_ids cibles (null=tous, []=aucun, [1,2]=specifiques)
        rollout_pct: Pourcentage de rollout 0-100 (utilise si target_tenants is null)
        metadata: Donnees arbitraires (plan, tier, config)

    Evaluation:
        1. is_enabled=False -> False (kill switch)
        2. target_tenants is not None -> whitelist mode
        3. target_tenants is None -> rollout_pct (hash deterministe)
    """

    __tablename__ = "feature_flags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        comment="Identifiant unique du flag (snake_case)"
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description humaine du flag"
    )

    is_enabled: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="Master switch global (False = desactive pour tous)"
    )

    target_tenants: Mapped[Optional[list[int]]] = mapped_column(
        ARRAY(Integer),
        nullable=True,
        comment="Tenant IDs cibles (null=tous, []=aucun, [1,2]=specifiques)"
    )

    rollout_pct: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        comment="Pourcentage de rollout 0-100"
    )

    metadata_json: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        default=dict,
        comment="Donnees arbitraires (plan, tier, config)"
    )

    __table_args__ = (
        CheckConstraint(
            "rollout_pct >= 0 AND rollout_pct <= 100",
            name="ck_feature_flags_rollout_pct_range"
        ),
        CheckConstraint(
            "name ~ '^[a-z][a-z0-9_]*$'",
            name="ck_feature_flags_name_format"
        ),
        Index("ix_feature_flags_name", "name", unique=True),
    )

    def __repr__(self) -> str:
        return f"<FeatureFlag(name='{self.name}', enabled={self.is_enabled})>"
