"""Repository pour l'entité Product."""
from typing import Optional
from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.product import Product
from app.models.product_image import ProductImage
from app.repositories.base import BaseRepository, AsyncBaseRepository


class ProductRepository(BaseRepository[Product]):
    """Repository pour les produits avec méthodes spécialisées."""

    def __init__(self, db: Session):
        """Initialise le repository Product.

        Args:
            db: Session SQLAlchemy active
        """
        super().__init__(db, Product)

    def get_by_sku(
        self,
        sku: str,
        tenant_id: int,
        include_inactive: bool = False
    ) -> Optional[Product]:
        """Récupère un produit par son SKU (unique par tenant).

        Args:
            sku: Code produit (normalisé en majuscules)
            tenant_id: ID du tenant (OBLIGATOIRE)
            include_inactive: Inclure les produits soft-deleted

        Returns:
            Le produit trouvé ou None

        Security:
            - Filtre tenant_id automatique
            - SKU normalisé en uppercase
        """
        query = select(Product).filter(
            Product.sku == sku.upper().strip()
        )
        query = self._apply_tenant_filter(query, tenant_id)

        if not include_inactive:
            query = self._apply_active_filter(query)

        result = self.db.execute(query).scalar_one_or_none()
        return result

    def sku_exists(
        self,
        sku: str,
        tenant_id: int,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Vérifie si un SKU existe déjà (pour validation unicité).

        Args:
            sku: SKU à vérifier
            tenant_id: ID du tenant (OBLIGATOIRE)
            exclude_id: ID du produit à exclure (pour UPDATE)

        Returns:
            True si le SKU existe déjà, False sinon
        """
        query = select(Product).filter(
            Product.sku == sku.upper().strip()
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)

        if exclude_id:
            query = query.filter(Product.id != exclude_id)

        result = self.db.execute(query).scalar_one_or_none()
        return result is not None

    def list_by_category(
        self,
        category: str,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> list[Product]:
        """Liste les produits filtrés par catégorie.

        Args:
            category: Catégorie ('assiette', 'verre', 'couvert', etc.)
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination

        Returns:
            Liste des produits de la catégorie spécifiée
        """
        return self.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters={"category": category}
        )

    def list_available(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None
    ) -> list[Product]:
        """Liste les produits disponibles (available_quantity > 0 et actifs).

        Args:
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination
            category: Filtrer par catégorie (optionnel)

        Returns:
            Liste des produits disponibles

        Security:
            - Filtre tenant_id automatique
            - Filtre is_active automatique
        """
        query = select(Product).filter(
            Product.available_quantity > 0
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)

        if category:
            query = query.filter(Product.category == category)

        query = query.order_by(Product.category, Product.name)
        query = query.offset(skip).limit(min(limit, 1000))

        result = self.db.execute(query).scalars().all()
        return list(result)

    def check_availability(
        self,
        product_id: int,
        quantity: int,
        tenant_id: int
    ) -> bool:
        """Vérifie si une quantité de produit est disponible.

        Args:
            product_id: ID du produit
            quantity: Quantité demandée
            tenant_id: ID du tenant (OBLIGATOIRE)

        Returns:
            True si la quantité est disponible, False sinon

        Use cases:
            - Avant création réservation
            - Avant confirmation réservation
        """
        product = self.get_by_id(product_id, tenant_id, include_inactive=False)
        if not product:
            return False

        return product.available_quantity >= quantity

    def _get_for_update(self, product_id: int, tenant_id: int) -> "Product | None":
        """Récupère un produit avec verrou exclusif (SELECT FOR UPDATE).

        Bypass le cache pour obtenir un row lock PostgreSQL.
        Empêche les race conditions sur les opérations de stock concurrentes.
        """
        query = select(Product).where(
            and_(
                Product.id == product_id,
                Product.tenant_id == tenant_id,
                Product.is_active == True,  # noqa: E712
            )
        ).with_for_update()
        return self.db.execute(query).scalar_one_or_none()

    def reserve_stock(
        self,
        product_id: int,
        quantity: int,
        tenant_id: int
    ) -> bool:
        """Réserve du stock (available_quantity -= quantity).

        Args:
            product_id: ID du produit
            quantity: Quantité à réserver
            tenant_id: ID du tenant (OBLIGATOIRE)

        Returns:
            True si réservation réussie, False si stock insuffisant

        Warning:
            - Pas de commit automatique (transaction gérée par service)
            - Utilise SELECT FOR UPDATE pour éviter les race conditions (fix B6)

        Security:
            - Filtre tenant_id automatique
        """
        product = self._get_for_update(product_id, tenant_id)
        if not product or product.available_quantity < quantity:
            return False

        product.available_quantity -= quantity
        self.db.flush()
        return True

    def release_stock(
        self,
        product_id: int,
        quantity: int,
        tenant_id: int
    ) -> bool:
        """Libère du stock (available_quantity += quantity).

        Args:
            product_id: ID du produit
            quantity: Quantité à libérer
            tenant_id: ID du tenant (OBLIGATOIRE)

        Returns:
            True si libération réussie, False si produit non trouvé

        Warning:
            - Pas de commit automatique
            - Utilise SELECT FOR UPDATE pour éviter les race conditions (fix B6)

        Security:
            - Filtre tenant_id automatique
        """
        product = self._get_for_update(product_id, tenant_id)
        if not product:
            return False

        new_available = product.available_quantity + quantity
        if new_available > product.stock_quantity:
            new_available = product.stock_quantity

        product.available_quantity = new_available
        self.db.flush()
        return True

    def list_with_search(
        self,
        tenant_id: int,
        search_term: str,
        skip: int = 0,
        limit: int = 100,
        condition: Optional[str] = None,
        supplier_id: Optional[int] = None,
    ) -> tuple[list[Product], int]:
        """Liste paginée avec count, filtrée par nom/SKU (ilike).

        Returns:
            Tuple (items, total)
        """
        search_pattern = f"%{search_term.lower()}%"
        name_sku_filter = (
            (Product.name.ilike(search_pattern)) |
            (Product.sku.ilike(search_pattern))
        )

        count_q = select(func.count()).select_from(Product).filter(name_sku_filter)
        count_q = self._apply_tenant_filter(count_q, tenant_id)
        count_q = self._apply_active_filter(count_q)
        if condition:
            count_q = count_q.filter(Product.condition == condition)
        if supplier_id is not None:
            count_q = count_q.filter(Product.supplier_id == supplier_id)
        total = self.db.execute(count_q).scalar() or 0

        query = select(Product).filter(name_sku_filter)
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        if condition:
            query = query.filter(Product.condition == condition)
        if supplier_id is not None:
            query = query.filter(Product.supplier_id == supplier_id)
        query = query.order_by(Product.category, Product.name)
        query = query.offset(skip).limit(min(limit, 1000))
        result = self.db.execute(query).scalars().all()
        return (list(result), total)

    def search_by_name(
        self,
        search_term: str,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> list[Product]:
        """Recherche des produits par nom ou SKU.

        Args:
            search_term: Terme de recherche (case-insensitive)
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination

        Returns:
            Liste des produits correspondants

        Security:
            - Filtre tenant_id automatique
        """
        search_pattern = f"%{search_term.lower()}%"

        query = select(Product).filter(
            (Product.name.ilike(search_pattern)) |
            (Product.sku.ilike(search_pattern))
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        query = query.order_by(Product.category, Product.name)
        query = query.offset(skip).limit(min(limit, 1000))

        result = self.db.execute(query).scalars().all()
        return list(result)


class AsyncProductRepository(AsyncBaseRepository[Product]):
    """Version async de ProductRepository pour FastAPI."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Product)

    async def get_by_id_with_images(
        self, product_id: int, tenant_id: int, include_inactive: bool = False
    ) -> Optional[Product]:
        """Récupère un produit avec ses images eagerly-loaded (évite MissingGreenlet)."""
        query = (
            select(Product)
            .filter(Product.id == product_id)
            .options(selectinload(Product.images))
        )
        query = self._apply_tenant_filter(query, tenant_id)
        if not include_inactive:
            query = self._apply_active_filter(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_sku(
        self, sku: str, tenant_id: int, include_inactive: bool = False
    ) -> Optional[Product]:
        query = select(Product).filter(Product.sku == sku.upper().strip())
        query = self._apply_tenant_filter(query, tenant_id)
        if not include_inactive:
            query = self._apply_active_filter(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def sku_exists(
        self, sku: str, tenant_id: int, exclude_id: Optional[int] = None
    ) -> bool:
        query = select(Product).filter(Product.sku == sku.upper().strip())
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        if exclude_id:
            query = query.filter(Product.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def list_by_category(
        self, category: str, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> list[Product]:
        items, _ = await self.list(
            tenant_id=tenant_id, skip=skip, limit=limit, filters={"category": category}
        )
        return items

    async def list_available(
        self, tenant_id: int, skip: int = 0, limit: int = 100, category: Optional[str] = None
    ) -> list[Product]:
        query = select(Product).filter(Product.available_quantity > 0)
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        if category:
            query = query.filter(Product.category == category)
        query = query.order_by(Product.category, Product.name).offset(skip).limit(min(limit, 1000))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def check_availability(self, product_id: int, quantity: int, tenant_id: int) -> bool:
        product = await self.get_by_id(product_id, tenant_id, include_inactive=False)
        if not product:
            return False
        return product.available_quantity >= quantity

    async def _get_for_update(self, product_id: int, tenant_id: int) -> "Product | None":
        query = select(Product).where(
            and_(
                Product.id == product_id,
                Product.tenant_id == tenant_id,
                Product.is_active == True,  # noqa: E712
            )
        ).with_for_update()
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def reserve_stock(self, product_id: int, quantity: int, tenant_id: int) -> bool:
        product = await self._get_for_update(product_id, tenant_id)
        if not product or product.available_quantity < quantity:
            return False
        product.available_quantity -= quantity
        await self.db.flush()
        return True

    async def release_stock(self, product_id: int, quantity: int, tenant_id: int) -> bool:
        product = await self._get_for_update(product_id, tenant_id)
        if not product:
            return False
        new_available = product.available_quantity + quantity
        if new_available > product.stock_quantity:
            new_available = product.stock_quantity
        product.available_quantity = new_available
        await self.db.flush()
        return True

    async def sync_available_from_variants(self, product_id: int, tenant_id: int) -> None:
        """Recalcule products.available_quantity et stock_quantity depuis les variantes actives.

        Source de vérité unique : SUM des variantes actives.
        Appelé après chaque reserve/release/create/delete sur une variante.
        Partage la même AsyncSession → même transaction implicite que l'UPDATE variant.
        """
        from sqlalchemy import update
        from app.models.product_variant import ProductVariant

        subq_available = (
            select(func.coalesce(func.sum(ProductVariant.available_quantity), 0))
            .where(
                ProductVariant.product_id == product_id,
                ProductVariant.tenant_id == tenant_id,
                ProductVariant.is_active == True,  # noqa: E712
            )
            .scalar_subquery()
        )
        subq_stock = (
            select(func.coalesce(func.sum(ProductVariant.stock_quantity), 0))
            .where(
                ProductVariant.product_id == product_id,
                ProductVariant.tenant_id == tenant_id,
                ProductVariant.is_active == True,  # noqa: E712
            )
            .scalar_subquery()
        )
        await self.db.execute(
            update(Product)
            .where(Product.id == product_id, Product.tenant_id == tenant_id)
            .values(available_quantity=subq_available, stock_quantity=subq_stock)
        )

    async def list_with_search(
        self,
        tenant_id: int,
        search_term: str,
        skip: int = 0,
        limit: int = 100,
        condition: Optional[str] = None,
        supplier_id: Optional[int] = None,
    ) -> tuple[list[Product], int]:
        search_pattern = f"%{search_term.lower()}%"
        name_sku_filter = (
            (Product.name.ilike(search_pattern)) | (Product.sku.ilike(search_pattern))
        )
        count_q = select(func.count()).select_from(Product).filter(name_sku_filter)
        count_q = self._apply_tenant_filter(count_q, tenant_id)
        count_q = self._apply_active_filter(count_q)
        if condition:
            count_q = count_q.filter(Product.condition == condition)
        if supplier_id is not None:
            count_q = count_q.filter(Product.supplier_id == supplier_id)
        total_result = await self.db.execute(count_q)
        total = total_result.scalar() or 0

        query = select(Product).filter(name_sku_filter)
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        if condition:
            query = query.filter(Product.condition == condition)
        if supplier_id is not None:
            query = query.filter(Product.supplier_id == supplier_id)
        query = query.order_by(Product.category, Product.name).offset(skip).limit(min(limit, 1000))
        result = await self.db.execute(query)
        return (list(result.scalars().all()), total)

    async def search_by_name(
        self, search_term: str, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> list[Product]:
        search_pattern = f"%{search_term.lower()}%"
        query = select(Product).filter(
            (Product.name.ilike(search_pattern)) | (Product.sku.ilike(search_pattern))
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        query = query.order_by(Product.category, Product.name).offset(skip).limit(min(limit, 1000))
        result = await self.db.execute(query)
        return list(result.scalars().all())
