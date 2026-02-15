"""Schemas Pydantic pour l'entite Category."""
from typing import Optional
from pydantic import Field
from app.schemas.base import BaseSchema, EntityResponseSchema


class CategoryCreate(BaseSchema):
    """Schema pour creation d'une nouvelle categorie."""

    name: str = Field(
        ...,
        max_length=200,
        description="Nom de la categorie"
    )
    slug: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Slug URL-safe (auto-genere si absent)"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Description de la categorie"
    )
    parent_id: Optional[int] = Field(
        default=None,
        description="ID de la categorie parente"
    )
    image_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL de l'image"
    )
    display_order: int = Field(
        default=0,
        ge=0,
        description="Ordre d'affichage"
    )


class CategoryUpdate(BaseSchema):
    """Schema pour mise a jour d'une categorie (PATCH partiel)."""

    name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Nom de la categorie"
    )
    slug: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Slug URL-safe"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Description"
    )
    parent_id: Optional[int] = Field(
        default=None,
        description="ID de la categorie parente"
    )
    image_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL de l'image"
    )
    display_order: Optional[int] = Field(
        default=None,
        ge=0,
        description="Ordre d'affichage"
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Actif"
    )


class CategoryResponse(EntityResponseSchema):
    """Schema de reponse pour une categorie."""

    name: str
    slug: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    image_url: Optional[str] = None
    display_order: int


class CategoryTreeNode(CategoryResponse):
    """Schema pour un noeud d'arbre hierarchique de categories."""

    children: list["CategoryTreeNode"] = []
    product_count: int = 0


class CategoryListResponse(BaseSchema):
    """Schema de reponse pour liste de categories."""

    categories: list[CategoryResponse]
    total: int
