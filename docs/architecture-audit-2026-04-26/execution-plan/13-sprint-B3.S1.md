# Sprint B3.S1 — Hotfixes ledger

> **STATUT** : ⏳ À démarrer après Bloc 2 complet
> **DURÉE MAX** : 1.5 semaines
> **OWNER** : Dev1 (lead Bloc 3 Money)
> **BLOQUE** : B3.S2 (FSM helper) → tout B3
> **DÉPEND DE** : Bloc 1 (RLS, KMS, Outbox) + Bloc 2 (auth + Account) complets
> **OBJECTIF** : Corriger les frictions Money qui ne sont pas P0 prod (déjà dans Sprint 1) mais bloquent la consolidation Bloc 3 — séquences PostgreSQL, Invoice immutable check, ApiKey legacy charges drop, F17 compteurs Redis LRU.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B3.S1.T1** | F17 compteurs Redis LRU → CREATE SEQUENCE PostgreSQL | P1 | 1 j | aucun |
| **B3.S1.T2** | Drop endpoint legacy `POST /invoices/{id}/charges` (TR-6) | P1 | 0.5 j | B3.S2 immutable trigger |
| **B3.S1.T3** | Drop modèles dupliqués `app/models/finance/*` (TR-8) | P1 | 1 j | aucun |
| **B3.S1.T4** | Reference UNIQUE per-tenant (TR-9) — RES-2026-00001 ne collisionne plus cross-tenant | P0 | 0.5 j | aucun |
| **B3.S1.T5** | Invoice immutable check service-level (préparation B3.S2 trigger DB) | P1 | 0.5 j | B3.S2 |

**Total effort** : 3.5 jours-homme.

---

# Story B3.S1.T1 — F17 séquences PostgreSQL pour numéros documents

## Contexte

**Friction** : F17 (vague 1 P1-02)
**Sévérité** : P1 — collisions ID numériques possibles sous éviction LRU Redis
**Code source** : compteurs Redis pour `reservation_number`, `invoice_number`, `devis_number`

### Description

Aujourd'hui : `redis_general.incr("counter:reservation:{tenant_id}")` avec eviction `allkeys-lru`. Sous pression mémoire Redis, le compteur peut être évincé → reset à 0 → collision `RES-2026-00001` déjà émise.

## Solution

Migration vers `CREATE SEQUENCE` PostgreSQL per-tenant :

```sql
-- alembic/versions/e1f2a3b4c5e2_create_document_sequences.py
-- Une séquence per-tenant per-document-type
-- Note : pour ~50 tenants × 4 types (reservation/devis/invoice/vente) = ~200 sequences
-- Acceptable en PostgreSQL (limite ~10k+ sequences/db sans impact perf)

DO $$
DECLARE
    t RECORD;
BEGIN
    FOR t IN SELECT id FROM tenants LOOP
        EXECUTE format('CREATE SEQUENCE IF NOT EXISTS seq_reservation_%s START 1', t.id);
        EXECUTE format('CREATE SEQUENCE IF NOT EXISTS seq_devis_%s START 1', t.id);
        EXECUTE format('CREATE SEQUENCE IF NOT EXISTS seq_invoice_%s START 1', t.id);
        EXECUTE format('CREATE SEQUENCE IF NOT EXISTS seq_vente_%s START 1', t.id);
    END LOOP;
END $$;
```

```python
# app/services/document_numbering.py (NEW)
class DocumentNumberingService:
    async def next_reservation_number(self, db: AsyncSession, tenant_id: int) -> str:
        """F17 fix : SEQUENCE PostgreSQL atomique (vs Redis LRU evictable)."""
        result = await db.execute(
            text(f"SELECT nextval('seq_reservation_{tenant_id}')")
        )
        seq_value = result.scalar()
        year = datetime.now(UTC).year
        return f"RES-{year}-{seq_value:05d}"
```

Hook au provisioning tenant (B2.S2 update) :
```python
# Dans TenantService.provision() — créer les 4 sequences pour le nouveau tenant
async with db.begin():
    # ... création tenant + brand + settings + account
    await db.execute(text(f"CREATE SEQUENCE seq_reservation_{tenant.id} START 1"))
    await db.execute(text(f"CREATE SEQUENCE seq_devis_{tenant.id} START 1"))
    await db.execute(text(f"CREATE SEQUENCE seq_invoice_{tenant.id} START 1"))
    await db.execute(text(f"CREATE SEQUENCE seq_vente_{tenant.id} START 1"))
```

## DoD

- [ ] Migration crée sequences pour tenants existants
- [ ] `TenantService.provision()` crée sequences pour nouveaux tenants
- [ ] Service `DocumentNumberingService` opérationnel
- [ ] Drop compteurs Redis legacy
- [ ] Test : 1000 réservations concurrentes → 1000 numéros uniques (sans collision)

---

# Story B3.S1.T2 — Drop endpoint legacy `POST /invoices/{id}/charges`

## Contexte

**Friction** : TR-6 (cf. `architecture-cible.md §3.1`) — `add_charge` mute facture émise (illégal fiscalement France)

### Description

Endpoint actuel `POST /api/v1/invoices/{id}/charges` permet d'ajouter une ligne à une facture déjà émise. **Article 289 CGI** : facture émise = immutable. Toute modification = avoir + nouvelle facture.

