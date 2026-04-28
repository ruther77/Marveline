"""Modèles Reservation et ReservationLine - Réservations d'événements."""
from datetime import date, datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, TIMESTAMP, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, TenantMixin
from app.constants import ReservationStatus

if TYPE_CHECKING:
    from app.models.product_variant import ProductVariant
    from app.models.bundle import ProductBundle


class Reservation(Base, TimestampMixin, TenantMixin):
    """Réservation d'un client pour un événement.

    Attributes:
        customer_id: ID du client (FK)
        reference: Référence unique (ex: "RES-2026-0001")
        event_date: Date de l'événement
        delivery_date: Date de livraison (≤ event_date)
        return_date: Date de retour (≥ event_date)
        event_location: Lieu de l'événement
        status: Statut (draft, confirmed, in_progress, completed, cancelled)
        total_amount: Montant total en CENTIMES
        deposit_amount: Montant caution en CENTIMES
        deposit_paid: Caution payée (oui/non)
    """

    __tablename__ = "reservations"

    # Clé primaire
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Client
    customer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="ID du client"
    )

    # Référence unique
    reference: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        comment="Référence unique de réservation (RES-2026-0001)"
    )

    # Dates
    event_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date de l'événement"
    )

    delivery_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date de livraison"
    )

    return_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date de retour"
    )

    # Lieu
    event_location: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Lieu de l'événement"
    )

    # Détails événement
    event_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Type d'événement (mariage, anniversaire, entreprise, autre)"
    )

    event_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Nom de l'événement"
    )

    guest_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Nombre d'invités"
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes libres sur la réservation"
    )

    # Statut
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ReservationStatus.DRAFT,
        comment="Statut de la réservation"
    )

    # Montants (en centimes)
    total_amount_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Montant total en centimes"
    )

    deposit_amount_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Montant caution en centimes"
    )

    deposit_paid: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="Caution payée"
    )

    # Acompte 40% (Option B — tracking sans split facture)
    advance_payment_amount_cents: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Montant acompte 40% en centimes (calculé à la confirmation)"
    )

    balance_due_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date échéance solde (event_date - BALANCE_DUE_DAYS_BEFORE_EVENT)"
    )

    advance_paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Horodatage encaissement acompte (NULL si non encaissé)"
    )

    # Devis lié (optionnel) — FK sans contrainte ORM pour éviter dépendance circulaire devis↔reservations
    devis_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Devis source (optionnel)"
    )

    # Signature
    signature_url: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="URL ou base64 signature client"
    )
    signed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Horodatage signature client"
    )

    # Archivage (masquage des listes courantes, sans suppression)
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="FALSE",
        comment="Réservation archivée (masquée des listes courantes)"
    )

    # Livraison
    delivery_zone_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("delivery_zones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Zone de livraison (FK)",
    )

    delivery_fee_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Frais de livraison en centimes",
    )

    delivery_method: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Méthode : self, carrier, pickup",
    )

    delivery_instructions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Instructions de livraison",
    )

    carrier_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Nom du transporteur (si delivery_method=carrier)",
    )

    carrier_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Code transporteur Boxtal (si delivery_method=carrier)",
    )

    # Adresse de livraison structurée
    delivery_address: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Adresse de livraison (rue, numéro)",
    )

    delivery_city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Ville de livraison",
    )

    delivery_postal_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Code postal de livraison",
    )

    # Affectation équipe (IAM v2 — référence account_id, pas de FK car table users supprimée)
    assigned_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="account_id de l'utilisateur affecté (TenantMembership.account_id)",
        index=True,
    )

    # Relations
    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="reservations"
    )

    lines: Mapped[list["ReservationLine"]] = relationship(
        "ReservationLine",
        back_populates="reservation",
        cascade="all, delete-orphan"
    )

    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice",
        back_populates="reservation",
        cascade="all, delete-orphan",
        lazy="select",
    )

    delivery_zone: Mapped[Optional["DeliveryZone"]] = relationship(
        "DeliveryZone",
        foreign_keys=[delivery_zone_id],
    )

    movements: Mapped[list["InventoryMovement"]] = relationship(
        "InventoryMovement",
        back_populates="reservation",
        foreign_keys="InventoryMovement.reservation_id",
    )

    # Contraintes
    __table_args__ = (
        # Dates cohérentes
        CheckConstraint(
            "delivery_date <= event_date",
            name="check_reservation_delivery_before_event"
        ),
        CheckConstraint(
            "return_date >= event_date",
            name="check_reservation_return_after_event"
        ),
        CheckConstraint(
            "return_date >= delivery_date",
            name="check_reservation_return_after_delivery"
        ),
        # Statut valide (synchronisé avec ReservationStatus enum)
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'pre_check', 'confirmed_risk', 'delivered', 'extended', 'returned', 'returned_dispute', 'completed', 'cancelled')",
            name="check_reservation_status_valid"
        ),
        # Montants positifs
        CheckConstraint(
            "total_amount_cents >= 0",
            name="check_reservation_total_positive"
        ),
        CheckConstraint(
            "deposit_amount_cents >= 0",
            name="check_reservation_deposit_positive"
        ),
        # Nombre d'invités positif si renseigné
        CheckConstraint(
            "guest_count IS NULL OR guest_count > 0",
            name="check_reservation_guest_count_positive"
        ),
        # Frais livraison positifs
        CheckConstraint(
            "delivery_fee_cents >= 0",
            name="check_reservation_delivery_fee_positive"
        ),
        # Méthode livraison valide
        CheckConstraint(
            "delivery_method IS NULL OR delivery_method IN ('self', 'carrier', 'pickup')",
            name="check_reservation_delivery_method_valid"
        ),
    )

    deposits: Mapped[list["Deposit"]] = relationship(
        "Deposit",
        back_populates="reservation",
        cascade="all, delete-orphan"
    )

    risks: Mapped[list["ReservationRisk"]] = relationship(
        "ReservationRisk",
        back_populates="reservation",
        cascade="all, delete-orphan",
        foreign_keys="ReservationRisk.reservation_id"
    )

    pre_check_items: Mapped[list["ReservationPreCheckItem"]] = relationship(
        "ReservationPreCheckItem",
        back_populates="reservation",
        cascade="all, delete-orphan",
        foreign_keys="ReservationPreCheckItem.reservation_id",
        order_by="ReservationPreCheckItem.sort_order"
    )

    extensions: Mapped[list["ReservationExtension"]] = relationship(
        "ReservationExtension",
        back_populates="reservation",
        cascade="all, delete-orphan",
        foreign_keys="ReservationExtension.reservation_id"
    )

    def __repr__(self) -> str:
        return f"<Reservation(id={self.id}, ref='{self.reference}', status='{self.status}')>"


