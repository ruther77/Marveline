# Sprint B3.S6 — e-invoicing schema prep + duplicates legacy drop

> **STATUT** : ⏳ À démarrer après B3.S5
> **DURÉE MAX** : 1 semaine
> **OWNER** : Dev1
> **BLOQUE** : B3.S7 (Supplier+Vente fiscal — pas de dépendance forte mais cohabitation propre)
> **DÉPEND DE** : B3.S2 (Invoice immutable trigger), B3.S5 (EmailGateway prêt pour notifications PDP futures)
> **OBJECTIF** : Préparer le schema e-invoicing UE (France 2026 PDP, ChorusPro B2G, PEPPOL B2B) selon Q19=A — colonnes nullables + enum status + feature flag d'activation différée. Supprimer définitivement les modèles legacy `app/models/finance/*` avec script CI bloquant. Pas d'activation prod du e-invoicing dans ce sprint, juste la prep schéma.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B3.S6.T1** | Q19=A — Colonnes nullables Invoice (`peppol_id`, `chorus_pro_id`, `electronic_invoice_id`, `e_invoice_status`) | P1 | 0.5 j | T2, T3 |
| **B3.S6.T2** | Feature flag `einvoicing_enabled` per-tenant + `einvoicing_mode` (peppol/chorus_pro/none) | P1 | 0.5 j | T3 |
| **B3.S6.T3** | Service `EInvoicingDispatcher` Protocol + stub `NoOpDispatcher` (production B3.S6+1) | P1 | 0.5 j | aucun |
| **B3.S6.T4** | Drop définitif `app/models/finance/*` + script CI bloquant `check_no_finance_legacy.py` | P0 | 1 j | aucun |
| **B3.S6.T5** | Validation schéma : tests round-trip Invoice → JSON UBL 2.1 (PEPPOL) sur fixture | P1 | 1 j | aucun |

**Total effort** : 3.5 jours-homme.

---

# Story B3.S6.T1 — Colonnes e-invoicing nullables sur `Invoice`

## Contexte

**Décision** : Q19=A (verrouillée 2026-04-27) — prep schéma maintenant, activation différée
**Sévérité** : P1 — blocage commercial 2026-09-01 (gros B2B obligation France) si schéma pas prêt
**Code source** : `app/models/invoice.py`

### Description

France 2026 e-invoicing :
- **2026-09-01** : obligation pour gros B2B (CA > 250M€)
- **2027-09-01** : extension PME

Bien que Marveline et Splendid soient en deçà du seuil 2026, la prep schéma maintenant évite une migration urgente plus tard. PEPPOL pour B2B UE, ChorusPro pour B2G France.

## Solution

### Migration

```python
# alembic/versions/e3f4a5b6c7df_invoice_einvoicing_columns.py
import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    # Enum e_invoice_status
    op.execute(text("""
        CREATE TYPE e_invoice_status AS ENUM (
            'not_emitted',
            'submitted',
            'accepted',
            'rejected'
        )
    """))
    # Colonnes nullables
    op.add_column("invoices", sa.Column("electronic_invoice_id", sa.String(255), nullable=True))
    op.add_column("invoices", sa.Column("peppol_id", sa.String(255), nullable=True))
    op.add_column("invoices", sa.Column("chorus_pro_id", sa.String(255), nullable=True))
    op.add_column(
        "invoices",
        sa.Column(
            "e_invoice_status",
            postgresql.ENUM(name="e_invoice_status", create_type=False),
            nullable=True,  # NULL = facture pré-2026 ou tenant sans einvoicing
            server_default="not_emitted",
        ),
    )
    op.add_column("invoices", sa.Column("e_invoice_submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("e_invoice_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("e_invoice_rejection_reason", sa.Text, nullable=True))

    # Index pour requêtes audit / status
    op.create_index(
        "ix_invoices_einvoice_status_pending",
        "invoices",
        ["tenant_id", "e_invoice_status"],
        postgresql_where=sa.text("e_invoice_status = 'submitted'"),
    )

    # CHECK : si einvoicing_mode='peppol' alors peppol_id requis quand status accepted/rejected
    # Ce check sera conditionnel — Story B3.S6.T2 ajoute la dépendance Tenant


def downgrade() -> None:
    op.drop_index("ix_invoices_einvoice_status_pending")
    for col in (
        "e_invoice_rejection_reason",
        "e_invoice_accepted_at",
        "e_invoice_submitted_at",
        "e_invoice_status",
        "chorus_pro_id",
        "peppol_id",
        "electronic_invoice_id",
    ):
        op.drop_column("invoices", col)
    op.execute(text("DROP TYPE e_invoice_status"))
```

### Modèle

```python
# app/models/invoice.py
from enum import Enum

class EInvoiceStatus(str, Enum):
    NOT_EMITTED = "not_emitted"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Invoice(Base):
    # ... existing
    electronic_invoice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    peppol_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chorus_pro_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    e_invoice_status: Mapped[EInvoiceStatus | None] = mapped_column(
        SqlEnum(EInvoiceStatus, name="e_invoice_status"),
        nullable=True,
        default=EInvoiceStatus.NOT_EMITTED,
    )
    e_invoice_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    e_invoice_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    e_invoice_rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### Schemas Pydantic

```python
# app/schemas/invoice.py
class InvoiceRead(BaseSchema):
    id: UUID
    # ... existing
    e_invoice_status: EInvoiceStatus | None = None
    peppol_id: str | None = None
    chorus_pro_id: str | None = None
```

### Whitelist trigger immutable

**Important** : ces colonnes sont mutables après émission (status `submitted → accepted` via PDP callback). Le trigger DB `invoice_immutable` (B3.S2.T3) doit **whitelister** :
```sql
-- Mutations autorisées sur Invoice émise (callback PDP) :
-- e_invoice_status, e_invoice_submitted_at, e_invoice_accepted_at, e_invoice_rejection_reason,
-- electronic_invoice_id, peppol_id, chorus_pro_id
-- Mutations TOUJOURS interdites : total_*, lines, tva_*, reference, customer_id
```

```sql
CREATE OR REPLACE FUNCTION invoice_immutable_check()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = 'emitted' THEN
        IF NEW.total_ht_cents IS DISTINCT FROM OLD.total_ht_cents
           OR NEW.total_ttc_cents IS DISTINCT FROM OLD.total_ttc_cents
           OR NEW.total_tva_cents IS DISTINCT FROM OLD.total_tva_cents
           OR NEW.reference IS DISTINCT FROM OLD.reference
           OR NEW.customer_id IS DISTINCT FROM OLD.customer_id THEN
            RAISE EXCEPTION 'invoice_immutable: cannot modify totals/reference/customer on emitted invoice %', OLD.id;
        END IF;
    END IF;
    RETURN NEW;
END $$ LANGUAGE plpgsql;
```

### Tests

```python
async def test_invoice_einvoice_columns_default_not_emitted(db, tenant):
    invoice = Invoice(tenant_id=tenant.id, status="emitted", ...)
    db.add(invoice); await db.commit()
    assert invoice.e_invoice_status == EInvoiceStatus.NOT_EMITTED

async def test_invoice_immutable_totals_on_emitted_but_einvoice_status_mutable(db, invoice_emitted):
    """Trigger immutable : totals interdits, e_invoice_status autorisé."""
    with pytest.raises(IntegrityError, match="invoice_immutable"):
        await db.execute(
            update(Invoice).where(Invoice.id == invoice_emitted.id).values(total_ttc_cents=999)
        )
    # Mais e_invoice_status mutable
    await db.execute(
        update(Invoice).where(Invoice.id == invoice_emitted.id)
        .values(e_invoice_status=EInvoiceStatus.SUBMITTED, e_invoice_submitted_at=func.now())
    )  # OK
