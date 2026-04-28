"""Modèles Devis — devis commerciaux et leurs sous-entités."""
from datetime import date, datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin
from app.constants import DevisStatus

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.reservation import Reservation
    from app.models.product import Product
    from app.models.bundle import ProductBundle
    from app.models.delivery_zone import DeliveryZone
from app.models.product_variant import ProductVariant


class Devis(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Devis commercial associé à un client.

    Statuts :
        draft          : Brouillon en cours de rédaction
        sent           : Envoyé au client, en attente de réponse
        negotiation    : En cours de négociation
        version_pending: Modification demandée, nouvelle version en cours
        accepted       : Accepté par le client
        refused        : Refusé par le client
        expired        : Date de validité dépassée
        converted      : Converti en réservation
        cancelled      : Annulé

    Attributes:
        reference: Référence unique (DEV-YYYY-NNNN) par tenant
        customer_id: FK vers le client
        valid_until: Date limite de validité du devis
        tva_rate: Taux TVA en centièmes de % (2000 = 20.00%)
        subtotal_cents: Montant HT total en centimes
        tva_cents: Montant TVA en centimes
        total_cents: Montant TTC total en centimes
        discount_pct: Remise globale en centièmes de % (500 = 5%)
        caution_required: Caution demandée au client
        caution_amount_cents: Montant caution en centimes
        converted_reservation_id: FK vers la réservation créée après conversion
    """

    __tablename__ = "devis"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    reference: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Référence unique DEV-YYYY-NNNN"
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers le client"
    )

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=DevisStatus.DRAFT,
        comment="Statut du devis"
    )

    event_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    event_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    delivery_date: Mapped[Optional[date]] = mapped_column(
        Date(), nullable=True,
        comment="Date de livraison prévue (propagée à la réservation lors de la conversion)"
    )
    return_date: Mapped[Optional[date]] = mapped_column(
        Date(), nullable=True,
        comment="Date de retour prévue (propagée à la réservation lors de la conversion)"
    )

    valid_until: Mapped[date] = mapped_column(
        Date(), nullable=False,
        comment="Date limite de validité"
    )

    tva_rate: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=2000,
        comment="Taux TVA en centièmes de % (2000 = 20.00%)"
    )

    subtotal_cents: Mapped[int] = mapped_column(
        BigInteger(), nullable=False, default=0,
        comment="Montant HT en centimes"
    )

    tva_cents: Mapped[int] = mapped_column(
        BigInteger(), nullable=False, default=0,
        comment="Montant TVA en centimes"
    )

    total_cents: Mapped[int] = mapped_column(
        BigInteger(), nullable=False, default=0,
        comment="Montant TTC en centimes"
    )

    discount_pct: Mapped[Optional[int]] = mapped_column(
        Integer(), nullable=True,
        comment="Remise globale en centièmes de % (500 = 5%)"
    )

    caution_required: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=False,
        comment="Caution demandée au client"
    )

    caution_amount_cents: Mapped[Optional[int]] = mapped_column(
        BigInteger(), nullable=True,
        comment="Montant caution en centimes"
    )

    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)

    conditions_paiement: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Conditions de paiement (30_acompte, 50_50, comptant, fin_evenement)"
    )

    message_accompagnement: Mapped[Optional[str]] = mapped_column(
        Text(), nullable=True,
        comment="Message d'accompagnement envoyé avec le devis"
    )

    signature_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
        comment="URL du fichier de signature électronique (base64 PNG stocké)"
    )

    signed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(), nullable=True,
        comment="Date et heure de la signature électronique"
    )

    refusal_reason: Mapped[Optional[str]] = mapped_column(
        Text(), nullable=True,
        comment="Raison du refus (renseignée lors du passage en status refused)"
    )

    # ── Livraison ─────────────────────────────────────────────────────────────
    delivery_method: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="Méthode : self, carrier, pickup"
    )
    delivery_fee_cents: Mapped[int] = mapped_column(
        BigInteger(), nullable=False, default=0,
        comment="Frais de livraison en centimes"
    )
    carrier_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Nom du transporteur (si delivery_method=carrier)"
    )
    carrier_code: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="Code transporteur Boxtal (si delivery_method=carrier)"
    )
    delivery_address: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
        comment="Adresse de livraison (rue, numéro)"
    )
    delivery_city: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Ville de livraison"
    )
    delivery_postal_code: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True,
        comment="Code postal de livraison"
    )
    delivery_zone_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("delivery_zones.id", ondelete="SET NULL"),
        nullable=True,
        comment="Zone de livraison (FK)"
    )
    delivery_instructions: Mapped[Optional[str]] = mapped_column(
        Text(), nullable=True,
        comment="Instructions de livraison"
    )

    # FK sans contrainte ORM pour éviter dépendance circulaire devis↔reservations
    converted_reservation_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="FK vers la réservation issue de la conversion"
    )

    # Relations
    customer: Mapped["Customer"] = relationship("Customer", foreign_keys=[customer_id])
    converted_reservation: Mapped[Optional["Reservation"]] = relationship(
        "Reservation",
        primaryjoin="foreign(Devis.converted_reservation_id) == Reservation.id",
        viewonly=True,
    )
    delivery_zone: Mapped[Optional["DeliveryZone"]] = relationship(
        "DeliveryZone",
        foreign_keys=[delivery_zone_id],
        lazy="joined",
    )
    lines: Mapped[list["DevisLine"]] = relationship(
        "DevisLine", back_populates="devis",
        cascade="all, delete-orphan", order_by="DevisLine.sort_order"
    )
    modules: Mapped[list["DevisModule"]] = relationship(
        "DevisModule", back_populates="devis",
        cascade="all, delete-orphan"
    )
    phases: Mapped[list["DevisPhase"]] = relationship(
        "DevisPhase", back_populates="devis",
        cascade="all, delete-orphan", order_by="DevisPhase.sort_order"
    )
    versions: Mapped[list["DevisVersion"]] = relationship(
        "DevisVersion", back_populates="devis",
        cascade="all, delete-orphan", order_by="DevisVersion.version_number"
    )
    negotiations: Mapped[list["DevisNegotiation"]] = relationship(
        "DevisNegotiation", back_populates="devis",
        cascade="all, delete-orphan"
    )
    change_requests: Mapped[list["DevisChangeRequest"]] = relationship(
        "DevisChangeRequest", back_populates="devis",
        cascade="all, delete-orphan"
    )
    coverage_items: Mapped[list["DevisCoverageItem"]] = relationship(
        "DevisCoverageItem", back_populates="devis",
        cascade="all, delete-orphan",
        order_by="DevisCoverageItem.sort_order"
    )
    attachments: Mapped[list["DevisAttachment"]] = relationship(
        "DevisAttachment", back_populates="devis",
        cascade="all, delete-orphan",
        order_by="DevisAttachment.sort_order"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "reference", name="uq_devis_tenant_reference"),
        CheckConstraint(
            "status IN ('draft','sent','negotiation','accepted','refused',"
            "'expired','converted','cancelled','version_pending')",
            name="check_devis_status_valid"
        ),
        CheckConstraint("total_cents >= 0", name="check_devis_total_positive"),
        CheckConstraint("delivery_fee_cents >= 0", name="check_devis_delivery_fee_positive"),
        CheckConstraint(
            "delivery_method IS NULL OR delivery_method IN ('self', 'carrier', 'pickup')",
            name="check_devis_delivery_method_valid"
        ),
        Index("ix_devis_tenant_id_composite", "tenant_id", "id"),
        Index("ix_devis_tenant_status", "tenant_id", "status"),
        Index("ix_devis_tenant_customer", "tenant_id", "customer_id"),
    )

    def __repr__(self) -> str:
        return f"<Devis(id={self.id}, ref='{self.reference}', status='{self.status}')>"


class DevisLine(Base, TimestampMixin, TenantMixin):
    """Ligne d'un devis commercial.

    Attributes:
        devis_id: FK vers le devis parent
        product_id: FK optionnelle vers un produit catalogue
        label: Description de la prestation/produit
        quantity: Quantité (> 0)
        unit_price_cents: Prix unitaire en centimes (>= 0)
        discount_pct: Remise en centièmes de % (0 = pas de remise)
        subtotal_cents: Sous-total calculé (qty × prix × (1 - discount/10000))
        sort_order: Ordre d'affichage
    """

    __tablename__ = "devis_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    devis_id: Mapped[int] = mapped_column(
        ForeignKey("devis.id", ondelete="CASCADE"), nullable=False
    )

    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )

    bundle_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("product_bundles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID du bundle (NULL si ligne produit ou libre)"
    )

    variant_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="ID de la variante choisie (NULL si bundle ou libre)"
    )

    label: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer(), nullable=False, default=1)
    unit_price_cents: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    discount_pct: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    subtotal_cents: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)

    devis: Mapped["Devis"] = relationship("Devis", back_populates="lines")
    product: Mapped[Optional["Product"]] = relationship("Product")
    bundle: Mapped[Optional["ProductBundle"]] = relationship(
        "ProductBundle", foreign_keys=[bundle_id]
    )
    variant: Mapped[Optional["ProductVariant"]] = relationship(
        "ProductVariant", foreign_keys=[variant_id]
    )

    __table_args__ = (
        CheckConstraint("unit_price_cents >= 0", name="check_devis_line_price_positive"),
        CheckConstraint("quantity > 0", name="check_devis_line_qty_positive"),
        Index("ix_devis_lines_tenant_devis", "tenant_id", "devis_id"),
    )

    def __repr__(self) -> str:
        return f"<DevisLine(id={self.id}, devis={self.devis_id}, label='{self.label}')>"


class DevisLineHistory(Base, TimestampMixin, TenantMixin):
    """Historique des modifications ligne par ligne d'un devis.

    Chaque creation, modification ou suppression d'une DevisLine
    genere une entree dans cette table. Append-only.

    Attributes:
        devis_id: FK vers le devis parent
        devis_line_id: FK vers la ligne (nullable si supprimee)
        action: create | update | delete
        old_values: Valeurs avant modification (JSON, null pour create)
        new_values: Valeurs apres modification (JSON, null pour delete)
        changed_by: ID de l'utilisateur qui a fait le changement
    """

    __tablename__ = "devis_line_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    devis_id: Mapped[int] = mapped_column(
        ForeignKey("devis.id", ondelete="CASCADE"), nullable=False
    )

    devis_line_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="ID de la ligne (null si supprimee avant enregistrement)"
    )

    action: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="Action: create | update | delete"
    )

    old_values: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="Valeurs avant modification (null pour create)"
    )

    new_values: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="Valeurs apres modification (null pour delete)"
    )

    changed_by: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="ID de l'utilisateur"
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('create', 'update', 'delete')",
            name="ck_devis_line_history_action"
        ),
        Index("ix_devis_line_history_devis", "devis_id"),
        Index("ix_devis_line_history_line", "devis_line_id"),
    )

    def __repr__(self) -> str:
        return f"<DevisLineHistory(id={self.id}, devis={self.devis_id}, action='{self.action}')>"


class DevisModule(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Module structurant d'un devis (socle, stock, facturation, sécurité, services).

    Attributes:
        module_type: Type parmi socle|stock|facturation|securite|services
        label: Titre du module
        content_json: Contenu structuré JSON du module
    """

    __tablename__ = "devis_modules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    devis_id: Mapped[int] = mapped_column(
        ForeignKey("devis.id", ondelete="CASCADE"), nullable=False
    )

    module_type: Mapped[str] = mapped_column(String(30), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    content_json: Mapped[dict] = mapped_column(JSON(), nullable=False, default=dict)
    delivery_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="a_cadrer"
    )

    devis: Mapped["Devis"] = relationship("Devis", back_populates="modules")

    __table_args__ = (
        CheckConstraint(
            "module_type IN ('socle','stock','facturation','securite','services')",
            name="check_devis_module_type_valid"
        ),
        CheckConstraint(
            "delivery_status IN ('a_cadrer','en_cours','livre')",
            name="check_devis_module_delivery_status_valid"
        ),
        Index("ix_devis_modules_tenant_devis", "tenant_id", "devis_id"),
    )

    def __repr__(self) -> str:
        return f"<DevisModule(id={self.id}, type='{self.module_type}', devis={self.devis_id})>"


