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

logger = logging.getLogger(__name__)


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

        Args:
            template_name: Nom du fichier template (ex: "reservation_confirmed.html")
            to: Adresse destinataire
            subject: Sujet de l'email
            **context: Variables passées au template

        Returns:
            True si envoi réussi
        """
        html_template = self.jinja_env.get_template(template_name)
        html_body = html_template.render(
            frontend_url=settings.FRONTEND_URL,
            subject=subject,
            **context,
        )
        text_body = self._html_to_text(html_body)
        return self._send_email(to, subject, html_body, text_body)

    # ── Password Reset (template inline — conservé tel quel) ──────────

    def send_password_reset_email(self, email: str, reset_url: str) -> bool:
        """Envoie un email de réinitialisation de mot de passe.

        Args:
            email: Adresse destinataire
            reset_url: URL complète avec token pour le reset

        Returns:
            True si envoi réussi, False sinon
        """
        subject = "Password Reset Request — Marveline"
        html_body = (
            "<html><body>"
            "<h2>Password Reset</h2>"
            "<p>You requested a password reset for your Marveline account.</p>"
            f'<p><a href="{reset_url}">Click here to reset your password</a></p>'
            "<p>This link expires in 30 minutes.</p>"
            "<p>If you did not request this, ignore this email.</p>"
            "</body></html>"
        )
        text_body = (
            "Password Reset\n\n"
            "You requested a password reset for your Marveline account.\n"
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
    ) -> bool:
        """Envoie la confirmation de réservation."""
        return self._render_and_send(
            "reservation_confirmed.html",
            to=email,
            subject=f"Réservation {reference} confirmée — Marveline",
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
    ) -> bool:
        """Envoie la notification de facture créée."""
        return self._render_and_send(
            "invoice_created.html",
            to=email,
            subject=f"Facture {invoice_number} — Marveline",
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
    ) -> bool:
        """Envoie la notification de livraison effectuée."""
        return self._render_and_send(
            "delivery_completed.html",
            to=email,
            subject=f"Livraison effectuée — {reservation_reference} — Marveline",
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
    ) -> bool:
        """Envoie la notification de retour effectué."""
        return self._render_and_send(
            "return_completed.html",
            to=email,
            subject=f"Retour enregistré — {reservation_reference} — Marveline",
            customer_name=customer_name,
            reservation_reference=reservation_reference,
            return_date=return_date,
        )

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


notification_service = NotificationService()