## Solution

```python
# app/api/v1/endpoints/invoices.py (refacto)
# Drop endpoint POST /invoices/{id}/charges
# Remplacé par : POST /invoices/{id}/credit-note (livré B3.S4)

# Migration legacy : si appels actuels en prod, retourner 410 Gone avec message d'orientation
@router.post("/invoices/{id}/charges", deprecated=True)
async def add_charge_deprecated(...):
    raise HTTPException(
        status_code=410,
        detail={
            "error": "ENDPOINT_DEPRECATED",
            "message": "Cet endpoint a été supprimé. Pour rectifier une facture émise, utilisez POST /invoices/{id}/credit-note (avoir).",
            "migration_url": "/docs/changelog#b3s1",
        }
    )
```

## DoD

- [ ] Endpoint retourne 410 + message migration
- [ ] OpenAPI `52-api-contracts.openapi.yml` reflète déprécation (déjà fait Phase 3)
- [ ] Communication clients : email "rectification facture = passer par avoir"

---

# Story B3.S1.T3 — Drop modèles dupliqués `app/models/finance/*`

## Contexte

**Friction** : TR-8 (cf. `architecture-cible.md §3.1`) — 2 sources de vérité Invoice (`app/models/invoice.py` + `app/models/finance/invoice.py`)

### Description

```bash
# État actuel
app/models/invoice.py           # Modèle canonique (Bloc 3)
app/models/finance/invoice.py   # Doublon legacy — risque confusion ORM
app/models/finance/payment.py   # Doublon
```

Le doublon `finance/` date d'une refonte avortée. Drop pour éliminer toute ambiguïté.

## Solution

```python
# tools/migrate_finance_imports.py (script one-shot)
# 1. grep tous imports `from app.models.finance import ...`
# 2. Remplacer par `from app.models import ...` (canonique)
# 3. Drop dossier `app/models/finance/`

# Vérification : aucun import résiduel
# grep -rn "from app.models.finance" app/ → 0
```

## DoD

- [ ] Imports migrés (0 résultat `grep from app.models.finance`)
- [ ] Dossier `app/models/finance/` supprimé
- [ ] Tests E2E Invoice/Payment passent

---

# Story B3.S1.T4 — Reference UNIQUE per-tenant (TR-9)

## Contexte

**Friction** : TR-9 — `reservation.reference` UNIQUE global cross-tenant. `RES-2026-00001` du tenant Marveline bloque le même numéro chez Splendid.

### Description

Migration UNIQUE de `(reference)` global vers `(tenant_id, reference)`.

## Solution

```python
# alembic/versions/e1f2a3b4c5e3_reference_unique_per_tenant.py
def upgrade() -> None:
    # Drop UNIQUE global
    op.drop_constraint("uq_reservations_reference", "reservations", type_="unique")
    # Recreate UNIQUE per-tenant
    op.create_unique_constraint(
        "uq_reservations_tenant_reference", "reservations", ["tenant_id", "reference"]
    )
    # Idem pour devis, invoices, ventes
    for table in ("devis", "invoices", "ventes"):
        op.drop_constraint(f"uq_{table}_reference", table, type_="unique")
        op.create_unique_constraint(
            f"uq_{table}_tenant_reference", table, ["tenant_id", "reference"]
        )
```

## DoD

- [ ] Migration appliquée sur 4 tables
- [ ] Test : créer RES-2026-00001 sur tenant A puis tenant B → 2 succès (avant : 2nd échouait)

---

# Story B3.S1.T5 — Invoice immutable check service-level

## Contexte

**Préparation** B3.S2 (trigger DB immutable). Service-level guard livré dès B3.S1 pour fail-fast côté API.

### Description

```python
# app/services/invoice.py
class InvoiceService:
    async def update(self, db, invoice_id: int, **changes):
        invoice = await db.get(Invoice, invoice_id)
        if invoice.status == InvoiceStatus.EMITTED:
            # Préparation B3.S2 — service-level check, sera doublé par trigger DB
            forbidden_fields = {"total_ht_cents", "total_ttc_cents", "total_tva_cents", "lines"}
            if any(field in changes for field in forbidden_fields):
                raise InvoiceImmutableError(
                    f"Facture émise : champs immutables modifiés ({forbidden_fields & changes.keys()}). "
                    "Utiliser POST /invoices/{id}/credit-note pour rectification."
                )
        # Apply changes safe (status, paid_at, etc.)
        for k, v in changes.items():
            setattr(invoice, k, v)
        await db.flush()
```

## DoD

- [ ] Guard service-level opérationnel
- [ ] Test : tenter `update_invoice(total_ht_cents=999)` sur facture EMITTED → InvoiceImmutableError

---

## Critères de succès Sprint B3.S1

- [ ] F17 séquences PostgreSQL en place (collision impossible)
- [ ] TR-6 endpoint legacy /charges droppé (410 Gone)
- [ ] TR-8 modèles `app/models/finance/*` supprimés
- [ ] TR-9 reference UNIQUE per-tenant
- [ ] Invoice immutable guard service-level (préparation B3.S2)

---

**Fin du document — 13-sprint-B3.S1.md**
