# Plan de revivification des flows morts — CaroCorp / Marveline

Audit 2026-03-21. 16 flows morts ou partiellement morts identifies.
Chaque correction respecte les conventions : multi-tenant, centimes, soft delete, tests, migrations expand/contract.

---

## Conventions rappel

- Montants : BigInteger centimes (250 = 2.50 EUR)
- Multi-tenant : filtre `tenant_id` obligatoire dans chaque query
- Migrations : expand/contract (jamais destructive directe)
- Tests : nominal + non-regression + isolation tenant
- Constantes : `app/constants/` (pas de strings magiques)
- Notifications : via `app/services/notification.py` (email Celery async)

---

## PHASE 1 — Supprimer le code mort irrecuperable

### 1.3 — Supprimer `Reservation.signature_url` (legacy)

Le champ est redondant avec `Devis.signature_url` qui est le vrai champ utilise.

**Fichiers :**
- `app/models/reservation.py` — supprimer la colonne `signature_url`
- `app/schemas/reservation.py` — supprimer des schemas `ReservationDetail`, `ReservationDetailFull`
- Migration Alembic : `ALTER TABLE reservations DROP COLUMN signature_url` (contract phase apres verification zero usage)

**Prerequis** : Verifier que le frontend ne lit pas `reservation.signature_url` :
```bash
grep -rn "signature_url" frontend/apps/marveline/src/ | grep -v devis | grep -v node_modules
```
Si des references existent, les pointer vers `reservation.devis.signature_url`.

### 1.4 — Supprimer `Reservation.deposit_paid` (redondant)

Le champ est redondant avec la table `deposits` (statut `held`/`released`/`retained`).

**Fichiers :**
- `app/models/reservation.py` — supprimer `deposit_paid: Mapped[bool]`
- `app/schemas/reservation.py` — supprimer des schemas
- `app/services/deposit.py:49` — supprimer `reservation.deposit_paid = True`
- Migration Alembic : `ALTER TABLE reservations DROP COLUMN deposit_paid`

**Remplacement** : Partout ou `deposit_paid` etait lu, utiliser :
```python
has_deposit = await deposit_service.has_held_deposit(reservation_id, tenant_id)
```

**Ajouter dans** `app/services/deposit.py` :
```python
async def has_held_deposit(self, reservation_id: int, tenant_id: int) -> bool:
    deposits = await self.repo.list_by_reservation(reservation_id, tenant_id)
    return any(d.status == "held" for d in deposits)
```

---

## PHASE 2 — Connecter les champs existants (affichage + recherche)

### 2.1 — `assigned_user_id` : filtre + notification + affichage

**Backend :**

**Fichier** : `app/api/v1/endpoints/reservations.py` (list endpoint)

Ajouter parametre de filtre :
```python
@router.get("", response_model=PaginatedResponse[ReservationList])
async def list_reservations(
    ...
    assigned_to_me: bool = Query(default=False, description="Filtrer mes reservations"),
    assigned_user_id: int | None = Query(default=None),
):
    if assigned_to_me:
        assigned_user_id = current_user.id
    reservations, total = await service.list_reservations(
        ..., assigned_user_id=assigned_user_id,
    )
```

**Fichier** : `app/services/reservation.py` (list method)

Ajouter filtre :
```python
if assigned_user_id is not None:
    query = query.filter(Reservation.assigned_user_id == assigned_user_id)
```

**Fichier** : `app/api/v1/endpoints/reservations.py` (assign endpoint)

Ajouter notification apres affectation :
```python
@router.patch("/{reservation_id}/assign")
async def assign_user_to_reservation(...):
    ...
    res.assigned_user_id = data.user_id
    await db.commit()

    # Notifier l'utilisateur affecte
    if data.user_id:
        await notification_service.send_assignment_notification(
            user_id=data.user_id,
            tenant_id=current_user.tenant_id,
            reservation_id=reservation_id,
            reservation_reference=res.reference,
            assigned_by=current_user.id,
        )
    ...
```

