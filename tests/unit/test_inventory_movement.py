"""Tests unitaires pour MovementService — mouvements de stock."""
import pytest
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException

from app.constants import (
    DeliveryMethod,
    InspectionStatus,
    ItemCondition,
    MovementStatus,
    MovementType,
)
from app.models.inventory_movement import InventoryMovement, MovementItem
from app.services.inventory_movement import MovementService, VALID_TRANSITIONS


TENANT_ID = 1
TENANT_ID_OTHER = 2


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def service(test_db):
    """MovementService avec session de test."""
    return MovementService(test_db)


@pytest.fixture
def future_date():
    """Date planifiée dans le futur."""
    return datetime.now(timezone.utc) + timedelta(days=7)


@pytest.fixture
def sample_items():
    """Items de base pour créer un mouvement via le service."""
    return [
        {"quantity_expected": 10},
        {"quantity_expected": 5},
    ]


# ── Helpers ───────────────────────────────────────────────────────────


def _create_movement_in_db(
    db,
    tenant_id=TENANT_ID,
    status=MovementStatus.SCHEDULED.value,
    **kwargs,
):
    """Crée un mouvement directement en DB (sans passer par le service)."""
    movement = InventoryMovement(
        tenant_id=tenant_id,
        movement_type=kwargs.get("movement_type", MovementType.DEPARTURE.value),
        scheduled_date=kwargs.get("scheduled_date", datetime.now(timezone.utc) + timedelta(days=7)),
        status=status,
        delivery_method=kwargs.get("delivery_method"),
        delivery_address=kwargs.get("delivery_address"),
        delivery_notes=kwargs.get("delivery_notes"),
        event_id=kwargs.get("event_id"),
        damage_fee=kwargs.get("damage_fee", 0),
        inspection_status=kwargs.get("inspection_status"),
    )
    db.add(movement)
    db.flush()
    db.refresh(movement)
    return movement


def _add_item_in_db(db, movement, **kwargs):
    """Ajoute un item directement en DB."""
    item = MovementItem(
        tenant_id=movement.tenant_id,
        movement_id=movement.id,
        quantity_expected=kwargs.get("quantity_expected", 5),
        product_id=kwargs.get("product_id"),
        event_item_id=kwargs.get("event_item_id"),
        product_variation_id=kwargs.get("product_variation_id"),
        quantity_actual=kwargs.get("quantity_actual"),
        condition=kwargs.get("condition"),
        condition_notes=kwargs.get("condition_notes"),
    )
    db.add(item)
    db.flush()
    db.refresh(item)
    return item


# ═══════════════════════════════════════════════════════════════════════
# Tests create_movement
# ═══════════════════════════════════════════════════════════════════════


def test_create_movement_departure_success(service, test_db, future_date, sample_items):
    """Crée un mouvement de type departure avec succès."""
    movement = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )

    assert movement.id is not None
    assert movement.tenant_id == TENANT_ID
    assert movement.movement_type == MovementType.DEPARTURE.value
    assert movement.status == MovementStatus.SCHEDULED.value
    assert movement.damage_fee == 0
    assert len(movement.items) == 2


def test_create_movement_return_success(service, test_db, future_date):
    """Crée un mouvement de type return avec succès."""
    movement = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.RETURN.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 3}],
    )

    assert movement.movement_type == MovementType.RETURN.value
    assert movement.status == MovementStatus.SCHEDULED.value
    assert len(movement.items) == 1


def test_create_movement_with_optional_fields(service, test_db, future_date):
    """Crée un mouvement avec tous les champs optionnels."""
    movement = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 2}],
        event_id=42,
        delivery_method=DeliveryMethod.DELIVERY.value,
        delivery_address="123 Rue Test",
        delivery_notes="Livrer avant 14h",
    )

    assert movement.event_id == 42
    assert movement.delivery_method == DeliveryMethod.DELIVERY.value
    assert movement.delivery_address == "123 Rue Test"
    assert movement.delivery_notes == "Livrer avant 14h"


