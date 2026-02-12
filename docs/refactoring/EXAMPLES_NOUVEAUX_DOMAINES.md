# Exemples de Nouveaux Domaines de Constantes

**Date** : 2026-02-12
**Statut** : Exemples à implémenter au besoin

Ce document montre des **exemples concrets** de nouveaux domaines de constantes que vous pourriez créer quand le besoin apparaît.

---

## 🔔 Exemple 1 : Notifications

**Quand créer ?** Lorsque vous ajoutez un système de notifications dans l'application.

### Fichier : `app/constants/notifications.py`

```python
"""Constantes pour le système de notifications.

Ce module centralise :
- Statuts des notifications
- Types de notifications
- Priorités
- Canaux de diffusion
"""

from enum import Enum


class NotificationStatus(str, Enum):
    """Statut d'une notification.

    Workflow :
        PENDING → SENT → DELIVERED
                       ↘ FAILED → RETRY

    Utilisé dans :
        - models.Notification.status
        - services.NotificationService (envoi async)
    """

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"


class NotificationType(str, Enum):
    """Type de notification.

    Utilisé dans :
        - models.Notification.type
        - Sélection du template approprié
    """

    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


class NotificationPriority(str, Enum):
    """Priorité d'envoi.

    Utilisé dans :
        - models.Notification.priority
        - Queue prioritaire (high → queue rapide)
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationChannel:
    """Canaux de diffusion des notifications.

    Usage :
        channel = NotificationChannel.get_channel(NotificationType.EMAIL)
    """

    EMAIL_SMTP_HOST = "smtp.gmail.com"
    EMAIL_SMTP_PORT = 587
    SMS_PROVIDER_URL = "https://api.sms-provider.com"

    @staticmethod
    def get_channel(notification_type: NotificationType) -> str:
        """Retourne le canal approprié selon le type."""
        mapping = {
            NotificationType.EMAIL: "email_queue",
            NotificationType.SMS: "sms_queue",
            NotificationType.PUSH: "push_queue",
            NotificationType.IN_APP: "in_app_queue",
        }
        return mapping.get(notification_type, "default_queue")


__all__ = [
    "NotificationStatus",
    "NotificationType",
    "NotificationPriority",
    "NotificationChannel",
]
```

### Intégration dans `__init__.py`

```python
# app/constants/__init__.py
from app.constants.notifications import (
    NotificationStatus,
    NotificationType,
    NotificationPriority,
    NotificationChannel,
)

__all__ = [
    # ... existants
    "NotificationStatus",
    "NotificationType",
    "NotificationPriority",
    "NotificationChannel",
]
```

### Usage

```python
from app.constants import NotificationStatus, NotificationType

notification = Notification(
    type=NotificationType.EMAIL,
    status=NotificationStatus.PENDING,
    priority=NotificationPriority.HIGH
)

# Dans le service
if notification.status == NotificationStatus.PENDING:
    await send_notification(notification)
    notification.status = NotificationStatus.SENT
```

---

## 📧 Exemple 2 : Emails

**Quand créer ?** Lorsque vous avez des templates d'emails standardisés.

### Fichier : `app/constants/emails.py`

```python
"""Constantes pour les emails transactionnels.

Ce module centralise :
- Templates d'emails
- Sujets standardisés
- Expéditeurs
"""


class EmailTemplates:
    """Templates d'emails (noms de fichiers Jinja2).

    Usage :
        template = EmailTemplates.RESERVATION_CONFIRMED
        # → charge "emails/reservation_confirmed.html"
    """

    # ─────────────────────────────────────────────────────────────────────
    # Réservations
    # ─────────────────────────────────────────────────────────────────────

    RESERVATION_CONFIRMED = "emails/reservation_confirmed.html"
    RESERVATION_CANCELLED = "emails/reservation_cancelled.html"
    RESERVATION_REMINDER = "emails/reservation_reminder.html"

    # ─────────────────────────────────────────────────────────────────────
    # Factures
    # ─────────────────────────────────────────────────────────────────────

    INVOICE_SENT = "emails/invoice_sent.html"
    INVOICE_PAID = "emails/invoice_paid.html"
    INVOICE_OVERDUE = "emails/invoice_overdue.html"

    # ─────────────────────────────────────────────────────────────────────
    # Authentification
    # ─────────────────────────────────────────────────────────────────────

    WELCOME = "emails/welcome.html"
    PASSWORD_RESET = "emails/password_reset.html"
    VERIFY_EMAIL = "emails/verify_email.html"


class EmailSubjects:
    """Sujets d'emails standardisés.

    Usage :
        subject = EmailSubjects.RESERVATION_CONFIRMED
    """

    # Réservations
    RESERVATION_CONFIRMED = "Votre réservation est confirmée"
    RESERVATION_CANCELLED = "Réservation annulée"
    RESERVATION_REMINDER = "Rappel : votre événement approche"

    # Factures
    INVOICE_SENT = "Facture n°{invoice_number}"
    INVOICE_PAID = "Paiement reçu - Facture n°{invoice_number}"
    INVOICE_OVERDUE = "Facture en retard - Action requise"

    # Authentification
    WELCOME = "Bienvenue sur CaroCorp !"
    PASSWORD_RESET = "Réinitialisation de votre mot de passe"
    VERIFY_EMAIL = "Vérifiez votre adresse email"

    @staticmethod
    def invoice_sent(invoice_number: str) -> str:
        """Génère le sujet d'une facture envoyée."""
        return EmailSubjects.INVOICE_SENT.format(invoice_number=invoice_number)


class EmailSenders:
    """Adresses d'expéditeur.

    Usage :
        from_email = EmailSenders.NO_REPLY
    """

    NO_REPLY = "noreply@carocorp.fr"
    SUPPORT = "support@carocorp.fr"
    BILLING = "facturation@carocorp.fr"
    RESERVATIONS = "reservations@carocorp.fr"


__all__ = [
    "EmailTemplates",
    "EmailSubjects",
    "EmailSenders",
]
```

