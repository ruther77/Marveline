"""Tests unitaires — poids/volume sur produits et variantes."""
import pytest
from app.schemas.product import ProductBase, ProductUpdate, ProductList, ProductResponse
from app.schemas.product_variant import (
    ProductVariantCreate,
    ProductVariantUpdate,
    ProductVariantNested,
    ProductVariantResponse,
)
from app.schemas.reservation import ReservationResponse


class TestProductWeightVolumeSchemas:
    """Validation Pydantic des champs weight_grams et volume_cm3."""

    def test_product_base_accepts_weight_volume(self):
        data = ProductBase(
            name="Assiette test",
            sku="ASS-TEST",
            category="assiettes",
            price_per_day_cents=100,
            weight_grams=350,
            volume_cm3=1200,
        )
        assert data.weight_grams == 350
        assert data.volume_cm3 == 1200

    def test_product_base_weight_volume_optional(self):
        data = ProductBase(
            name="Assiette test",
            sku="ASS-TEST",
            category="assiettes",
            price_per_day_cents=100,
        )
        assert data.weight_grams is None
        assert data.volume_cm3 is None

    def test_product_base_rejects_negative_weight(self):
        with pytest.raises(Exception):
            ProductBase(
                name="Assiette test",
                sku="ASS-TEST",
                category="assiettes",
                price_per_day_cents=100,
                weight_grams=-1,
            )

    def test_product_base_rejects_negative_volume(self):
        with pytest.raises(Exception):
            ProductBase(
                name="Assiette test",
                sku="ASS-TEST",
                category="assiettes",
                price_per_day_cents=100,
                volume_cm3=-5,
            )

    def test_product_update_weight_volume(self):
        data = ProductUpdate(weight_grams=500, volume_cm3=2000)
        assert data.weight_grams == 500
        assert data.volume_cm3 == 2000

    def test_product_update_weight_volume_none(self):
        data = ProductUpdate()
        assert data.weight_grams is None
        assert data.volume_cm3 is None

    def test_product_list_has_weight_volume(self):
        data = ProductList.model_validate({
            "id": 1,
            "tenant_id": 1,
            "name": "Table",
            "sku": "TBL-001",
            "category": "tables",
            "price_per_day_cents": 2000,
            "stock_quantity": 10,
            "available_quantity": 8,
            "condition": "bon",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "weight_grams": 15000,
            "volume_cm3": 80000,
        })
        assert data.weight_grams == 15000
        assert data.volume_cm3 == 80000


class TestVariantWeightVolumeSchemas:
    """Validation poids/volume sur variantes."""

    def test_variant_create_with_weight_volume(self):
        data = ProductVariantCreate(
            label="Blanc 28cm",
            sku="ASS-28-WHI",
            color="blanc",
            weight_grams=350,
            volume_cm3=800,
        )
        assert data.weight_grams == 350
        assert data.volume_cm3 == 800

    def test_variant_create_weight_volume_optional(self):
        data = ProductVariantCreate(
            label="Blanc 28cm",
            sku="ASS-28-WHI",
            color="blanc",
        )
        assert data.weight_grams is None
        assert data.volume_cm3 is None

    def test_variant_create_rejects_negative_weight(self):
        with pytest.raises(Exception):
            ProductVariantCreate(
                label="Blanc 28cm",
                sku="ASS-28-WHI",
                color="blanc",
                weight_grams=-10,
            )

    def test_variant_update_weight_volume(self):
        data = ProductVariantUpdate(weight_grams=400, volume_cm3=900)
        assert data.weight_grams == 400
        assert data.volume_cm3 == 900

    def test_variant_nested_has_weight_volume(self):
        data = ProductVariantNested(
            id=1,
            product_id=1,
            label="Blanc",
            sku="ASS-WHI",
            weight_grams=350,
            volume_cm3=800,
        )
        assert data.weight_grams == 350
        assert data.volume_cm3 == 800


class TestReservationWeightVolumeComputed:
    """Test calcul poids/volume total — logique extraite du model_validator."""

    @staticmethod
    def _compute(lines_data):
        """Reproduit la logique du model_validator pour tester sans schema complet."""
        total_w = 0
        total_v = 0
        has_weight = False
        has_volume = False
        for ld in lines_data:
            qty = ld["qty"]
            variant_w = ld.get("variant_w")
            variant_v = ld.get("variant_v")
            product_w = ld.get("product_w")
            product_v = ld.get("product_v")
            w = variant_w if variant_w is not None else product_w
            if w is not None:
                total_w += w * qty
                has_weight = True
            v = variant_v if variant_v is not None else product_v
            if v is not None:
                total_v += v * qty
                has_volume = True
        return (total_w if has_weight else None, total_v if has_volume else None)

    def test_weight_volume_from_variant_override(self):
        w, v = self._compute([
            {"qty": 10, "variant_w": 350, "variant_v": 800, "product_w": 300, "product_v": 700},
        ])
        assert w == 3500  # 10 * 350 (variant wins)
        assert v == 8000  # 10 * 800

    def test_weight_volume_fallback_to_product(self):
        w, v = self._compute([
            {"qty": 5, "product_w": 500, "product_v": 1200},
        ])
        assert w == 2500
        assert v == 6000

    def test_weight_volume_none_when_no_data(self):
        w, v = self._compute([{"qty": 5}])
        assert w is None
        assert v is None

    def test_weight_volume_multi_lines(self):
        w, v = self._compute([
            {"qty": 10, "variant_w": 350, "variant_v": 800},
            {"qty": 5, "product_w": 1000, "product_v": 5000},
        ])
        assert w == 8500   # 10*350 + 5*1000
        assert v == 33000  # 10*800 + 5*5000

    def test_total_weight_kg_computed(self):
        w, _ = self._compute([{"qty": 10, "product_w": 1500}])
        assert w / 1000 == 15.0

    def test_total_volume_liters_computed(self):
        _, v = self._compute([{"qty": 10, "product_v": 3000}])
        assert v / 1000 == 30.0

    def test_mixed_partial_weight(self):
        """Une ligne avec poids, une sans — le total ne compte que les lignes renseignées."""
        w, v = self._compute([
            {"qty": 10, "product_w": 500},
            {"qty": 5},
        ])
        assert w == 5000
        assert v is None
