"""Tests unitaires — Logique métier mouvements stock (Phase 4C+4D)."""
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.constants import MovementStatus, MovementType
from app.constants.business import LATE_RETURN_PENALTY_RATE
from app.services.inventory_movement import MovementService


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_service() -> MovementService:
    """Service avec DB mock (AsyncMock pour méthodes awaitées)."""
    db = MagicMock()
    # Les méthodes awaitées doivent être AsyncMock
    db.get = AsyncMock(return_value=None)
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()

    svc = MovementService(db)
    svc.repo = MagicMock()
    svc.repo.create = AsyncMock()
    svc.repo.update = AsyncMock()
    svc.repo.get_by_id = AsyncMock()
    svc.item_repo = MagicMock()
    svc.item_repo.create = AsyncMock()
    return svc


def _make_product(price_per_day_cents: int = 500) -> MagicMock:
    """Produit mock avec price_per_day_cents en centimes."""
    p = MagicMock()
    p.price_per_day_cents = price_per_day_cents
    return p


def _make_item(
    condition: str,
    quantity_expected: int = 10,
    quantity_actual: int | None = None,
    product_id: int | None = 1,
    variant_id: int | None = None,
) -> MagicMock:
    """MovementItem mock."""
    item = MagicMock()
    item.condition = condition
    item.quantity_expected = quantity_expected
    item.quantity_actual = quantity_actual
    item.product_id = product_id
    item.variant_id = variant_id
    return item


def _make_movement(
    movement_type: str = MovementType.RETURN.value,
    damage_fee_cents: int = 0,
    items: list | None = None,
    reservation_id: int | None = 1,
    scheduled_date: datetime | None = None,
    actual_date: datetime | None = None,
    tenant_id: int = 1,
    status_value: str | None = None,
) -> MagicMock:
    """InventoryMovement mock."""
    m = MagicMock()
    m.id = 1
    m.tenant_id = tenant_id
    m.movement_type = movement_type
    m.damage_fee_cents = damage_fee_cents
    m.items = items or []
    m.reservation_id = reservation_id
    m.scheduled_date = scheduled_date or datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
    m.actual_date = actual_date
    m.status = status_value or MovementStatus.IN_TRANSIT.value
    return m