def test_create_movement_items_have_correct_data(service, test_db, future_date):
    """Les items créés ont les bonnes quantités et sont liés au mouvement."""
    items_data = [
        {"quantity_expected": 10, "condition": ItemCondition.PERFECT.value},
        {"quantity_expected": 5, "condition_notes": "Fragile"},
    ]
    movement = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=items_data,
    )

    assert movement.items[0].quantity_expected == 10
    assert movement.items[0].condition == ItemCondition.PERFECT.value
    assert movement.items[1].quantity_expected == 5
    assert movement.items[1].condition_notes == "Fragile"
    for item in movement.items:
        assert item.movement_id == movement.id
        assert item.tenant_id == TENANT_ID


def test_create_movement_no_items_error(service, future_date):
    """Erreur 400 si aucun item fourni."""
    with pytest.raises(HTTPException) as exc_info:
        service.create_movement(
            tenant_id=TENANT_ID,
            movement_type=MovementType.DEPARTURE.value,
            scheduled_date=future_date,
            items=[],
        )

    assert exc_info.value.status_code == 400
    assert "At least one item" in exc_info.value.detail


def test_create_movement_invalid_type_error(service, future_date):
    """Erreur 400 si movement_type invalide."""
    with pytest.raises(HTTPException) as exc_info:
        service.create_movement(
            tenant_id=TENANT_ID,
            movement_type="invalid_type",
            scheduled_date=future_date,
            items=[{"quantity_expected": 1}],
        )

    assert exc_info.value.status_code == 400
    assert "Invalid movement_type" in exc_info.value.detail


# ═══════════════════════════════════════════════════════════════════════
# Tests get_movement
# ═══════════════════════════════════════════════════════════════════════


def test_get_movement_success(service, test_db, future_date, sample_items):
    """Récupère un mouvement existant par ID."""
    created = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )

    fetched = service.get_movement(created.id, TENANT_ID)
    assert fetched.id == created.id
    assert fetched.movement_type == MovementType.DEPARTURE.value


def test_get_movement_not_found(service):
    """Erreur 404 pour ID inexistant."""
    with pytest.raises(HTTPException) as exc_info:
        service.get_movement(99999, TENANT_ID)

    assert exc_info.value.status_code == 404
    assert "Movement not found" in exc_info.value.detail


def test_get_movement_cross_tenant_not_found(service, test_db, future_date, sample_items):
    """Erreur 404 quand on accède au mouvement d'un autre tenant."""
    created = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.get_movement(created.id, TENANT_ID_OTHER)

    assert exc_info.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Tests list_movements
# ═══════════════════════════════════════════════════════════════════════


def test_list_movements_returns_all(service, test_db, future_date):
    """Liste retourne tous les mouvements actifs du tenant."""
    for _ in range(3):
        service.create_movement(
            tenant_id=TENANT_ID,
            movement_type=MovementType.DEPARTURE.value,
            scheduled_date=future_date,
            items=[{"quantity_expected": 1}],
        )

    movements, total = service.list_movements(tenant_id=TENANT_ID)
    assert total == 3
    assert len(movements) == 3


def test_list_movements_filter_by_type(service, test_db, future_date):
    """Filtre par movement_type fonctionne."""
    service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )
    service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.RETURN.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )

    departures, total = service.list_movements(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
    )
    assert total == 1
    assert departures[0].movement_type == MovementType.DEPARTURE.value


