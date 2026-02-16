"""Middleware pour audit automatique des requetes API."""

import logging
import re
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.constants import AuthEndpoints, HTTPMethods, PublicEndpoints
from app.core.database import get_db_context
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware pour enregistrement automatique des actions dans audit log.

    Architecture:
        - Génère request_id unique (UUID) pour chaque requête
        - Extrait user_id et tenant_id depuis JWT Bearer token
        - Audite mutations (POST/PUT/PATCH/DELETE) si réponse 2xx
        - Audite lectures sensibles (GET customers/invoices/users)
        - Parse path API pour extraire entity_type et entity_id

    Endpoints audités:
        - Mutations: Tous POST/PUT/PATCH/DELETE authentifiés avec réponse 2xx
        - Lectures sensibles: GET /customers/{id}, /invoices/{id}, /users/{id}

    Endpoints exclus:
        - Health check (/health)
        - Documentation (/docs, /redoc, /openapi.json)
        - Auth endpoints (/auth/login, /auth/refresh, /auth/csrf)
        - Requêtes non authentifiées (pas de JWT)
        - Réponses échec (status >= 300)

    Security:
        - Pas d'exception levée (fail-safe)
        - Commit séparé pour audit (pas de rollback si audit échoue)
        - Pas de modification requête/réponse
        - Pas de ralentissement user (audit en arrière-plan)

    Example:
        >>> # app/main.py
        >>> from app.middleware.audit import AuditMiddleware
        >>> app.add_middleware(AuditMiddleware)

        >>> # Audit automatique pour:
        >>> # POST /api/v1/customers → action=CREATE, entity_type=Customer
        >>> # PUT /api/v1/reservations/123 → action=UPDATE, entity_type=Reservation, entity_id=123
        >>> # GET /api/v1/customers/456 → action=READ_SENSITIVE, entity_type=Customer, entity_id=456
    """

    # Endpoints sensibles à auditer (lecture données personnelles)
    SENSITIVE_READ_PATTERNS = [
        r"^/api/v1/customers/\d+$",      # GET /customers/{id}
        r"^/api/v1/invoices/\d+$",       # GET /invoices/{id}
        r"^/api/v1/users/\d+$",          # GET /users/{id}
    ]

    # Endpoints à exclure de l'audit (publics ou non critiques)
    EXCLUDED_PATHS = [
        PublicEndpoints.HEALTH,
        PublicEndpoints.DOCS,
        PublicEndpoints.REDOC,
        PublicEndpoints.OPENAPI,
        AuthEndpoints.LOGIN,
        AuthEndpoints.REFRESH,
        AuthEndpoints.CSRF,
        AuthEndpoints.LOGOUT,
    ]

    async def dispatch(self, request: Request, call_next: Callable):
        """Intercepte requête, exécute, puis audite si nécessaire.

        Flow:
            1. Générer request_id unique
            2. Extraire user info depuis JWT
            3. Exécuter requête (call_next)
            4. Auditer si mutation réussie OU lecture sensible
            5. Retourner réponse (pas de modification)

        Args:
            request: FastAPI Request
            call_next: Next middleware/endpoint dans stack

        Returns:
            Response inchangée (pas de modification)
        """
        # Utiliser request_id depuis RequestContextMiddleware (fix B3: plus de double generation)
        request_id = getattr(request.state, "request_id", None)

        # Skip audit si request_id manquant (bug de configuration middleware)
        if not request_id:
            logger.error(
                "request_id absent de request.state — RequestContextMiddleware mal configure ou manquant"
            )
            return await call_next(request)

        # Skip audit pour endpoints exclus
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Utiliser user_id/tenant_id/api_key_id depuis RequestContextMiddleware (fix B3: plus de JWT triple decode)
        user_id = getattr(request.state, "user_id", None)
        tenant_id = getattr(request.state, "tenant_id", None)
        api_key_id = getattr(request.state, "api_key_id", None)
        principal_type = getattr(request.state, "principal_type", None)

        # Skip audit si non authentifié (user OU api_key requis)
        if not tenant_id or (not user_id and not api_key_id):
            return await call_next(request)

        # Extraire IP et User-Agent
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")

        # Exécuter requête
        response = await call_next(request)

        # Auditer seulement si réponse succès (2xx)
        if 200 <= response.status_code < 300:
            method = request.method
            path = request.url.path

            # Auditer mutations (POST, PUT, PATCH, DELETE)
            if method in HTTPMethods.UNSAFE_METHODS:
                self._audit_mutation(
                    method=method,
                    path=path,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    api_key_id=api_key_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_id=request_id
                )

            # Auditer lectures sensibles (GET données personnelles)
            elif method == HTTPMethods.GET and self._is_sensitive_read(path):
                self._audit_sensitive_read(
                    path=path,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    api_key_id=api_key_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_id=request_id
                )

        return response

    def _audit_mutation(
        self,
        method: str,
        path: str,
        tenant_id: int,
        user_id: int | None,
        api_key_id: int | None,
        ip_address: str,
        user_agent: str,
        request_id: str
    ) -> None:
        """Audite mutation (CREATE/UPDATE/DELETE) en base de données.

        Args:
            method: HTTP method (POST, PUT, PATCH, DELETE)
            path: URL path (/api/v1/customers/123)
            tenant_id: ID tenant
            user_id: ID utilisateur (None si auth API key)
            api_key_id: ID API key (None si auth utilisateur)
            ip_address: IP client
            user_agent: User-Agent
            request_id: UUID corrélation

        Example:
            >>> # POST /api/v1/customers
            >>> _audit_mutation("POST", "/api/v1/customers", ...)
            >>> # → action=CREATE, entity_type=Customer, entity_id=None (pas encore créé)

            >>> # PUT /api/v1/reservations/123
            >>> _audit_mutation("PUT", "/api/v1/reservations/123", ...)
            >>> # → action=UPDATE, entity_type=Reservation, entity_id=123
        """
        try:
            # Ouvrir nouvelle session DB avec context manager (fix B1)
            with get_db_context() as db:
                audit_service = AuditService(db)

                # Mapper HTTP method → action
                action_map = {
                    HTTPMethods.POST: "CREATE",
                    HTTPMethods.PUT: "UPDATE",
                    HTTPMethods.PATCH: "UPDATE",
                    HTTPMethods.DELETE: "DELETE"
                }
                action = action_map[method]

                # Parser entity_type et entity_id depuis path
                entity_type, entity_id = self._parse_entity_from_path(path)

                # Enregistrer audit log
                audit_service.log_action(
                    action=action,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    api_key_id=api_key_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    description=f"{method} {path}",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_id=request_id
                )

                # Commit séparé (pas de rollback si audit échoue)
                db.commit()

        except Exception:
            # Fail-safe : ne pas crasher requete si audit echoue (fix M1)
            logger.exception("Erreur audit mutation %s %s", method, path)

    def _audit_sensitive_read(
        self,
        path: str,
        tenant_id: int,
        user_id: int | None,
        api_key_id: int | None,
        ip_address: str,
        user_agent: str,
        request_id: str
    ) -> None:
        """Audite lecture de données sensibles (RGPD).

        Args:
            path: URL path (/api/v1/customers/123)
            tenant_id: ID tenant
            user_id: ID utilisateur (None si auth API key)
            api_key_id: ID API key (None si auth utilisateur)
            ip_address: IP client
            user_agent: User-Agent
            request_id: UUID corrélation

        Example:
            >>> # GET /api/v1/customers/456
            >>> _audit_sensitive_read("/api/v1/customers/456", ...")
            >>> # → action=READ_SENSITIVE, entity_type=Customer, entity_id=456
        """
        try:
            # Ouvrir nouvelle session DB avec context manager (fix B1)
            with get_db_context() as db:
                audit_service = AuditService(db)

                # Parser entity_type et entity_id
                entity_type, entity_id = self._parse_entity_from_path(path)

                # Enregistrer lecture sensible
                audit_service.log_read_sensitive(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    api_key_id=api_key_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_id=request_id
                )

                # Commit séparé
                db.commit()

        except Exception:
            # Fail-safe (fix M1)
            logger.exception("Erreur audit lecture sensible %s", path)

    def _parse_entity_from_path(self, path: str) -> tuple[str | None, int | None]:
        """Extrait entity_type et entity_id depuis path API.

        Pattern: /api/v1/{entity_type_plural}/{entity_id}

        Args:
            path: URL path (/api/v1/customers/123)

        Returns:
            Tuple (entity_type, entity_id) ou (None, None) si parsing échoue

        Examples:
            >>> _parse_entity_from_path("/api/v1/customers/123")
            ("Customer", 123)

            >>> _parse_entity_from_path("/api/v1/reservations/456")
            ("Reservation", 456)

            >>> _parse_entity_from_path("/api/v1/customers")
            ("Customer", None)  # POST création (pas encore d'ID)

            >>> _parse_entity_from_path("/health")
            (None, None)  # Pas un endpoint API
        """
        # Pattern: /api/v1/{entity_type}/{entity_id}
        parts = path.strip('/').split('/')

        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
            # Entity type (pluriel → singulier capitalisé)
            entity_type_plural = parts[2]
            entity_type = self._singularize_entity_type(entity_type_plural)

            # Entity ID (si présent)
            entity_id = None
            if len(parts) > 3 and parts[3].isdigit():
                entity_id = int(parts[3])

            return entity_type, entity_id

        return None, None

    def _singularize_entity_type(self, plural: str) -> str:
        """Convertit nom pluriel en singulier capitalisé.

        Args:
            plural: Nom pluriel (customers, reservations, invoices)

        Returns:
            Nom singulier capitalisé (Customer, Reservation, Invoice)

        Examples:
            >>> _singularize_entity_type("customers")
            "Customer"

            >>> _singularize_entity_type("reservations")
            "Reservation"

            >>> _singularize_entity_type("invoices")
            "Invoice"
        """
        # Mapping explicite pour les entités CaroCorp
        known = {
            "customers": "Customer",
            "reservations": "Reservation",
            "invoices": "Invoice",
            "users": "User",
            "products": "Product",
            "categories": "Category",
            "bundles": "Bundle",
            "services": "Service",
            "sessions": "Session",
            "mfa": "MFA",
            "audit": "Audit",
        }
        if plural in known:
            return known[plural]

        # Fallback : règles simples
        if plural.endswith("ies"):
            singular = plural[:-3] + "y"
        elif plural.endswith("ses") or plural.endswith("xes") or plural.endswith("zes"):
            singular = plural[:-2]
        elif plural.endswith("s"):
            singular = plural[:-1]
        else:
            singular = plural

        return singular.capitalize()

    def _is_sensitive_read(self, path: str) -> bool:
        """Vérifie si path correspond à lecture de données sensibles.

        Args:
            path: URL path (/api/v1/customers/123)

        Returns:
            True si lecture sensible (RGPD), False sinon

        Examples:
            >>> _is_sensitive_read("/api/v1/customers/123")
            True  # Données personnelles client

            >>> _is_sensitive_read("/api/v1/invoices/456")
            True  # Facture avec montants

            >>> _is_sensitive_read("/api/v1/products/789")
            False  # Produit non sensible
        """
        for pattern in self.SENSITIVE_READ_PATTERNS:
            if re.match(pattern, path):
                return True
        return False