def _make_reservation(total_amount_cents: int = 100_000) -> MagicMock:
    """Réservation mock."""
    r = MagicMock()
    r.total_amount_cents = total_amount_cents
    return r


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 4C — _calculate_damage_fee_from_items
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculateDamageFeeFromItems:

    async def test_no_items_returns_zero(self):
        svc = _make_service()
        movement = _make_movement(items=[])
        assert await svc._calculate_damage_fee_from_items(movement) == 0

    async def test_all_perfect_items_returns_zero(self):
        svc = _make_service()
        items = [_make_item("perfect", quantity_expected=5, quantity_actual=5)]
        movement = _make_movement(items=items)
        assert await svc._calculate_damage_fee_from_items(movement) == 0

    async def test_all_good_items_returns_zero(self):
        svc = _make_service()
        items = [_make_item("good", quantity_expected=10, quantity_actual=10)]
        movement = _make_movement(items=items)
        assert await svc._calculate_damage_fee_from_items(movement) == 0

    async def test_missing_items_calculated(self):
        """3 items manquants sur 10 → fee = 3 × price_per_day."""
        svc = _make_service()
        product = _make_product(price_per_day_cents=500)  # 5€
        svc.db.get = AsyncMock(return_value=product)

        items = [_make_item("missing", quantity_expected=10, quantity_actual=7)]
        movement = _make_movement(items=items)

        fee = await svc._calculate_damage_fee_from_items(movement)

        assert fee == 3 * 500  # 15€ = 1500 centimes

    async def test_damaged_items_calculated(self):
        """5 items damaged (quantity_actual=5) → fee = 5 × price_per_day."""
        svc = _make_service()
        product = _make_product(price_per_day_cents=1000)  # 10€
        svc.db.get = AsyncMock(return_value=product)

        items = [_make_item("damaged", quantity_expected=10, quantity_actual=5)]
        movement = _make_movement(items=items)

        fee = await svc._calculate_damage_fee_from_items(movement)

        assert fee == 5 * 1000  # 50€ = 5000 centimes

    async def test_mixed_conditions(self):
        """Un item perfect + un item missing + un item damaged."""
        svc = _make_service()
        product = _make_product(price_per_day_cents=200)  # 2€

        perfect = _make_item("perfect", quantity_expected=5, quantity_actual=5)
        missing = _make_item("missing", quantity_expected=10, quantity_actual=8)  # 2 manquants
        damaged = _make_item("damaged", quantity_expected=3, quantity_actual=3, product_id=2)

        # db.get retourne le même produit pour les deux product_ids
        svc.db.get = AsyncMock(return_value=product)
        movement = _make_movement(items=[perfect, missing, damaged])

        fee = await svc._calculate_damage_fee_from_items(movement)

        # missing: 2 × 200 = 400 ; damaged: 3 × 200 = 600
        assert fee == 400 + 600

    async def test_item_without_product_id_skipped(self):
        """Item sans product_id est ignoré."""
        svc = _make_service()
        items = [_make_item("missing", quantity_expected=5, quantity_actual=0, product_id=None)]
        movement = _make_movement(items=items)

        fee = await svc._calculate_damage_fee_from_items(movement)

        assert fee == 0
        svc.db.get.assert_not_called()

    async def test_product_not_found_skipped(self):
        """Produit introuvable → item ignoré."""
        svc = _make_service()
        svc.db.get = AsyncMock(return_value=None)
        items = [_make_item("missing", quantity_expected=5, quantity_actual=0)]
        movement = _make_movement(items=items)

        assert await svc._calculate_damage_fee_from_items(movement) == 0

    async def test_product_with_zero_price_skipped(self):
        """Produit à 0€ → pas de fee calculé."""
        svc = _make_service()
        product = _make_product(price_per_day_cents=0)
        svc.db.get = AsyncMock(return_value=product)
        items = [_make_item("damaged", quantity_expected=5, quantity_actual=5)]
        movement = _make_movement(items=items)

        assert await svc._calculate_damage_fee_from_items(movement) == 0

    async def test_missing_quantity_actual_none_means_all_missing(self):
        """quantity_actual=None et condition=missing → qty_actual=quantity_expected → qty_issue=0."""
        svc = _make_service()
        product = _make_product(price_per_day_cents=500)
        svc.db.get = AsyncMock(return_value=product)
        # Si quantity_actual est None → qty_actual = quantity_expected → qty_issue = 0
        items = [_make_item("missing", quantity_expected=5, quantity_actual=None)]
        movement = _make_movement(items=items)

        assert await svc._calculate_damage_fee_from_items(movement) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 4C — complete_movement() auto-calcul damage_fee
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompleteMovementAutoFee:
    """Tests du flux auto-calcul damage_fee_cents dans complete_movement.

    Note : complete_movement utilise `db.execute(select(...))` pour charger le
    mouvement (pas `get_movement`). On mocke donc `db.execute` directement.
    On passe `_internal=True` pour bypasser le garde-fou 409 (réservation liée).
    """

    def _patch_db_execute(self, svc: MovementService, movement: MagicMock) -> None:
        """Configure db.execute pour renvoyer `movement` via scalar_one_or_none/scalar_one."""
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = movement
        exec_result.scalar_one.return_value = movement
        svc.db.execute = AsyncMock(return_value=exec_result)

    async def test_return_with_damage_sets_fee_auto(self):
        """complete_movement RETURN : damage_fee_cents auto-calculé si items damaged."""
        svc = _make_service()
        product = _make_product(price_per_day_cents=1000)
        svc.db.get = AsyncMock(return_value=product)

        item = _make_item("damaged", quantity_expected=2, quantity_actual=2)
        movement = _make_movement(
            items=[item], movement_type="return", damage_fee_cents=0, reservation_id=None
        )
        self._patch_db_execute(svc, movement)

        with (
            patch.object(svc, "_update_stock_on_complete", new=AsyncMock()),
            patch.object(svc, "_update_reservation_on_complete", new=AsyncMock()),
        ):
            await svc.complete_movement(movement.id, movement.tenant_id, _internal=True)

        # Vérifier que repo.update a été appelé avec damage_fee_cents=2000
        assert svc.repo.update.await_count >= 1
        call_args = svc.repo.update.await_args
        update_data = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("data")
        assert update_data.get("damage_fee_cents") == 2 * 1000

    async def test_return_with_existing_fee_not_overridden(self):
        """Si damage_fee_cents déjà > 0, il ne doit pas être écrasé automatiquement."""
        svc = _make_service()
        product = _make_product(price_per_day_cents=1000)
        svc.db.get = AsyncMock(return_value=product)

        item = _make_item("damaged", quantity_expected=5, quantity_actual=5)
        movement = _make_movement(
            items=[item], movement_type="return", damage_fee_cents=99999, reservation_id=None
        )
        self._patch_db_execute(svc, movement)

        with (
            patch.object(svc, "_update_stock_on_complete", new=AsyncMock()),
            patch.object(svc, "_update_reservation_on_complete", new=AsyncMock()),
        ):
            await svc.complete_movement(movement.id, movement.tenant_id, _internal=True)

        call_args = svc.repo.update.await_args
        update_data = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("data")
        assert "damage_fee_cents" not in update_data

    async def test_departure_no_fee_calculation(self):
        """complete_movement DEPARTURE : pas de calcul damage_fee_cents."""
        svc = _make_service()
        item = _make_item("damaged", quantity_expected=5, quantity_actual=5)
        movement = _make_movement(
            items=[item], movement_type="departure", damage_fee_cents=0, reservation_id=None
        )
        self._patch_db_execute(svc, movement)

        with (
            patch.object(svc, "_update_stock_on_complete", new=AsyncMock()),
            patch.object(svc, "_update_reservation_on_complete", new=AsyncMock()),
        ):
            await svc.complete_movement(movement.id, movement.tenant_id, _internal=True)

        call_args = svc.repo.update.await_args
        update_data = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("data")
        assert "damage_fee_cents" not in update_data


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 4D — calculate_late_penalty
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculateLatePenalty:

    async def test_on_time_return_no_penalty(self):
        """Retour à l'heure → pénalité = 0."""
        svc = _make_service()
        scheduled = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)
        actual = datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc)
        movement = _make_movement(scheduled_date=scheduled, actual_date=actual)

        assert await svc.calculate_late_penalty(movement) == 0

    async def test_one_day_late(self):
        """1 jour de retard → 20% × total_amount × 1."""
        svc = _make_service()
        reservation = _make_reservation(total_amount_cents=100_000)  # 1000€

        scheduled = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)
        actual = datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc)
        movement = _make_movement(scheduled_date=scheduled, actual_date=actual)

        with patch("app.repositories.reservation.AsyncReservationRepository") as MockRepo:
            MockRepo.return_value.get_by_id = AsyncMock(return_value=reservation)
            penalty = await svc.calculate_late_penalty(movement)

        assert penalty == int(100_000 * LATE_RETURN_PENALTY_RATE * 1)  # 20 000

    async def test_three_days_late(self):
        """3 jours de retard → 20% × total × 3."""
        svc = _make_service()
        reservation = _make_reservation(total_amount_cents=50_000)  # 500€

        scheduled = datetime(2026, 9, 15, tzinfo=timezone.utc)
        actual = datetime(2026, 9, 18, tzinfo=timezone.utc)
        movement = _make_movement(scheduled_date=scheduled, actual_date=actual)

        with patch("app.repositories.reservation.AsyncReservationRepository") as MockRepo:
            MockRepo.return_value.get_by_id = AsyncMock(return_value=reservation)
            penalty = await svc.calculate_late_penalty(movement)

        assert penalty == int(50_000 * LATE_RETURN_PENALTY_RATE * 3)  # 30 000

    async def test_departure_returns_zero(self):
        """Mouvement DEPARTURE → pas de pénalité retard."""
        svc = _make_service()
        movement = _make_movement(movement_type="departure")
        assert await svc.calculate_late_penalty(movement) == 0

    async def test_no_reservation_returns_zero(self):
        """Mouvement sans réservation liée → pénalité = 0."""
        svc = _make_service()
        scheduled = datetime(2026, 9, 15, tzinfo=timezone.utc)
        actual = datetime(2026, 9, 17, tzinfo=timezone.utc)
        movement = _make_movement(
            scheduled_date=scheduled,
            actual_date=actual,
            reservation_id=None,
        )
        assert await svc.calculate_late_penalty(movement) == 0

    async def test_reservation_not_found_returns_zero(self):
        """Réservation introuvable → pénalité = 0."""
        svc = _make_service()
        scheduled = datetime(2026, 9, 15, tzinfo=timezone.utc)
        actual = datetime(2026, 9, 17, tzinfo=timezone.utc)
        movement = _make_movement(scheduled_date=scheduled, actual_date=actual)

        with patch("app.repositories.reservation.AsyncReservationRepository") as MockRepo:
            MockRepo.return_value.get_by_id = AsyncMock(return_value=None)
            penalty = await svc.calculate_late_penalty(movement)

        assert penalty == 0

    async def test_no_actual_date_uses_now(self):
        """Si actual_date=None, utilise datetime.now → pas de retard si scheduled dans le passé proche."""
        svc = _make_service()
        reservation = _make_reservation(total_amount_cents=100_000)
        # Scheduled très dans le passé → days_late > 0
        scheduled = datetime(2026, 1, 1, tzinfo=timezone.utc)
        movement = _make_movement(scheduled_date=scheduled, actual_date=None)

        with patch("app.repositories.reservation.AsyncReservationRepository") as MockRepo:
            MockRepo.return_value.get_by_id = AsyncMock(return_value=reservation)
            penalty = await svc.calculate_late_penalty(movement)

        # Juste vérifier que c'est > 0 (scheduled très dans le passé)
        assert penalty > 0

    def test_rate_matches_constant(self):
        """Le taux utilisé est bien LATE_RETURN_PENALTY_RATE."""
        assert LATE_RETURN_PENALTY_RATE == 0.20


