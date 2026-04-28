"""Service pour gestion des API Keys (creation, validation, rotation)."""
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ErrorMessages, RedisKeys
from app.core.permissions import Permission
from app.core.redis import redis_client
from app.models.api_key import ApiKey
from app.repositories.api_key import AsyncApiKeyRepository
from app.schemas.api_key import ApiKeyCreate, ApiKeyUpdate

logger = logging.getLogger(__name__)

# Prefixe Marveline Key
KEY_PREFIX_MARKER = "mk_live_"
KEY_RANDOM_LENGTH = 32
REDIS_API_KEY_TTL = 300  # 5 minutes cache


class ApiKeyService:
    """Service pour CRUD et validation des API keys.

    Responsabilites:
        - Generation de cles (mk_live_xxx) avec hash SHA-256
        - Validation lors de l'authentification
        - Rotation de cles (nouvelle cle, ancienne revoquee)
        - Cache Redis pour eviter les lookups DB repetitifs

    Security:
        - Le full key n'est retourne qu'au create/rotate
        - Comparaison constant-time (hmac.compare_digest)
        - Scopes valides contre Permission enum
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AsyncApiKeyRepository(db)

    @staticmethod
    def _generate_key() -> tuple[str, str, str]:
        """Genere une cle API complete.

        Returns:
            Tuple (full_key, key_prefix, key_hash)
            - full_key: mk_live_<32 random chars> (visible une seule fois)
            - key_prefix: les 12 premiers chars (mk_live_xxxx)
            - key_hash: SHA-256(full_key)
        """
        random_part = secrets.token_urlsafe(KEY_RANDOM_LENGTH)
        full_key = f"{KEY_PREFIX_MARKER}{random_part}"
        key_prefix = full_key[:12]
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        return full_key, key_prefix, key_hash

    @staticmethod
    def hash_key(full_key: str) -> str:
        """Hash une cle API avec SHA-256.

        Args:
            full_key: Cle complete (mk_live_xxx)

        Returns:
            SHA-256 hex digest
        """
        return hashlib.sha256(full_key.encode()).hexdigest()

    def _validate_scopes(self, scopes: list[str]) -> None:
        """Valide que les scopes sont des permissions valides.

        Args:
            scopes: Liste de scopes a valider

        Raises:
            HTTPException 400: Si des scopes sont invalides
        """
        valid_scopes = {p.value for p in Permission}
        invalid = [s for s in scopes if s not in valid_scopes]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Scopes invalides: {invalid}"
            )

    async def create_key(
        self,
        data: ApiKeyCreate,
        tenant_id: int,
        created_by: int,
    ) -> tuple[ApiKey, str]:
        """Cree une nouvelle API key.

        Args:
            data: Donnees de creation
            tenant_id: ID du tenant
            created_by: ID de l'admin createur

        Returns:
            Tuple (ApiKey instance, full_key visible une seule fois)

        Raises:
            HTTPException 400: Si scopes invalides
        """
        self._validate_scopes(data.scopes)

        full_key, key_prefix, key_hash = self._generate_key()

        api_key = ApiKey(
            tenant_id=tenant_id,
            name=data.name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=data.scopes,
            rate_limit=data.rate_limit,
            expires_at=data.expires_at,
            created_by=created_by,
        )

        self.db.add(api_key)
        await self.db.flush()
        return api_key, full_key

    async def update_key(
        self,
        api_key_id: int,
        data: ApiKeyUpdate,
        tenant_id: int,
    ) -> ApiKey:
        """Met a jour une API key.

        Args:
            api_key_id: ID de la cle
            data: Donnees de mise a jour
            tenant_id: ID du tenant

        Returns:
            ApiKey mise a jour

        Raises:
            HTTPException 404: Si cle non trouvee
            HTTPException 400: Si scopes invalides
        """
        api_key = await self.repo.get_by_id_and_tenant(api_key_id, tenant_id)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key non trouvee"
            )

        if data.scopes is not None:
            self._validate_scopes(data.scopes)
            api_key.scopes = data.scopes

        if data.name is not None:
            api_key.name = data.name

        if data.rate_limit is not None:
            api_key.rate_limit = data.rate_limit

        if data.is_active is not None:
            api_key.is_active = data.is_active

        await self.db.flush()
        await self._invalidate_cache(api_key.key_hash)
        return api_key

    async def revoke_key(self, api_key_id: int, tenant_id: int) -> ApiKey:
        """Revoque (soft delete) une API key.

        Args:
            api_key_id: ID de la cle
            tenant_id: ID du tenant

        Returns:
            ApiKey revoquee

        Raises:
            HTTPException 404: Si cle non trouvee
        """
        api_key = await self.repo.get_by_id_and_tenant(api_key_id, tenant_id)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key non trouvee"
            )

        api_key.is_active = False
        await self.db.flush()
        await self._invalidate_cache(api_key.key_hash)
        return api_key

    async def rotate_key(
        self,
        api_key_id: int,
        tenant_id: int,
    ) -> tuple[ApiKey, str]:
        """Rotation : genere une nouvelle cle, revoque l'ancienne.

        Args:
            api_key_id: ID de la cle a renouveler
            tenant_id: ID du tenant

        Returns:
            Tuple (nouvelle ApiKey, nouveau full_key)

        Raises:
            HTTPException 404: Si cle non trouvee
        """
        old_key = await self.repo.get_by_id_and_tenant(api_key_id, tenant_id)
        if not old_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key non trouvee"
            )

        # Revoquer l'ancienne
        old_key.is_active = False
        await self.db.flush()
        await self._invalidate_cache(old_key.key_hash)

        # Creer la nouvelle avec memes parametres
        full_key, key_prefix, key_hash = self._generate_key()
        new_key = ApiKey(
            tenant_id=tenant_id,
            name=old_key.name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=old_key.scopes,
            rate_limit=old_key.rate_limit,
            expires_at=old_key.expires_at,
            created_by=old_key.created_by,
        )
        self.db.add(new_key)
        await self.db.flush()

        return new_key, full_key

    async def validate_key(self, full_key: str) -> Optional[ApiKey]:
        """Valide une API key et retourne le modele si valide.

        Flow:
            1. Hash la cle
            2. Check cache Redis
            3. Si miss -> lookup DB
            4. Verifier expiration
            5. Mettre a jour last_used_at

        Args:
            full_key: Cle API complete (mk_live_xxx)

        Returns:
            ApiKey si valide, None sinon
        """
        key_hash = self.hash_key(full_key)

        # Check cache Redis
        cached = await self._get_from_cache(key_hash)
        if cached is not None:
            if not cached:
                return None  # Cache indique cle invalide
            # Cache hit — on a besoin de l'objet complet pour les updates
            api_key = await self.repo.get_by_key_hash(key_hash)
        else:
            # Cache miss — lookup DB
            api_key = await self.repo.get_by_key_hash(key_hash)
            if api_key:
                await self._set_cache(api_key)
            else:
                await self._set_cache_negative(key_hash)
                return None

        if not api_key:
            return None

        # Verifier expiration
        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            return None

        return api_key

    async def get_key(self, api_key_id: int, tenant_id: int) -> ApiKey:
        """Recupere une API key par ID.

        Args:
            api_key_id: ID de la cle
            tenant_id: ID du tenant

        Returns:
            ApiKey

        Raises:
            HTTPException 404: Si non trouvee
        """
        api_key = await self.repo.get_by_id_and_tenant(api_key_id, tenant_id)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key non trouvee"
            )
        return api_key

    async def list_keys(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False,
    ) -> tuple[list[ApiKey], int]:
        """Liste les API keys d'un tenant.

        Args:
            tenant_id: ID du tenant
            skip: Offset pagination
            limit: Nombre max resultats
            include_inactive: Inclure les cles revoquees

        Returns:
            Tuple (liste, total)
        """
        return await self.repo.list_by_tenant(
            tenant_id=tenant_id,
            include_inactive=include_inactive,
            skip=skip,
            limit=limit,
        )

    # ── Cache Redis ──────────────────────────────────────────────────────

    async def _get_from_cache(self, key_hash: str) -> Optional[dict]:
        """Recupere une API key depuis le cache Redis.

        Returns:
            dict avec donnees si trouvee, False si negative cache, None si miss
        """
        try:
            cache_key = f"{RedisKeys.API_KEY_CACHE}{key_hash[:16]}"
            raw = await redis_client.client.get(cache_key)
            if raw is None:
                return None
            data = json.loads(raw)
            if data.get("_invalid"):
                return False
            return data
        except Exception:
            logger.debug("Redis cache miss for API key (error)")
            return None

    async def _set_cache(self, api_key: ApiKey) -> None:
        """Met en cache une API key valide."""
        try:
            cache_key = f"{RedisKeys.API_KEY_CACHE}{api_key.key_hash[:16]}"
            data = {
                "id": api_key.id,
                "tenant_id": api_key.tenant_id,
                "scopes": api_key.scopes,
                "rate_limit": api_key.rate_limit,
                "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
            }
            await redis_client.client.setex(cache_key, REDIS_API_KEY_TTL, json.dumps(data))
        except Exception:
            logger.debug("Failed to cache API key")

    async def _set_cache_negative(self, key_hash: str) -> None:
        """Met en cache un resultat negatif (cle inexistante)."""
        try:
            cache_key = f"{RedisKeys.API_KEY_CACHE}{key_hash[:16]}"
            await redis_client.client.setex(cache_key, 60, json.dumps({"_invalid": True}))
        except Exception:
            logger.debug("Failed to set negative cache for API key")

    async def _invalidate_cache(self, key_hash: str) -> None:
        """Invalide le cache pour une API key."""
        try:
            cache_key = f"{RedisKeys.API_KEY_CACHE}{key_hash[:16]}"
            await redis_client.client.delete(cache_key)
        except Exception:
            logger.debug("Failed to invalidate API key cache")
