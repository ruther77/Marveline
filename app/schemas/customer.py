"""Schemas Pydantic pour l'entité Customer (clients)."""
from typing import Optional, Literal
from pydantic import EmailStr, Field, field_validator, model_validator
from app.schemas.base import BaseSchema, EntityResponseSchema


class CustomerBase(BaseSchema):
    """Schema de base partagé entre Create et Update."""

    customer_type: Literal["individual", "company"] = Field(
        ...,
        description="Type de client: individual (particulier) ou company (entreprise)"
    )

    email: EmailStr = Field(
        ...,
        max_length=255,
        description="Email de contact (unique par tenant)"
    )

    @field_validator('email')
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        """Normaliser email en minuscules."""
        return v.lower()

    phone: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Téléphone de contact"
    )

    # Informations particulier
    first_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Prénom (requis si individual)"
    )

    last_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nom (requis si individual)"
    )

    # Informations entreprise
    company_name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Raison sociale (requis si company)"
    )

    # Adresse
    address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Adresse postale complète"
    )

    city: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Ville"
    )

    postal_code: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Code postal"
    )

    country: str = Field(
        default="France",
        max_length=100,
        description="Pays"
    )

    @model_validator(mode='after')
    def validate_customer_data_coherence(self):
        """Validation cohérence données individual vs company.

        Rules:
            - individual: first_name et last_name requis
            - company: company_name requis
        """
        if self.customer_type == "individual":
            if not self.first_name or not self.last_name:
                raise ValueError(
                    "first_name and last_name are required for individual customers"
                )
        elif self.customer_type == "company":
            if not self.company_name:
                raise ValueError(
                    "company_name is required for company customers"
                )
        return self


class CustomerCreate(CustomerBase):
    """Schema pour création d'un nouveau client.

    Le tenant_id sera automatiquement ajouté depuis le JWT du user connecté.

    Example:
        {
            "customer_type": "individual",
            "first_name": "Jean",
            "last_name": "Dupont",
            "email": "jean.dupont@example.com",
            "phone": "+33612345678",
            "address": "123 Rue de la Paix",
            "city": "Paris",
            "postal_code": "75001",
            "country": "France"
        }
    """
    pass


class CustomerUpdate(BaseSchema):
    """Schema pour mise à jour d'un client existant.

    Tous les champs sont optionnels (PATCH partiel).
    customer_type est immutable (ne peut pas être changé après création).

    Example:
        {
            "phone": "+33698765432",
            "address": "456 Avenue des Champs",
            "city": "Lyon"
        }
    """

    email: Optional[EmailStr] = Field(
        default=None,
        max_length=255,
        description="Email de contact"
    )

    phone: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Téléphone de contact"
    )

    first_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Prénom"
    )

    last_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nom"
    )

    company_name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Raison sociale"
    )

    address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Adresse postale"
    )

    city: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Ville"
    )

    postal_code: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Code postal"
    )

    country: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Pays"
    )


class CustomerList(EntityResponseSchema):
    """Schema simplifié pour listes de clients (sans relations)."""

    customer_type: str
    email: str
    phone: Optional[str] = None

    # Champs conditionnels selon type
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None

    # Adresse
    city: Optional[str] = None
    country: str

    @property
    def display_name(self) -> str:
        """Nom d'affichage du client (calculé côté frontend aussi)."""
        if self.customer_type == "individual" and self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.company_name or "Client sans nom"


class CustomerResponse(EntityResponseSchema):
    """Schema complet pour réponse détaillée d'un client."""

    customer_type: str
    email: str
    phone: Optional[str] = None

    # Informations particulier
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    # Informations entreprise
    company_name: Optional[str] = None

    # Adresse complète
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: str

    # Relations (optionnel selon endpoint)
    # reservations: Optional[list["ReservationList"]] = None

    @property
    def display_name(self) -> str:
        """Nom d'affichage du client."""
        if self.customer_type == "individual" and self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.company_name or "Client sans nom"

    model_config = EntityResponseSchema.model_config.copy()
    model_config["json_schema_extra"] = {
        "examples": [
            {
                "id": 1,
                "tenant_id": 1,
                "customer_type": "individual",
                "first_name": "Jean",
                "last_name": "Dupont",
                "email": "jean.dupont@example.com",
                "phone": "+33612345678",
                "address": "123 Rue de la Paix",
                "city": "Paris",
                "postal_code": "75001",
                "country": "France",
                "is_active": True,
                "created_at": "2026-01-15T10:00:00Z",
                "updated_at": "2026-01-15T10:00:00Z"
            }
        ]
    }
