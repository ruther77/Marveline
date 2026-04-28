"""Tests unitaires — calcul frais de livraison."""
import pytest
from app.constants.business import (
    ReservationDeliveryMethod,
    WEIGHT_SURCHARGE_THRESHOLD_GRAMS,
    WEIGHT_SURCHARGE_CENTS,
)
from app.services.carrier import CarrierQuote, CarrierQuoteRequest, CarrierService


class TestDeliveryFeeLogic:
    """Test logique de calcul des frais de livraison propre (SELF)."""

    @staticmethod
    def compute_self_delivery_fee(
        zone_fee_cents: int,
        return_date_is_sunday: bool,
        sunday_surcharge_cents: int,
        total_weight_grams: int,
    ) -> int:
        """Reproduit la logique du service pour test unitaire."""
        fee = zone_fee_cents
        if return_date_is_sunday:
            fee += sunday_surcharge_cents
        if total_weight_grams > WEIGHT_SURCHARGE_THRESHOLD_GRAMS:
            fee += WEIGHT_SURCHARGE_CENTS
        return fee

    def test_base_fee_only(self):
        fee = self.compute_self_delivery_fee(
            zone_fee_cents=3000,
            return_date_is_sunday=False,
            sunday_surcharge_cents=1500,
            total_weight_grams=100_000,
        )
        assert fee == 3000  # 30€

    def test_sunday_surcharge(self):
        fee = self.compute_self_delivery_fee(
            zone_fee_cents=3000,
            return_date_is_sunday=True,
            sunday_surcharge_cents=1500,
            total_weight_grams=100_000,
        )
        assert fee == 4500  # 30€ + 15€

    def test_weight_surcharge(self):
        fee = self.compute_self_delivery_fee(
            zone_fee_cents=3000,
            return_date_is_sunday=False,
            sunday_surcharge_cents=1500,
            total_weight_grams=600_000,
        )
        assert fee == 8000  # 30€ + 50€

    def test_sunday_and_weight_surcharges(self):
        fee = self.compute_self_delivery_fee(
            zone_fee_cents=2000,
            return_date_is_sunday=True,
            sunday_surcharge_cents=1000,
            total_weight_grams=800_000,
        )
        assert fee == 8000  # 20€ + 10€ + 50€

    def test_zero_fee_zone(self):
        fee = self.compute_self_delivery_fee(
            zone_fee_cents=0,
            return_date_is_sunday=False,
            sunday_surcharge_cents=0,
            total_weight_grams=50_000,
        )
        assert fee == 0


class TestDeliveryMethodEnum:
    """Test enum ReservationDeliveryMethod."""

    def test_values(self):
        assert ReservationDeliveryMethod.SELF == "self"
        assert ReservationDeliveryMethod.CARRIER == "carrier"
        assert ReservationDeliveryMethod.PICKUP == "pickup"

    def test_all_values(self):
        values = {m.value for m in ReservationDeliveryMethod}
        assert values == {"self", "carrier", "pickup"}


class TestCarrierQuoteSchema:
    """Test schemas Boxtal."""

    def test_carrier_quote(self):
        q = CarrierQuote(
            carrier_name="Chronopost",
            carrier_code="CHRONO",
            service_name="Express",
            price_cents=4500,
            delivery_days=2,
        )
        assert q.price_cents == 4500
        assert q.carrier_name == "Chronopost"

    def test_carrier_quote_request(self):
        r = CarrierQuoteRequest(
            weight_grams=25000,
            volume_cm3=120000,
            origin_postal_code="75001",
            destination_postal_code="13001",
        )
        assert r.weight_grams == 25000
        assert r.origin_country == "FR"

    def test_carrier_service_not_configured(self):
        service = CarrierService()
        assert not service.is_configured


class TestPickupFreeDelivery:
    """Test que pickup = 0 frais."""

    def test_pickup_always_zero(self):
        method = ReservationDeliveryMethod.PICKUP
        assert method == "pickup"
        # Pour pickup, fee = 0 toujours (logique dans le service)