class ReservationLine(Base, TimestampMixin, TenantMixin):
    """Ligne de réservation - produit et quantité réservée.

    Attributes:
        reservation_id: ID de la réservation (FK)
        product_id: ID du produit (FK)
        quantity: Quantité réservée (> 0)
        unit_price: Prix unitaire par jour en CENTIMES (snapshot au moment de la réservation)
        subtotal: Sous-total en CENTIMES (quantity × unit_price)
    """

    __tablename__ = "reservation_lines"

    # Clé primaire
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Réservation
    reservation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID de la réservation"
    )

    # Produit (nullable — XOR avec bundle_id)
    product_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="ID du produit (NULL si ligne bundle)"
    )

    # Bundle (nullable — XOR avec product_id)
    bundle_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("product_bundles.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="ID du bundle (NULL si ligne produit)"
    )

    # Variante couleur (nullable si le produit n'a pas de variantes)
    variant_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="ID de la variante couleur choisie"
    )

    # Quantité
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Quantité réservée"
    )

    # Prix snapshot (en centimes)
    unit_price_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Prix unitaire par jour en centimes (snapshot)"
    )

    subtotal_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Sous-total en centimes (quantity × unit_price_cents)"
    )

    # TVA (snapshot au moment de la réservation)
    tva_rate: Mapped[float] = mapped_column(
        nullable=False,
        default=0.20,
        comment="Snapshot taux TVA au moment de la réservation (ex: 0.20 = 20%)"
    )

    # Relations
    reservation: Mapped["Reservation"] = relationship(
        "Reservation",
        back_populates="lines"
    )

    product: Mapped[Optional["Product"]] = relationship(
        "Product",
        back_populates="reservation_lines"
    )

    bundle: Mapped[Optional["ProductBundle"]] = relationship(
        "ProductBundle",
        foreign_keys=[bundle_id],
    )

    variant: Mapped[Optional["ProductVariant"]] = relationship(
        "ProductVariant",
        foreign_keys=[variant_id],
    )

    # Contraintes
    __table_args__ = (
        # Un même produit une seule fois par réservation (si product_id défini)
        Index(
            "uq_resa_line_product",
            "reservation_id", "product_id",
            unique=True,
            postgresql_where=text("product_id IS NOT NULL"),
        ),
        # Un même bundle une seule fois par réservation (si bundle_id défini)
        Index(
            "uq_resa_line_bundle",
            "reservation_id", "bundle_id",
            unique=True,
            postgresql_where=text("bundle_id IS NOT NULL"),
        ),
        # Exactement l'un des deux : product_id XOR bundle_id
        CheckConstraint(
            "(product_id IS NOT NULL AND bundle_id IS NULL) "
            "OR (product_id IS NULL AND bundle_id IS NOT NULL)",
            name="ck_resa_line_product_xor_bundle"
        ),
        # Quantité positive
        CheckConstraint(
            "quantity > 0",
            name="check_reservation_line_quantity_positive"
        ),
    )

    def __repr__(self) -> str:
        return f"<ReservationLine(id={self.id}, reservation_id={self.reservation_id}, qty={self.quantity})>"