### Usage

```python
from app.constants import EmailTemplates, EmailSubjects, EmailSenders

await send_email(
    to=customer.email,
    from_email=EmailSenders.RESERVATIONS,
    subject=EmailSubjects.RESERVATION_CONFIRMED,
    template=EmailTemplates.RESERVATION_CONFIRMED,
    context={"reservation": reservation}
)
```

---

## 📁 Exemple 3 : Files (Upload de Fichiers)

**Quand créer ?** Lorsque vous permettez l'upload de fichiers (photos de produits, documents, etc.).

### Fichier : `app/constants/files.py`

```python
"""Constantes pour la gestion des fichiers uploadés.

Ce module centralise :
- Types de fichiers autorisés
- Tailles maximales
- Chemins de stockage
"""

from enum import Enum


class AllowedFileTypes:
    """Types MIME autorisés pour les uploads.

    Usage :
        if file.content_type not in AllowedFileTypes.IMAGES:
            raise ValueError("Type de fichier non autorisé")
    """

    # ─────────────────────────────────────────────────────────────────────
    # Images
    # ─────────────────────────────────────────────────────────────────────

    IMAGE_JPEG = "image/jpeg"
    IMAGE_PNG = "image/png"
    IMAGE_WEBP = "image/webp"

    IMAGES = frozenset([IMAGE_JPEG, IMAGE_PNG, IMAGE_WEBP])

    # ─────────────────────────────────────────────────────────────────────
    # Documents
    # ─────────────────────────────────────────────────────────────────────

    PDF = "application/pdf"
    WORD = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    DOCUMENTS = frozenset([PDF, WORD, EXCEL])

    # ─────────────────────────────────────────────────────────────────────
    # Tous types autorisés
    # ─────────────────────────────────────────────────────────────────────

    ALL_ALLOWED = IMAGES | DOCUMENTS


class MaxFileSizes:
    """Tailles maximales de fichiers (en bytes).

    Usage :
        if file.size > MaxFileSizes.PRODUCT_IMAGE:
            raise ValueError(f"Image trop grande (max {MaxFileSizes.PRODUCT_IMAGE_MB}MB)")
    """

    # Images de produits
    PRODUCT_IMAGE = 5 * 1024 * 1024  # 5 MB
    PRODUCT_IMAGE_MB = 5

    # Documents factures/devis
    INVOICE_PDF = 10 * 1024 * 1024  # 10 MB
    INVOICE_PDF_MB = 10

    # Documents généraux
    GENERAL_DOCUMENT = 20 * 1024 * 1024  # 20 MB
    GENERAL_DOCUMENT_MB = 20

    # Avatar utilisateur
    USER_AVATAR = 2 * 1024 * 1024  # 2 MB
    USER_AVATAR_MB = 2


class FileCategory(str, Enum):
    """Catégories de fichiers stockés.

    Utilisé dans :
        - models.File.category
        - Chemins de stockage S3
    """

    PRODUCT_IMAGE = "product_image"
    USER_AVATAR = "user_avatar"
    INVOICE_PDF = "invoice_pdf"
    CONTRACT = "contract"
    OTHER = "other"


class StoragePaths:
    """Chemins de stockage des fichiers.

    Usage :
        path = StoragePaths.get_path(FileCategory.PRODUCT_IMAGE, product_id)
        # → "uploads/products/123/image.jpg"
    """

    UPLOAD_ROOT = "uploads"
    PRODUCTS = f"{UPLOAD_ROOT}/products"
    USERS = f"{UPLOAD_ROOT}/users"
    INVOICES = f"{UPLOAD_ROOT}/invoices"
    CONTRACTS = f"{UPLOAD_ROOT}/contracts"

    @staticmethod
    def get_path(category: FileCategory, entity_id: int, filename: str) -> str:
        """Génère le chemin de stockage d'un fichier."""
        mapping = {
            FileCategory.PRODUCT_IMAGE: f"{StoragePaths.PRODUCTS}/{entity_id}/{filename}",
            FileCategory.USER_AVATAR: f"{StoragePaths.USERS}/{entity_id}/{filename}",
            FileCategory.INVOICE_PDF: f"{StoragePaths.INVOICES}/{entity_id}/{filename}",
            FileCategory.CONTRACT: f"{StoragePaths.CONTRACTS}/{entity_id}/{filename}",
        }
        return mapping.get(category, f"{StoragePaths.UPLOAD_ROOT}/{entity_id}/{filename}")


__all__ = [
    "AllowedFileTypes",
    "MaxFileSizes",
    "FileCategory",
    "StoragePaths",
]
```

