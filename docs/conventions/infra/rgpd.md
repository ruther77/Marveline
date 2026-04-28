# Infra — RGPD

## Principes

- Minimisation des données : collecter uniquement ce qui est nécessaire
- Durée de rétention définie par catégorie de données
- Droit à l'oubli implémenté
- Audit trail sur toutes les mutations de données personnelles
- Anonymisation avant export/logs

## Catégories de Données et Rétention

```python
# app/constants/rgpd.py
DATA_RETENTION_DAYS = {
    "user_sessions": 90,
    "audit_logs": 365 * 7,   # 7 ans (obligations légales)
    "invoices": 365 * 10,    # 10 ans (comptabilité)
    "personal_data": 365 * 3, # 3 ans après dernière activité
    "marketing_data": 365,   # 1 an
    "technical_logs": 90,
}
```

## Anonymisation

```python
import hashlib
import re

def anonymize_email(email: str) -> str:
    """one-way anonymisation pour logs et analytics"""
    return hashlib.sha256(email.encode()).hexdigest()[:16] + "@anon.invalid"

def anonymize_phone(phone: str) -> str:
    return re.sub(r'\d(?=\d{4})', '*', phone)

def anonymize_name(name: str) -> str:
    parts = name.split()
    return " ".join(p[0] + "***" for p in parts)

def scrub_pii_from_log(log_data: dict) -> dict:
    """Supprimer les PII avant d'écrire dans les logs"""
    sensitive_fields = {"email", "phone", "address", "iban", "card_number"}
    return {
        k: "[REDACTED]" if k in sensitive_fields else v
        for k, v in log_data.items()
    }
```

## Droit à l'Oubli (Right to Erasure)

```python
class UserDeletionService:
    """Implémentation RGPD Article 17 — Droit à l'effacement"""

    def __init__(self, db: Session):
        self.db = db

    def erase_user(self, tenant_id: int, user_id: int, reason: str) -> dict:
        """
        Anonymiser les données personnelles tout en préservant
        l'intégrité des données comptables (obligations légales)
        """
        user = self.db.query(User).filter(
            User.tenant_id == tenant_id,
            User.id == user_id,
        ).first()

        if not user:
            raise NotFound(f"User {user_id} not found")

        # Log d'audit avant anonymisation
        self._log_erasure_request(user_id, reason)

        # Anonymiser les données personnelles
        user.email = f"deleted_{user.id}@erased.invalid"
        user.first_name = "[DELETED]"
        user.last_name = "[DELETED]"
        user.phone = None
        user.address = None
        user.is_active = False
        user.erased_at = datetime.utcnow()
        user.erasure_reason = reason

        # NE PAS supprimer :
        # - Les factures (obligations comptables 10 ans)
        # - Les logs d'audit (traçabilité légale)
        # - Les réservations passées (intégrité financière)

        self.db.commit()

        return {
            "user_id": user_id,
            "erased_at": user.erased_at.isoformat(),
            "preserved": ["invoices", "audit_logs", "reservations"],
        }

    def _log_erasure_request(self, user_id: int, reason: str):
        audit = AuditLog(
            action="user.erased",
            entity_type="user",
            entity_id=user_id,
            details={"reason": reason},
        )
        self.db.add(audit)
```

## Export des Données (Portabilité)

```python
class DataExportService:
    """RGPD Article 20 — Portabilité des données"""

    def export_user_data(self, tenant_id: int, user_id: int) -> dict:
        """Exporter toutes les données d'un utilisateur en JSON"""
        user = self._get_user(tenant_id, user_id)
        reservations = self._get_reservations(tenant_id, user_id)
        invoices = self._get_invoices(tenant_id, user_id)

        return {
            "export_date": datetime.utcnow().isoformat(),
            "user": {
                "email": user.email,
                "name": f"{user.first_name} {user.last_name}",
                "created_at": user.created_at.isoformat(),
            },
            "reservations": [r.model_dump() for r in reservations],
            "invoices": [i.model_dump() for i in invoices],
        }
```

## Consentement

```python
class ConsentRecord(Base, TimestampMixin):
    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    consent_type: Mapped[str] = mapped_column(String(50), nullable=False)  # marketing, analytics...
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(500))
    # Ne jamais modifier un enregistrement de consentement — append-only
```

## Cleanup Automatique (Celery)

```python
@celery_app.task
def cleanup_expired_personal_data():
    """Tâche quotidienne : anonymiser les données expirées"""
    cutoff = datetime.utcnow() - timedelta(days=DATA_RETENTION_DAYS["personal_data"])

    with get_db_context() as db:
        expired_users = db.query(User).filter(
            User.last_active_at < cutoff,
            User.erased_at.is_(None),
        ).all()

        for user in expired_users:
            erasure_service.erase_user(
                user.tenant_id, user.id,
                reason="auto_retention_policy"
            )
```

## Règles

- Jamais de PII dans les logs — `scrub_pii_from_log()` avant logging
- Jamais de PII dans les traces OpenTelemetry
- Droit à l'oubli = anonymisation, pas suppression (intégrité comptable)
- Consentements = append-only (pas de UPDATE)
- Durées de rétention définies dans les constantes, pas hardcodées
- Audit trail sur toute opération impliquant des données personnelles
