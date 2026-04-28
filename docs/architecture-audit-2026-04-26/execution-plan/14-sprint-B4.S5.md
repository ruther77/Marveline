# Sprint B4.S5 — PII chiffrement complet + scope read_pii + audit_action delete

> **STATUT** : ⏳ À démarrer après B4.S4
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev2
> **BLOQUE** : B4.S6 (CSV bulk respecte PII), B6.S2 (audit refondu sur PII changes)
> **DÉPEND DE** : B1.S3 (KMS + EncryptedField)
> **OBJECTIF** : Livrer le chiffrement PII complet (TR-26, Q24/Q28=A) — pas seulement `notes` (effet placebo si limité), mais aussi `phone`, `address`, `first_name`, `last_name`, `contact_name`, `description`. Scope séparé `customers:read_pii`. Décorateur `@audit_action` sur tous les `delete_*` (TR-36). Vocabulaire `condition` unifié (TR-37 — déjà fait B4.S3.T6, vérifier cohérence).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B4.S5.T1** | TR-26/Q28=A — `EncryptedField` sur Customer.{notes, phone, address, first_name, last_name} | P0 | 2 j | T2, T3 |
| **B4.S5.T2** | Q28=A — `EncryptedField` sur Supplier.{notes, contact_name}, EventIncident.description, Evenement.notes, MovementItem.condition_notes, StockItem.notes | P0 | 1.5 j | aucun |
| **B4.S5.T3** | Scope `customers:read_pii` séparé + filtre dans schemas Read selon présence scope | P0 | 1 j | aucun |
| **B4.S5.T4** | Migration Celery `migrate_pii_encryption_task` chiffre rows existantes (batch 1000) | P0 | 1 j | aucun |
| **B4.S5.T5** | TR-36 — Décorateur `@audit_action(op='delete')` sur 5 endpoints delete | P1 | 1 j | aucun |
| **B4.S5.T6** | Schemas Pydantic stricts : champs PII requis seulement avec scope, sinon masqués | P1 | 0.5 j | aucun |

**Total effort** : 7 jours-homme.

---

# Story B4.S5.T1 — `EncryptedField` Customer PII complet (TR-26/Q28=A)

## Contexte

**Friction** : TR-26 (cf. `architecture-cible.md §4.2.7`)
**Sévérité** : P0 — RGPD Article 32 : un user `customers:read` voit allergies, anniversaires, références familiales en clair dans `notes`. PII étendue : phone, address, prénom = data sensibles.
**Code source** : `app/models/customer.py`

### Description

Étendre `EncryptedField(KMSContext)` à 5 colonnes Customer (vs juste `notes` actuellement) :
- `notes` (déjà ciblé)
- `phone` (vague 5 — V5-P0-01)
- `address_line1`, `address_line2`, `postal_code` (vague 5)
- `first_name`, `last_name` (V5-P0-01 cont.)

**Note** : seuls `notes` et `phone` étaient ciblés en Phase 3 initial. Vague 5 a identifié l'effet **placebo** si limité à `notes`. Q24/Q28=A étend correctement.

## Solution

### Modèle

```python
# app/models/customer.py
from app.core.crypto import EncryptedField, KMSContext


class Customer(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    # Identité PII (chiffrée)
    first_name: Mapped[str] = mapped_column(EncryptedField(KMSContext("customer:first_name"), Text))
    last_name: Mapped[str] = mapped_column(EncryptedField(KMSContext("customer:last_name"), Text))
    email: Mapped[str]  # NON chiffré (clé login + lookup)
    phone: Mapped[str | None] = mapped_column(EncryptedField(KMSContext("customer:phone"), Text), nullable=True)

    # Adresse (chiffrée)
    address_line1: Mapped[str | None] = mapped_column(EncryptedField(KMSContext("customer:address"), Text), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(EncryptedField(KMSContext("customer:address"), Text), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(EncryptedField(KMSContext("customer:address"), Text), nullable=True)
    city: Mapped[str | None]  # NON chiffré (statistique pays/ville-niveau OK)
    country: Mapped[str | None]  # NON chiffré

    # Notes (chiffrée)
    notes: Mapped[str | None] = mapped_column(EncryptedField(KMSContext("customer:notes"), Text), nullable=True)

    # Métadonnées non sensibles
    requires_deposit: Mapped[bool] = mapped_column(default=True)
    # ...
```

### Lookup email (non chiffré)

```python
# Email reste non chiffré pour lookup login + RFM segmentation
# Compromis : email clear text mais hashed pour audit/log
```

### Test

