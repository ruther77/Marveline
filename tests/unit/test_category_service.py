"""Tests unitaires pour CategoryService."""
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.models.category import Category
from app.models.product import Product
from app.services.category import CategoryService
from app.utils.slug import slugify
from app.constants import ErrorMessages


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

async def _make_category(db, tenant_id=1, name="Test Category", slug=None,
                         parent_id=None, display_order=0):
    """Cree une categorie de test."""
    cat = Category(
        tenant_id=tenant_id,
        name=name,
        slug=slug or slugify(name),
        parent_id=parent_id,
        display_order=display_order,
    )
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return cat


async def _make_product(db, tenant_id=1, name="Produit Test", sku="PRD-001",
                        category="test_category"):
    """Cree un produit de test."""
    prod = Product(
        tenant_id=tenant_id,
        name=name,
        sku=sku,
        category=category,
        price_per_day_cents=250,
        deposit_amount_cents=0,
        stock_quantity=10,
        available_quantity=10,
        condition="bon",
    )
    db.add(prod)
    await db.flush()
    await db.refresh(prod)
    return prod


# ─────────────────────────────────────────────────────────────────────
# Slugify
# ─────────────────────────────────────────────────────────────────────

class TestSlugify:
    """Tests pour la fonction slugify."""

    def test_basic_lowercase(self):
        assert slugify("Assiettes") == "assiettes"

    def test_spaces_to_underscores(self):
        assert slugify("Vaisselle Service") == "vaisselle_service"

    def test_accents_removed(self):
        assert slugify("Decoration Noel") == "decoration_noel"

    def test_hyphens_to_underscores(self):
        assert slugify("Mange-debout") == "mange_debout"

    def test_trim_and_collapse_spaces(self):
        assert slugify("  Candy  Bar  ") == "candy_bar"

    def test_special_chars_removed(self):
        assert slugify("Test@#$%Category!") == "test_category"

    def test_unicode_accents(self):
        assert slugify("Decors de fetes") == "decors_de_fetes"

    def test_empty_after_strip(self):
        assert slugify("@#$%") == ""