class DevisPhase(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Phase temporelle d'un devis.

    Attributes:
        label: Description de la phase
        date_start: Date de début
        date_end: Date de fin (>= date_start)
        sort_order: Ordre d'affichage
    """

    __tablename__ = "devis_phases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    devis_id: Mapped[int] = mapped_column(
        ForeignKey("devis.id", ondelete="CASCADE"), nullable=False
    )

    label: Mapped[str] = mapped_column(String(255), nullable=False)
    date_start: Mapped[date] = mapped_column(Date(), nullable=False)
    date_end: Mapped[date] = mapped_column(Date(), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)

    devis: Mapped["Devis"] = relationship("Devis", back_populates="phases")

    __table_args__ = (
        CheckConstraint("date_end >= date_start", name="check_devis_phase_dates_valid"),
        Index("ix_devis_phases_tenant_devis", "tenant_id", "devis_id"),
    )

    def __repr__(self) -> str:
        return f"<DevisPhase(id={self.id}, label='{self.label}', devis={self.devis_id})>"


class DevisVersion(Base, TenantMixin):
    """Snapshot immuable d'un devis à un instant donné.

    Pas de TimestampMixin (created_at uniquement, updated_at n'a pas de sens).
    Pas de SoftDeleteMixin (les snapshots sont des archives immuables).

    Attributes:
        version_number: Numéro de version incrémental par devis
        snapshot_json: Snapshot complet du devis au moment de la version
        created_by: FK vers l'utilisateur ayant créé la version
        created_at: Timestamp de création (immuable)
    """

    __tablename__ = "devis_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    devis_id: Mapped[int] = mapped_column(
        ForeignKey("devis.id", ondelete="CASCADE"), nullable=False
    )

    version_number: Mapped[int] = mapped_column(Integer(), nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON(), nullable=False)

    created_by: Mapped[int] = mapped_column(BigInteger(), nullable=False)

    created_at: Mapped[datetime] = mapped_column(nullable=False)

    devis: Mapped["Devis"] = relationship("Devis", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("devis_id", "version_number", name="uq_devis_version"),
        Index("ix_devis_versions_tenant_devis", "tenant_id", "devis_id"),
    )

    def __repr__(self) -> str:
        return f"<DevisVersion(id={self.id}, devis={self.devis_id}, v={self.version_number})>"


class DevisNegotiation(Base, TenantMixin):
    """Message de négociation sur un devis.

    Pas de SoftDeleteMixin (les messages sont archivés, pas supprimés).
    Pas de updated_at (immuable après création).

    Attributes:
        author_id: FK vers l'utilisateur auteur du message
        message: Contenu du message
        proposed_amount_cents: Montant proposé en centimes (optionnel)
        created_at: Timestamp de création
    """

    __tablename__ = "devis_negotiations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    devis_id: Mapped[int] = mapped_column(
        ForeignKey("devis.id", ondelete="CASCADE"), nullable=False
    )

    author_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)

    message: Mapped[str] = mapped_column(Text(), nullable=False)
    proposed_amount_cents: Mapped[Optional[int]] = mapped_column(BigInteger(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(nullable=False)

    devis: Mapped["Devis"] = relationship("Devis", back_populates="negotiations")

    __table_args__ = (
        Index("ix_devis_negotiations_tenant_devis", "tenant_id", "devis_id"),
    )

    def __repr__(self) -> str:
        return f"<DevisNegotiation(id={self.id}, devis={self.devis_id})>"


class DevisChangeRequest(Base, TimestampMixin, TenantMixin):
    """Demande de modification sur un devis.

    Attributes:
        author_id: FK vers l'auteur de la demande
        description: Description de la modification demandée
        status: État de la demande (pending|accepted|refused)
    """

    __tablename__ = "devis_change_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    devis_id: Mapped[int] = mapped_column(
        ForeignKey("devis.id", ondelete="CASCADE"), nullable=False
    )

    author_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)

    description: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )

    devis: Mapped["Devis"] = relationship("Devis", back_populates="change_requests")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','accepted','refused')",
            name="check_change_request_status_valid"
        ),
        Index("ix_devis_change_requests_tenant_devis", "tenant_id", "devis_id"),
    )

    def __repr__(self) -> str:
        return f"<DevisChangeRequest(id={self.id}, devis={self.devis_id}, status='{self.status}')>"


class DevisCoverageItem(Base, TimestampMixin, TenantMixin):
    """Item de la matrice de couverture fonctionnelle d'un devis.

    Représente un livrable ou une fonctionnalité contractuelle avec son statut
    de réalisation (a_cadrer | en_cours | livre).

    Attributes:
        devis_id: Devis parent
        title: Intitulé de l'item
        description: Détail / critère de recette
        status: État de réalisation
        sort_order: Ordre d'affichage dans la matrice
    """

    __tablename__ = "devis_coverage_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    devis_id: Mapped[int] = mapped_column(
        ForeignKey("devis.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="a_cadrer"
    )
    sort_order: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)

    devis: Mapped["Devis"] = relationship("Devis", back_populates="coverage_items")

    __table_args__ = (
        CheckConstraint(
            "status IN ('a_cadrer','en_cours','livre')",
            name="check_devis_coverage_item_status_valid"
        ),
        Index("ix_devis_coverage_items_tenant_devis", "tenant_id", "devis_id"),
    )

    def __repr__(self) -> str:
        return f"<DevisCoverageItem(id={self.id}, devis={self.devis_id}, status='{self.status}')>"


class DevisAttachment(Base, TimestampMixin, TenantMixin):
    """Piece jointe d'un devis (PDF, images).

    Stockage : fichier sur disque dans uploads/devis/{devis_id}/
    MIME types autorises : PDF, JPEG, PNG, WEBP
    Limites : 10 MB par fichier, 10 fichiers max par devis

    Attributes:
        devis_id: FK vers le devis parent
        filename: Nom original du fichier
        mime_type: Type MIME (application/pdf, image/jpeg, etc.)
        file_path: Chemin relatif du fichier stocke
        file_size: Taille en octets
        uploaded_by: ID de l'utilisateur qui a uploade
        sort_order: Ordre d'affichage
    """

    __tablename__ = "devis_attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    devis_id: Mapped[int] = mapped_column(
        ForeignKey("devis.id", ondelete="CASCADE"), nullable=False
    )

    filename: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Nom original du fichier"
    )

    mime_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Type MIME (application/pdf, image/jpeg, image/png, image/webp)"
    )

    file_path: Mapped[str] = mapped_column(
        String(500), nullable=False,
        comment="Chemin relatif du fichier stocke"
    )

    file_size: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Taille en octets"
    )

    uploaded_by: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="ID de l'utilisateur"
    )

    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    devis: Mapped["Devis"] = relationship("Devis", back_populates="attachments")

    __table_args__ = (
        CheckConstraint(
            "mime_type IN ('application/pdf', 'image/jpeg', 'image/png', 'image/webp')",
            name="ck_devis_attachments_mime"
        ),
        CheckConstraint("file_size > 0 AND file_size <= 10485760", name="ck_devis_attachments_size"),
        Index("ix_devis_attachments_devis", "devis_id"),
    )

    def __repr__(self) -> str:
        return f"<DevisAttachment(id={self.id}, devis={self.devis_id}, file='{self.filename}')>"
