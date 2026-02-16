"""Service AuditLog pour traçabilité complète et conformité RGPD/SOC2."""
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from typing import Optional, Any
import uuid


class AuditService:
    """Service pour enregistrer actions dans audit log immuable.

    Responsabilités:
        - Enregistrement audit trail complet (CREATE, UPDATE, DELETE, READ_SENSITIVE)
        - Logging authentification (LOGIN_SUCCESS, LOGIN_FAILED, LOGOUT)
        - Conformité RGPD Article 30 (registre activités traitement)
        - Conformité SOC 2 (traçabilité complète)

    Pattern:
        - Transactions gérées par appelant (service/endpoint)
        - Pas de commit dans ce service
        - UUID auto-généré si request_id manquant
        - Détection automatique champs modifiés (UPDATE)

    Security:
        - Pas de validation métier (append-only simple)
        - Trigger PostgreSQL empêche UPDATE/DELETE
        - Pas d'exposition données sensibles dans logs

    Example:
        >>> audit_service = AuditService(db)
        >>> audit_service.log_create(
        ...     entity_type="Customer",
        ...     entity_id=123,
        ...     entity_data={"email": "john@example.com"},
        ...     tenant_id=1,
        ...     user_id=42,
        ...     ip_address="192.168.1.100",
        ...     user_agent="Mozilla/5.0...",
        ...     request_id="550e8400-..."
        ... )
        >>> db.commit()  # Transaction gérée par appelant
    """

    def __init__(self, db: Session):
        """Initialise le service avec session DB.

        Args:
            db: Session SQLAlchemy (transaction gérée par appelant)
        """
        self.db = db

    def log_action(
        self,
        action: str,
        tenant_id: int,
        user_id: Optional[int] = None,
        api_key_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        changes: Optional[dict[str, Any]] = None,
        description: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> AuditLog:
        """Enregistre une action générique dans l'audit log.

        Méthode bas-niveau utilisée par toutes les méthodes spécialisées.

        Args:
            action: Type d'action (CREATE, UPDATE, DELETE, SOFT_DELETE, READ_SENSITIVE,
                   LOGIN_SUCCESS, LOGIN_FAILED, LOGOUT)
            tenant_id: ID du tenant (isolation multi-tenant)
            user_id: ID utilisateur (NULL pour actions système automatiques)
            entity_type: Type d'entité (Customer, Reservation, Invoice, etc.)
            entity_id: ID de l'entité impactée (NULL pour actions globales)
            changes: Dictionnaire modifications (format varie selon action):
                    - UPDATE: {"field": {"before": old, "after": new}}
                    - CREATE: {"after": entity_data}
                    - DELETE: {"before": entity_data}
            description: Description humaine pour lisibilité logs admin
            ip_address: IP du client (IPv4/IPv6)
            user_agent: User-Agent navigateur/API client
            request_id: UUID corrélation logs (auto-généré si absent)

        Returns:
            AuditLog créé (ajouté à session, pas encore committée)

        Example:
            >>> audit_service.log_action(
            ...     action="CREATE",
            ...     tenant_id=1,
            ...     user_id=42,
            ...     entity_type="Reservation",
            ...     entity_id=123,
            ...     changes={"after": {"status": "draft", "total_amount": 10000}},
            ...     description="Created Reservation #123",
            ...     ip_address="192.168.1.100",
            ...     user_agent="Mozilla/5.0...",
            ...     request_id="550e8400-e29b-41d4-a716-446655440000"
            ... )
        """
        audit_log = AuditLog(
            user_id=user_id,
            api_key_id=api_key_id,
            tenant_id=tenant_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id or str(uuid.uuid4())  # Auto-generate si absent
        )

        self.db.add(audit_log)
        # Pas de commit ici (transaction gérée par endpoint/service appelant)

        return audit_log

    def log_create(
        self,
        entity_type: str,
        entity_id: int,
        entity_data: dict[str, Any],
        tenant_id: int,
        user_id: int,
        ip_address: str,
        user_agent: str,
        request_id: str
    ) -> AuditLog:
        """Enregistre création d'entité.

        Args:
            entity_type: Type d'entité créée (Customer, Reservation, Invoice, etc.)
            entity_id: ID de l'entité créée
            entity_data: Données complètes de l'entité créée (dict depuis Pydantic)
            tenant_id: ID tenant
            user_id: ID utilisateur ayant créé
            ip_address: IP du client
            user_agent: User-Agent
            request_id: UUID corrélation

        Returns:
            AuditLog action=CREATE

        Example:
            >>> audit_service.log_create(
            ...     entity_type="Customer",
            ...     entity_id=123,
            ...     entity_data={
            ...         "customer_type": "individual",
            ...         "first_name": "John",
            ...         "last_name": "Doe",
            ...         "email": "john.doe@example.com"
            ...     },
            ...     tenant_id=1,
            ...     user_id=42,
            ...     ip_address="192.168.1.100",
            ...     user_agent="Mozilla/5.0...",
            ...     request_id="550e8400-..."
            ... )
        """
        return self.log_action(
            action="CREATE",
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            changes={"after": entity_data},  # Stocke données complètes après création
            description=f"Created {entity_type} #{entity_id}",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )

    def log_update(
        self,
        entity_type: str,
        entity_id: int,
        before: dict[str, Any],
        after: dict[str, Any],
        tenant_id: int,
        user_id: int,
        ip_address: str,
        user_agent: str,
        request_id: str
    ) -> AuditLog:
        """Enregistre modification d'entité avec détection champs modifiés.

        Calcule automatiquement diff (before/after) pour chaque champ modifié.

        Args:
            entity_type: Type d'entité modifiée
            entity_id: ID de l'entité modifiée
            before: État AVANT modification (dict depuis ORM)
            after: État APRÈS modification (dict depuis Pydantic)
            tenant_id: ID tenant
            user_id: ID utilisateur ayant modifié
            ip_address: IP du client
            user_agent: User-Agent
            request_id: UUID corrélation

        Returns:
            AuditLog action=UPDATE avec changes contenant seulement champs modifiés

        Example:
            >>> audit_service.log_update(
            ...     entity_type="Reservation",
            ...     entity_id=456,
            ...     before={"status": "draft", "total_amount": 10000},
            ...     after={"status": "confirmed", "total_amount": 12000},
            ...     tenant_id=1,
            ...     user_id=42,
            ...     ip_address="192.168.1.100",
            ...     user_agent="Mozilla/5.0...",
            ...     request_id="550e8400-..."
            ... )
            # changes = {
            #     "status": {"before": "draft", "after": "confirmed"},
            #     "total_amount": {"before": 10000, "after": 12000}
            # }
        """
        # Calculer uniquement champs modifiés (optimisation stockage)
        changes = {}
        for key in after:
            if key in before and before[key] != after[key]:
                changes[key] = {"before": before[key], "after": after[key]}

        return self.log_action(
            action="UPDATE",
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes,
            description=f"Updated {entity_type} #{entity_id}: {', '.join(changes.keys())}",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )

    def log_delete(
        self,
        entity_type: str,
        entity_id: int,
        entity_data: dict[str, Any],
        tenant_id: int,
        user_id: int,
        ip_address: str,
        user_agent: str,
        request_id: str,
        soft_delete: bool = True
    ) -> AuditLog:
        """Enregistre suppression d'entité (soft ou hard).

        Args:
            entity_type: Type d'entité supprimée
            entity_id: ID de l'entité supprimée
            entity_data: Données complètes AVANT suppression (pour forensics)
            tenant_id: ID tenant
            user_id: ID utilisateur ayant supprimé
            ip_address: IP du client
            user_agent: User-Agent
            request_id: UUID corrélation
            soft_delete: True=soft delete (is_active=False), False=hard delete (DROP row)

        Returns:
            AuditLog action=SOFT_DELETE ou HARD_DELETE

        Example:
            >>> audit_service.log_delete(
            ...     entity_type="Customer",
            ...     entity_id=123,
            ...     entity_data={"email": "john.doe@example.com", ...},
            ...     tenant_id=1,
            ...     user_id=42,
            ...     ip_address="192.168.1.100",
            ...     user_agent="Mozilla/5.0...",
            ...     request_id="550e8400-...",
            ...     soft_delete=True
            ... )
        """
        action = "SOFT_DELETE" if soft_delete else "HARD_DELETE"
        return self.log_action(
            action=action,
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            changes={"before": entity_data},  # Stocke état complet avant suppression
            description=f"{'Soft' if soft_delete else 'Hard'} deleted {entity_type} #{entity_id}",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )

    def log_read_sensitive(
        self,
        entity_type: str,
        entity_id: int,
        tenant_id: int,
        user_id: int | None = None,
        api_key_id: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None
    ) -> AuditLog:
        """Enregistre accès à données sensibles (conformité RGPD).

        Obligatoire pour tracer qui a consulté données personnelles (RGPD Article 30).

        Args:
            entity_type: Type d'entité consultée (Customer, Invoice, User)
            entity_id: ID de l'entité consultée
            tenant_id: ID tenant
            user_id: ID utilisateur ayant consulté (None si auth API key)
            api_key_id: ID API key (None si auth utilisateur)
            ip_address: IP du client
            user_agent: User-Agent
            request_id: UUID corrélation

        Returns:
            AuditLog action=READ_SENSITIVE

        Example:
            >>> # Audit lecture GET /customers/123
            >>> audit_service.log_read_sensitive(
            ...     entity_type="Customer",
            ...     entity_id=123,
            ...     tenant_id=1,
            ...     user_id=42,
            ...     ip_address="192.168.1.100",
            ...     user_agent="Mozilla/5.0...",
            ...     request_id="550e8400-..."
            ... )
        """
        return self.log_action(
            action="READ_SENSITIVE",
            tenant_id=tenant_id,
            user_id=user_id,
            api_key_id=api_key_id,
            entity_type=entity_type,
            entity_id=entity_id,
            description=f"Accessed sensitive data {entity_type} #{entity_id}",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )

    def log_login(
        self,
        user_id: int,
        tenant_id: int,
        ip_address: str,
        user_agent: str,
        request_id: str,
        success: bool = True,
        email: Optional[str] = None
    ) -> AuditLog:
        """Enregistre tentative login (succès ou échec).

        Args:
            user_id: ID utilisateur (NULL si échec et user non trouvé)
            tenant_id: ID tenant
            ip_address: IP du client
            user_agent: User-Agent
            request_id: UUID corrélation
            success: True=login réussi, False=login échoué
            email: Email utilisé pour login (pour tracer tentatives brute force)

        Returns:
            AuditLog action=LOGIN_SUCCESS ou LOGIN_FAILED

        Example:
            >>> # Login réussi
            >>> audit_service.log_login(
            ...     user_id=42,
            ...     tenant_id=1,
            ...     ip_address="192.168.1.100",
            ...     user_agent="Mozilla/5.0...",
            ...     request_id="550e8400-...",
            ...     success=True,
            ...     email="user@example.com"
            ... )

            >>> # Login échoué
            >>> audit_service.log_login(
            ...     user_id=None,  # User non trouvé ou password incorrect
            ...     tenant_id=1,
            ...     ip_address="192.168.1.100",
            ...     user_agent="Mozilla/5.0...",
            ...     request_id="550e8400-...",
            ...     success=False,
            ...     email="attacker@example.com"
            ... )
        """
        action = "LOGIN_SUCCESS" if success else "LOGIN_FAILED"
        description = f"Login {'successful' if success else 'failed'}"
        if email:
            description += f" for {email}"

        return self.log_action(
            action=action,
            tenant_id=tenant_id,
            user_id=user_id if success else None,  # NULL si échec (user non trouvé)
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )

    def log_logout(
        self,
        user_id: int,
        tenant_id: int,
        ip_address: str,
        user_agent: str,
        request_id: str
    ) -> AuditLog:
        """Enregistre logout utilisateur.

        Args:
            user_id: ID utilisateur se déconnectant
            tenant_id: ID tenant
            ip_address: IP du client
            user_agent: User-Agent
            request_id: UUID corrélation

        Returns:
            AuditLog action=LOGOUT

        Example:
            >>> audit_service.log_logout(
            ...     user_id=42,
            ...     tenant_id=1,
            ...     ip_address="192.168.1.100",
            ...     user_agent="Mozilla/5.0...",
            ...     request_id="550e8400-..."
            ... )
        """
        return self.log_action(
            action="LOGOUT",
            tenant_id=tenant_id,
            user_id=user_id,
            description="User logged out",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )
