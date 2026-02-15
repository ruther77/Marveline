"""Schemas Pydantic pour les Feature Flags."""
from datetime import datetime
from typing import Optional
from pydantic import Field, field_validator
from app.schemas.base import BaseSchema, IDSchema, TimestampSchema


class FeatureFlagCreate(BaseSchema):
    """Schema pour creation d'un feature flag.

    Example:
        POST /api/v1/features
        {
            "name": "stripe_payments",
            "description": "Active Stripe Checkout pour le tenant",
            "is_enabled": true,
            "target_tenants": [1, 2],
            "rollout_pct": 100
        }
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Identifiant unique du flag (snake_case)"
    )

    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Description humaine du flag"
    )

    is_enabled: bool = Field(
        default=False,
        description="Master switch global (False = desactive pour tous)"
    )

    target_tenants: Optional[list[int]] = Field(
        default=None,
        description="Tenant IDs cibles (null=tous, []=aucun, [1,2]=specifiques)"
    )

    rollout_pct: int = Field(
        default=100,
        ge=0,
        le=100,
        description="Pourcentage de rollout 0-100"
    )

    metadata_json: Optional[dict] = Field(
        default=None,
        description="Donnees arbitraires (plan, tier, config)"
    )

    @field_validator("target_tenants")
    @classmethod
    def validate_target_tenants(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        """Valide que les tenant IDs sont positifs et uniques."""
        if v is None:
            return v
        invalid = [t for t in v if t <= 0]
        if invalid:
            raise ValueError(f"Tenant IDs doivent etre positifs: {invalid}")
        return sorted(set(v))


class FeatureFlagUpdate(BaseSchema):
    """Schema pour mise a jour partielle d'un feature flag.

    Example:
        PATCH /api/v1/features/1
        {
            "is_enabled": false,
            "rollout_pct": 50
        }
    """

    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Nouvelle description"
    )

    is_enabled: Optional[bool] = Field(
        default=None,
        description="Activer/desactiver le flag"
    )

    target_tenants: Optional[list[int]] = Field(
        default=None,
        description="Nouveaux tenant IDs cibles"
    )

    rollout_pct: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Nouveau pourcentage de rollout"
    )

    metadata_json: Optional[dict] = Field(
        default=None,
        description="Nouvelles donnees arbitraires"
    )

    @field_validator("target_tenants")
    @classmethod
    def validate_target_tenants(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        """Valide que les tenant IDs sont positifs et uniques."""
        if v is None:
            return v
        invalid = [t for t in v if t <= 0]
        if invalid:
            raise ValueError(f"Tenant IDs doivent etre positifs: {invalid}")
        return sorted(set(v))


class FeatureFlagResponse(IDSchema, TimestampSchema):
    """Schema pour reponse complete d'un feature flag.

    Example:
        {
            "id": 1,
            "name": "stripe_payments",
            "description": "Active Stripe Checkout",
            "is_enabled": true,
            "target_tenants": [1, 2],
            "rollout_pct": 100,
            "metadata_json": {"tier": "premium"},
            "created_at": "2026-02-15T10:00:00Z",
            "updated_at": "2026-02-15T10:00:00Z"
        }
    """

    name: str = Field(..., description="Identifiant unique du flag")
    description: Optional[str] = Field(None, description="Description humaine")
    is_enabled: bool = Field(..., description="Master switch global")
    target_tenants: Optional[list[int]] = Field(None, description="Tenant IDs cibles")
    rollout_pct: int = Field(..., description="Pourcentage de rollout 0-100")
    metadata_json: Optional[dict] = Field(None, description="Donnees arbitraires")


class FeatureFlagEvaluated(BaseSchema):
    """Schema pour resultat d'evaluation d'un flag pour un tenant.

    Example:
        GET /api/v1/features/check/stripe_payments?tenant_id=1
        {
            "name": "stripe_payments",
            "enabled": true,
            "reason": "whitelist"
        }
    """

    name: str = Field(..., description="Nom du flag")
    enabled: bool = Field(..., description="Flag actif pour ce tenant")
    reason: str = Field(
        ...,
        description="Raison: kill_switch, whitelist, not_in_whitelist, rollout, disabled"
    )


class FeatureFlagList(BaseSchema):
    """Schema simplifie pour listing des feature flags."""

    id: int = Field(..., gt=0)
    name: str
    description: Optional[str] = None
    is_enabled: bool
    target_tenants: Optional[list[int]] = None
    rollout_pct: int
    created_at: datetime
