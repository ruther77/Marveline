# Sprint B3.S2 — FSM helper + DB triggers immutability

> **STATUT** : ⏳ À démarrer après B3.S1
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev1
> **BLOQUE** : B3.S3 (PricingEngine), B3.S4 (Conversion atomique), B5 (FSM resto/épicerie)
> **DÉPEND DE** : B3.S1 (Invoice immutable service-level)
> **OBJECTIF** : Livrer le pattern FSM helper class avec matrices documentées (Q12 Devis/Reservation/Invoice/Vente/Deposit) + 7 triggers DB immutables (Q1 ledgers + audit + stock_movements). Garantie cross-cutting : transitions illégales = 409, mutation ledger = exception SQL.

## Vue d'ensemble

| Story | Description | Estimation | Bloque |
|---|---|---|---|
| **B3.S2.T1** | `app/services/fsm.py` helper class + matrix declarations | 1.5 j | T2 |
| **B3.S2.T2** | DDL `fsm_transitions` table audit + trigger logging | 1 j | T3 |
| **B3.S2.T3** | 7 triggers DB immutability ledgers (Q1) | 1.5 j | aucun |
| **B3.S2.T4** | Application FSM helper aux entités Devis/Reservation/Invoice/Deposit/Vente | 2 j | B3.S3-S4 |

**Total effort** : 6 jours-homme.

---

# Story B3.S2.T1 — FSM helper class

## Contexte

**Décision** : Q12=A — FSM matrices documentées avec `assert_transition` (architecture-cible §3.2.5)

### Description

Pattern unique pour toutes les FSM Bloc 3-5 :
- Matrice des transitions valides codée en classe
- Méthode `assert_transition(from_state, to_state)` lève `InvalidTransition` si pas dans la matrice
- Logging automatique dans `fsm_transitions` table (audit)
- Reusable Bloc 5 (CommandeRestaurantFSM, EpicerieVenteFSM, etc.)

## Solution

```python
# app/services/fsm.py (NEW)
from dataclasses import dataclass
from typing import ClassVar


class InvalidTransition(Exception):
    pass


@dataclass(frozen=True)
class FSMMatrix:
    """Définit la matrice des transitions valides."""
    entity_type: str
    transitions: set[tuple[str, str]]  # {(from_state, to_state)}
    initial_states: set[str]
    terminal_states: set[str]

    def is_valid(self, from_state: str, to_state: str) -> bool:
        return (from_state, to_state) in self.transitions


# Matrices documentées
DEVIS_FSM = FSMMatrix(
    entity_type="devis",
    transitions={
        ("draft", "valid"),
        ("valid", "converted"),  # Q12=A — vers Reservation atomique
        ("valid", "cancelled"),
        ("draft", "cancelled"),
        ("valid", "expired"),
    },
    initial_states={"draft"},
    terminal_states={"converted", "cancelled", "expired"},
)

RESERVATION_FSM = FSMMatrix(
    entity_type="reservation",
    transitions={
        ("draft", "confirmed"),
        ("confirmed", "delivered"),
        ("delivered", "returned"),
        ("returned", "closed"),
        ("confirmed", "cancelled"),
        ("delivered", "cancelled_with_recovery"),  # cas exceptionnel
    },
    initial_states={"draft"},
    terminal_states={"closed", "cancelled", "cancelled_with_recovery"},
)

INVOICE_FSM = FSMMatrix(
    entity_type="invoice",
    transitions={
        # Q12=A — émission directe à conversion (pas de draft → emitted)
        ("emitted", "paid"),
        ("emitted", "cancelled"),  # via credit_note
    },
    initial_states={"emitted"},  # Création directe en emitted
    terminal_states={"paid", "cancelled"},
)

DEPOSIT_FSM = FSMMatrix(
    entity_type="deposit",
    transitions={
        ("none", "held"),
        ("held", "released"),
        ("held", "retained"),
    },
    initial_states={"none"},
    terminal_states={"released", "retained"},
)

VENTE_FSM = FSMMatrix(
    entity_type="vente",
    transitions={
        ("draft", "validated"),
        ("validated", "paid"),
        ("paid", "refunded"),
        ("draft", "cancelled"),
        ("validated", "cancelled"),
    },
    initial_states={"draft"},
    terminal_states={"paid", "refunded", "cancelled"},
)


# Registry
FSM_MATRICES = {
    "devis": DEVIS_FSM,
    "reservation": RESERVATION_FSM,
    "invoice": INVOICE_FSM,
    "deposit": DEPOSIT_FSM,
    "vente": VENTE_FSM,
}


# Helper API
class FSMHelper:
    @staticmethod
    async def assert_transition(
        db: AsyncSession,
        entity_type: str,
        entity_id: int,
        from_state: str,
        to_state: str,
        actor_id: int,
        reason: str = "",
    ) -> None:
        """Vérifie + logge la transition.

        Raises:
            InvalidTransition: si (from_state, to_state) pas dans la matrice
        """
        matrix = FSM_MATRICES.get(entity_type)
        if matrix is None:
            raise ValueError(f"Unknown FSM entity_type: {entity_type}")

        if not matrix.is_valid(from_state, to_state):
            raise InvalidTransition(
                f"Invalid transition for {entity_type}: {from_state} → {to_state}. "
                f"Valid transitions from {from_state}: "
                f"{[to for f, to in matrix.transitions if f == from_state]}"
            )

        # Audit transition
        db.add(FSMTransition(
            entity_type=entity_type,
            entity_id=entity_id,
            from_state=from_state,
            to_state=to_state,
            actor_account_id=actor_id,
            reason=reason,
            transitioned_at=datetime.now(UTC),
        ))
        await db.flush()
```