def test_list_movements_filter_by_status(service, test_db, future_date):
    """Filtre par status fonctionne."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )
    # Passer en in_transit
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)

    # Créer un second mouvement (rest scheduled)
    service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )

    in_transit, total = service.list_movements(
        tenant_id=TENANT_ID,
        movement_status=MovementStatus.IN_TRANSIT.value,
    )
    assert total == 1
    assert in_transit[0].status == MovementStatus.IN_TRANSIT.value


def test_list_movements_filter_by_event_id(service, test_db, future_date):
    """Filtre par event_id fonctionne."""
    service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
        event_id=10,
    )
    service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
        event_id=20,
    )

    results, total = service.list_movements(tenant_id=TENANT_ID, event_id=10)
    assert total == 1
    assert results[0].event_id == 10


def test_list_movements_pagination(service, test_db, future_date):
    """Pagination skip/limit fonctionne."""
    for _ in range(5):
        service.create_movement(
            tenant_id=TENANT_ID,
            movement_type=MovementType.DEPARTURE.value,
            scheduled_date=future_date,
            items=[{"quantity_expected": 1}],
        )

    page, total = service.list_movements(tenant_id=TENANT_ID, skip=2, limit=2)
    assert total == 5
    assert len(page) == 2


def test_list_movements_empty(service, test_db):
    """Liste vide pour un tenant sans mouvements."""
    movements, total = service.list_movements(tenant_id=TENANT_ID)
    assert total == 0
    assert movements == []


def test_list_movements_tenant_isolation(service, test_db, future_date):
    """list_movements ne retourne que les mouvements du tenant demandé."""
    service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )
    service.create_movement(
        tenant_id=TENANT_ID_OTHER,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )

    t1_results, t1_total = service.list_movements(tenant_id=TENANT_ID)
    t2_results, t2_total = service.list_movements(tenant_id=TENANT_ID_OTHER)

    assert t1_total == 1
    assert t2_total == 1
    assert t1_results[0].tenant_id == TENANT_ID
    assert t2_results[0].tenant_id == TENANT_ID_OTHER


# ═══════════════════════════════════════════════════════════════════════
# Tests update_movement
# ═══════════════════════════════════════════════════════════════════════


def test_update_movement_basic_fields(service, test_db, future_date, sample_items):
    """Met à jour les champs basiques (delivery, notes)."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )

    updated = service.update_movement(
        m.id, TENANT_ID,
        delivery_address="456 Rue Nouvelle",
        delivery_notes="Urgent",
        delivery_method=DeliveryMethod.SHIPPING.value,
    )

    assert updated.delivery_address == "456 Rue Nouvelle"
    assert updated.delivery_notes == "Urgent"
    assert updated.delivery_method == DeliveryMethod.SHIPPING.value


def test_update_movement_damage_fee(service, test_db, future_date, sample_items):
    """Met à jour le damage_fee en centimes."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )

    updated = service.update_movement(m.id, TENANT_ID, damage_fee=1500)
    assert updated.damage_fee == 1500  # 15.00 EUR


def test_update_movement_inspection(service, test_db, future_date, sample_items):
    """Met à jour le statut d'inspection."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )

    updated = service.update_movement(
        m.id, TENANT_ID,
        inspection_status=InspectionStatus.DAMAGED.value,
        inspection_notes="Caisse abimee",
    )

    assert updated.inspection_status == InspectionStatus.DAMAGED.value
    assert updated.inspection_notes == "Caisse abimee"


def test_update_movement_not_found(service):
    """Erreur 404 si mouvement inexistant."""
    with pytest.raises(HTTPException) as exc_info:
        service.update_movement(99999, TENANT_ID, delivery_notes="test")

    assert exc_info.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Tests status transitions
# ═══════════════════════════════════════════════════════════════════════


def test_transition_scheduled_to_in_transit(service, test_db, future_date, sample_items):
    """Transition scheduled → in_transit autorisée."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )

    updated = service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)
    assert updated.status == MovementStatus.IN_TRANSIT.value


def test_transition_scheduled_to_cancelled(service, test_db, future_date, sample_items):
    """Transition scheduled → cancelled autorisée."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )

    updated = service.update_movement(m.id, TENANT_ID, status=MovementStatus.CANCELLED.value)
    assert updated.status == MovementStatus.CANCELLED.value


def test_transition_in_transit_to_completed(service, test_db, future_date, sample_items):
    """Transition in_transit → completed autorisée."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)

    updated = service.update_movement(m.id, TENANT_ID, status=MovementStatus.COMPLETED.value)
    assert updated.status == MovementStatus.COMPLETED.value


def test_transition_in_transit_to_late(service, test_db, future_date, sample_items):
    """Transition in_transit → late autorisée."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)

    updated = service.update_movement(m.id, TENANT_ID, status=MovementStatus.LATE.value)
    assert updated.status == MovementStatus.LATE.value


def test_transition_in_transit_to_cancelled(service, test_db, future_date, sample_items):
    """Transition in_transit → cancelled autorisée."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)

    updated = service.update_movement(m.id, TENANT_ID, status=MovementStatus.CANCELLED.value)
    assert updated.status == MovementStatus.CANCELLED.value


def test_transition_late_to_completed(service, test_db, future_date, sample_items):
    """Transition late → completed autorisée."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.LATE.value)

    updated = service.update_movement(m.id, TENANT_ID, status=MovementStatus.COMPLETED.value)
    assert updated.status == MovementStatus.COMPLETED.value


def test_transition_late_to_cancelled(service, test_db, future_date, sample_items):
    """Transition late → cancelled autorisée."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.LATE.value)

    updated = service.update_movement(m.id, TENANT_ID, status=MovementStatus.CANCELLED.value)
    assert updated.status == MovementStatus.CANCELLED.value


def test_transition_scheduled_to_completed_invalid(service, test_db, future_date, sample_items):
    """Transition scheduled → completed interdite (doit passer par in_transit)."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.update_movement(m.id, TENANT_ID, status=MovementStatus.COMPLETED.value)

    assert exc_info.value.status_code == 400
    assert "Invalid status transition" in exc_info.value.detail


def test_transition_scheduled_to_late_invalid(service, test_db, future_date, sample_items):
    """Transition scheduled → late interdite."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.update_movement(m.id, TENANT_ID, status=MovementStatus.LATE.value)

    assert exc_info.value.status_code == 400


def test_transition_from_completed_invalid(service, test_db, future_date, sample_items):
    """Aucune transition depuis completed (statut terminal)."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.COMPLETED.value)

    for target in [MovementStatus.SCHEDULED.value, MovementStatus.IN_TRANSIT.value,
                   MovementStatus.LATE.value, MovementStatus.CANCELLED.value]:
        with pytest.raises(HTTPException) as exc_info:
            service.update_movement(m.id, TENANT_ID, status=target)
        assert exc_info.value.status_code == 400
        assert "none" in exc_info.value.detail.lower()


def test_transition_from_cancelled_invalid(service, test_db, future_date, sample_items):
    """Aucune transition depuis cancelled (statut terminal)."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.CANCELLED.value)

    for target in [MovementStatus.SCHEDULED.value, MovementStatus.IN_TRANSIT.value,
                   MovementStatus.COMPLETED.value, MovementStatus.LATE.value]:
        with pytest.raises(HTTPException) as exc_info:
            service.update_movement(m.id, TENANT_ID, status=target)
        assert exc_info.value.status_code == 400


def test_transition_same_status_no_error(service, test_db, future_date, sample_items):
    """Re-set du meme statut ne declenche pas d'erreur."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )

    # Mettre scheduled → scheduled ne change rien et ne leve pas d'erreur
    updated = service.update_movement(m.id, TENANT_ID, status=MovementStatus.SCHEDULED.value)
    assert updated.status == MovementStatus.SCHEDULED.value


# ═══════════════════════════════════════════════════════════════════════
# Tests delete_movement
# ═══════════════════════════════════════════════════════════════════════


def test_delete_movement_success(service, test_db, future_date, sample_items):
    """Soft delete d'un mouvement scheduled."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )

    result = service.delete_movement(m.id, TENANT_ID)
    assert result is True

    # Mouvement plus visible via get (is_active=False)
    with pytest.raises(HTTPException) as exc_info:
        service.get_movement(m.id, TENANT_ID)
    assert exc_info.value.status_code == 404


def test_delete_movement_in_transit(service, test_db, future_date, sample_items):
    """Soft delete d'un mouvement in_transit (autorise)."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)

    result = service.delete_movement(m.id, TENANT_ID)
    assert result is True


def test_delete_completed_movement_error(service, test_db, future_date, sample_items):
    """Erreur 400 si on tente de supprimer un mouvement completed."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.COMPLETED.value)

    with pytest.raises(HTTPException) as exc_info:
        service.delete_movement(m.id, TENANT_ID)

    assert exc_info.value.status_code == 400
    assert "Cannot delete a completed movement" in exc_info.value.detail


def test_delete_movement_not_found(service):
    """Erreur 404 si mouvement inexistant."""
    with pytest.raises(HTTPException) as exc_info:
        service.delete_movement(99999, TENANT_ID)

    assert exc_info.value.status_code == 404


def test_delete_movement_cross_tenant(service, test_db, future_date, sample_items):
    """Erreur 404 si on tente de supprimer un mouvement d'un autre tenant."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.delete_movement(m.id, TENANT_ID_OTHER)

    assert exc_info.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Tests complete_movement
# ═══════════════════════════════════════════════════════════════════════


