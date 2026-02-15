"""Repository de base générique avec isolation multi-tenant stricte."""
from typing import Generic, TypeVar, Type, Optional, Any
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session
from sqlalchemy.orm.util import identity_key
from app.models.base import Base, TenantMixin, SoftDeleteMixin
from app.services.cache import cache_service, cache_invalidate
from app.core.metrics import cache_hits_total, cache_misses_total, cache_hit_rate


# Type générique pour le modèle
T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Repository de base générique pour toutes les entités.

    Fournit les opérations CRUD de base avec:
        - Isolation multi-tenant stricte (filtre tenant_id automatique)
        - Support soft delete (filtre is_active automatique)
        - Pagination
        - Filtres personnalisés

    Type Parameters:
        T: Type du modèle SQLAlchemy (doit hériter de Base)

    Attributes:
        db: Session SQLAlchemy
        model_class: Classe du modèle SQLAlchemy

    Security:
        - TOUS les queries filtrent automatiquement sur tenant_id
        - Impossible d'accéder aux données d'un autre tenant
        - Cross-tenant access → None (pas d'erreur 404 explicite pour éviter info leakage)
    """

    def __init__(self, db: Session, model_class: Type[T]):
        """Initialise le repository.

        Args:
            db: Session SQLAlchemy active
            model_class: Classe du modèle SQLAlchemy
        """
        self.db = db
        self.model_class = model_class
        self._cache_ttl_map = {
            "Product": 300,      # 5 min (catalogue stable)
            "Customer": 600,     # 10 min (changements rares)
            "Reservation": 60,   # 1 min (statut change souvent)
            "Invoice": 180,      # 3 min (medium volatilité)
        }

    def _get_cache_key(self, entity_id: int, tenant_id: int) -> str:
        """Génère clé cache pour entité.

        Args:
            entity_id: ID de l'entité
            tenant_id: ID du tenant

        Returns:
            Clé cache format "entity:tenant_id:id"

        Example:
            >>> repo._get_cache_key(123, 1)
            "product:1:123"
        """
        entity_name = self.model_class.__name__.lower()
        return f"{entity_name}:{tenant_id}:{entity_id}"

    def _get_cache_ttl(self) -> int:
        """Retourne TTL cache approprié pour type d'entité.

        Returns:
            TTL en secondes (défaut 300s si entité inconnue)
        """
        entity_name = self.model_class.__name__
        return self._cache_ttl_map.get(entity_name, 300)

    def _has_tenant_mixin(self) -> bool:
        """Vérifie si le modèle hérite de TenantMixin."""
        return issubclass(self.model_class, TenantMixin)

    def _has_soft_delete_mixin(self) -> bool:
        """Vérifie si le modèle hérite de SoftDeleteMixin."""
        return issubclass(self.model_class, SoftDeleteMixin)

    def _apply_tenant_filter(self, query, tenant_id: int):
        """Applique le filtre tenant_id si le modèle a TenantMixin.

        Args:
            query: Query SQLAlchemy
            tenant_id: ID du tenant

        Returns:
            Query avec filtre tenant_id appliqué
        """
        if self._has_tenant_mixin():
            return query.filter(self.model_class.tenant_id == tenant_id)
        return query

    def _apply_active_filter(self, query):
        """Applique le filtre is_active=True si le modèle a SoftDeleteMixin.

        Args:
            query: Query SQLAlchemy

        Returns:
            Query avec filtre is_active appliqué
        """
        if self._has_soft_delete_mixin():
            return query.filter(self.model_class.is_active == True)
        return query

    def _update_cache_hit_rate(self, entity_name: str) -> None:
        """Calcule et met à jour la métrique cache_hit_rate.

        Args:
            entity_name: Nom de l'entité (product, customer, etc.)

        Note:
            - Calcule hits / (hits + misses) depuis les counters Prometheus
            - Met à jour la Gauge cache_hit_rate pour cette entité
            - Appelé après chaque get_by_id() pour maintenir métrique à jour
        """
        try:
            # Récupérer les valeurs actuelles des counters
            hits = cache_hits_total.labels(entity=entity_name)._value.get()
            misses = cache_misses_total.labels(entity=entity_name)._value.get()

            total = hits + misses
            if total > 0:
                hit_rate_value = hits / total
                cache_hit_rate.labels(entity=entity_name).set(hit_rate_value)
        except Exception:
            # Fail silently - métriques non critiques
            pass

    def get_by_id(
        self,
        id: int,
        tenant_id: int,
        include_inactive: bool = False
    ) -> Optional[T]:
        """Récupère une entité par son ID avec filtre tenant strict + cache Redis.

        Args:
            id: ID de l'entité
            tenant_id: ID du tenant (OBLIGATOIRE pour sécurité)
            include_inactive: Inclure les entités soft-deleted (défaut: False)

        Returns:
            L'entité trouvée ou None (cross-tenant access → None)

        Security:
            - Filtre tenant_id automatique
            - Retourne None si autre tenant (pas 404 pour éviter info leakage)

        Performance:
            - Cache Redis layer (TTL différencié par entité)
            - Cache HIT → ~2-5ms (95% réduction latence vs DB)
            - Cache MISS → Query DB + cache result
        """
        # 1. Check cache Redis (fail-open strategy)
        cache_key = self._get_cache_key(id, tenant_id)
        cached_data = cache_service.get(cache_key)

        if cached_data is not None:
            # Cache HIT
            entity_name = self.model_class.__name__.lower()
            cache_hits_total.labels(entity=entity_name).inc()
            self._update_cache_hit_rate(entity_name)

            # Vérifier si l'instance est déjà dans la session (identity map).
            # Si oui, retourner l'instance en session — elle a l'état le plus récent
            # (avec d'éventuelles modifications dirty non encore flush).
            # merge() écraserait ces modifications avec les données stales du cache.
            key = identity_key(class_=self.model_class, ident=(id,))
            existing = self.db.identity_map.get(key)
            if existing is not None:
                # Valider isolation tenant
                if self._has_tenant_mixin() and existing.tenant_id != tenant_id:
                    return None
                # Valider soft delete
                if not include_inactive and self._has_soft_delete_mixin() and not existing.is_active:
                    return None
                return existing

            # Pas en session → reconstruire depuis cache et attacher
            instance = self.model_class.from_dict(cached_data)
            instance = self.db.merge(instance)
            return instance

        # 2. Cache MISS → Query DB
        entity_name = self.model_class.__name__.lower()
        cache_misses_total.labels(entity=entity_name).inc()
        self._update_cache_hit_rate(entity_name)

        query = select(self.model_class).filter(self.model_class.id == id)
        query = self._apply_tenant_filter(query, tenant_id)

        if not include_inactive:
            query = self._apply_active_filter(query)

        result = self.db.execute(query).scalar_one_or_none()

        # 3. Cacher résultat si trouvé (sérialiser ORM → dict)
        if result is not None:
            ttl = self._get_cache_ttl()
            cache_service.set(cache_key, result.to_dict(), ttl=ttl)

        return result

    def list(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[dict[str, Any]] = None,
        include_inactive: bool = False,
        order_by: Optional[str] = None
    ) -> list[T]:
        """Liste les entités avec pagination et filtres.

        Args:
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Nombre d'éléments à sauter (offset)
            limit: Nombre maximum d'éléments à retourner (max 1000)
            filters: Dictionnaire de filtres additionnels (ex: {"status": "active"})
            include_inactive: Inclure les entités soft-deleted
            order_by: Nom de la colonne pour tri (défaut: "id")

        Returns:
            Tuple (items, total) où items est la liste paginée et total le nombre total d'entités

        Security:
            - Filtre tenant_id automatique
            - Seules les entités du tenant courant sont retournées
        """
        # Limite max sécurité
        limit = min(limit, 1000)

        # Compter le total d'abord
        total = self.count(tenant_id=tenant_id, filters=filters, include_inactive=include_inactive)

        query = select(self.model_class)
        query = self._apply_tenant_filter(query, tenant_id)

        if not include_inactive:
            query = self._apply_active_filter(query)

        # Filtres additionnels
        if filters:
            for key, value in filters.items():
                # Parser les opérateurs de comparaison (ex: "available_quantity__gt")
                if "__" in key:
                    field_name, operator = key.rsplit("__", 1)
                    if not hasattr(self.model_class, field_name):
                        continue

                    field = getattr(self.model_class, field_name)

                    # Appliquer l'opérateur approprié
                    if operator == "gt":
                        query = query.filter(field > value)
                    elif operator == "gte":
                        query = query.filter(field >= value)
                    elif operator == "lt":
                        query = query.filter(field < value)
                    elif operator == "lte":
                        query = query.filter(field <= value)
                    elif operator == "ne":
                        query = query.filter(field != value)
                    else:
                        # Opérateur inconnu, ignorer
                        continue
                elif hasattr(self.model_class, key):
                    query = query.filter(getattr(self.model_class, key) == value)

        # Tri
        if order_by and hasattr(self.model_class, order_by):
            query = query.order_by(getattr(self.model_class, order_by))
        else:
            query = query.order_by(self.model_class.id)

        # Pagination
        query = query.offset(skip).limit(limit)

        result = self.db.execute(query).scalars().all()
        return (list(result), total)

    def count(
        self,
        tenant_id: int,
        filters: Optional[dict[str, Any]] = None,
        include_inactive: bool = False
    ) -> int:
        """Compte le nombre total d'entités (pour pagination).

        Args:
            tenant_id: ID du tenant (OBLIGATOIRE)
            filters: Dictionnaire de filtres additionnels
            include_inactive: Inclure les entités soft-deleted

        Returns:
            Nombre total d'entités correspondant aux critères

        Security:
            - Filtre tenant_id automatique
        """
        query = select(func.count()).select_from(self.model_class)
        query = self._apply_tenant_filter(query, tenant_id)

        if not include_inactive:
            query = self._apply_active_filter(query)

        # Filtres additionnels
        if filters:
            for key, value in filters.items():
                # Parser les opérateurs de comparaison (ex: "available_quantity__gt")
                if "__" in key:
                    field_name, operator = key.rsplit("__", 1)
                    if not hasattr(self.model_class, field_name):
                        continue

                    field = getattr(self.model_class, field_name)

                    # Appliquer l'opérateur approprié
                    if operator == "gt":
                        query = query.filter(field > value)
                    elif operator == "gte":
                        query = query.filter(field >= value)
                    elif operator == "lt":
                        query = query.filter(field < value)
                    elif operator == "lte":
                        query = query.filter(field <= value)
                    elif operator == "ne":
                        query = query.filter(field != value)
                    else:
                        # Opérateur inconnu, ignorer
                        continue
                elif hasattr(self.model_class, key):
                    query = query.filter(getattr(self.model_class, key) == value)

        result = self.db.execute(query).scalar()
        return result or 0

    def create(self, obj: T) -> T:
        """Crée une nouvelle entité.

        Args:
            obj: Instance du modèle à créer (tenant_id DOIT être déjà assigné)

        Returns:
            L'entité créée avec ID assigné

        Raises:
            ValueError: Si tenant_id manquant sur un modèle TenantMixin

        Security:
            - Validation que tenant_id est présent avant création
            - Pas de commit automatique (contrôle dans service layer)
        """
        # Validation tenant_id pour modèles multi-tenant
        if self._has_tenant_mixin():
            if not hasattr(obj, 'tenant_id') or obj.tenant_id is None:
                raise ValueError(
                    f"{self.model_class.__name__} requires tenant_id to be set before creation"
                )

        self.db.add(obj)
        self.db.flush()  # Assigne l'ID sans commit
        self.db.refresh(obj)
        return obj

    def update(self, obj: T) -> T:
        """Met à jour une entité existante + invalidation cache.

        Args:
            obj: Instance du modèle à mettre à jour (doit être attachée à la session)

        Returns:
            L'entité mise à jour

        Note:
            - Pas de commit automatique (contrôle dans service layer)
            - L'objet doit déjà être attaché à la session (via get_by_id)
            - Cache invalidé après flush (write-through pattern)
        """
        self.db.flush()
        self.db.refresh(obj)

        # Invalider cache pour cette entité (write-through)
        if hasattr(obj, 'id') and self._has_tenant_mixin() and hasattr(obj, 'tenant_id'):
            cache_key = self._get_cache_key(obj.id, obj.tenant_id)
            cache_service.delete(cache_key)

        return obj

    def soft_delete(self, id: int, tenant_id: int) -> bool:
        """Supprime logiquement une entité (is_active = False) + invalidation cache.

        Args:
            id: ID de l'entité
            tenant_id: ID du tenant (OBLIGATOIRE)

        Returns:
            True si suppression réussie, False si entité non trouvée

        Security:
            - Filtre tenant_id automatique
            - Cross-tenant → False (pas d'erreur)

        Note:
            - Fonctionne uniquement si le modèle a SoftDeleteMixin
            - Pas de commit automatique
            - Cache invalidé après suppression
        """
        if not self._has_soft_delete_mixin():
            raise NotImplementedError(
                f"{self.model_class.__name__} does not support soft delete (missing SoftDeleteMixin)"
            )

        obj = self.get_by_id(id, tenant_id, include_inactive=False)
        if not obj:
            return False

        obj.soft_delete()
        self.db.flush()

        # Invalider cache
        cache_key = self._get_cache_key(id, tenant_id)
        cache_service.delete(cache_key)

        return True

    def hard_delete(self, id: int, tenant_id: int) -> bool:
        """Supprime physiquement une entité de la base (DANGEREUX) + invalidation cache.

        Args:
            id: ID de l'entité
            tenant_id: ID du tenant (OBLIGATOIRE)

        Returns:
            True si suppression réussie, False si entité non trouvée

        Security:
            - Filtre tenant_id automatique
            - À utiliser avec PRÉCAUTION (préférer soft_delete)

        Warning:
            - Suppression irréversible
            - Peut violer contraintes FK (RESTRICT)
            - Pas de commit automatique
            - Cache invalidé après suppression
        """
        obj = self.get_by_id(id, tenant_id, include_inactive=True)
        if not obj:
            return False

        self.db.delete(obj)
        self.db.flush()

        # Invalider cache
        cache_key = self._get_cache_key(id, tenant_id)
        cache_service.delete(cache_key)

        return True

    def exists(self, id: int, tenant_id: int, include_inactive: bool = False) -> bool:
        """Vérifie si une entité existe.

        Args:
            id: ID de l'entité
            tenant_id: ID du tenant (OBLIGATOIRE)
            include_inactive: Inclure les entités soft-deleted

        Returns:
            True si l'entité existe, False sinon

        Security:
            - Filtre tenant_id automatique
        """
        return self.get_by_id(id, tenant_id, include_inactive) is not None

    def restore(self, id: int, tenant_id: int) -> bool:
        """Restaure une entité soft-deleted (is_active = True).

        Args:
            id: ID de l'entité
            tenant_id: ID du tenant (OBLIGATOIRE)

        Returns:
            True si restauration réussie, False si entité non trouvée

        Security:
            - Filtre tenant_id automatique

        Note:
            - Fonctionne uniquement si le modèle a SoftDeleteMixin
            - Pas de commit automatique
        """
        if not self._has_soft_delete_mixin():
            raise NotImplementedError(
                f"{self.model_class.__name__} does not support restore (missing SoftDeleteMixin)"
            )

        obj = self.get_by_id(id, tenant_id, include_inactive=True)
        if not obj or obj.is_active:
            return False

        obj.restore()
        self.db.flush()
        return True
