"""Service pour gestion des Feature Flags avec evaluation et cache Redis."""
import hashlib
import json
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.constants import RedisKeys
from app.core.redis import redis_client
from app.models.feature_flag import FeatureFlag
from app.repositories.feature_flag import FeatureFlagRepository
from app.schemas.feature_flag import FeatureFlagCreate, FeatureFlagUpdate

logger = logging.getLogger(__name__)

FEATURE_FLAG_CACHE_TTL = 60  # 60 secondes


class FeatureFlagService:
    """Service pour CRUD et evaluation des feature flags.

    Responsabilites:
        - CRUD des feature flags (admin only)
        - Evaluation: is_feature_enabled(flag_name, tenant_id)
        - Cache Redis pour eviter les lookups DB repetitifs

    Evaluation logic:
        1. is_enabled=False -> False (kill switch)
        2. target_tenants is not None -> whitelist mode
        3. target_tenants is None -> rollout_pct (hash deterministe)
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = FeatureFlagRepository(db)

    def create_flag(self, data: FeatureFlagCreate) -> FeatureFlag:
        """Cree un nouveau feature flag.

        Args:
            data: Donnees de creation

        Returns:
            FeatureFlag cree

        Raises:
            HTTPException 409: Si le nom existe deja
        """
        if self.repo.name_exists(data.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Feature flag '{data.name}' existe deja"
            )

        flag = FeatureFlag(
            name=data.name,
            description=data.description,
            is_enabled=data.is_enabled,
            target_tenants=data.target_tenants,
            rollout_pct=data.rollout_pct,
            metadata_json=data.metadata_json,
        )

        return self.repo.create(flag)

    def update_flag(
        self,
        flag_id: int,
        data: FeatureFlagUpdate,
    ) -> FeatureFlag:
        """Met a jour un feature flag.

        Args:
            flag_id: ID du flag
            data: Donnees de mise a jour

        Returns:
            FeatureFlag mis a jour

        Raises:
            HTTPException 404: Si flag non trouve
        """
        flag = self.repo.get_by_id(flag_id)
        if not flag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feature flag non trouve"
            )

        if data.description is not None:
            flag.description = data.description

        if data.is_enabled is not None:
            flag.is_enabled = data.is_enabled

        # target_tenants: distinguer None (pas de changement) de [] (vider la liste)
        # On utilise model_fields_set pour detecter si le champ a ete explicitement passe
        if "target_tenants" in data.model_fields_set:
            flag.target_tenants = data.target_tenants

        if data.rollout_pct is not None:
            flag.rollout_pct = data.rollout_pct

        if data.metadata_json is not None:
            flag.metadata_json = data.metadata_json

        self.repo.update(flag)
        self._invalidate_cache(flag.name)
        return flag

    def delete_flag(self, flag_id: int) -> None:
        """Supprime un feature flag (hard delete).

        Args:
            flag_id: ID du flag

        Raises:
            HTTPException 404: Si flag non trouve
        """
        flag = self.repo.get_by_id(flag_id)
        if not flag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feature flag non trouve"
            )

        flag_name = flag.name
        self.repo.delete(flag)
        self._invalidate_cache(flag_name)

    def get_flag(self, flag_id: int) -> FeatureFlag:
        """Recupere un feature flag par ID.

        Args:
            flag_id: ID du flag

        Returns:
            FeatureFlag

        Raises:
            HTTPException 404: Si non trouve
        """
        flag = self.repo.get_by_id(flag_id)
        if not flag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feature flag non trouve"
            )
        return flag

    def get_flag_by_name(self, name: str) -> FeatureFlag:
        """Recupere un feature flag par nom.

        Args:
            name: Nom du flag

        Returns:
            FeatureFlag

        Raises:
            HTTPException 404: Si non trouve
        """
        flag = self.repo.get_by_name(name)
        if not flag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature flag '{name}' non trouve"
            )
        return flag

    def list_flags(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[FeatureFlag], int]:
        """Liste tous les feature flags.

        Args:
            skip: Offset pagination
            limit: Nombre max resultats

        Returns:
            Tuple (liste, total)
        """
        return self.repo.list_all(skip=skip, limit=limit)

    def is_feature_enabled(self, flag_name: str, tenant_id: int) -> tuple[bool, str]:
        """Evalue si un feature flag est actif pour un tenant donne.

        Logique d'evaluation:
            1. is_enabled=False -> (False, "kill_switch")
            2. target_tenants is not None:
               - tenant_id in target_tenants -> (True, "whitelist")
               - tenant_id not in list -> (False, "not_in_whitelist")
            3. target_tenants is None -> rollout_pct avec hash deterministe
               - hash(flag_name + tenant_id) % 100 < rollout_pct -> (True, "rollout")
               - sinon -> (False, "rollout")

        Args:
            flag_name: Nom du flag
            tenant_id: ID du tenant a evaluer

        Returns:
            Tuple (enabled: bool, reason: str)
        """
        # Tenter le cache Redis
        flag_data = self._get_from_cache(flag_name)

        if flag_data is None:
            # Cache miss -> lookup DB
            flag = self.repo.get_by_name(flag_name)
            if not flag:
                return False, "not_found"

            flag_data = {
                "is_enabled": flag.is_enabled,
                "target_tenants": flag.target_tenants,
                "rollout_pct": flag.rollout_pct,
            }
            self._set_cache(flag_name, flag_data)

        # 1. Kill switch
        if not flag_data["is_enabled"]:
            return False, "kill_switch"

        # 2. Whitelist mode
        target_tenants = flag_data["target_tenants"]
        if target_tenants is not None:
            if tenant_id in target_tenants:
                return True, "whitelist"
            return False, "not_in_whitelist"

        # 3. Rollout progressif avec hash deterministe
        rollout_pct = flag_data["rollout_pct"]
        if rollout_pct >= 100:
            return True, "rollout"
        if rollout_pct <= 0:
            return False, "rollout"

        hash_input = f"{flag_name}:{tenant_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        bucket = hash_value % 100

        if bucket < rollout_pct:
            return True, "rollout"
        return False, "rollout"

    # -- Cache Redis --------------------------------------------------------

    def _get_from_cache(self, flag_name: str) -> Optional[dict]:
        """Recupere un flag depuis le cache Redis.

        Returns:
            dict avec donnees si trouve, None si miss
        """
        try:
            cache_key = f"{RedisKeys.FEATURE_FLAG_CACHE}{flag_name}"
            raw = redis_client.client.get(cache_key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.debug("Redis cache miss for feature flag '%s' (error)", flag_name)
            return None

    def _set_cache(self, flag_name: str, data: dict) -> None:
        """Met en cache les donnees d'un flag."""
        try:
            cache_key = f"{RedisKeys.FEATURE_FLAG_CACHE}{flag_name}"
            redis_client.client.setex(
                cache_key, FEATURE_FLAG_CACHE_TTL, json.dumps(data)
            )
        except Exception:
            logger.debug("Failed to cache feature flag '%s'", flag_name)

    def _invalidate_cache(self, flag_name: str) -> None:
        """Invalide le cache pour un flag."""
        try:
            cache_key = f"{RedisKeys.FEATURE_FLAG_CACHE}{flag_name}"
            redis_client.client.delete(cache_key)
        except Exception:
            logger.debug("Failed to invalidate feature flag cache '%s'", flag_name)