# ── Validation stock départ ──────────────────────────────────────────────────

class TestStockValidationOnDeparture:
    """create_movement() doit refuser un départ si stock insuffisant."""

    def _make_product_mock(self, available_quantity: int, tenant_id: int = 1):
        p = MagicMock()
        p.available_quantity = available_quantity
        p.tenant_id = tenant_id
        return p

    async def test_departure_insufficient_stock_raises_400(self):
        from fastapi import HTTPException
        svc = _make_service()
        product_mock = self._make_product_mock(available_quantity=2)
        svc.db.get = AsyncMock(return_value=product_mock)

        with pytest.raises(HTTPException) as exc_info:
            await svc.create_movement(
                tenant_id=1,
                movement_type=MovementType.DEPARTURE.value,
                scheduled_date=datetime.now(timezone.utc),
                items=[{"product_id": 1, "quantity_expected": 5}],
            )
        assert exc_info.value.status_code == 400
        assert "insuffisant" in exc_info.value.detail

    async def test_departure_sufficient_stock_passes(self):
        svc = _make_service()
        product_mock = self._make_product_mock(available_quantity=10)
        svc.db.get = AsyncMock(return_value=product_mock)
        movement_mock = MagicMock()
        movement_mock.id = 1
        svc.repo.create = AsyncMock(return_value=movement_mock)

        # Ne doit pas lever d'exception
        await svc.create_movement(
            tenant_id=1,
            movement_type=MovementType.DEPARTURE.value,
            scheduled_date=datetime.now(timezone.utc),
            items=[{"product_id": 1, "quantity_expected": 3}],
        )

    async def test_return_skips_stock_validation(self):
        """Les mouvements de retour ne vérifient pas le stock."""
        svc = _make_service()
        product_mock = self._make_product_mock(available_quantity=0)
        svc.db.get = AsyncMock(return_value=product_mock)
        movement_mock = MagicMock()
        movement_mock.id = 1
        svc.repo.create = AsyncMock(return_value=movement_mock)

        # Ne doit pas lever d'exception même si stock = 0
        await svc.create_movement(
            tenant_id=1,
            movement_type=MovementType.RETURN.value,
            scheduled_date=datetime.now(timezone.utc),
            items=[{"product_id": 1, "quantity_expected": 5}],
        )

    async def test_departure_no_product_id_skips_check(self):
        """Sans product_id, la validation de stock est ignorée."""
        svc = _make_service()
        movement_mock = MagicMock()
        movement_mock.id = 1
        svc.repo.create = AsyncMock(return_value=movement_mock)

        # Ne doit pas lever d'exception (pas de product_id → pas de vérification)
        await svc.create_movement(
            tenant_id=1,
            movement_type=MovementType.DEPARTURE.value,
            scheduled_date=datetime.now(timezone.utc),
            items=[{"quantity_expected": 5}],
        )