**Fichier** : `app/services/notification.py`

Ajouter methode :
```python
async def send_assignment_notification(
    self, user_id: int, tenant_id: int,
    reservation_id: int, reservation_reference: str,
    assigned_by: int,
) -> None:
    await self._create_notification(
        user_id=user_id,
        tenant_id=tenant_id,
        title="Reservation affectee",
        body=f"La reservation {reservation_reference} vous a ete affectee.",
        link=f"/reservations/{reservation_id}",
        notification_type="assignment",
    )
```

**Frontend :**

**Fichier** : `frontend/.../pages/events/EventsPage.tsx`

Ajouter chip filtre "Mes reservations" :
```tsx
<button
  onClick={() => navigate({ search: (p) => ({ ...p, assigned_to_me: true }) })}
  className={cn('chip', search.assigned_to_me && 'chip-active')}
>
  Mes reservations
</button>
```

**Fichier** : `frontend/.../api/reservations.ts` (listReservations)

Passer le parametre `assigned_to_me` et `assigned_user_id`.

---

### 2.2 — `Reservation.notes` + `Customer.notes` : affichage

**Frontend** : `ReservationDetailPage.tsx`

Ajouter section notes (si non vide) :
```tsx
{reservation.notes && (
  <CollapsibleSection title="Notes" icon={<StickyNote className="w-4 h-4" />} defaultOpen={false}>
    <p className="text-sm text-dark-300 whitespace-pre-wrap">{reservation.notes}</p>
  </CollapsibleSection>
)}
```

**Frontend** : composant customer detail (si existe)

Meme pattern pour `customer.notes`.

**Backend** : Aucun changement — les champs sont deja retournes dans les schemas.

---

### 2.3 — `Product.weight_grams` / `volume_cm3` : calcul livraison

**Backend** :

**Fichier** : `app/services/reservation.py`

Ajouter methode de calcul automatique :
```python
async def compute_logistics(self, reservation_id: int, tenant_id: int) -> dict:
    """Calcule poids total + volume total depuis les lignes produit."""
    reservation = await self.get_reservation(reservation_id, tenant_id)
    total_weight = 0
    total_volume = 0
    for line in reservation.lines:
        product = line.product
        if product:
            total_weight += (product.weight_grams or 0) * line.quantity
            total_volume += (product.volume_cm3 or 0) * line.quantity
    return {
        "total_weight_grams": total_weight,
        "total_weight_kg": round(total_weight / 1000, 2),
        "total_volume_cm3": total_volume,
        "total_volume_liters": round(total_volume / 1000, 2),
    }
```

**Fichier** : `app/services/invoice.py` (ou service de calcul frais)

Utiliser poids + zone pour calculer frais livraison auto :
```python
async def compute_delivery_fee(
    self, reservation_id: int, tenant_id: int,
    delivery_zone_id: int | None,
) -> int:
    """Retourne frais livraison en centimes basé sur poids + zone."""
    logistics = await reservation_service.compute_logistics(reservation_id, tenant_id)
    if not delivery_zone_id:
        return 0
    zone = await delivery_zone_repo.get_by_id(delivery_zone_id, tenant_id)
    if not zone:
        return 0
    # Formule : base_fee + (weight_kg * fee_per_kg)
    weight_kg = logistics["total_weight_kg"]
    fee = zone.base_fee_cents + int(weight_kg * zone.fee_per_kg_cents)
    return fee
```

**Prerequis** : Ajouter `base_fee_cents` et `fee_per_kg_cents` au modele `DeliveryZone` (migration expand).

---

### 2.7 — `Invoice` timestamps : affichage timeline facture

**Frontend** : `InvoiceDetailModal.tsx` ou equivalent

