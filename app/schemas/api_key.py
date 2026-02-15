"""Schemas Pydantic pour les API Keys (authentification M2M)."""
from datetime import datetime
from typing import Optional
from pydantic import Field, field_validator
from app.schemas.base import BaseSchema, EntityResponseSchema
from app.core.permissions import Permission


# Scopes valides = toutes les valeurs de Permission enum
_VALID_SCOPES = {p.value for p in Permission}


class ApiKeyCreate(BaseSchema):
    """Schema pour creation d'une API key.

    Example:
        POST /api/v1/api-keys
        {
            "name": "Caisse magasin 1",
            "scopes": ["products:read", "inventory:read"],
            "rate_limit": 500,
            "expires_at": "2027-01-01T00:00:00Z"
        }
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nom descriptif de la cle API"
    )

    scopes: list[str] = Field(
        ...,
        min_length=1,
        description="Permissions accordees (resource:action)"
    )

    rate_limit: Optional[int] = Field(
        default=1000,
        gt=0,
        description="Limite requetes par heure (null = defaut tenant)"
    )

    expires_at: Optional[datetime] = Field(
        default=None,
        description="Date d'expiration (null = pas d'expiration)"
    )

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        """Valide que les scopes sont des permissions valides."""
        invalid = [s for s in v if s not in _VALID_SCOPES]
        if invalid:
            raise ValueError(
                f"Scopes invalides: {invalid}. "
                f"Valeurs acceptees: {sorted(_VALID_SCOPES)}"
            )
        return sorted(set(v))


class ApiKeyUpdate(BaseSchema):
    """Schema pour mise a jour partielle d'une API key.

    Example:
        PATCH /api/v1/api-keys/1
        {
            "name": "Caisse magasin 2",
            "scopes": ["products:read"],
            "is_active": false
        }
    """

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Nouveau nom"
    )

    scopes: Optional[list[str]] = Field(
        default=None,
        min_length=1,
        description="Nouveaux scopes"
    )

    rate_limit: Optional[int] = Field(
        default=None,
        gt=0,
        description="Nouvelle limite requetes/heure"
    )

    is_active: Optional[bool] = Field(
        default=None,
        description="Activer/desactiver la cle"
    )

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Valide que les scopes sont des permissions valides."""
        if v is None:
            return v
        invalid = [s for s in v if s not in _VALID_SCOPES]
        if invalid:
            raise ValueError(
                f"Scopes invalides: {invalid}. "
                f"Valeurs acceptees: {sorted(_VALID_SCOPES)}"
            )
        return sorted(set(v))


class ApiKeyResponse(EntityResponseSchema):
    """Schema pour reponse API key (sans le full key).

    Example:
        {
            "id": 1,
            "name": "Caisse magasin 1",
            "key_prefix": "mk_live_a1b2",
            "scopes": ["products:read", "inventory:read"],
            "rate_limit": 500,
            "expires_at": "2027-01-01T00:00:00Z",
            "is_active": true,
            "last_used_at": null,
            "usage_count": 0,
            "created_by": 1,
            "created_at": "2026-02-15T10:00:00Z",
            "updated_at": "2026-02-15T10:00:00Z"
        }
    """

    name: str = Field(..., description="Nom descriptif")
    key_prefix: str = Field(..., description="Prefixe visible (mk_live_xxxx)")
    scopes: list[str] = Field(..., description="Permissions accordees")
    rate_limit: Optional[int] = Field(None, description="Limite req/heure")
    expires_at: Optional[datetime] = Field(None, description="Date d'expiration")
    last_used_at: Optional[datetime] = Field(None, description="Derniere utilisation")
    last_used_ip: Optional[str] = Field(None, description="IP derniere utilisation")
    usage_count: int = Field(0, description="Nombre d'utilisations")
    created_by: int = Field(..., description="ID de l'admin createur")


class ApiKeyCreated(ApiKeyResponse):
    """Schema pour reponse de creation/rotation (avec full key).

    Le full_key n'est visible QU'UNE SEULE FOIS (create ou rotate).
    """

    full_key: str = Field(
        ...,
        description="Cle API complete (visible uniquement a la creation/rotation)"
    )


class ApiKeyList(BaseSchema):
    """Schema simplifie pour listing des API keys."""

    id: int = Field(..., gt=0)
    name: str
    key_prefix: str
    scopes: list[str]
    is_active: bool
    last_used_at: Optional[datetime] = None
    usage_count: int = 0
    created_at: datetime