```

## DoD

- [ ] Migration créée : enum `e_invoice_status` + 7 colonnes nullables sur Invoice
- [ ] Index partiel `ix_invoices_einvoice_status_pending` actif
- [ ] Trigger immutable whitelist colonnes e-invoicing
- [ ] Test : modifier `total_ttc_cents` post-emit → IntegrityError ; modifier `e_invoice_status` post-emit → OK
- [ ] Schema Pydantic `InvoiceRead` expose les nouveaux champs

---

# Story B3.S6.T2 — Feature flag `einvoicing_enabled` per-tenant

## Contexte

**Décision** : Q19=A — activation différée via feature flag (cf. B6.S3 fail-safe)
**Sévérité** : P1 — un tenant ne doit pas envoyer e-invoice tant que pas configuré PDP

### Description

Cible :
- `Tenant.einvoicing_enabled: bool = False` (défaut OFF)
- `Tenant.einvoicing_mode: enum('none', 'peppol', 'chorus_pro') = 'none'`
- `Tenant.einvoicing_pdp_endpoint: str | None` (URL PDP du tenant)
- `Tenant.einvoicing_credentials_encrypted: bytes | None` (cred chiffrés KMS)

Quand `einvoicing_enabled=True`, le `EInvoicingDispatcher` (T3) prend le relai. Sinon, no-op.

## Solution

```python
# alembic/versions/e3f4a5b6c7e0_tenant_einvoicing_config.py
def upgrade() -> None:
    op.execute(text("""
        CREATE TYPE einvoicing_mode AS ENUM ('none', 'peppol', 'chorus_pro')
    """))
    op.add_column("tenants", sa.Column("einvoicing_enabled", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("tenants", sa.Column(
        "einvoicing_mode",
        postgresql.ENUM(name="einvoicing_mode", create_type=False),
        nullable=False,
        server_default="none",
    ))
    op.add_column("tenants", sa.Column("einvoicing_pdp_endpoint", sa.String(512), nullable=True))
    op.add_column("tenants", sa.Column("einvoicing_credentials_encrypted", sa.LargeBinary, nullable=True))
    # CHECK cohérence : mode != 'none' implique enabled = True
    op.create_check_constraint(
        "ck_tenants_einvoicing_consistency",
        "tenants",
        "(einvoicing_mode = 'none' OR einvoicing_enabled = true)",
    )
```

### Cohabitation avec FF Redis (B6.S3)

Le flag `einvoicing_enabled` est volontairement **per-tenant DB** (pas Redis FF) car :
1. Activation contractuelle (un tenant souscrit/résilie le service e-invoicing) — pas un toggle ops
2. Persistence forte requise (perte Redis ne doit jamais activer einvoicing par accident)
3. Cohérent avec Q19=A (activation différée propre, pas A/B test)

Le FF Redis B6.S3 reste pour rollout progressif features ops (ex: `dunning_v2_enabled`).

### Test

```python
async def test_tenant_default_einvoicing_off(db):
    tenant = Tenant(...)
    db.add(tenant); await db.commit()
    assert tenant.einvoicing_enabled is False
    assert tenant.einvoicing_mode == "none"

async def test_check_consistency_violations(db, tenant):
    """mode=peppol mais enabled=false → IntegrityError."""
    tenant.einvoicing_mode = "peppol"
    tenant.einvoicing_enabled = False
    with pytest.raises(IntegrityError, match="ck_tenants_einvoicing_consistency"):
        await db.commit()
```

## DoD

- [ ] Enum `einvoicing_mode` + 4 colonnes Tenant
- [ ] CHECK cohérence mode/enabled
- [ ] Credentials stockés via `EncryptedField` KMS (B1.S3)
- [ ] Test : tenant nouveau → einvoicing OFF par défaut
- [ ] Test : config incohérente → IntegrityError

---

# Story B3.S6.T3 — `EInvoicingDispatcher` Protocol + stub

## Contexte

Préparation B3.S6+1 (sprint hors plan, post-2026-04 phase 2 implémentation prod). Le dispatcher est le point d'entrée pour `peppol_send` / `chorus_send` qui sera implémenté quand on aura un partenaire PDP réel.

## Solution

```python
# app/services/einvoicing/dispatcher.py (NEW)
from typing import Protocol
from dataclasses import dataclass


@dataclass(frozen=True)
class DispatchResult:
    success: bool
    pdp_id: str | None  # ID retourné par la PDP
    submission_status: EInvoiceStatus
    error_code: str | None
    error_message: str | None


class EInvoicingDispatcher(Protocol):
    """Stub Protocol — implémentations PEPPOL/ChorusPro livrées en sprint post-B3.S6."""

    async def submit(self, invoice: Invoice, tenant: Tenant) -> DispatchResult: ...

    async def fetch_status(self, pdp_id: str, tenant: Tenant) -> DispatchResult: ...


# app/services/einvoicing/noop.py (NEW)
class NoOpDispatcher:
    """Default dispatcher pour tenants sans einvoicing activé.

    Plus tard, sera remplacé par PeppolDispatcher / ChorusProDispatcher selon
    `Tenant.einvoicing_mode`. Pour l'instant, juste log + status='not_emitted'.
    """

    async def submit(self, invoice: Invoice, tenant: Tenant) -> DispatchResult:
        if tenant.einvoicing_enabled:
            logger.warning(
                "einvoicing_enabled but no real dispatcher configured",
                tenant_id=tenant.id, invoice_id=invoice.id,
            )
        return DispatchResult(
            success=True,
            pdp_id=None,
            submission_status=EInvoiceStatus.NOT_EMITTED,
            error_code=None,
            error_message=None,
        )

    async def fetch_status(self, pdp_id, tenant):
        return DispatchResult(True, pdp_id, EInvoiceStatus.NOT_EMITTED, None, None)


# app/core/deps.py
async def get_einvoicing_dispatcher(tenant: Tenant = Depends(get_tenant)) -> EInvoicingDispatcher:
    """Sélection dispatcher selon mode tenant — pour l'instant tous → NoOp."""
    if not tenant.einvoicing_enabled:
        return NoOpDispatcher()
    if tenant.einvoicing_mode == "peppol":
        # return PeppolDispatcher(...)  # B3.S6+1
        return NoOpDispatcher()
    if tenant.einvoicing_mode == "chorus_pro":
        # return ChorusProDispatcher(...)  # B3.S6+1
        return NoOpDispatcher()
    return NoOpDispatcher()
```

### Hook dans InvoiceService

```python
# app/services/invoice.py
class InvoiceService:
    async def create_emitted_from_reservation(self, reservation, pricing_result, actor_id) -> Invoice:
        # ... logique existante (création + status='emitted')
        # Hook einvoicing — async non-bloquant via Outbox
        await self.db.execute(
            insert(OutboxEvent).values(
                event_type="InvoiceEmittedForEInvoicing",
                aggregate_id=invoice.id,
                tenant_id=tenant_id,
                payload={"invoice_id": str(invoice.id)},
            )
        )
        return invoice

# app/workers/outbox_handlers/einvoicing.py
async def handle_invoice_emitted_for_einvoicing(event: OutboxEvent, db: AsyncSession):
    invoice = await db.get(Invoice, event.aggregate_id)
    tenant = await db.get(Tenant, invoice.tenant_id)
    dispatcher = await get_einvoicing_dispatcher(tenant)
    result = await dispatcher.submit(invoice, tenant)
    if result.success and result.pdp_id:
        invoice.electronic_invoice_id = result.pdp_id
        invoice.e_invoice_status = result.submission_status
        invoice.e_invoice_submitted_at = datetime.now(UTC)
```

## DoD

- [ ] `EInvoicingDispatcher` Protocol + `NoOpDispatcher` stub livrés
- [ ] DI `get_einvoicing_dispatcher` switch sur `Tenant.einvoicing_mode`
- [ ] Outbox event `InvoiceEmittedForEInvoicing` publié à l'émission
- [ ] Handler Outbox appelle dispatcher (NoOp pour l'instant)
- [ ] Test : tenant einvoicing OFF → submit() = success + status not_emitted (no-op)

---

# Story B3.S6.T4 — Drop définitif `app/models/finance/*` + CI bloquant

## Contexte

**Friction** : TR-8 (cf. `architecture-cible.md §3.2.9`)
**Sévérité** : P0 — 2 sources de vérité Invoice persistantes = risque divergence ORM
**Code source** : `app/models/finance/invoice.py`, `app/models/finance/payment.py`

### Description

B3.S1.T3 a déjà droppé les imports + le dossier. **Cette story** ajoute le **garde-fou CI** qui bloque la réintroduction. Sans ce filet, un dev pourrait recréer le dossier par habitude → drift.

## Solution

### Script CI

```python
# tools/check_no_finance_legacy.py (NEW)
"""Refuse `app/models/finance/*` qui dupliquerait Invoice/Payment canoniques.

Source unique : app/models/invoice.py + app/models/payment.py.
"""
import sys
from pathlib import Path

LEGACY_PATH = Path("app/models/finance")
LEGACY_IMPORT_RE = re.compile(r"from\s+app\.models\.finance\b")

violations = []

# 1. Le dossier ne doit pas exister
if LEGACY_PATH.exists():
    files = list(LEGACY_PATH.rglob("*.py"))
    if files:
        violations.append(f"Dossier {LEGACY_PATH} existe et contient {len(files)} fichiers : {[str(f) for f in files]}")

# 2. Aucun import résiduel
for py in Path(".").rglob("*.py"):
    if "site-packages" in str(py) or ".venv" in str(py):
        continue
    text = py.read_text(errors="ignore")
    for m in LEGACY_IMPORT_RE.finditer(text):
        line = text[:m.start()].count("\n") + 1
        violations.append(f"{py}:{line} — import legacy 'from app.models.finance' interdit")

if violations:
    print("❌ TR-8 violations :")
    print("\n".join(f"  - {v}" for v in violations))
    print("\nUtiliser app.models.invoice / app.models.payment (canoniques).")
    sys.exit(1)

print("✅ TR-8 — aucun legacy app/models/finance/")
```

### CI integration

Ajouté à `54-ci-invariants.md` script #26 :
```yaml
# .github/workflows/ci.yml
- name: Check no finance legacy (TR-8)
  run: python tools/check_no_finance_legacy.py
```

### Pre-commit hook

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: check-no-finance-legacy
      name: TR-8 — no app/models/finance/
      entry: python tools/check_no_finance_legacy.py
      language: system
      pass_filenames: false
```

### Test du script

```python
# tests/test_check_no_finance_legacy.py
def test_script_exits_zero_when_clean(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("app/models").mkdir(parents=True)
    (Path("app/models") / "invoice.py").write_text("# canonical")
    result = subprocess.run([sys.executable, REAL_SCRIPT_PATH], capture_output=True)
    assert result.returncode == 0

def test_script_exits_one_when_legacy_dir_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("app/models/finance").mkdir(parents=True)
    (Path("app/models/finance") / "invoice.py").write_text("# legacy")
    result = subprocess.run([sys.executable, REAL_SCRIPT_PATH], capture_output=True)
    assert result.returncode == 1
```

## DoD

- [ ] Script `tools/check_no_finance_legacy.py` livré
- [ ] CI workflow exécute le script à chaque PR
- [ ] Pre-commit hook configuré
- [ ] Tests script : clean = 0, legacy dir = 1, import résiduel = 1

---

# Story B3.S6.T5 — Tests round-trip Invoice → UBL 2.1 (PEPPOL)

## Contexte

**Validation** : avant l'activation prod e-invoicing (sprint post-B3.S6), s'assurer que le schéma actuel d'`Invoice` peut sérialiser un document UBL 2.1 valide (format PEPPOL).

### Description

UBL 2.1 (Universal Business Language) est le standard XML pour PEPPOL e-invoicing. Champs obligatoires :
- Émetteur : SIRET, nom, adresse, TVA intracom
- Destinataire : idem
- Lignes : qty, unit_price, tva_rate, line_total
- Totals : HT, TVA breakdown, TTC

Si notre `Invoice` ne porte pas tous ces champs, on doit migrer.

## Solution

### Sérialiseur stub

```python
# app/services/einvoicing/ubl_serializer.py (NEW)
from xml.etree import ElementTree as ET


class UblSerializer:
    """Stub UBL 2.1 (PEPPOL) — valide la complétude du schéma Invoice."""

    NS = {
        "ubl": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    }

    def serialize(self, invoice: Invoice, tenant: Tenant, customer: Customer) -> str:
        # Validation pré-sérialisation : champs obligatoires PEPPOL
        if not tenant.siret:
            raise UblValidationError("Tenant.siret requis pour UBL")
        if not tenant.tva_intracom:
            raise UblValidationError("Tenant.tva_intracom requis pour UBL")
        if not customer.address_line1 or not customer.postal_code:
            raise UblValidationError("Customer adresse incomplète pour UBL")

        root = ET.Element("Invoice", attrib={"xmlns": self.NS["ubl"]})
        ET.SubElement(root, "{cbc}ID").text = invoice.reference
        ET.SubElement(root, "{cbc}IssueDate").text = invoice.emitted_at.date().isoformat()
        # ... émetteur, destinataire, lignes, totals
        return ET.tostring(root, encoding="unicode")
```

### Test round-trip

```python
async def test_invoice_serializes_to_ubl_when_complete(db, tenant_marveline_complete, customer_marveline):
    """Tenant + Customer complets → UBL valide."""
    invoice = await invoice_factory.create_emitted(tenant_marveline_complete, customer_marveline)
    xml = serializer.serialize(invoice, tenant_marveline_complete, customer_marveline)
    # Validation XML schema (xsd PEPPOL téléchargé)
    schema = etree.XMLSchema(etree.parse("tests/fixtures/UBL-Invoice-2.1.xsd"))
    schema.assertValid(etree.fromstring(xml.encode()))

async def test_invoice_serialization_fails_if_tenant_no_siret(db, tenant_no_siret):
    invoice = await invoice_factory.create_emitted(tenant_no_siret, customer)
    with pytest.raises(UblValidationError, match="Tenant.siret"):
        serializer.serialize(invoice, tenant_no_siret, customer)
```

### Identification des trous schéma

Si le test échoue → on identifie quels champs manquent dans `Tenant` / `Customer` / `Invoice` pour PEPPOL et on les ajoute en migration. Cible : 0 champ manquant à la fin du sprint.

## DoD

- [ ] `UblSerializer.serialize` stub avec validation pré-serialisation
- [ ] Fixtures Marveline + Splendid avec données complètes (SIRET, TVA intracom, adresse)
- [ ] Test round-trip : Invoice → UBL → schema XSD valide
- [ ] Test fail-fast : champ manquant → `UblValidationError` explicite
- [ ] Audit : liste des champs manquants identifiés (ouvre tickets futurs)

---

## Critères de succès Sprint B3.S6

- [ ] **Q19=A schéma prêt** : Invoice porte 7 colonnes e-invoicing nullables, status enum `e_invoice_status`
- [ ] **Tenant config** : `einvoicing_enabled` + `einvoicing_mode` + creds chiffrés
- [ ] **Dispatcher Protocol** : `EInvoicingDispatcher` + `NoOpDispatcher` livrés
- [ ] **Hook Outbox** : `InvoiceEmittedForEInvoicing` publié à émission
- [ ] **TR-8 verrouillé CI** : `tools/check_no_finance_legacy.py` actif sur chaque PR + pre-commit
- [ ] **Validation UBL** : sérialisation Invoice → UBL 2.1 testée sur fixtures Marveline + Splendid
- [ ] Trigger Invoice immutable mis à jour : whitelist colonnes e-invoicing
- [ ] **Pas d'activation prod** : tous tenants `einvoicing_enabled=false` en sortie de sprint

---

**Fin du document — 13-sprint-B3.S6.md**