### Usage

```python
from app.constants import AllowedFileTypes, MaxFileSizes, FileCategory, StoragePaths

# Validation upload
if file.content_type not in AllowedFileTypes.IMAGES:
    raise HTTPException(status_code=400, detail="Type de fichier non autorisé")

if file.size > MaxFileSizes.PRODUCT_IMAGE:
    raise HTTPException(
        status_code=400,
        detail=f"Image trop grande (max {MaxFileSizes.PRODUCT_IMAGE_MB}MB)"
    )

# Stockage
path = StoragePaths.get_path(FileCategory.PRODUCT_IMAGE, product.id, file.filename)
await s3_client.upload(path, file.content)
```

---

## 📋 Checklist : Ajouter un Nouveau Domaine

Quand vous identifiez le besoin d'un nouveau domaine de constantes :

1. [ ] **Identifier le domaine** (notifications, emails, files, etc.)
2. [ ] **Créer le fichier** `app/constants/nouveau_domaine.py`
3. [ ] **Définir les constantes** avec docstrings complètes
4. [ ] **Ajouter `__all__`** pour les exports
5. [ ] **Importer dans `__init__.py`** :
   ```python
   from app.constants.nouveau_domaine import MaConstante
   __all__ = [..., "MaConstante"]
   ```
6. [ ] **Tester les imports** :
   ```bash
   poetry run python -c "from app.constants import MaConstante; print(MaConstante.VALEUR)"
   ```
7. [ ] **Mettre à jour la documentation** (CONSTANTS_RESTRUCTURATION.md)
8. [ ] **Remplacer les strings hardcodées** par les nouvelles constantes
9. [ ] **Vérifier les tests** passent toujours

---

## 🎯 Principes de Conception

### 1. **Just-In-Time** (pas de sur-ingénierie)
- Ne créer un domaine que quand le besoin **réel** apparaît
- ❌ Ne pas créer `notifications.py` si pas de système de notifications

### 2. **Cohérence avec l'existant**
- Suivre le pattern des fichiers existants (business.py, errors.py, etc.)
- Docstrings complètes avec "Utilisé dans :"
- `__all__` pour exports clairs

### 3. **Helpers utiles**
- Ajouter des méthodes statiques pour génération (ex: `StoragePaths.get_path()`)
- frozenset pour collections immuables (ex: `AllowedFileTypes.IMAGES`)

### 4. **Nommage clair**
- Nom de fichier = domaine fonctionnel (notifications, emails, files)
- Classes descriptives (EmailTemplates, NotificationStatus, FileCategory)

---

## 📚 Autres Domaines Potentiels

Si votre application grandit, vous pourriez avoir besoin de :

- **`webhooks.py`** : WebhookEvents, WebhookStatus
- **`analytics.py`** : EventTypes, MetricNames
- **`billing.py`** : SubscriptionPlans, PaymentProviders
- **`integrations.py`** : ExternalServices, APIEndpoints
- **`reports.py`** : ReportTypes, ExportFormats
- **`cron.py`** : ScheduleIntervals, CronTasks

**Règle d'or** : Créer quand le domaine contient ≥ 3 constantes répétées ou 1 Enum complet.

---

**Généré le** : 2026-02-12
**Usage** : Référence pour l'ajout de nouveaux domaines de constantes
