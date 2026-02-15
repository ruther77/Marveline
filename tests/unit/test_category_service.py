"""Tests unitaires pour CategoryService."""
import pytest
from fastapi import HTTPException
from app.models.category import Category
from app.models.product import Product
from app.services.category import CategoryService
from app.repositories.category import CategoryRepository
from app.utils.slug import slugify
from app.constants import ErrorMessages


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _make_category(db, tenant_id=1, name="Test Category", slug=None, parent_id=None, display_order=0):
    """Cree une categorie de test."""
    cat = Category(
        tenant_id=tenant_id,
        name=name,
        slug=slug or slugify(name),
        parent_id=parent_id,
        display_order=display_order,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def _make_product(db, tenant_id=1, name="Produit Test", sku="PRD-001", category="test_category"):
    """Cree un produit de test."""
    prod = Product(
        tenant_id=tenant_id,
        name=name,
        sku=sku,
        category=category,
        price_per_day=250,
        deposit_amount=0,
        stock_quantity=10,
        available_quantity=10,
        condition="bon",
    )
    db.add(prod)
    db.commit()
    db.refresh(prod)
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

class TestCreateCategory:
    """Tests pour CategoryService.create_category."""

    def test_create_with_auto_slug(self, test_db):
        service = CategoryService(test_db)
        from app.schemas.category import CategoryCreate
        data = CategoryCreate(name="Assiettes")
        cat = service.create_category(data, tenant_id=1)
        test_db.commit()
        assert cat.name == "Assiettes"
        assert cat.slug == "assiettes"
        assert cat.tenant_id == 1

    def test_create_with_explicit_slug(self, test_db):
        service = CategoryService(test_db)
        from app.schemas.category import CategoryCreate
        data = CategoryCreate(name="Verres a vin", slug="verres_vin")
        cat = service.create_category(data, tenant_id=1)
        test_db.commit()
        assert cat.slug == "verres_vin"

    def test_create_with_valid_parent(self, test_db):
        parent = _make_category(test_db, name="Mobilier")
        service = CategoryService(test_db)
        from app.schemas.category import CategoryCreate
        data = CategoryCreate(name="Tables", parent_id=parent.id)
        cat = service.create_category(data, tenant_id=1)
        test_db.commit()
        assert cat.parent_id == parent.id

    def test_create_with_invalid_parent_raises(self, test_db):
        service = CategoryService(test_db)
        from app.schemas.category import CategoryCreate
        data = CategoryCreate(name="Orphan", parent_id=99999)
        with pytest.raises(HTTPException) as exc_info:
            service.create_category(data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.CATEGORY_PARENT_NOT_FOUND in exc_info.value.detail

    def test_create_slug_duplicate_raises(self, test_db):
        _make_category(test_db, name="Chaises", slug="chaises")
        service = CategoryService(test_db)
        from app.schemas.category import CategoryCreate
        data = CategoryCreate(name="Chaises Luxe", slug="chaises")
        with pytest.raises(HTTPException) as exc_info:
            service.create_category(data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.CATEGORY_SLUG_EXISTS in exc_info.value.detail

    def test_create_name_duplicate_raises(self, test_db):
        _make_category(test_db, name="Nappes", slug="nappes_existing")
        service = CategoryService(test_db)
        from app.schemas.category import CategoryCreate
        data = CategoryCreate(name="Nappes", slug="nappes_new")
        with pytest.raises(HTTPException) as exc_info:
            service.create_category(data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.CATEGORY_NAME_EXISTS in exc_info.value.detail

    def test_create_with_description_and_image(self, test_db):
        service = CategoryService(test_db)
        from app.schemas.category import CategoryCreate
        data = CategoryCreate(
            name="Decorations",
            description="Toute la deco",
            image_url="https://cdn.example.com/deco.jpg",
            display_order=5,
        )
        cat = service.create_category(data, tenant_id=1)
        test_db.commit()
        assert cat.description == "Toute la deco"
        assert cat.image_url == "https://cdn.example.com/deco.jpg"
        assert cat.display_order == 5


# ─────────────────────────────────────────────────────────────────────
# Update
# ─────────────────────────────────────────────────────────────────────

class TestUpdateCategory:
    """Tests pour CategoryService.update_category."""

    def test_update_name(self, test_db):
        cat = _make_category(test_db, name="Old Name")
        service = CategoryService(test_db)
        from app.schemas.category import CategoryUpdate
        data = CategoryUpdate(name="New Name")
        updated = service.update_category(cat.id, data, tenant_id=1)
        test_db.commit()
        assert updated.name == "New Name"

    def test_update_slug_unique_violation_raises(self, test_db):
        _make_category(test_db, name="Cat A", slug="cat_a")
        cat_b = _make_category(test_db, name="Cat B", slug="cat_b")
        service = CategoryService(test_db)
        from app.schemas.category import CategoryUpdate
        data = CategoryUpdate(slug="cat_a")
        with pytest.raises(HTTPException) as exc_info:
            service.update_category(cat_b.id, data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.CATEGORY_SLUG_EXISTS in exc_info.value.detail

    def test_update_parent_self_cycle_raises(self, test_db):
        cat = _make_category(test_db, name="Self Ref")
        service = CategoryService(test_db)
        from app.schemas.category import CategoryUpdate
        data = CategoryUpdate(parent_id=cat.id)
        with pytest.raises(HTTPException) as exc_info:
            service.update_category(cat.id, data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.CATEGORY_PARENT_CYCLE in exc_info.value.detail

    def test_update_not_found_raises(self, test_db):
        service = CategoryService(test_db)
        from app.schemas.category import CategoryUpdate
        data = CategoryUpdate(name="Does Not Exist")
        with pytest.raises(HTTPException) as exc_info:
            service.update_category(99999, data, tenant_id=1)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# Delete
# ─────────────────────────────────────────────────────────────────────

class TestDeleteCategory:
    """Tests pour CategoryService.delete_category."""

    def test_delete_without_children(self, test_db):
        cat = _make_category(test_db, name="Leaf")
        service = CategoryService(test_db)
        result = service.delete_category(cat.id, tenant_id=1)
        test_db.commit()
        assert result is True
        # Verifier soft delete
        repo = CategoryRepository(test_db)
        deleted = repo.get_by_id(cat.id, tenant_id=1, include_inactive=True)
        assert deleted.is_active is False

    def test_delete_with_active_children_raises(self, test_db):
        parent = _make_category(test_db, name="Parent Cat")
        _make_category(test_db, name="Child Cat", parent_id=parent.id)
        service = CategoryService(test_db)
        with pytest.raises(HTTPException) as exc_info:
            service.delete_category(parent.id, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.CATEGORY_HAS_CHILDREN in exc_info.value.detail

    def test_delete_not_found_raises(self, test_db):
        service = CategoryService(test_db)
        with pytest.raises(HTTPException) as exc_info:
            service.delete_category(99999, tenant_id=1)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# Tree
# ─────────────────────────────────────────────────────────────────────

class TestGetTree:
    """Tests pour CategoryService.get_tree."""

    def test_tree_builds_correctly(self, test_db):
        root = _make_category(test_db, name="Root")
        child = _make_category(test_db, name="Child", parent_id=root.id)
        _make_category(test_db, name="Grandchild", parent_id=child.id)

        service = CategoryService(test_db)
        tree = service.get_tree(tenant_id=1)

        assert len(tree) == 1
        assert tree[0].name == "Root"
        assert len(tree[0].children) == 1
        assert tree[0].children[0].name == "Child"
        assert len(tree[0].children[0].children) == 1
        assert tree[0].children[0].children[0].name == "Grandchild"

    def test_tree_tenant_isolation(self, test_db):
        _make_category(test_db, tenant_id=1, name="Tenant 1 Cat")
        _make_category(test_db, tenant_id=2, name="Tenant 2 Cat")

        service = CategoryService(test_db)
        tree_t1 = service.get_tree(tenant_id=1)
        tree_t2 = service.get_tree(tenant_id=2)

        t1_names = [n.name for n in tree_t1]
        t2_names = [n.name for n in tree_t2]
        assert "Tenant 1 Cat" in t1_names
        assert "Tenant 2 Cat" not in t1_names
        assert "Tenant 2 Cat" in t2_names
        assert "Tenant 1 Cat" not in t2_names

    def test_tree_with_product_count(self, test_db):
        cat = _make_category(test_db, name="Verres", slug="verres")
        _make_product(test_db, name="Verre 1", sku="V-001", category="verres")
        _make_product(test_db, name="Verre 2", sku="V-002", category="verres")

        service = CategoryService(test_db)
        tree = service.get_tree(tenant_id=1)

        verres_node = next(n for n in tree if n.slug == "verres")
        assert verres_node.product_count == 2

    def test_tree_empty_tenant(self, test_db):
        service = CategoryService(test_db)
        tree = service.get_tree(tenant_id=999)
        assert tree == []
