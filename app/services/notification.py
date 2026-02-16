"""Service de notification email (SMTP)."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Service d'envoi d'emails via SMTP.

    En dev: MailHog (localhost:1025) — pas d'auth, pas de TLS.
    En prod: SMTP réel avec TLS (configurable via env).
    """

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

    def _send_email(
        self, to: str, subject: str, html_body: str, text_body: str
    ) -> bool:
        """Envoie un email via SMTP.

        Args:
            to: Adresse destinataire
            subject: Sujet
            html_body: Corps HTML
            text_body: Corps texte brut (fallback)

        Returns:
            True si envoi réussi
        """
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