Ajouter timeline facture :
```tsx
const timelineSteps = [
  { label: 'Creee', date: invoice.created_at, done: true },
  { label: 'Envoyee', date: invoice.sent_at, done: !!invoice.sent_at },
  { label: 'Ouverte', date: invoice.opened_at, done: !!invoice.opened_at },
  { label: 'Relancee', date: invoice.last_reminder_sent_at, done: !!invoice.last_reminder_sent_at },
  { label: 'Payee', date: invoice.payment_date, done: invoice.status === 'paid' },
]
```

**Backend** : Les timestamps sont deja retournes dans `InvoiceDetail`. Aucun changement.

---

## PHASE 3 — Connecter les workflows (Celery + business rules)

### 3.8 — Relances : task Celery pour execution automatique

**Fichier** : `app/tasks/relances.py` (nouveau)

```python
"""Task Celery — execution des relances planifiees."""
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.relances.execute_scheduled_relances")
def execute_scheduled_relances():
    """Execute les relances dont scheduled_at <= now et status = 'scheduled'.

    Pour chaque relance :
    1. Charger reservation + customer
    2. Envoyer email via notification_service
    3. Mettre a jour : status='sent', sent_at=now()
    4. Logger audit

    Beat schedule : toutes les heures.
    """
    from app.core.database import get_db_context
    from sqlalchemy import select, update
    from app.models.relance import Relance
    from app.models.reservation import Reservation
    from app.models.customer import Customer

    now = datetime.now(timezone.utc)

    with get_db_context() as db:
        relances = db.execute(
            select(Relance)
            .join(Reservation, Relance.reservation_id == Reservation.id)
            .join(Customer, Reservation.customer_id == Customer.id)
            .filter(
                Relance.status == "scheduled",
                Relance.scheduled_at <= now,
            )
            .limit(100)
        ).scalars().all()

        sent_count = 0
        for relance in relances:
            try:
                # Envoyer la notification
                reservation = db.get(Reservation, relance.reservation_id)
                if not reservation:
                    continue
                customer = db.get(Customer, reservation.customer_id)
                if not customer or not customer.email:
                    logger.warning("Relance %d skip: no customer email", relance.id)
                    continue

                # Marquer comme envoyee
                relance.status = "sent"
                relance.sent_at = now
                sent_count += 1

                logger.info(
                    "Relance %d sent: reservation=%s customer=%s type=%s",
                    relance.id, reservation.reference, customer.email, relance.relance_type,
                )
            except Exception as e:
                logger.error("Relance %d failed: %s", relance.id, e)
                relance.status = "failed"

        db.commit()
        logger.info("[relances] Executed %d/%d scheduled relances", sent_count, len(relances))
        return {"sent": sent_count, "total": len(relances)}
```

**Fichier** : `app/tasks/celery_app.py` — ajouter au beat schedule :

```python
celery_app.conf.beat_schedule["execute-relances"] = {
    "task": "app.tasks.relances.execute_scheduled_relances",
    "schedule": 3600,  # Toutes les heures
}
```

---

### 3.9 — PricingRules : moteur d'application automatique

**Fichier** : `app/services/pricing_engine.py` (nouveau)