# ─────────────────────────────────────────────────────────────────────
# Create
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestCreateCategory:
    """Tests pour CategoryService.create_category."""

    async def test_create_with_auto_slug(self, async_db):
        service = CategoryService(async_db)
        from app.schemas.category import CategoryCreate
        data = CategoryCreate(name="Assiettes")
        cat = await service.create_category(data, tenant_id=1)
        await async_db.commit()
        assert cat.name == "Assiettes"
        assert cat.slug == "assiettes"
        assert cat.tenant_id == 1

    async def test_create_with_explicit_slug(self, async_db):
        service = CategoryService(async_db)
        from app.schemas.category import CategoryCreate
        data = CategoryCreate(name="Verres a vin", slug="verres_vin")
        cat = await service.create_category(data, tenant_id=1)
        await async_db.commit()
        assert cat.slug == "verres_vin"

    async def test_create_with_valid_parent(self, async_db):
        parent = await _make_category(async_db, name="Mobilier")
        service = CategoryService(async_db)
        from app.schemas.category import CategoryCreate
        data = CategoryCreate(name="Tables", parent_id=parent.id)
        cat = await service.create_category(data, tenant_id=1)
        await async_db.commit()
        assert cat.parent_id == parent.id

    async def test_create_with_invalid_parent_raises(self, async_db):
        service = CategoryService(async_db)
        from app.schemas.category import CategoryCreate
        data = CategoryCreate(name="Orphan", parent_id=99999)
        with pytest.raises(HTTPException) as exc_info:
            await service.create_category(data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.CATEGORY_PARENT_NOT_FOUND in exc_info.value.detail

    async def test_create_slug_duplicate_raises(self, async_db):
        await _make_category(async_db, name="Chaises", slug="chaises")
        service = CategoryService(async_db)
        from app.schemas.category import CategoryCreate
        data = CategoryCreate(name="Chaises Luxe", slug="chaises")
        with pytest.raises(HTTPException) as exc_info:
            await service.create_category(data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.CATEGORY_SLUG_EXISTS in exc_info.value.detail

    async def test_create_name_duplicate_raises(self, async_db):
        await _make_category(async_db, name="Nappes", slug="nappes_existing")
        service = CategoryService(async_db)
        from app.schemas.category import CategoryCreate
        data = CategoryCreate(name="Nappes", slug="nappes_new")
        with pytest.raises(HTTPException) as exc_info:
            await service.create_category(data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.CATEGORY_NAME_EXISTS in exc_info.value.detail

    async def test_create_with_description_and_image(self, async_db):
        service = CategoryService(async_db)
        from app.schemas.category import CategoryCreate
        data = CategoryCreate(
            name="Decorations",
            description="Toute la deco",
            image_url="https://cdn.example.com/deco.jpg",
            display_order=5,
        )
        cat = await service.create_category(data, tenant_id=1)
        await async_db.commit()
        assert cat.description == "Toute la deco"
        assert cat.image_url == "https://cdn.example.com/deco.jpg"
        assert cat.display_order == 5


# ─────────────────────────────────────────────────────────────────────
# Update
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestUpdateCategory:
    """Tests pour CategoryService.update_category."""

    async def test_update_name(self, async_db):
        cat = await _make_category(async_db, name="Old Name")
        service = CategoryService(async_db)
        from app.schemas.category import CategoryUpdate
        data = CategoryUpdate(name="New Name")
        updated = await service.update_category(cat.id, data, tenant_id=1)
        await async_db.commit()
        assert updated.name == "New Name"

    async def test_update_slug_unique_violation_raises(self, async_db):
        await _make_category(async_db, name="Cat A", slug="cat_a")
        cat_b = await _make_category(async_db, name="Cat B", slug="cat_b")
        service = CategoryService(async_db)
        from app.schemas.category import CategoryUpdate
        data = CategoryUpdate(slug="cat_a")
        with pytest.raises(HTTPException) as exc_info:
            await service.update_category(cat_b.id, data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.CATEGORY_SLUG_EXISTS in exc_info.value.detail

    async def test_update_parent_self_cycle_raises(self, async_db):
        cat = await _make_category(async_db, name="Self Ref")
        service = CategoryService(async_db)
        from app.schemas.category import CategoryUpdate
        data = CategoryUpdate(parent_id=cat.id)
        with pytest.raises(HTTPException) as exc_info:
            await service.update_category(cat.id, data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.CATEGORY_PARENT_CYCLE in exc_info.value.detail

    async def test_update_not_found_raises(self, async_db):
        service = CategoryService(async_db)
        from app.schemas.category import CategoryUpdate
        data = CategoryUpdate(name="Does Not Exist")
        with pytest.raises(HTTPException) as exc_info:
            await service.update_category(99999, data, tenant_id=1)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# Delete
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestDeleteCategory:
    """Tests pour CategoryService.delete_category."""

    async def test_delete_without_children(self, async_db):
        cat = await _make_category(async_db, name="Leaf")
        service = CategoryService(async_db)
        result = await service.delete_category(cat.id, tenant_id=1)
        await async_db.commit()
        assert result is True
        # Verifier soft delete via requête directe
        res = await async_db.execute(
            select(Category).where(Category.id == cat.id)
        )
        deleted = res.scalars().first()
        assert deleted is not None
        assert deleted.is_active is False

    async def test_delete_with_active_children_raises(self, async_db):
        parent = await _make_category(async_db, name="Parent Cat")
        await _make_category(async_db, name="Child Cat", parent_id=parent.id)
        service = CategoryService(async_db)
        with pytest.raises(HTTPException) as exc_info:
            await service.delete_category(parent.id, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.CATEGORY_HAS_CHILDREN in exc_info.value.detail

    async def test_delete_not_found_raises(self, async_db):
        service = CategoryService(async_db)
        with pytest.raises(HTTPException) as exc_info:
            await service.delete_category(99999, tenant_id=1)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# Tree
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestGetTree:
    """Tests pour CategoryService.get_tree."""

    async def test_tree_builds_correctly(self, async_db):
        root = await _make_category(async_db, name="Root")
        child = await _make_category(async_db, name="Child", parent_id=root.id)
        await _make_category(async_db, name="Grandchild", parent_id=child.id)

        service = CategoryService(async_db)
        tree = await service.get_tree(tenant_id=1)

        assert len(tree) == 1
        assert tree[0].name == "Root"
        assert len(tree[0].children) == 1
        assert tree[0].children[0].name == "Child"
        assert len(tree[0].children[0].children) == 1
        assert tree[0].children[0].children[0].name == "Grandchild"

    async def test_tree_tenant_isolation(self, async_db):
        await _make_category(async_db, tenant_id=1, name="Tenant 1 Cat")
        await _make_category(async_db, tenant_id=2, name="Tenant 2 Cat")

        service = CategoryService(async_db)
        tree_t1 = await service.get_tree(tenant_id=1)
        tree_t2 = await service.get_tree(tenant_id=2)

        t1_names = [n.name for n in tree_t1]
        t2_names = [n.name for n in tree_t2]
        assert "Tenant 1 Cat" in t1_names
        assert "Tenant 2 Cat" not in t1_names
        assert "Tenant 2 Cat" in t2_names
        assert "Tenant 1 Cat" not in t2_names

    async def test_tree_with_product_count(self, async_db):
        await _make_category(async_db, name="Verres", slug="verres")
        await _make_product(async_db, name="Verre 1", sku="V-001", category="verres")
        await _make_product(async_db, name="Verre 2", sku="V-002", category="verres")

        service = CategoryService(async_db)
        tree = await service.get_tree(tenant_id=1)

        verres_node = next(n for n in tree if n.slug == "verres")
        assert verres_node.product_count == 2

    async def test_tree_empty_tenant(self, async_db):
        service = CategoryService(async_db)
        tree = await service.get_tree(tenant_id=999)
        assert tree == []