## DoD

- [ ] `app/services/fsm.py` opérationnel avec 5 matrices (devis, resa, invoice, deposit, vente)
- [ ] CI invariant `check_fsm_transitions_present.py` (54 §14) vert
- [ ] Documentation `docs/fsm-matrices.md` avec diagrammes

---

# Story B3.S2.T2 — Table `fsm_transitions` audit

## Contexte

**Décision** : Audit traçable de toutes les transitions FSM (forensics + debug)

### Description

Table append-only qui log chaque transition autorisée. Lue par INV-4 (53 §8.4) pour vérifier que toutes les transitions DB sont dans la matrice documentée.

## Solution

```sql
-- Cf. 50-sql-schema.md (à compléter dans cette story)
CREATE TABLE fsm_transitions (
    id BIGSERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id BIGINT NOT NULL,
    from_state VARCHAR(50) NOT NULL,
    to_state VARCHAR(50) NOT NULL,
    actor_account_id BIGINT REFERENCES accounts(id),
    actor_api_key_id BIGINT REFERENCES api_keys(id),
    actor_type VARCHAR(20) NOT NULL DEFAULT 'account',
    reason VARCHAR(500),
    transitioned_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fsm_transitions_entity ON fsm_transitions (entity_type, entity_id);
CREATE INDEX idx_fsm_transitions_date ON fsm_transitions (transitioned_at DESC);

-- Append-only : pas d'UPDATE/DELETE
CREATE OR REPLACE FUNCTION trg_fsm_transitions_immutable_fn() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'fsm_transitions is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_fsm_transitions_immutable
    BEFORE UPDATE OR DELETE ON fsm_transitions
    FOR EACH ROW
    EXECUTE FUNCTION trg_fsm_transitions_immutable_fn();
```

## DoD

- [ ] Migration appliquée
- [ ] INV-4 (53 §8.4) vert : toutes les transitions DB sont dans matrices

---

# Story B3.S2.T3 — 7 triggers DB immutability ledgers (Q1)

## Contexte

**Décision** : Q1 — 7 tables append-only (cf. INV-3 53 §8.3 vague 1+2 corrections)
**Frictions** : TR-7 (immutabilité code-only sans trigger DB → admin psql peut altérer points_ledger sans trace)

### Description

7 triggers `BEFORE UPDATE OR DELETE` qui lèvent exception PL/pgSQL. Convention nom : `trg_{table}_immutable`.

