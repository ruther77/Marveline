"""Service métier pour les produits."""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.models.product import Product
from app.repositories.product import ProductRepository
from app.schemas.product import ProductCreate, ProductUpdate


class ProductService:
    """Service métier pour gestion des produits.

    Responsibilities:
        - Création/modification produits avec validation
        - Gestion du stock (réservation/libération)
        - Vérification disponibilité
        - Validation règles métier

    Transactions:
        - Pas de commit automatique
        - Rollback automatique en cas d'exception
    """

    def __init__(self, db: Session):
        """Initialise le service produit.

        Args:
            db: Session SQLAlchemy active
        """
        self.db = db
        self.repo = ProductRepository(db)

    def create_product(
        self,
        product_data: ProductCreate,
        tenant_id: int
    ) -> Product:
        """Crée un nouveau produit.

        Args:
            product_data: Données du produit (DTO)
            tenant_id: ID du tenant (depuis JWT)

        Returns:
            Produit créé

        Raises:
            HTTPException 400: Si SKU déjà existant ou données invalides

        Business Rules:
            - SKU unique par tenant
            - available_quantity <= stock_quantity
            - price_per_day >= 0

        Example:
            product = product_service.create_product(
                ProductCreate(name="...", sku="...", ...),
                tenant_id=1
            )
            db.commit()
        """
        # Vérifier unicité SKU
        if self.repo.sku_exists(product_data.sku, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product with SKU '{product_data.sku}' already exists"
            )

        # Créer modèle
        product = Product(
            tenant_id=tenant_id,
            name=product_data.name,
            sku=product_data.sku,
            category=product_data.category,
            price_per_day=product_data.price_per_day_cents,
            deposit_amount=product_data.deposit_amount_cents,
            stock_quantity=product_data.stock_quantity,
            available_quantity=product_data.available_quantity,
            condition=product_data.condition,
            image_url=product_data.image_url,
            is_active=True
        )

        # Validation métier : available <= stock
        if product.available_quantity > product.stock_quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="available_quantity cannot exceed stock_quantity"
            )

        try:
            return self.repo.create(product)
        except IntegrityError as e:
            # Race condition : SKU déjà créé par thread concurrent
            if "unique constraint" in str(e).lower() or "sku" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product with SKU '{product.sku}' already exists"
                )
            raise

    def update_product(
        self,
        product_id: int,
        product_data: ProductUpdate,
        tenant_id: int
    ) -> Product:
        """Met à jour un produit existant.

        Args:
            product_id: ID du produit
            product_data: Données à mettre à jour (PATCH partiel)
            tenant_id: ID du tenant (depuis JWT)

        Returns:
            Produit mis à jour

        Raises:
            HTTPException 404: Si produit non trouvé
            HTTPException 400: Si validation échoue

        Business Rules:
            - SKU immutable (ne peut pas être changé)
            - available_quantity <= stock_quantity

        Example:
            product = product_service.update_product(
                product_id=1,
                ProductUpdate(price_per_day_cents=300),
                tenant_id=1
            )
            db.commit()
        """
        # Charger produit
        product = self.repo.get_by_id(product_id, tenant_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )

        # Appliquer modifications (PATCH partiel)
        update_data = product_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            # Mapping champs DTO → modèle
            if field == "price_per_day_cents":
                setattr(product, "price_per_day", value)
            elif field == "deposit_amount_cents":
                setattr(product, "deposit_amount", value)
            else:
                setattr(product, field, value)

        # Validation métier : available <= stock
        if product.available_quantity > product.stock_quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="available_quantity cannot exceed stock_quantity"
            )

        return self.repo.update(product)

    def reserve_stock(
        self,
        product_id: int,
        quantity: int,
        tenant_id: int
    ) -> bool:
        """Réserve du stock pour une réservation.

        Args:
            product_id: ID du produit
            quantity: Quantité à réserver
            tenant_id: ID du tenant

        Returns:
            True si réservation réussie

        Raises:
            HTTPException 404: Si produit non trouvé
            HTTPException 400: Si stock insuffisant

        Business Rules:
            - Vérifie available_quantity >= quantity
            - Décrémente available_quantity
            - Transaction atomique (commit dans service appelant)

        Warning:
            - Pas de commit automatique
            - À appeler dans une transaction (ex: confirm_reservation)

        Example:
            product_service.reserve_stock(product_id=1, quantity=10, tenant_id=1)
            # Autres opérations...
            db.commit()  # Transaction atomique
        """
        # Vérifier disponibilité
        if not self.repo.check_availability(product_id, quantity, tenant_id):
            product = self.repo.get_by_id(product_id, tenant_id)
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Product not found"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock. Available: {product.available_quantity}, Requested: {quantity}"
            )

        # Réserver stock
        success = self.repo.reserve_stock(product_id, quantity, tenant_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to reserve stock"
            )

        return True

    def release_stock(
        self,
        product_id: int,
        quantity: int,
        tenant_id: int
    ) -> bool:
        """Libère du stock (annulation réservation).

        Args:
            product_id: ID du produit
            quantity: Quantité à libérer
            tenant_id: ID du tenant

        Returns:
            True si libération réussie

        Raises:
            HTTPException 404: Si produit non trouvé

        Business Rules:
            - Incrémente available_quantity
            - Plafonne à stock_quantity (pas de sur-libération)
            - Transaction atomique

        Warning:
            - Pas de commit automatique
            - À appeler dans une transaction

        Example:
            product_service.release_stock(product_id=1, quantity=10, tenant_id=1)
            db.commit()
        """
        success = self.repo.release_stock(product_id, quantity, tenant_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )

        return True

    def delete_product(
        self,
        product_id: int,
        tenant_id: int,
        hard_delete: bool = False
    ) -> bool:
        """Supprime un produit (soft ou hard delete).

        Args:
            product_id: ID du produit
            tenant_id: ID du tenant
            hard_delete: Si True, suppression physique (défaut: soft delete)

        Returns:
            True si suppression réussie

        Raises:
            HTTPException 404: Si produit non trouvé
            HTTPException 400: Si contraintes FK (hard delete)

        Business Rules:
            - Soft delete par défaut (is_active=False)
            - Hard delete seulement si aucune réservation liée

        Warning:
            - Pas de commit automatique

        Example:
            product_service.delete_product(product_id=1, tenant_id=1)
            db.commit()
        """
        if hard_delete:
            success = self.repo.hard_delete(product_id, tenant_id)
        else:
            success = self.repo.soft_delete(product_id, tenant_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )

        return True