```python
async def test_customer_pii_encrypted_at_rest(db, tenant):
    customer = Customer(
        tenant_id=tenant.id, first_name="Jean", last_name="Dupont",
        email="jean@example.com", phone="0612345678",
        address_line1="42 rue de la Paix", postal_code="75002",
    )
    db.add(customer); await db.commit()
    
    # Lecture raw SQL → chiffré
    raw = await db.execute(text("""
        SELECT first_name, phone, address_line1 FROM customers WHERE id = :id
    """), {"id": str(customer.id)})
    fn, phone, addr = raw.first()
    assert "Jean" not in str(fn)
    assert "0612345678" not in str(phone)
    assert "rue de la Paix" not in str(addr)

async def test_customer_email_not_encrypted(db, tenant):
    customer = Customer(tenant_id=tenant.id, email="jean@example.com", ...)
    db.add(customer); await db.commit()
    raw = await db.execute(text("SELECT email FROM customers WHERE id = :id"), {"id": str(customer.id)})
    assert raw.scalar() == "jean@example.com"  # clear pour lookup
```

## DoD

- [ ] 8 colonnes Customer chiffrées via `EncryptedField`
- [ ] `email`, `city`, `country` non chiffrés (raison documentée)
- [ ] Test : SELECT raw → données chiffrées illisibles
- [ ] ORM accessor `customer.first_name` retourne clear text (déchiffrage transparent)

---

# Story B4.S5.T2 — PII chiffrement étendu (Supplier, EventIncident, Evenement, MovementItem, StockItem)

## Contexte

**Décision** : Q28=A — chiffrement PII obligatoire sur 7 modèles
**Sévérité** : P0 — fournisseur contact_name lisible par tout user `suppliers:read`

### Description

Cibles :
- `Supplier.notes`, `Supplier.contact_name`
- `EventIncident.description`
- `Evenement.notes`
- `MovementItem.condition_notes`
- `StockItem.notes`

## Solution

```python
# app/models/supplier.py
class Supplier(Base):
    notes: Mapped[str | None] = mapped_column(EncryptedField(KMSContext("supplier:notes"), Text), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(EncryptedField(KMSContext("supplier:contact_name"), Text), nullable=True)

# app/models/event_incident.py
class EventIncident(Base):
    description: Mapped[str] = mapped_column(EncryptedField(KMSContext("incident:description"), Text))

# Idem evenement, movement_item, stock_item
```

## DoD

- [ ] 6 colonnes additionnelles chiffrées
- [ ] Test : SELECT raw chiffré sur chaque table
- [ ] Test : ORM accessor déchiffrage transparent

---

# Story B4.S5.T3 — Scope `customers:read_pii` séparé

## Contexte

**Décision** : Q28=A — scope séparé pour exposer PII en clair côté API

### Description

- `customers:read` : voir Customer mais avec PII masquée (`first_name="***"`)
- `customers:read_pii` : voir Customer avec PII en clair

## Solution

```python
# app/constants/security.py
class Scope(str, Enum):
    CUSTOMERS_READ = "customers:read"
    CUSTOMERS_READ_PII = "customers:read_pii"  # NEW
    # ...

# app/schemas/customer.py
class CustomerRead(BaseSchema):
    id: UUID
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None
    address_line1: str | None

# app/api/v1/endpoints/customers.py
@router.get("/customers/{id}")
async def get_customer(
    id: UUID,
    user: User = Depends(require_scope(Scope.CUSTOMERS_READ)),
    has_pii: bool = Depends(check_scope(Scope.CUSTOMERS_READ_PII, optional=True)),
):
    customer = await service.get(id, user.tenant_id)
    if not has_pii:
        return CustomerRead(
            id=customer.id,
            first_name="***",
            last_name="***",
            email=customer.email,  # email reste visible (key login)
            phone="*** *** ***",
            address_line1=None,
        )
    return CustomerRead.from_orm(customer)
```

### Tests

```python
async def test_customer_pii_masked_without_scope(client_no_pii, customer):
    response = await client_no_pii.get(f"/api/v1/customers/{customer.id}")
    assert response.json()["first_name"] == "***"
    assert response.json()["phone"] == "*** *** ***"
    assert response.json()["email"] == customer.email  # email visible

async def test_customer_pii_clear_with_scope(client_with_pii, customer):
    response = await client_with_pii.get(f"/api/v1/customers/{customer.id}")
    assert response.json()["first_name"] != "***"
```

## DoD

- [ ] Scope `customers:read_pii` ajouté
- [ ] Endpoint masque sans scope, expose avec scope
- [ ] Email reste visible avec ou sans scope (login key)
- [ ] Test : sans scope → masqué ; avec scope → clair

---

# Story B4.S5.T4 — Migration Celery `migrate_pii_encryption_task`

## Contexte

Migration data : chiffrer les rows existantes (pré-deploy ce sprint, customers ont PII en clair).

### Description

Celery task one-shot qui boucle batch 1000 → re-écrit via SQLAlchemy ORM (déclenche `EncryptedField`).

## Solution