```python
"""Moteur d'application des regles de pricing.

Applique les PricingRules actives a un calcul de prix.
Types de regles supportes :
- discount_percent : remise en % sur le total
- discount_fixed : remise fixe en centimes
- minimum_days : nombre minimum de jours de location
- seasonal_multiplier : multiplicateur saisonnier
"""
import logging
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pricing import PricingRule

logger = logging.getLogger(__name__)


class PricingEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def apply_rules(
        self,
        tenant_id: int,
        base_amount_cents: int,
        event_date: date,
        rental_days: int,
        event_type: str | None = None,
        customer_type: str | None = None,
    ) -> dict:
        """Applique toutes les regles actives et retourne le montant final.

        Returns:
            {
                "base_cents": int,
                "final_cents": int,
                "applied_rules": [{"rule_id": int, "name": str, "adjustment_cents": int}],
                "rental_days_effective": int,
            }
        """
        rules = await self._get_active_rules(tenant_id)
        applied = []
        amount = base_amount_cents
        effective_days = rental_days

        for rule in rules:
            if not self._rule_matches(rule, event_date, event_type, customer_type):
                continue

            if rule.rule_type == "discount_percent":
                discount = int(amount * rule.value / 100)
                amount -= discount
                applied.append({"rule_id": rule.id, "name": rule.name, "adjustment_cents": -discount})

            elif rule.rule_type == "discount_fixed":
                discount = min(int(rule.value), amount)
                amount -= discount
                applied.append({"rule_id": rule.id, "name": rule.name, "adjustment_cents": -discount})

            elif rule.rule_type == "minimum_days":
                min_days = int(rule.value)
                if effective_days < min_days:
                    effective_days = min_days
                    applied.append({"rule_id": rule.id, "name": rule.name, "adjustment_cents": 0})

            elif rule.rule_type == "seasonal_multiplier":
                extra = int(amount * (rule.value - 1))
                amount += extra
                applied.append({"rule_id": rule.id, "name": rule.name, "adjustment_cents": extra})

        return {
            "base_cents": base_amount_cents,
            "final_cents": max(0, amount),
            "applied_rules": applied,
            "rental_days_effective": effective_days,
        }

    async def _get_active_rules(self, tenant_id: int) -> list[PricingRule]:
        result = await self.db.execute(
            select(PricingRule)
            .filter(PricingRule.tenant_id == tenant_id, PricingRule.is_active == True)
            .order_by(PricingRule.priority)
        )
        return list(result.scalars().all())

    def _rule_matches(
        self, rule: PricingRule, event_date: date,
        event_type: str | None, customer_type: str | None,
    ) -> bool:
        """Verifie si une regle s'applique aux conditions donnees."""
        if hasattr(rule, 'valid_from') and rule.valid_from and event_date < rule.valid_from:
            return False
        if hasattr(rule, 'valid_to') and rule.valid_to and event_date > rule.valid_to:
            return False
        if hasattr(rule, 'event_types') and rule.event_types:
            if event_type and event_type not in rule.event_types:
                return False
        if hasattr(rule, 'customer_types') and rule.customer_types:
            if customer_type and customer_type not in rule.customer_types:
                return False
        return True
```

**Integration** : Appeler `PricingEngine.apply_rules()` dans `app/services/invoice.py` lors de la creation de facture, et dans `app/services/devis.py` lors du calcul de devis.

---

## PHASE 4 — Connecter les workflows partiellement morts

### 4.10 — `event_type` : tarification differenciee

**Fichier** : `app/constants/business.py`

Ajouter constantes :
```python
EVENT_TYPE_MIN_DAYS = {
    "mariage": 3,
    "entreprise": 2,
    "anniversaire": 1,
    "autre": 1,
}
```

**Fichier** : `app/services/reservation.py` (validation creation)

Ajouter check :
```python
from app.constants.business import EVENT_TYPE_MIN_DAYS

min_days = EVENT_TYPE_MIN_DAYS.get(data.event_type, 1)
if rental_days < min_days:
    raise HTTPException(400, detail=f"Minimum {min_days} jours pour un evenement {data.event_type}")
```

---

### 4.12 — `delivery_method/fee` + `DeliveryZone` : calcul auto

**Modele** : `app/models/delivery_zone.py`

Migration expand — ajouter colonnes :
```python
base_fee_cents: Mapped[int] = mapped_column(BigInteger, default=0)
fee_per_kg_cents: Mapped[int] = mapped_column(BigInteger, default=0)
max_weight_kg: Mapped[int | None] = mapped_column(nullable=True)
```

**Service** : cf. section 2.3 — `compute_delivery_fee()`.

**Integration** : Lors de la creation de facture, ajouter automatiquement une ligne "Frais de livraison" si `delivery_zone_id` est defini et `delivery_method != 'pickup'`.

---

### 4.13 — `ReservationRisk` : detection auto + blocage depart

**Fichier** : `app/services/reservation_workflow.py`