def test_complete_movement_from_in_transit(service, test_db, future_date, sample_items):
    """complete_movement depuis in_transit passe en completed avec actual_date."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)

    before = datetime.now(timezone.utc)
    completed = service.complete_movement(m.id, TENANT_ID)

    assert completed.status == MovementStatus.COMPLETED.value
    assert completed.actual_date is not None
    assert completed.actual_date >= before


def test_complete_movement_from_late(service, test_db, future_date, sample_items):
    """complete_movement depuis late passe en completed."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.LATE.value)

    completed = service.complete_movement(m.id, TENANT_ID)
    assert completed.status == MovementStatus.COMPLETED.value
    assert completed.actual_date is not None


def test_complete_movement_from_scheduled_error(service, test_db, future_date, sample_items):
    """complete_movement depuis scheduled echoue (doit passer par in_transit)."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=sample_items,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.complete_movement(m.id, TENANT_ID)

    assert exc_info.value.status_code == 400
    assert "Invalid status transition" in exc_info.value.detail


# ═══════════════════════════════════════════════════════════════════════
# Tests special queries
# ═══════════════════════════════════════════════════════════════════════


def test_get_late_movements(service, test_db, future_date):
    """get_late_movements retourne uniquement les mouvements late."""
    # Creer un mouvement late
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.LATE.value)

    # Creer un mouvement scheduled (pas late)
    service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )

    late, total = service.get_late_movements(TENANT_ID)
    assert total == 1
    assert late[0].status == MovementStatus.LATE.value


def test_get_pending_inspections(service, test_db, future_date):
    """get_pending_inspections retourne les mouvements avec inspection pending."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.RETURN.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )
    service.update_movement(m.id, TENANT_ID, inspection_status=InspectionStatus.PENDING.value)

    # Mouvement sans inspection
    service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )

    pending, total = service.get_pending_inspections(TENANT_ID)
    assert total == 1
    assert pending[0].inspection_status == InspectionStatus.PENDING.value


def test_get_statistics(service, test_db, future_date):
    """get_statistics retourne les bons comptes par statut."""
    # 2 scheduled
    for _ in range(2):
        service.create_movement(
            tenant_id=TENANT_ID,
            movement_type=MovementType.DEPARTURE.value,
            scheduled_date=future_date,
            items=[{"quantity_expected": 1}],
        )

    # 1 in_transit
    m1 = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )
    service.update_movement(m1.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)

    # 1 completed avec damage_fee
    m2 = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )
    service.update_movement(m2.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)
    service.update_movement(m2.id, TENANT_ID, status=MovementStatus.COMPLETED.value, damage_fee=2500)

    stats = service.get_statistics(TENANT_ID)
    assert stats["total_movements"] == 4
    assert stats["scheduled"] == 2
    assert stats["in_transit"] == 1
    assert stats["completed"] == 1
    assert stats["late"] == 0
    assert stats["cancelled"] == 0
    assert stats["total_damage_fees"] == 2500


def test_get_statistics_empty(service, test_db):
    """get_statistics pour un tenant vide retourne des zeros."""
    stats = service.get_statistics(TENANT_ID)
    assert stats["total_movements"] == 0
    assert stats["total_damage_fees"] == 0


# ═══════════════════════════════════════════════════════════════════════
# Tests add_item
# ═══════════════════════════════════════════════════════════════════════


def test_add_item_success(service, test_db, future_date):
    """Ajoute un item a un mouvement scheduled."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )

    new_item = service.add_item(
        movement_id=m.id,
        tenant_id=TENANT_ID,
        quantity_expected=7,
        condition=ItemCondition.GOOD.value,
    )

    assert new_item.id is not None
    assert new_item.movement_id == m.id
    assert new_item.quantity_expected == 7
    assert new_item.condition == ItemCondition.GOOD.value


def test_add_item_to_in_transit(service, test_db, future_date):
    """Ajout d'item a un mouvement in_transit autorise."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)

    item = service.add_item(movement_id=m.id, tenant_id=TENANT_ID, quantity_expected=3)
    assert item.movement_id == m.id


def test_add_item_to_completed_error(service, test_db, future_date):
    """Erreur 400 si on ajoute un item a un mouvement completed."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.COMPLETED.value)

    with pytest.raises(HTTPException) as exc_info:
        service.add_item(movement_id=m.id, tenant_id=TENANT_ID, quantity_expected=1)

    assert exc_info.value.status_code == 400
    assert "completed or cancelled" in exc_info.value.detail


def test_add_item_to_cancelled_error(service, test_db, future_date):
    """Erreur 400 si on ajoute un item a un mouvement cancelled."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 1}],
    )
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.CANCELLED.value)

    with pytest.raises(HTTPException) as exc_info:
        service.add_item(movement_id=m.id, tenant_id=TENANT_ID, quantity_expected=1)

    assert exc_info.value.status_code == 400
    assert "completed or cancelled" in exc_info.value.detail


