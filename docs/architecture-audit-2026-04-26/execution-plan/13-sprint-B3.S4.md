# Sprint B3.S4 — Conversion atomique Devis→Résa + Cancel cascade + Deposit FSM

> **STATUT** : ⏳ À démarrer après B3.S3
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev1
> **BLOQUE** : B3.S5 (Celery jobs s'appuient sur FSM Devis/Reservation), B5.S3 (cascade resto/épicerie)
> **DÉPEND DE** : B3.S2 (FSM helper), B3.S3 (`PricingEngine.quote()`)
> **OBJECTIF** : Implémenter la conversion **Devis → Reservation → Invoice émise** atomique en 1 transaction (Q12=A — Invoice émise immédiatement à signature). Livrer la cascade `Cancel` explicite (TR-5) qui orchestre stock release + deposit refund + credit_note. Livrer la FSM `Deposit` avec immutabilité montant.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B3.S4.T1** | TR-12 — Conversion Devis→Résa atomique avec Invoice émise (Q12=A) | P0 | 2.5 j | T2, B3.S5 |
| **B3.S4.T2** | TR-5 — Cancel cascade explicite (FSM + stock release + deposit refund + credit_note) | P0 | 2 j | T3, B5.S3 |
| **B3.S4.T3** | DepositFSM + `amount_cents` immutable trigger (F675) | P1 | 1 j | aucun |
| **B3.S4.T4** | `DepositPolicyService.resolve` (Q14=C — `Customer.requires_deposit` overridable) | P1 | 1 j | T1 |
| **B3.S4.T5** | `ReservationCancelService` orchestrateur + Outbox event `ReservationCancelled` | P1 | 0.5 j | aucun |

**Total effort** : 7 jours-homme.

---

# Story B3.S4.T1 — Conversion Devis→Reservation atomique avec Invoice émise

## Contexte

**Friction** : TR-12 (cf. `architecture-cible.md §3.2.6`)
**Sévérité** : P0 — flux conversion incohérent : Devis converti sans réservation stock, ou Réservation créée sans facture, ou Invoice draft jamais émise → comptabilité fausse + double-vente du même créneau
**Code source** : `app/services/devis.py:convert_to_reservation`, `app/services/reservation.py:from_devis`, `app/services/invoice.py:create_from_reservation`
**Décision** : Q12=A (verrouillée 2026-04-27) — Invoice émise dès `Reservation.status='confirmed'`, pas à la livraison

### Description

Aujourd'hui : conversion en 3 endpoints séparés
- `POST /devis/{id}/convert` → crée Reservation seulement
- `POST /reservations/{id}/confirm` → reserve stock
- `POST /reservations/{id}/invoice` → crée Invoice draft

Chaque étape peut échouer indépendamment → état inconsistant :
- Devis converti, Reservation existante, Stock non réservé → double-booking
- Reservation confirmée, Invoice jamais créée → CA non comptabilisé
- Stock réservé, Invoice draft jamais émise → TVA non déclarée

**Q12=A** : tout doit se passer en 1 TX atomique :
1. Lock Devis + assert FSM transition `pending → converted`
2. Reserve stock (lock per `reservation_id`, cf. STOCK-RELEASE-BLIND-01 résolu)
3. Créer Reservation (`status='confirmed'`)
4. Émettre Invoice IMMÉDIATEMENT (`status='emitted'`, pas draft) — déclenche trigger DB immutability
5. FSM Devis transition + Outbox event `DevisConverted`

## Solution

### Service orchestrateur

```python
# app/services/devis_conversion.py (NEW)
from app.services.fsm import FSMHelper, InvalidTransition
from app.services.pricing.engine import PricingEngine
from app.services.stock import StockService
from app.services.invoice import InvoiceService
from app.core.exceptions import StockInsufficient


class DevisConversionResult:
    devis: Devis
    reservation: Reservation
    invoice: Invoice
    deposit_required_cents: int
    pricing_snapshot: PricingResult


class DevisConversionService:
    """Q12=A — conversion atomique Devis→Reservation→Invoice émise (1 TX)."""

    def __init__(
        self,
        db: AsyncSession,
        pricing: PricingEngine,
        stock: StockService,
        invoice: InvoiceService,
        deposit_policy: DepositPolicyService,
        fsm: FSMHelper,
    ):
        self.db = db
        self.pricing = pricing
        self.stock = stock
        self.invoice = invoice
        self.deposit_policy = deposit_policy
        self.fsm = fsm

    async def convert(
        self,
        devis_id: UUID,
        actor_id: UUID,
        tenant_id: int,
    ) -> DevisConversionResult:
        # 1. Lock Devis + reload sous lock
        async with self.db.begin():
            devis = (await self.db.execute(
                select(Devis)
                .where(Devis.id == devis_id, Devis.tenant_id == tenant_id)
                .with_for_update()
            )).scalar_one_or_none()
            if devis is None:
                raise NotFound(f"Devis {devis_id}")

            # 2. FSM assert transition légale (B3.S2)
            await self.fsm.assert_transition(
                self.db, "devis", devis.id, devis.status, "converted",
                actor_id=actor_id, reason="convert_to_reservation",
            )

            # 3. Recalculer pricing snapshot (le PricingEngine garantit consistency)
            pricing_result = await self._rebuild_pricing(devis, tenant_id)

            # 4. Reserve stock (advisory lock per ligne, propage reservation_id futur)
            reservation_id = uuid4()
            try:
                await self.stock.reserve(
                    reservation_id=reservation_id,
                    tenant_id=tenant_id,
                    lines=[(l.product_id, l.qty) for l in devis.lines],
                    db=self.db,
                )
            except StockInsufficient as e:
                # Pas de rollback partiel : la TX entière annule
                raise

            # 5. Créer Reservation status='confirmed' (Q12=A)
            reservation = Reservation(
                id=reservation_id,
                tenant_id=tenant_id,
                devis_id=devis.id,
                customer_id=devis.customer_id,
                status="confirmed",
                event_date=devis.event_date,
                total_ht_cents=pricing_result.total_ht_cents,
                total_tva_cents=pricing_result.total_tva_cents,
                total_ttc_cents=pricing_result.total_ttc_cents,
                lines=[
                    ReservationLine(
                        product_id=ls.product_id,
                        qty=ls.qty,
                        unit_price_ht_cents=ls.unit_price_ht_cents,
                        tva_rate_snapshot=ls.tva_rate_snapshot,
                        discount_pct_applied=ls.discount_pct_applied,
                        line_total_ht_cents=ls.line_total_ht_cents,
                        line_total_tva_cents=ls.line_total_tva_cents,
                    )
                    for ls in pricing_result.lines
                ],
            )
            self.db.add(reservation)
            await self.db.flush()

            # 6. Émettre Invoice IMMÉDIATEMENT (Q12=A : status='emitted', pas draft)
            invoice = await self.invoice.create_emitted_from_reservation(
                reservation, pricing_result, actor_id,
            )
            # Trigger DB immutability (B3.S2.T3) protège invoice à partir d'ici

            # 7. FSM Devis transition + Outbox audit
            devis.status = "converted"
            await self.fsm.log_transition(
                self.db, "devis", devis.id, "pending", "converted", actor_id,
                metadata={"reservation_id": str(reservation_id), "invoice_id": str(invoice.id)},
            )
            await self.db.execute(
                insert(OutboxEvent).values(
                    event_type="DevisConverted",
                    aggregate_id=devis.id,
                    tenant_id=tenant_id,
                    payload={
                        "reservation_id": str(reservation_id),
                        "invoice_id": str(invoice.id),
                        "total_ttc_cents": pricing_result.total_ttc_cents,
                    },
                )
            )

            # 8. Calculer acompte requis (Q14=C — DepositPolicyService)
            deposit_pct = await self.deposit_policy.resolve(
                customer_id=devis.customer_id, tenant_id=tenant_id,
            )
            deposit_required = int(pricing_result.total_ttc_cents * deposit_pct)

            return DevisConversionResult(
                devis=devis,
                reservation=reservation,
                invoice=invoice,
                deposit_required_cents=deposit_required,
                pricing_snapshot=pricing_result,
            )

    async def _rebuild_pricing(self, devis: Devis, tenant_id: int) -> PricingResult:
        """Reconstruit le snapshot pricing depuis les lignes du devis (lit tva_rate_snapshot,
        appelle PricingEngine pour cumul discount additif consistent)."""
        line_inputs = [
            LineInput(
                product_id=l.product_id,
                qty=l.qty,
                unit_price_ht_cents=l.unit_price_ht_cents,
                tva_rate=l.tva_rate_snapshot,  # lecture snapshot, pas re-resolve
            )
            for l in devis.lines
        ]
        discounts = await self._resolve_discounts(devis, tenant_id)
        return self.pricing.quote(line_inputs, discounts, tenant_id)
```

### Endpoint

```python
# app/api/v1/endpoints/devis.py
@router.post("/devis/{devis_id}/convert", response_model=ConversionResponse)
async def convert_devis_to_reservation(
    devis_id: UUID,
    service: DevisConversionService = Depends(get_devis_conversion_service),
    user: User = Depends(require_scope(Scope.RESERVATIONS_WRITE)),
    tenant_id: int = Depends(get_tenant_id),
):
    result = await service.convert(devis_id, actor_id=user.id, tenant_id=tenant_id)
    return ConversionResponse(
        devis_id=result.devis.id,
        reservation_id=result.reservation.id,
        invoice_id=result.invoice.id,
        invoice_status="emitted",
        total_ttc_cents=result.pricing_snapshot.total_ttc_cents,
        deposit_required_cents=result.deposit_required_cents,
    )
```

### Test atomicité

```python
# tests/test_devis_conversion_atomic.py
async def test_conversion_rollback_si_stock_insufficient(db, tenant, devis_with_unstocked_product):
    """Si reserve stock échoue → pas de Reservation, pas d'Invoice, Devis reste 'pending'."""
    with pytest.raises(StockInsufficient):
        await service.convert(devis_with_unstocked_product.id, actor_id=user.id, tenant_id=tenant.id)

    # Vérifier état post-rollback
    devis = await db.get(Devis, devis_with_unstocked_product.id)
    assert devis.status == "pending"  # FSM pas mutée
    reservations = await db.execute(select(Reservation).where(Reservation.devis_id == devis.id))
    assert reservations.first() is None  # pas de réservation orpheline
    invoices = await db.execute(select(Invoice).where(Invoice.devis_id == devis.id))
    assert invoices.first() is None  # pas d'invoice draft

async def test_conversion_invoice_immediately_emitted(db, tenant, devis):
    result = await service.convert(devis.id, actor_id=user.id, tenant_id=tenant.id)
    assert result.invoice.status == "emitted"  # Q12=A
    # Trigger DB immutability actif : modifier total → exception
    with pytest.raises(IntegrityError, match="immutable"):
        await db.execute(
            update(Invoice).where(Invoice.id == result.invoice.id).values(total_ttc_cents=999)
        )

async def test_conversion_double_call_idempotent(db, tenant, devis):
    """Double POST /convert (retry réseau) → 2e appel échoue avec InvalidTransition (FSM pending→converted déjà fait)."""
    await service.convert(devis.id, actor_id=user.id, tenant_id=tenant.id)
    with pytest.raises(InvalidTransition):
        await service.convert(devis.id, actor_id=user.id, tenant_id=tenant.id)
```

## DoD

- [ ] `DevisConversionService.convert` implémenté avec `async with db.begin()`
- [ ] Lock `Devis with_for_update` + `FSMHelper.assert_transition`
- [ ] Reserve stock avec `reservation_id` (cf. STOCK-RELEASE-BLIND-01)
- [ ] Invoice émise (`status='emitted'`) immédiatement, pas draft
- [ ] Outbox event `DevisConverted` publié dans la même TX
- [ ] Test rollback si stock insuffisant : 0 entité créée
- [ ] Test idempotence : 2e convert → InvalidTransition

---

# Story B3.S4.T2 — Cancel cascade explicite (TR-5)

## Contexte

**Friction** : TR-5 (cf. `architecture-cible.md §3.2.7`)
**Sévérité** : P0 — annulation Reservation sans cascade laisse stock réservé bloqué + acompte non remboursé + facture émise sans avoir
**Code source** : `app/services/reservation.py:cancel`, `app/services/stock.py:release`, `app/services/deposit.py`

### Description

Aujourd'hui : `ReservationService.cancel(resa_id)` mute juste `status='cancelled'`. Conséquences :
- Stock reste réservé → indisponible alors que résa annulée → blocage commercial
- Acompte payé reste sur compte client → litige
- Invoice émise reste valide → comptabilité incorrecte (facture sans contrepartie)
- Aucune relance email client

**Cible** : `ReservationCancelService` orchestre dans 1 TX :
1. FSM transition `confirmed → cancelled` (assert)
2. Stock release par `reservation_id`
3. Deposit policy : refund OR retain selon délai préavis
4. CreditNote complète si Invoice émise (annule la facture)
5. Outbox event `ReservationCancelled` → relance email auto

## Solution

### Service orchestrateur

```python
# app/services/reservation_cancel.py (NEW)
from enum import Enum

class CancelReason(str, Enum):
    CUSTOMER_REQUEST = "customer_request"
    SUPPLIER_CANCEL = "supplier_cancel"
    NO_SHOW = "no_show"
    FORCE_MAJEURE = "force_majeure"


class CancelResult:
    reservation: Reservation
    stock_released: bool
    deposit_action: str  # 'refunded' | 'retained' | 'no_deposit'
    credit_note: Invoice | None
    refund_amount_cents: int


class ReservationCancelService:
    """TR-5 — Cancel cascade orchestré : FSM + stock + deposit + credit_note + outbox."""

    def __init__(
        self,
        db: AsyncSession,
        fsm: FSMHelper,
        stock: StockService,
        deposit: DepositService,
        invoice: InvoiceService,
    ):
        self.db = db
        self.fsm = fsm
        self.stock = stock
        self.deposit = deposit
        self.invoice = invoice

    async def cancel(
        self,
        reservation_id: UUID,
        reason: CancelReason,
        actor_id: UUID,
        tenant_id: int,
    ) -> CancelResult:
        async with self.db.begin():
            # 1. Lock Reservation + assert FSM
            reservation = (await self.db.execute(
                select(Reservation)
                .where(Reservation.id == reservation_id, Reservation.tenant_id == tenant_id)
                .options(selectinload(Reservation.invoice))
                .with_for_update()
            )).scalar_one_or_none()
            if reservation is None:
                raise NotFound(f"Reservation {reservation_id}")

            await self.fsm.assert_transition(
                self.db, "reservation", reservation.id,
                reservation.status, "cancelled",
                actor_id=actor_id, reason=reason.value,
            )

            # 2. Stock release par reservation_id (STOCK-RELEASE-BLIND-01 résolu)
            await self.stock.release(reservation_id=reservation.id, tenant_id=tenant_id, db=self.db)

            # 3. Deposit : refund vs retain selon politique tenant + préavis
            deposit_action = "no_deposit"
            refund_amount = 0
            existing_deposit = await self.deposit.find_for_reservation(reservation.id)
            if existing_deposit and existing_deposit.status == "paid":
                policy_decision = await self.deposit.policy_for_cancel(
                    reservation, reason, now=datetime.now(UTC),
                )
                if policy_decision.refund:
                    await self.deposit.refund(existing_deposit.id, full=policy_decision.full)
                    deposit_action = "refunded"
                    refund_amount = policy_decision.refund_amount_cents
                else:
                    await self.deposit.retain(existing_deposit.id, reason=reason.value)
                    deposit_action = "retained"

            # 4. CreditNote si Invoice émise (article 289 CGI : facture immutable, annulation = avoir)
            credit_note = None
            if reservation.invoice and reservation.invoice.status == "emitted":
                credit_note = await self.invoice.create_credit_note(
                    invoice_id=reservation.invoice.id,
                    full=True,
                    reason=f"Reservation cancelled: {reason.value}",
                    actor_id=actor_id,
                )

            # 5. FSM mutation + Outbox event
            reservation.status = "cancelled"
            reservation.cancelled_at = datetime.now(UTC)
            reservation.cancelled_reason = reason.value
            await self.fsm.log_transition(
                self.db, "reservation", reservation.id,
                from_state="confirmed", to_state="cancelled",
                actor_id=actor_id,
                metadata={
                    "reason": reason.value,
                    "stock_released": True,
                    "deposit_action": deposit_action,
                    "credit_note_id": str(credit_note.id) if credit_note else None,
                },
            )
            await self.db.execute(
                insert(OutboxEvent).values(
                    event_type="ReservationCancelled",
                    aggregate_id=reservation.id,
                    tenant_id=tenant_id,
                    payload={
                        "reservation_id": str(reservation.id),
                        "customer_id": str(reservation.customer_id),
                        "reason": reason.value,
                        "deposit_action": deposit_action,
                        "refund_amount_cents": refund_amount,
                        "credit_note_id": str(credit_note.id) if credit_note else None,
                    },
                )
            )

            return CancelResult(
                reservation=reservation,
                stock_released=True,
                deposit_action=deposit_action,
                credit_note=credit_note,
                refund_amount_cents=refund_amount,
            )
```

### Email handler outbox

```python
# app/workers/outbox_handlers/reservation_cancelled.py
async def handle_reservation_cancelled(event: OutboxEvent):
    """Worker outbox lit ReservationCancelled → email client via EmailGateway (B3.S5)."""
    customer = await get_customer(event.payload["customer_id"])
    await email_gateway.send(
        to=customer.email,
        subject=f"Annulation de votre réservation",
        body_html=render_template("cancellation.html.j2", event.payload),
        tenant_id=event.tenant_id,
    )
```

## DoD

- [ ] `ReservationCancelService.cancel` orchestré en 1 TX
- [ ] Stock release par `reservation_id` (pas d'aveugle)
- [ ] Deposit policy decision : refund/retain selon délai préavis tenant
- [ ] CreditNote auto si Invoice émise
- [ ] Outbox event `ReservationCancelled` publié
- [ ] Test : annuler résa avec acompte payé J-30 → refund full
- [ ] Test : annuler résa avec acompte payé J-2 → retain (politique défaut)
- [ ] Test : annuler résa Invoice émise → CreditNote créée + sa Invoice référence l'originale

---

# Story B3.S4.T3 — DepositFSM + `amount_cents` immutable

## Contexte

**Friction** : F675 (vague 6, angles morts)
**Sévérité** : P1 — montant acompte mutable post-paiement = risque comptable
**Code source** : `app/models/deposit.py`

### Description

Aujourd'hui : `Deposit.amount_cents` peut être modifié après statut `paid`. Si un dev recalcule un acompte et l'écrit, l'historique paiement client diverge des écritures comptables.

## Solution

### FSM matrix

```python
# app/services/fsm.py — ajouter dans le registry
DEPOSIT_FSM = FSMMatrix(
    entity_type="deposit",
    transitions={
        ("required", "paid"),
        ("required", "waived"),
        ("paid", "refunded"),
        ("paid", "retained"),
    },
    initial_states={"required"},
    terminal_states={"refunded", "retained", "waived"},
)
FSM_MATRICES["deposit"] = DEPOSIT_FSM
```

### Trigger DB immutability

```python
# alembic/versions/e3f4a5b6c7da_deposit_amount_immutable.py
def upgrade() -> None:
    op.execute(text("""
        CREATE OR REPLACE FUNCTION deposit_amount_immutable_check()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status IN ('paid', 'refunded', 'retained') 
               AND NEW.amount_cents IS DISTINCT FROM OLD.amount_cents THEN
                RAISE EXCEPTION 'deposit_amount_immutable: cannot modify amount_cents on deposit %  (status=%)', 
                    OLD.id, OLD.status;
            END IF;
            RETURN NEW;
        END $$ LANGUAGE plpgsql;
    """))
    op.execute(text("""
        CREATE TRIGGER trg_deposits_amount_immutable
        BEFORE UPDATE ON deposits
        FOR EACH ROW EXECUTE FUNCTION deposit_amount_immutable_check();
    """))

def downgrade() -> None:
    op.execute(text("DROP TRIGGER IF EXISTS trg_deposits_amount_immutable ON deposits"))
    op.execute(text("DROP FUNCTION IF EXISTS deposit_amount_immutable_check()"))
```

### Test

```python
async def test_deposit_amount_immutable_after_paid(db, deposit_paid):
    with pytest.raises(IntegrityError, match="deposit_amount_immutable"):
        await db.execute(
            update(Deposit).where(Deposit.id == deposit_paid.id).values(amount_cents=999)
        )

async def test_deposit_status_mutable_after_paid(db, deposit_paid):
    """Status peut transitionner (paid→refunded), montant non."""
    await db.execute(
        update(Deposit).where(Deposit.id == deposit_paid.id).values(status="refunded")
    )  # OK
```

## DoD

- [ ] `DEPOSIT_FSM` ajouté au registry FSM_MATRICES
- [ ] Trigger DB `deposit_amount_immutable_check` actif
- [ ] Test : modifier `amount_cents` après paid → IntegrityError
- [ ] Test : modifier `status` paid→refunded → OK

---

# Story B3.S4.T4 — `DepositPolicyService.resolve` (Q14=C)

## Contexte

**Décision** : Q14=C (verrouillée 2026-04-27) — `Customer.requires_deposit` boolean overridable + `Customer.deposit_override_pct` + `Tenant.default_deposit_pct`
**Sévérité** : P1 — UX Marveline : "Client régulier — pas d'acompte" doit être configurable per-customer

### Description

Cible :
```python
DepositPolicyService.resolve(customer, tenant) -> Decimal:
    if not customer.requires_deposit:
        return 0
    return customer.deposit_override_pct ?? tenant.default_deposit_pct ?? 0.30
```

## Solution

### Migrations

```python
# alembic/versions/e3f4a5b6c7db_customer_deposit_overrides.py
def upgrade() -> None:
    op.add_column("customers", sa.Column("requires_deposit", sa.Boolean, nullable=False, server_default="true"))
    op.add_column("customers", sa.Column("deposit_override_pct", sa.Numeric(5, 4), nullable=True))
    op.create_check_constraint(
        "ck_customers_deposit_override_range",
        "customers",
        "deposit_override_pct IS NULL OR (deposit_override_pct >= 0 AND deposit_override_pct <= 1)",
    )
    op.add_column("tenants", sa.Column("default_deposit_pct", sa.Numeric(5, 4), nullable=False, server_default="0.30"))
```

### Service

```python
# app/services/deposit_policy.py (NEW)
class DepositPolicyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve(self, customer_id: UUID, tenant_id: int) -> Decimal:
        result = await self.db.execute(
            select(
                Customer.requires_deposit,
                Customer.deposit_override_pct,
                Tenant.default_deposit_pct,
            )
            .join(Tenant, Tenant.id == Customer.tenant_id)
            .where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        )
        row = result.one_or_none()
        if row is None:
            raise NotFound(f"Customer {customer_id}")

        requires, override_pct, tenant_default = row
        if not requires:
            return Decimal("0")
        return override_pct if override_pct is not None else tenant_default
```

### Test

```python
async def test_customer_no_deposit(db, tenant, customer_no_deposit):
    customer_no_deposit.requires_deposit = False
    pct = await service.resolve(customer_no_deposit.id, tenant.id)
    assert pct == Decimal("0")

async def test_customer_override_pct(db, tenant, customer):
    customer.deposit_override_pct = Decimal("0.50")
    pct = await service.resolve(customer.id, tenant.id)
    assert pct == Decimal("0.50")

async def test_fallback_tenant_default(db, tenant, customer):
    tenant.default_deposit_pct = Decimal("0.40")
    pct = await service.resolve(customer.id, tenant.id)
    assert pct == Decimal("0.40")
```

## DoD

- [ ] Migration `Customer.requires_deposit` + `deposit_override_pct` + `Tenant.default_deposit_pct`
- [ ] CHECK [0, 1] sur `deposit_override_pct`
- [ ] `DepositPolicyService.resolve` implémenté
- [ ] Tests 3 chemins : no_deposit, override, fallback tenant

---

# Story B3.S4.T5 — Outbox event `ReservationCancelled` + handler email

## Contexte

Préparation B3.S5 (EmailGateway prod) — l'event `ReservationCancelled` doit être publié dès B3.S4 même si le worker n'envoie pas encore l'email réel.

## Solution

```python
# app/workers/outbox_router.py
EVENT_HANDLERS = {
    "DevisConverted": handle_devis_converted,
    "ReservationCancelled": handle_reservation_cancelled,
    # ...
}

# app/workers/outbox_handlers/reservation_cancelled.py
async def handle_reservation_cancelled(event: OutboxEvent, db: AsyncSession):
    """Lit l'event → enqueue Relance(type='cancellation_email') ou send direct selon B3.S5."""
    relance = Relance(
        tenant_id=event.tenant_id,
        type="cancellation",
        target_id=event.aggregate_id,
        status="due",
        scheduled_for=datetime.now(UTC),
        payload=event.payload,
    )
    db.add(relance)
```

## DoD

- [ ] Handler `handle_reservation_cancelled` enregistré dans router outbox
- [ ] Test : appel `cancel()` → Relance(status='due') créée
- [ ] B3.S5 prendra le relai : worker dunning lit Relance + envoie email via EmailGateway

---

## Critères de succès Sprint B3.S4

- [ ] **TR-12 résolu** : conversion Devis→Resa→Invoice émise atomique en 1 TX
- [ ] **TR-5 résolu** : `ReservationCancelService` orchestre stock + deposit + credit_note + outbox
- [ ] **F675 résolu** : `Deposit.amount_cents` immutable post-paid via trigger DB
- [ ] **Q14=C livré** : `DepositPolicyService.resolve` opérationnel
- [ ] Test rollback : stock insuffisant → 0 entité créée, Devis reste 'pending'
- [ ] Test atomicité Invoice : émise immédiatement, immutable via trigger
- [ ] Test cancel cascade : J-30 refund full, J-2 retain, Invoice → CreditNote
- [ ] Outbox event `DevisConverted` + `ReservationCancelled` publiés dans même TX

---

**Fin du document — 13-sprint-B3.S4.md**