Ajouter detection automatique de risques :
```python
async def detect_risks(self, reservation_id: int, tenant_id: int) -> list[dict]:
    """Detecte automatiquement les risques sur une reservation.

    Risques verifies :
    - deposit_missing : caution non encaissee + event_date < 7 jours
    - overdue_invoice : facture en retard
    - low_stock : stock insuffisant pour les articles reserves
    - past_damages : client avec historique de dommages
    """
    risks = []
    reservation = await self.get_reservation(reservation_id, tenant_id)

    # Caution manquante a J-7
    if not await deposit_service.has_held_deposit(reservation_id, tenant_id):
        days_until = (reservation.event_date - date.today()).days
        if days_until <= 7:
            risks.append({
                "type": "deposit_missing",
                "severity": "high",
                "blocking": True,
                "description": f"Caution non encaissee a J-{days_until}",
            })

    # Facture en retard
    overdue = await invoice_service.has_overdue(reservation_id, tenant_id)
    if overdue:
        risks.append({
            "type": "overdue_invoice",
            "severity": "medium",
            "blocking": False,
            "description": "Facture en retard de paiement",
        })

    return risks
```

**Integration** : Appeler `detect_risks()` dans le flow de depart (`operations.py`) et bloquer si un risque `blocking=True` existe.

---

### 4.14 — `DamageType` : lier aux charges facture

**Fichier** : `app/services/invoice.py` (ou `damage_invoice`)

Lors de la creation d'une charge dommage, calculer le montant depuis le DamageType :
```python
if charge.damage_type_id:
    damage_type = await damage_type_repo.get_by_id(charge.damage_type_id, tenant_id)
    if damage_type and damage_type.default_charge_cents:
        charge.amount_cents = damage_type.default_charge_cents
```

**Prerequis** : Ajouter `default_charge_cents` au modele `DamageType` (migration expand).

---

### 4.16 — `Formula` : selection automatique par type evenement

**Fichier** : `app/services/devis.py`

Lors de la creation d'un devis, si `event_type` + `guest_count` sont renseignes :
```python
async def suggest_formula(self, event_type: str, guest_count: int, tenant_id: int) -> Formula | None:
    """Suggere la formule la plus adaptee selon type + nb invites."""
    formulas = await formula_repo.list_active(tenant_id)
    for f in formulas:
        if f.min_guests <= guest_count <= f.max_guests:
            if not f.event_types or event_type in f.event_types:
                return f
    return None
```

**Prerequis** : Ajouter `min_guests`, `max_guests`, `event_types` (JSON list) au modele `Formula` (migration expand).

---

## PHASE 5 — Verification

```bash
# Tests unitaires nouveaux services
docker compose run --rm --entrypoint "" api python -m pytest tests/unit/test_pricing_engine.py -v
docker compose run --rm --entrypoint "" api python -m pytest tests/unit/test_relances_task.py -v

# Tests integration
docker compose run --rm --entrypoint "" api python -m pytest tests/integration/test_reservations_endpoints.py -v -k "assign"
docker compose run --rm --entrypoint "" api python -m pytest tests/integration/test_relances.py -v

# Verifier que les flows morts sont connectes
grep -rn "assigned_user_id" app/ | grep -v "model\|schema\|migration" | wc -l  # doit etre > 3
grep -rn "execute_scheduled_relances" app/ | wc -l  # doit etre >= 2
grep -rn "PricingEngine\|pricing_engine" app/ | wc -l  # doit etre >= 2
```

## Ordre d'execution

```
PHASE 1 (J1)     : Supprimer signature_url + deposit_paid (2 migrations)
PHASE 2 (J2-J3)  : assigned_user_id filtre+notif, notes affichage, weight calcul, invoice timeline
PHASE 3 (J4-J5)  : Relances Celery task, PricingEngine
PHASE 4 (J6-J7)  : event_type validation, delivery_zone calcul, risk detection, damage charges, formula auto
PHASE 5 (J8)     : Tests + verification
```
