"""Modèle Customer - Clients B2B/B2C pour locations de vaisselle."""
from typing import Optional
from sqlalchemy import CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin
from app.constants import CustomerType


class Customer(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Client individuel ou entreprise louant la vaisselle.

    Attributes:
        customer_type: 'individual' (particulier) ou 'company' (entreprise)
        first_name: Prénom (requis si individual)
        last_name: Nom (requis si individual)
        company_name: Raison sociale (requis si company)
        email: Email unique par tenant
        phone: Téléphone de contact
        address: Adresse postale
        city: Ville
        postal_code: Code postal
        country: Pays (défaut: 'France')
    """

    __tablename__ = "customers"

    # Clé primaire
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Type de client
    customer_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Type de client: individual ou company"
    )

    # Informations particulier
    first_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Prénom (requis si individual)"
    )

    last_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Nom (requis si individual)"
    )

    # Informations entreprise
    company_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Raison sociale (requis si company)"
    )

    # Contact
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Email de contact (unique par tenant)"
    )

    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Téléphone de contact"
    )

    # Adresse
    address: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Adresse postale complète"
    )

    city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Ville"
    )

    postal_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Code postal"
    )

    country: Mapped[str] = mapped_column(
        String(100),
        default="France",
        nullable=False,
        comment="Pays"
    )

    # B2B — identifiants entreprise
    siret: Mapped[Optional[str]] = mapped_column(
        String(14),
        nullable=True,
        comment="SIRET (14 chiffres, entreprises francaises)"
    )

    vat_number: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="TVA intracommunautaire (ex: FR12345678901)"
    )

    # Note interne (visible équipe uniquement)
    notes: Mapped[Optional[str]] = mapped_column(
        String(2000),
        nullable=True,
        comment="Note interne (non visible client)"
    )

    # Relations
    reservations: Mapped[list["Reservation"]] = relationship(
        "Reservation",
        back_populates="customer",
        passive_deletes=True  # Laisse PostgreSQL gérer DELETE (FK RESTRICT)
        # Pas de cascade - respecte RESTRICT de la FK pour protéger l'historique
    )

    # Contraintes CHECK
    __table_args__ = (
        # Type de client valide
        CheckConstraint(
            "customer_type IN ('individual', 'company', 'professional', 'association')",
            name="check_customer_type_valid"
        ),
        # Cohérence données : individual → prénom+nom, autres → raison sociale
        CheckConstraint(
            "(customer_type='individual' AND first_name IS NOT NULL AND last_name IS NOT NULL) "
            "OR (customer_type IN ('company', 'professional', 'association') AND company_name IS NOT NULL)",
            name="check_customer_data_coherence"
        ),
        # Email unique par tenant
        UniqueConstraint("tenant_id", "email", name="uq_customer_tenant_email"),
    )

    @property
    def display_name(self) -> str:
        """Nom d'affichage du client (nom complet ou raison sociale)."""
        if self.customer_type == CustomerType.INDIVIDUAL:
            return f"{self.first_name} {self.last_name}"
        return self.company_name or "Client sans nom"

    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, type={self.customer_type}, name='{self.display_name}')>"
