"""Modèle ORM TenantSettings — paramètres métier par tenant."""
from sqlalchemy import Boolean, Column, Float, Integer, String

from app.models.base import Base, TimestampMixin


class TenantSettings(Base, TimestampMixin):
    __tablename__ = "tenant_settings"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, unique=True, index=True)

    # Identité société
    company_name = Column(String(200), nullable=True)
    company_email = Column(String(200), nullable=True)
    company_phone = Column(String(50), nullable=True)
    company_address = Column(String(500), nullable=True)

    # Paramètres fiscaux
    vat_rate = Column(Float, nullable=False, default=0.20)

    # Tarifs main-d'œuvre (EUR/heure)
    hourly_rate_weekday = Column(Float, nullable=False, default=30.0)
    hourly_rate_weekend = Column(Float, nullable=False, default=60.0)

    # Paramètres réservation
    default_currency = Column(String(3), nullable=False, default="EUR")

    # CGV Marveline — paramètres financiers réservation
    advance_rate = Column(Float, nullable=False, default=0.40)
    """Taux d'acompte : 40% du montant TTC dû à la confirmation."""

    deposit_multiplier = Column(Float, nullable=False, default=3.0)
    """Caution = deposit_multiplier × montant TTC facture."""

    cancellation_threshold_days = Column(Integer, nullable=False, default=15)
    """Seuil (jours avant événement) pour distinguer annulation tardive."""

    cancellation_early_penalty_rate = Column(Float, nullable=False, default=0.40)
    """Pénalité annulation avant seuil : taux conservé (ex: 0.40 = acompte)."""

    cancellation_late_penalty_rate = Column(Float, nullable=False, default=1.0)
    """Pénalité annulation après seuil : taux du total facturé (1.0 = 100%)."""

    # Guards livraison (cf. analyse 2026-04-26 — défauts de design détectés)
    block_delivery_without_advance = Column(
        Boolean, nullable=False, default=True, server_default="true",
        comment="Bloque /deliver si acompte non encaissé. False = facturation à terme (B2B).",
    )
    """Bloque la livraison tant que l'acompte n'est pas payé.

    True par défaut (loueur événementiel B2C standard).
    False pour les modèles B2B sur compte courant.
    """

    require_signature_before_delivery = Column(
        Boolean, nullable=False, default=True, server_default="true",
        comment="Exige signature_url avant /deliver.",
    )
    """Exige la signature du contrat de location avant livraison.

    True par défaut (protection juridique loueur).
    False pour les workflows physiques (papier signé hors-app).
    """

    # Logistique — adresse d'expédition
    origin_postal_code = Column(String(20), nullable=True, comment="Code postal entrepôt (pour devis transporteurs)")

    # Impression tickets (ESC/POS réseau)
    printer_host = Column(String(100), nullable=True, comment="IP imprimante ticket (ex: 192.168.1.50)")
    printer_port = Column(Integer, nullable=False, default=9100, comment="Port TCP imprimante (défaut 9100)")

    # Infos commerce (en-tête ticket)
    nom_commerce = Column(String(200), nullable=True, comment="Nom affiché sur ticket")
    adresse = Column(String(500), nullable=True, comment="Adresse sur ticket")
    siret = Column(String(20), nullable=True, comment="SIRET sur ticket")
    telephone = Column(String(20), nullable=True, comment="Tél. sur ticket")

    # Identite tenant-scoped (emails, MFA QR code)
    frontend_url = Column(String(500), nullable=True, comment="URL frontend (emails). NULL = fallback settings.FRONTEND_URL")
    mfa_issuer_name = Column(String(100), nullable=True, comment="Issuer TOTP authenticator. NULL = fallback settings.MFA_ISSUER_NAME")

    # ── Reporting (uplift CA hors POS) ───────────────────────────────────────
    # Pour les commerces (resto, bar) qui ont un volume de ventes hors POS
    # (commandes réservées, événements, prépaiements) non encore intégrées
    # dans l'app, on applique un coefficient correctif au CA jour pour le
    # reporting. Ex: 12 = +12% appliqué au ca_cts. Default 0 (= POS pur).
    reservation_uplift_pct = Column(
        Integer, nullable=False, default=0,
        comment="% d'uplift appliqué au CA jour pour intégrer les commandes "
                "réservées hors POS. 0 = aucun, 12 = +12%.",
    )