## Solution

```sql
-- Pattern reproductible pour 7 tables
CREATE OR REPLACE FUNCTION trg_immutable_fn() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% is immutable post-creation. Cf. Bloc 3 Q1.', TG_TABLE_NAME
        USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

-- Application aux 7 tables
CREATE TRIGGER trg_revenue_ledger_immutable
    BEFORE UPDATE OR DELETE ON revenue_ledger
    FOR EACH ROW EXECUTE FUNCTION trg_immutable_fn();

CREATE TRIGGER trg_payment_ledger_immutable
    BEFORE UPDATE OR DELETE ON payment_ledger
    FOR EACH ROW EXECUTE FUNCTION trg_immutable_fn();

CREATE TRIGGER trg_points_ledger_immutable
    BEFORE UPDATE OR DELETE ON points_ledger
    FOR EACH ROW EXECUTE FUNCTION trg_immutable_fn();

CREATE TRIGGER trg_audit_logs_immutable
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION trg_immutable_fn();

CREATE TRIGGER trg_inventory_movements_immutable
    BEFORE UPDATE OR DELETE ON inventory_movements
    FOR EACH ROW EXECUTE FUNCTION trg_immutable_fn();

CREATE TRIGGER trg_epicerie_stock_movements_immutable
    BEFORE UPDATE OR DELETE ON epicerie_stock_movements
    FOR EACH ROW EXECUTE FUNCTION trg_immutable_fn();

CREATE TRIGGER trg_mouvements_stock_restaurant_immutable
    BEFORE UPDATE OR DELETE ON mouvements_stock_restaurant
    FOR EACH ROW EXECUTE FUNCTION trg_immutable_fn();
```

**Note B3.S2.T3 vs Sprint B6.S2** : Le trigger sur `audit_logs` est posé ici (immutabilité simple). B6.S2 ajoute en plus le HMAC chain check via trigger BEFORE INSERT.

## DoD

- [ ] 7 triggers actifs en DB
- [ ] INV-3 (53 §8.3) vert sur les 7 tables
- [ ] CI invariant `check_ledger_immutable_triggers.py` (54 §9) vert
- [ ] Test : `UPDATE points_ledger SET ...` → `check_violation` exception

---

# Story B3.S2.T4 — Application FSM helper aux entités

## Contexte

**Sévérité** : P1 — refacto code utilisant les FSM

### Description

Migrer les services Devis/Reservation/Invoice/Deposit/Vente vers `FSMHelper.assert_transition()`.

## Solution

```python
# app/services/devis.py (refacto)
class DevisService:
    async def cancel(self, db, devis_id: int, actor_id: int, reason: str = ""):
        devis = await db.get(Devis, devis_id)

        # FSM guard avant toute mutation
        await FSMHelper.assert_transition(
            db=db,
            entity_type="devis",
            entity_id=devis_id,
            from_state=devis.status,
            to_state="cancelled",
            actor_id=actor_id,
            reason=reason,
        )

        devis.status = "cancelled"
        devis.cancelled_at = datetime.now(UTC)
        devis.cancelled_reason = reason
        await db.flush()


# Idem pour ReservationService, InvoiceService, DepositService, VenteService
```

## DoD

- [ ] 5 services migrés (Devis, Reservation, Invoice, Deposit, Vente)
- [ ] Tests E2E : transition illégale → 409 + audit `fsm_transitions` row absente
- [ ] Tests E2E : transition légale → state changé + audit row présente

## Risque

- Probabilité 3, impact 4 → score 12 HIGH

---

## Critères de succès Sprint B3.S2

- [ ] FSM helper class + 5 matrices documentées
- [ ] Table `fsm_transitions` append-only
- [ ] 7 triggers DB immutability actifs
- [ ] 5 services migrés vers FSMHelper.assert_transition
- [ ] INV-3, INV-4 verts (53 §8)
- [ ] B3.S3 + B3.S4 peuvent démarrer

---

**Fin du document — 13-sprint-B3.S2.md**