class ReservationRisk(Base, TimestampMixin, TenantMixin):
    """Risque associé à une réservation (dépôt manquant, litige, etc.)."""

    __tablename__ = "reservation_risks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reservation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_at: Mapped[Optional[date]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    reservation: Mapped["Reservation"] = relationship(
        "Reservation", back_populates="risks", foreign_keys=[reservation_id]
    )

    def __repr__(self) -> str:
        return f"<ReservationRisk(id={self.id}, reservation_id={self.reservation_id}, severity={self.severity})>"


class ReservationPreCheckItem(Base, TenantMixin):
    """Item de checklist pré-départ pour une réservation."""

    __tablename__ = "reservation_pre_check_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reservation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    checked_at: Mapped[Optional[date]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    checked_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[date] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"
    )

    reservation: Mapped["Reservation"] = relationship(
        "Reservation", back_populates="pre_check_items", foreign_keys=[reservation_id]
    )

    def __repr__(self) -> str:
        return f"<ReservationPreCheckItem(id={self.id}, label={self.label!r}, checked={self.checked})>"


class ReservationExtension(Base, TenantMixin):
    """Extension de la durée d'une réservation."""

    __tablename__ = "reservation_extensions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reservation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_return_date: Mapped[date] = mapped_column(Date, nullable=False)
    new_return_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    extra_charge_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[date] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"
    )
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )

    reservation: Mapped["Reservation"] = relationship(
        "Reservation", back_populates="extensions", foreign_keys=[reservation_id]
    )

    def __repr__(self) -> str:
        return f"<ReservationExtension(id={self.id}, reservation_id={self.reservation_id}, new_return={self.new_return_date})>"


class ReservationReturnInspectionItem(Base, TimestampMixin, TenantMixin):
    """Constat de retour item-level (good/damaged/missing/partial).

    Source-of-truth pour calculer les charges à imputer sur la caution
    et déclencher RETURNED_DISPUTE quand un manquant/dégât est détecté.
    """

    __tablename__ = "reservation_return_inspection_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reservation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reservation_line_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("reservation_lines.id", ondelete="SET NULL"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity_expected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_returned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_damaged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_missing: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    condition: Mapped[str] = mapped_column(String(20), nullable=False, default="good")
    damage_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    charge_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    inspected_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    inspected_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "condition IN ('good','damaged','missing','partial')",
            name="check_inspection_condition",
        ),
        CheckConstraint(
            "quantity_returned >= 0 AND quantity_damaged >= 0 AND quantity_missing >= 0",
            name="check_inspection_quantities_positive",
        ),
        CheckConstraint("charge_cents >= 0", name="check_inspection_charge_positive"),
    )

    def __repr__(self) -> str:
        return (
            f"<ReservationReturnInspectionItem(id={self.id}, "
            f"reservation_id={self.reservation_id}, condition={self.condition})>"
        )


class ReservationDisputeLog(Base, TenantMixin):
    """Audit trail d'un litige sur retour (open/note/charge/resolve).

    Append-only : ligne immuable, jamais modifiée. Sert à reconstituer
    la chronologie d'un dispute pour clôture comptable.
    """

    __tablename__ = "reservation_dispute_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reservation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    charge_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('opened','note_added','charge_applied','resolved')",
            name="check_dispute_action",
        ),
        CheckConstraint("charge_cents >= 0", name="check_dispute_charge_positive"),
    )

    def __repr__(self) -> str:
        return (
            f"<ReservationDisputeLog(id={self.id}, "
            f"reservation_id={self.reservation_id}, action={self.action})>"
        )
