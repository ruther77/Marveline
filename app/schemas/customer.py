"""Schemas Pydantic pour l'entité Customer (clients)."""
from datetime import date
from typing import Optional, List
from pydantic import EmailStr, Field, computed_field, field_validator, model_validator
from app.schemas.base import BaseSchema, EntityResponseSchema
from app.constants import CustomerType


class CustomerBase(BaseSchema):
    """Schema de base partagé entre Create et Update."""

    customer_type: CustomerType = Field(
        ...,
        description="Type de client: individual, company, professional ou association"
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

    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Note interne (non visible client)"
    )

    @model_validator(mode='after')
    def validate_customer_data_coherence(self):
        """Validation cohérence données selon le type de client.

        Rules:
            - individual: first_name et last_name requis
            - company / professional / association: company_name requis
        """
        org_types = {CustomerType.COMPANY, CustomerType.PROFESSIONAL, CustomerType.ASSOCIATION}
        if self.customer_type == CustomerType.INDIVIDUAL:
            if not self.first_name or not self.last_name:
                raise ValueError(
                    "first_name and last_name are required for individual customers"
                )
        elif self.customer_type in org_types:
            if not self.company_name:
                raise ValueError(
                    "company_name is required for company, professional and association customers"
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

    Example:
        {
            "customer_type": "company",
            "company_name": "SARL Exemple",
            "phone": "+33698765432"
        }
    """

    customer_type: Optional[CustomerType] = Field(
        default=None,
        description="Type de client (particulier ou entreprise)"
    )

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

    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Note interne (non visible client)"
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
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: str

    # Note interne
    notes: Optional[str] = None

    @computed_field
    @property
    def display_name(self) -> str:
        """Nom d'affichage du client (calculé côté frontend aussi)."""
        if self.customer_type == CustomerType.INDIVIDUAL and self.first_name and self.last_name:
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

    # Note interne
    notes: Optional[str] = None

    # Relations (optionnel selon endpoint)
    # reservations: Optional[list["ReservationList"]] = None

    @computed_field
    @property
    def display_name(self) -> str:
        """Nom d'affichage du client."""
        if self.customer_type == CustomerType.INDIVIDUAL and self.first_name and self.last_name:
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


class CustomerHistoryReservation(BaseSchema):
    """Résumé de réservation pour l'historique client."""

    id: int
    reference: str
    event_date: date
    status: str
    total_amount: int = Field(description="Montant total en centimes")


class CustomerHistoryInvoice(BaseSchema):
    """Résumé de facture pour l'historique client."""

    id: int
    invoice_number: str
    status: str
    total_amount: int = Field(description="Montant total en centimes")
    paid_amount: int = Field(description="Montant payé en centimes")


class CustomerHistoryStats(BaseSchema):
    """Statistiques agrégées d'un client."""

    total_reservations: int
    total_revenue_cents: int
    last_event_date: Optional[date] = None


class CustomerHistory(BaseSchema):
    """Historique complet d'un client : réservations, factures, stats."""

    customer: CustomerResponse
    reservations: List[CustomerHistoryReservation]
    invoices: List[CustomerHistoryInvoice]
    stats: CustomerHistoryStats


class CustomerRFMItem(BaseSchema):
    """Résultat RFM pour un client (Recency / Frequency / Monetary)."""

    customer_id: int
    customer_name: str
    recency_days: int
    frequency: int
    monetary_cents: int
    segment: str  # Champions | Loyal | Potential | At Risk | Lost | New


class CustomerRFMResponse(BaseSchema):
    """Réponse complète de l'analyse RFM."""

    items: List[CustomerRFMItem]
    total: int


class RFMCampaignRequest(BaseSchema):
    """Requête d'envoi de campagne email par segment RFM."""

    segment: str = Field(
        ...,
        description="Segment RFM ciblé",
        pattern=r"^(Champions|Loyal|Potential|At Risk|Lost|New)$",
    )
    subject: str = Field(
        ..., min_length=3, max_length=200,
        description="Sujet de l'email",
    )
    message: str = Field(
        ..., min_length=10, max_length=5000,
        description="Corps du message (texte brut)",
    )


class RFMCampaignResponse(BaseSchema):
    """Résultat d'envoi de campagne RFM."""

    segment: str
    recipients_count: int
    sent_count: int
    failed_count: int
