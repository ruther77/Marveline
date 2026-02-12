"""Schemas de base Pydantic pour les DTOs de l'API."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    """Schema de base pour tous les DTOs avec configuration commune.

    Configuration:
        - from_attributes: Permet conversion depuis modèles SQLAlchemy
        - populate_by_name: Permet utilisation des alias de champs
        - str_strip_whitespace: Nettoie automatiquement les espaces
        - validate_assignment: Valide lors de l'assignation après création
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        # JSON schema customization
        json_schema_extra={
            "examples": []
        }
    )


class TimestampSchema(BaseSchema):
    """Schema avec timestamps pour les réponses d'entités."""

    created_at: datetime = Field(
        ...,
        description="Date de création de l'enregistrement"
    )

    updated_at: datetime = Field(
        ...,
        description="Date de dernière modification"
    )


class TenantSchema(BaseSchema):
    """Schema avec tenant_id pour isolation multi-tenant."""

    tenant_id: int = Field(
        ...,
        gt=0,
        description="ID du tenant (organisation cliente)"
    )


class SoftDeleteSchema(BaseSchema):
    """Schema pour entités avec suppression logique."""

    is_active: bool = Field(
        default=True,
        description="Actif (False = supprimé logiquement)"
    )


class IDSchema(BaseSchema):
    """Schema avec ID pour les réponses d'entités."""

    id: int = Field(
        ...,
        gt=0,
        description="Identifiant unique de l'entité"
    )


class EntityResponseSchema(IDSchema, TimestampSchema, TenantSchema, SoftDeleteSchema):
    """Schema complet pour les réponses d'entités avec tous les champs système.

    Combine:
        - ID unique
        - Timestamps (created_at, updated_at)
        - Multi-tenant (tenant_id)
        - Soft delete (is_active)
    """
    pass
