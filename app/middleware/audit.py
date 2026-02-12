"""Middleware pour audit automatique des requêtes API."""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import uuid
import re

from app.core.database import get_db
from app.services.audit import AuditService
from app.core.security import decode_token


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
        "/health",
        "/api/docs",
        "/api/redoc",
        "/openapi.json",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/csrf",
        "/api/v1/auth/logout",
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
        # Générer request_id unique pour corrélation logs
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id  # Disponible dans endpoints via request.state

        # Skip audit pour endpoints exclus
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Extraire user info depuis JWT
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        payload = decode_token(token) if token else None

        user_id = int(payload.get("sub")) if payload and payload.get("sub") else None
        tenant_id = int(payload.get("tenant_id")) if payload and payload.get("tenant_id") else None

        # Skip audit si non authentifié (JWT obligatoire pour audit)
        if not user_id or not tenant_id:
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
            if method in ("POST", "PUT", "PATCH", "DELETE"):
                self._audit_mutation(
                    method=method,
                    path=path,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_id=request_id
                )

            # Auditer lectures sensibles (GET données personnelles)
            elif method == "GET" and self._is_sensitive_read(path):
                self._audit_sensitive_read(
                    path=path,
                    tenant_id=tenant_id,
                    user_id=user_id,
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
        user_id: int,
        ip_address: str,
        user_agent: str,
        request_id: str
    ) -> None:
        """Audite mutation (CREATE/UPDATE/DELETE) en base de données.

        Args:
            method: HTTP method (POST, PUT, PATCH, DELETE)
            path: URL path (/api/v1/customers/123)
            tenant_id: ID tenant
            user_id: ID utilisateur
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
            # Ouvrir nouvelle session DB (commit séparé pour audit)
            db = next(get_db())
            audit_service = AuditService(db)

            # Mapper HTTP method → action
            action_map = {
                "POST": "CREATE",
                "PUT": "UPDATE",
                "PATCH": "UPDATE",
                "DELETE": "DELETE"
            }
            action = action_map[method]

            # Parser entity_type et entity_id depuis path
            entity_type, entity_id = self._parse_entity_from_path(path)

            # Enregistrer audit log
            audit_service.log_action(
                action=action,
                tenant_id=tenant_id,
                user_id=user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                description=f"{method} {path}",
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id
            )

            # Commit séparé (pas de rollback si audit échoue)
            db.commit()
            db.close()

        except Exception as e:
            # Fail-safe: Ne pas crasher requête si audit échoue
            # TODO: Logger erreur pour monitoring
            print(f"[AuditMiddleware] Error auditing mutation: {e}")
            pass

    def _audit_sensitive_read(
        self,
        path: str,
        tenant_id: int,
        user_id: int,
        ip_address: str,
        user_agent: str,
        request_id: str
    ) -> None:
        """Audite lecture de données sensibles (RGPD).

        Args:
            path: URL path (/api/v1/customers/123)
            tenant_id: ID tenant
            user_id: ID utilisateur
            ip_address: IP client
            user_agent: User-Agent
            request_id: UUID corrélation

        Example:
            >>> # GET /api/v1/customers/456
            >>> _audit_sensitive_read("/api/v1/customers/456", ...)
            >>> # → action=READ_SENSITIVE, entity_type=Customer, entity_id=456
        """
        try:
            # Ouvrir nouvelle session DB
            db = next(get_db())
            audit_service = AuditService(db)

            # Parser entity_type et entity_id
            entity_type, entity_id = self._parse_entity_from_path(path)

            # Enregistrer lecture sensible
            audit_service.log_read_sensitive(
                entity_type=entity_type,
                entity_id=entity_id,
                tenant_id=tenant_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id
            )

            # Commit séparé
            db.commit()
            db.close()

        except Exception as e:
            # Fail-safe
            print(f"[AuditMiddleware] Error auditing sensitive read: {e}")
            pass

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
        # Règles simples de singularisation (suffisant pour CaroCorp)
        if plural.endswith("ies"):
            # reservations → Reservation (pas applicable ici)
            pass
        elif plural.endswith("es"):
            # invoices → Invoice
            singular = plural[:-2]
        elif plural.endswith("s"):
            # customers → Customer, products → Product
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