```python
# app/workers/tasks/migrate_pii_encryption.py
@shared_task(name="migrate_pii_encryption", bind=True)
def migrate_pii_encryption_task(self, model_name: str, batch_size: int = 1000):
    """One-shot : re-écrit chaque row via ORM pour déclencher EncryptedField."""
    async def _run():
        Model = MODELS_REGISTRY[model_name]  # Customer, Supplier, etc.
        async with AsyncSessionLocal() as db:
            offset = 0
            total_migrated = 0
            while True:
                rows = await db.scalars(
                    select(Model).order_by(Model.id).limit(batch_size).offset(offset)
                )
                rows = rows.all()
                if not rows:
                    break
                # Touch chaque champ chiffré → ORM marque dirty → re-write via EncryptedField
                for row in rows:
                    if hasattr(row, "first_name") and row.first_name:
                        row.first_name = row.first_name  # trigger re-encrypt
                    if hasattr(row, "phone") and row.phone:
                        row.phone = row.phone
                    # ... etc
                await db.commit()
                total_migrated += len(rows)
                offset += batch_size
                logger.info("pii_migration_progress", model=model_name, migrated=total_migrated)
            return total_migrated
    return asyncio.run(_run())
```

### Pré-deploy runbook

```bash
# Étape 1 : DB backup
pg_dump prod_db > backup_pre_pii.sql

# Étape 2 : déployer code avec EncryptedField (mais laisse data clear text)
# Lecture transparente : EncryptedField détecte clear text et passe through

# Étape 3 : run migration en background
celery -A app call migrate_pii_encryption Customer 1000
celery -A app call migrate_pii_encryption Supplier 1000
# ... etc

# Étape 4 : audit post-migration
SELECT COUNT(*) FROM customers WHERE first_name NOT LIKE '\\\\x%';  -- clear text restant
```

## DoD

- [ ] Task `migrate_pii_encryption` Celery
- [ ] Batch 1000 + commit par batch
- [ ] Logs progress
- [ ] Runbook pré-deploy documenté
- [ ] Test : 100 rows clear → 100 rows chiffrées après task

---

# Story B4.S5.T5 — `@audit_action` sur `delete_*` (TR-36)

## Contexte

**Friction** : TR-36 (cf. `architecture-cible.md §5.1`)
**Sévérité** : P1 — pattern récurrent : aucune action destructive tracée

### Description

Cible : décorateur `@audit_action(op='delete')` sur :
- `delete_customer`, `delete_supplier`, `delete_product`, `delete_bundle`, `delete_category`

## Solution

```python
# app/services/customer.py
class CustomerService:
    @audit_action(entity_type="Customer", action_template="customer.{op}")
    async def delete(self, customer_id: UUID, actor_id: UUID, tenant_id: int) -> None:
        # Soft delete
        customer = await self.db.get(Customer, customer_id)
        customer.is_active = False
        customer.deleted_at = datetime.now(UTC)
```

## DoD

- [ ] 5 méthodes delete décorées
- [ ] Test : `delete_customer` → AuditLog `action='customer.delete'` créé
- [ ] Test : delete sans actor_id → ValueError (audit obligatoire)

---

# Story B4.S5.T6 — Schemas stricts PII selon scope

## Contexte

Pattern Pydantic : 2 schemas (avec/sans PII) selon scope.

## Solution

```python
# app/schemas/customer.py
class CustomerReadMinimal(BaseSchema):
    """Sans scope read_pii — PII masquée."""
    id: UUID
    email: EmailStr
    city: str | None  # ville visible (statistique OK)
    country: str | None
    first_name_masked: str = "***"
    phone_masked: str = "***"

class CustomerReadFull(CustomerReadMinimal):
    """Avec scope read_pii — PII clear."""
    first_name: str
    last_name: str
    phone: str | None
    address_line1: str | None
    address_line2: str | None
    postal_code: str | None
    notes: str | None
```

```python
# Endpoint switch selon scope
async def get_customer(...):
    customer = await service.get(...)
    if has_pii:
        return CustomerReadFull.from_orm(customer)
    return CustomerReadMinimal(
        id=customer.id, email=customer.email, city=customer.city, country=customer.country,
    )
```

## DoD

- [ ] 2 schemas Pydantic distincts
- [ ] Endpoint sélectionne selon scope
- [ ] Test : OpenAPI doc montre 2 réponses possibles
- [ ] Test : champ PII absent du JSON sans scope (pas même `null`)

---

## Critères de succès Sprint B4.S5

- [ ] **TR-26/Q28=A complet** : 14 colonnes chiffrées (Customer + Supplier + EventIncident + Evenement + MovementItem + StockItem)
- [ ] **Pas de placebo** : `first_name`, `last_name`, `phone`, `address` chiffrés (vs juste `notes`)
- [ ] Scope `customers:read_pii` séparé + masking sans scope
- [ ] Migration Celery rows existantes
- [ ] **TR-36 résolu** : `@audit_action` sur 5 deletes
- [ ] Schemas Pydantic stricts (2 variantes selon scope)
- [ ] Test E2E : user `customers:read` voit `first_name='***'` ; `customers:read_pii` voit clair
- [ ] Test : SELECT raw SQL → 14 colonnes chiffrées illisibles

---

**Fin du document — 14-sprint-B4.S5.md**
