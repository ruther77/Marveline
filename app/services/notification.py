"""Service de notification email (SMTP) avec templates Jinja2."""
import logging
import re
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.services.invoice_pdf import _DEFAULT_BRAND

logger = logging.getLogger(__name__)


def _brand_or_default(brand: dict | None) -> dict:
    """Retourne brand fourni, ou le defaut Marveline centralise."""
    return brand or _DEFAULT_BRAND.copy()


class NotificationService:
    """Service d'envoi d'emails via SMTP.

    En dev: MailHog (localhost:1025) — pas d'auth, pas de TLS.
    En prod: SMTP réel avec TLS (configurable via env).
    """

    def __init__(self):
        template_dir = Path(__file__).parent.parent / "templates" / "emails"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html"]),
        )

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _format_amount(amount_cents: int) -> str:
        """Formate un montant en centimes vers un affichage EUR.

        Args:
            amount_cents: Montant en centimes (25000 = 250.00 EUR)

        Returns:
            Montant formaté (ex: "250,00 €")
        """
        euros = amount_cents / 100
        # Format avec 2 décimales, virgule décimale, espace insécable milliers
        formatted = f"{euros:,.2f}"
        # Swap separators: 1,250.00 → 1 250,00
        formatted = formatted.replace(",", "\x00").replace(".", ",").replace("\x00", "\u202f")
        return f"{formatted} €"

    @staticmethod
    def _html_to_text(html: str) -> str:
        """Conversion basique HTML → texte brut."""
        text = re.sub(r"<br\s*/?>", "\n", html)
        text = re.sub(r"</?p[^>]*>", "\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _render_and_send(self, template_name: str, to: str, subject: str, **context) -> bool:
        """Rend un template Jinja2 et envoie l'email.

        Le contexte peut inclure `brand` (dict {name, legal_name, email}).
        Si absent, les templates retombent sur le défaut "Marveline".
        """
        html_template = self.jinja_env.get_template(template_name)
        context.setdefault("brand", _DEFAULT_BRAND.copy())
        # frontend_url tenant-scoped : si brand.frontend_url present, prime sur global
        brand_fu = context["brand"].get("frontend_url") if isinstance(context.get("brand"), dict) else None
        effective_frontend_url = brand_fu or settings.FRONTEND_URL
        html_body = html_template.render(
            frontend_url=effective_frontend_url,
            subject=subject,
            **context,
        )
        text_body = self._html_to_text(html_body)
        return self._send_email(to, subject, html_body, text_body)

    # ── Password Reset (template inline — conservé tel quel) ──────────

    def send_password_reset_email(self, email: str, reset_url: str, brand_name: str = "Marveline") -> bool:
        """Envoie un email de réinitialisation de mot de passe."""
        subject = f"Password Reset Request — {brand_name}"
        html_body = (
            "<html><body>"
            "<h2>Password Reset</h2>"
            f"<p>You requested a password reset for your {brand_name} account.</p>"
            f'<p><a href="{reset_url}">Click here to reset your password</a></p>'
            "<p>This link expires in 30 minutes.</p>"
            "<p>If you did not request this, ignore this email.</p>"
            "</body></html>"
        )
        text_body = (
            "Password Reset\n\n"
            f"You requested a password reset for your {brand_name} account.\n"
            f"Reset your password: {reset_url}\n\n"
            "This link expires in 30 minutes.\n"
            "If you did not request this, ignore this email."
        )
        return self._send_email(email, subject, html_body, text_body)

    # ── Notifications métier (templates Jinja2) ───────────────────────

    def send_reservation_confirmed(
        self,
        email: str,
        customer_name: str,
        reference: str,
        event_date: date,
        delivery_date: date,
        return_date: date,
        event_location: str,
        total_cents: int,
        deposit_cents: int,
        brand: dict | None = None,
    ) -> bool:
        """Envoie la confirmation de réservation."""
        bn = (brand or {}).get("name", "Marveline")
        return self._render_and_send(
            "reservation_confirmed.html",
            to=email,
            subject=f"Réservation {reference} confirmée — {bn}",
            brand=_brand_or_default(brand),
            customer_name=customer_name,
            reference=reference,
            event_date=event_date,
            delivery_date=delivery_date,
            return_date=return_date,
            event_location=event_location,
            total_amount_display=self._format_amount(total_cents),
            deposit_amount_display=self._format_amount(deposit_cents),
        )

    def send_invoice_created(
        self,
        email: str,
        customer_name: str,
        invoice_number: str,
        reservation_reference: str,
        total_cents: int,
        due_date: date,
        issue_date: date,
        brand: dict | None = None,
    ) -> bool:
        """Envoie la notification de facture créée."""
        bn = (brand or {}).get("name", "Marveline")
        return self._render_and_send(
            "invoice_created.html",
            to=email,
            subject=f"Facture {invoice_number} — {bn}",
            brand=_brand_or_default(brand),
            customer_name=customer_name,
            invoice_number=invoice_number,
            reservation_reference=reservation_reference,
            total_amount_display=self._format_amount(total_cents),
            due_date=due_date,
            issue_date=issue_date,
        )

    def send_delivery_completed(
        self,
        email: str,
        customer_name: str,
        reservation_reference: str,
        delivery_address: str,
        delivery_date: date,
        brand: dict | None = None,
    ) -> bool:
        """Envoie la notification de livraison effectuée."""
        bn = (brand or {}).get("name", "Marveline")
        return self._render_and_send(
            "delivery_completed.html",
            to=email,
            subject=f"Livraison effectuée — {reservation_reference} — {bn}",
            brand=_brand_or_default(brand),
            customer_name=customer_name,
            reservation_reference=reservation_reference,
            delivery_address=delivery_address,
            delivery_date=delivery_date,
        )

    def send_return_completed(
        self,
        email: str,
        customer_name: str,
        reservation_reference: str,
        return_date: date,
        brand: dict | None = None,
    ) -> bool:
        """Envoie la notification de retour effectué."""
        bn = (brand or {}).get("name", "Marveline")
        return self._render_and_send(
            "return_completed.html",
            to=email,
            subject=f"Retour enregistré — {reservation_reference} — {bn}",
            brand=_brand_or_default(brand),
            customer_name=customer_name,
            reservation_reference=reservation_reference,
            return_date=return_date,
        )

    def send_deposit_reminder(
        self,
        email: str,
        customer_name: str,
        reservation_reference: str,
        event_date,
        amount_cents: int,
        brand: dict | None = None,
    ) -> bool:
        """Envoie un rappel d'acompte à payer avant l'événement."""
        bn = (brand or {}).get("name", "Marveline")
        return self._render_and_send(
            "deposit_reminder.html",
            to=email,
            subject=f"Rappel acompte — {reservation_reference} — {bn}",
            brand=_brand_or_default(brand),
            customer_name=customer_name,
            reservation_reference=reservation_reference,
            event_date=event_date,
            amount_euros=amount_cents / 100,
        )

    def send_supplier_order_confirmation(
        self,
        email: str,
        supplier_name: str,
        reference: str,
        order_date: str,
        expected_date: str,
        lines_count: int,
        total_cents: int,
        brand_name: str = "Marveline",
    ) -> bool:
        """Envoie une confirmation de commande au fournisseur."""
        subject = f"Commande {reference} — {brand_name}"
        html_body = (
            f"<p>Bonjour {supplier_name},</p>"
            f"<p>Nous vous confirmons la commande <strong>{reference}</strong>.</p>"
            f"<ul>"
            f"<li>Date de commande : {order_date}</li>"
            f"<li>Livraison souhaitee : {expected_date}</li>"
            f"<li>Nombre de lignes : {lines_count}</li>"
            f"<li>Total HT : {self._format_amount(total_cents)}</li>"
            f"</ul>"
            f"<p>Merci de confirmer la prise en charge.</p>"
            f"<p>Cordialement,<br>{brand_name}</p>"
        )
        text_body = self._html_to_text(html_body)
        return self._send_email(email, subject, html_body, text_body)

    # ── Transport SMTP ────────────────────────────────────────────────

    def _send_email(
        self, to: str, subject: str, html_body: str, text_body: str
    ) -> bool:
        """Envoie un email via SMTP."""
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = settings.SMTP_FROM
            msg["To"] = to
            msg["Subject"] = subject

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.sendmail(settings.SMTP_FROM, to, msg.as_string())

            logger.info("Email sent to %s: %s", to, subject)
            return True

        except Exception:
            logger.exception("Failed to send email to %s: %s", to, subject)
            return False


    async def send_plain_email(self, to: str, subject: str, body: str) -> None:
        """Envoie un email texte brut (sans template Jinja2).

        Raises:
            RuntimeError: si l'envoi échoue.
        """
        html_body = f"<pre>{body}</pre>"
        success = self._send_email(to, subject, html_body, body)
        if not success:
            raise RuntimeError(f"Email send failed for {to}")

    def send_relance_email(
        self,
        *,
        email: str,
        customer_name: str,
        invoice_number: str,
        invoice_total_cts: int,
        invoice_due_date: str,
        tenant_brand_name: str = "Marveline",
    ) -> bool:
        """F1058 fix Sprint 1 — envoi email de relance impayé via SMTP.

        Migration vers EmailGateway Postmark async = Bloc 6 §6.2.1 (B6.S1).

        Returns:
            True si gateway 200, False sinon (caller doit gérer le retry).
        """
        subject = f"Relance facture {invoice_number}"
        total_eur = invoice_total_cts / 100

        body_html = (
            "<html><body style=\"font-family: Arial, sans-serif;\">"
            f"<p>Bonjour {customer_name},</p>"
            f"<p>Sauf erreur de notre part, votre facture <strong>{invoice_number}</strong> "
            f"d'un montant de <strong>{total_eur:.2f} &euro;</strong> "
            f"(&eacute;ch&eacute;ance {invoice_due_date}) n'a pas encore &eacute;t&eacute; r&eacute;gl&eacute;e.</p>"
            f"<p>Merci de proc&eacute;der au r&egrave;glement dans les meilleurs d&eacute;lais.</p>"
            f"<p>Cordialement,<br>L'&eacute;quipe {tenant_brand_name}</p>"
            "</body></html>"
        )
        body_text = (
            f"Bonjour {customer_name},\n\n"
            f"Sauf erreur de notre part, votre facture {invoice_number} "
            f"d'un montant de {total_eur:.2f} EUR (echeance {invoice_due_date}) "
            f"n'a pas encore ete reglee.\n\n"
            f"Merci de proceder au reglement dans les meilleurs delais.\n\n"
            f"Cordialement,\nL'equipe {tenant_brand_name}"
        )

        return self._send_email(to=email, subject=subject, html_body=body_html, text_body=body_text)


notification_service = NotificationService()