def test_add_item_movement_not_found(service):
    """Erreur 404 si mouvement inexistant."""
    with pytest.raises(HTTPException) as exc_info:
        service.add_item(movement_id=99999, tenant_id=TENANT_ID, quantity_expected=1)

    assert exc_info.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Tests update_item
# ═══════════════════════════════════════════════════════════════════════


def test_update_item_quantity_actual(service, test_db, future_date):
    """Met a jour la quantite effective d'un item."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 10}],
    )
    item_id = m.items[0].id

    updated = service.update_item(item_id, TENANT_ID, quantity_actual=8)
    assert updated.quantity_actual == 8


def test_update_item_condition(service, test_db, future_date):
    """Met a jour la condition d'un item."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 5}],
    )
    item_id = m.items[0].id

    updated = service.update_item(
        item_id, TENANT_ID,
        condition=ItemCondition.DAMAGED.value,
        condition_notes="Ecran fissure",
    )
    assert updated.condition == ItemCondition.DAMAGED.value
    assert updated.condition_notes == "Ecran fissure"


def test_update_item_not_found(service):
    """Erreur 404 si item inexistant."""
    with pytest.raises(HTTPException) as exc_info:
        service.update_item(99999, TENANT_ID, quantity_actual=1)

    assert exc_info.value.status_code == 404
    assert "Movement item not found" in exc_info.value.detail


# ═══════════════════════════════════════════════════════════════════════
# Tests remove_item
# ═══════════════════════════════════════════════════════════════════════


def test_remove_item_success(service, test_db, future_date):
    """Supprime un item (hard delete) d'un mouvement scheduled."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 5}, {"quantity_expected": 3}],
    )
    item_to_remove = m.items[0].id

    result = service.remove_item(item_to_remove, TENANT_ID)
    assert result is True

    # Verifier que l'item est supprime
    with pytest.raises(HTTPException) as exc_info:
        service.update_item(item_to_remove, TENANT_ID, quantity_actual=1)
    assert exc_info.value.status_code == 404


def test_remove_item_from_completed_error(service, test_db, future_date):
    """Erreur 400 si on retire un item d'un mouvement completed."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 5}],
    )
    item_id = m.items[0].id
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.IN_TRANSIT.value)
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.COMPLETED.value)

    with pytest.raises(HTTPException) as exc_info:
        service.remove_item(item_id, TENANT_ID)

    assert exc_info.value.status_code == 400
    assert "completed or cancelled" in exc_info.value.detail


def test_remove_item_from_cancelled_error(service, test_db, future_date):
    """Erreur 400 si on retire un item d'un mouvement cancelled."""
    m = service.create_movement(
        tenant_id=TENANT_ID,
        movement_type=MovementType.DEPARTURE.value,
        scheduled_date=future_date,
        items=[{"quantity_expected": 5}],
    )
    item_id = m.items[0].id
    service.update_movement(m.id, TENANT_ID, status=MovementStatus.CANCELLED.value)

    with pytest.raises(HTTPException) as exc_info:
        service.remove_item(item_id, TENANT_ID)

    assert exc_info.value.status_code == 400


def test_remove_item_not_found(service):
    """Erreur 404 si item inexistant."""
    with pytest.raises(HTTPException) as exc_info:
        service.remove_item(99999, TENANT_ID)

    assert exc_info.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Tests VALID_TRANSITIONS exhaustif
# ═══════════════════════════════════════════════════════════════════════


def test_valid_transitions_dict_completeness():
    """VALID_TRANSITIONS couvre tous les statuts de MovementStatus."""
    all_statuses = {s.value for s in MovementStatus}
    assert set(VALID_TRANSITIONS.keys()) == all_statuses


def test_terminal_states_have_no_transitions():
    """completed et cancelled sont des etats terminaux (aucune transition sortante)."""
    assert VALID_TRANSITIONS[MovementStatus.COMPLETED.value] == set()
    assert VALID_TRANSITIONS[MovementStatus.CANCELLED.value] == set()
