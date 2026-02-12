"""Schemas communs réutilisables dans toute l'API."""
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel, Field, field_validator
from app.schemas.base import BaseSchema


# Type générique pour les réponses paginées
T = TypeVar("T")


class PaginationParams(BaseModel):
    """Paramètres de pagination pour les endpoints de liste.

    Attributes:
        skip: Nombre d'éléments à sauter (offset)
        limit: Nombre maximum d'éléments à retourner

    Validation:
        - skip >= 0
        - 1 <= limit <= 1000 (protection contre abus)
    """

    skip: int = Field(
        default=0,
        ge=0,
        description="Nombre d'éléments à sauter (offset)"
    )

    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Nombre maximum d'éléments à retourner"
    )

    @field_validator('limit')
    @classmethod
    def limit_max_1000(cls, v: int) -> int:
        """Validation explicite du max 1000 (redondant mais clair)."""
        if v > 1000:
            raise ValueError('limit cannot exceed 1000')
        return v


class PaginatedResponse(BaseSchema, Generic[T]):
    """Réponse paginée générique pour les endpoints de liste.

    Type Parameters:
        T: Type des items dans la liste

    Attributes:
        items: Liste des éléments retournés
        total: Nombre total d'éléments (avant pagination)
        skip: Offset utilisé pour cette page
        limit: Limite utilisée pour cette page
        has_more: Indicateur s'il y a d'autres pages
    """

    items: list[T] = Field(
        ...,
        description="Liste des éléments de cette page"
    )

    total: int = Field(
        ...,
        ge=0,
        description="Nombre total d'éléments (sans pagination)"
    )

    skip: int = Field(
        ...,
        ge=0,
        description="Offset utilisé pour cette page"
    )

    limit: int = Field(
        ...,
        ge=1,
        description="Limite utilisée pour cette page"
    )

    @property
    def has_more(self) -> bool:
        """Indique s'il y a d'autres pages après celle-ci."""
        return (self.skip + self.limit) < self.total

    @property
    def page_count(self) -> int:
        """Nombre total de pages."""
        if self.limit == 0:
            return 0
        return (self.total + self.limit - 1) // self.limit


class ErrorDetail(BaseModel):
    """Détail d'une erreur de validation ou métier."""

    field: Optional[str] = Field(
        default=None,
        description="Nom du champ en erreur (None si erreur globale)"
    )

    message: str = Field(
        ...,
        description="Message d'erreur descriptif"
    )

    code: Optional[str] = Field(
        default=None,
        description="Code d'erreur machine (ex: INVALID_EMAIL, OUT_OF_STOCK)"
    )


class ErrorResponse(BaseModel):
    """Réponse d'erreur standardisée pour l'API.

    Attributes:
        detail: Message d'erreur principal
        errors: Liste des erreurs de validation (optionnel)
        code: Code d'erreur HTTP ou métier

    Examples:
        Erreur simple:
        {
            "detail": "Product not found",
            "code": 404
        }

        Erreur de validation:
        {
            "detail": "Validation failed",
            "code": 422,
            "errors": [
                {"field": "email", "message": "Invalid email format", "code": "INVALID_EMAIL"},
                {"field": "price", "message": "Must be positive", "code": "INVALID_PRICE"}
            ]
        }
    """

    detail: str = Field(
        ...,
        description="Message d'erreur principal"
    )

    code: int = Field(
        ...,
        ge=400,
        lt=600,
        description="Code HTTP de l'erreur"
    )

    errors: Optional[list[ErrorDetail]] = Field(
        default=None,
        description="Liste détaillée des erreurs de validation"
    )


class SuccessResponse(BaseModel):
    """Réponse de succès standardisée pour opérations sans retour d'entité.

    Utilisé pour:
        - Confirmations d'opérations (DELETE, UPDATE sans body)
        - Actions métier (confirm_reservation, cancel_invoice)
    """

    success: bool = Field(
        default=True,
        description="Indicateur de succès"
    )

    message: str = Field(
        ...,
        description="Message de confirmation"
    )

    data: Optional[dict] = Field(
        default=None,
        description="Données additionnelles optionnelles"
    )
