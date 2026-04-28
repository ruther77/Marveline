# Module 21 — Invoice / Payment / InvoiceCharge / CreditNote

> **Phase C.** Audit du domaine facturation : Invoice (FSM 5 statuts, split full/advance/balance), Payment, InvoiceCharge (DAMAGE/LABOR/DELIVERY), CreditNote (avoir), TVA multi-taux, génération PDF.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/invoice.py` | 241 |
| `app/models/payment.py` | 67 |
| `app/models/invoice_charge.py` | 91 |
| `app/models/invoice_credit_note.py` | 71 |
| `app/models/finance/invoice.py` | 160 (duplicate folder) |
| `app/models/finance/payment.py` | 74 (duplicate) |
| `app/services/invoice.py` | 481 |
| `app/services/invoice_payment_rules.py` | 61 |
| `app/services/invoice_credit_note.py` | 231 |
| `app/services/invoice_pdf.py` | 197 |
| `app/services/payment.py` | 128 |
| `app/repositories/invoice.py` | 557 |
| `app/repositories/payment.py` | 78 |
| `app/api/v1/endpoints/invoices.py` | 495 |
| `app/schemas/invoice.py` | 505 |

**Volume total** : ~3 850 LoC.

---

## 2. Architecture observée

```
Invoice (FSM 5 statuts)
  status: draft → sent → paid | overdue | cancelled
  invoice_type: full | advance | balance (split 40/60)
  Unique (tenant, reservation_id, invoice_type)
  ↓ 1:N
  ├── InvoiceCharge (DAMAGE | LABOR | DELIVERY) — modifie total_amount_cents post-creation (cf. F700)
  ├── Payment (CHECK amount_cents > 0)
  └── Relance (cf. mod. 23)
  +
  CreditNote (avoir, 1:N, mod. séparé)

apply_invoice_payment (services/invoice_payment_rules.py) :
  - Modifie invoice.paid_amount_cents
  - NE CRÉE PAS de Payment row (cf. F695)
  - Status auto-transitions :
    * paid_amount >= total → PAID
    * draft + payment → SENT (étrange F704)

generate_tva_report : filtre status=PAID seulement (F708)
```

---

## 3. Frictions identifiées — module 21

> Compteur cumulé (mod. 01-20) ≈ 694. Module 21 ouvre à **F695**.

### 3.1 P0

#### F695 — `apply_invoice_payment` ne crée **PAS** de Payment row

**Constat.** `services/invoice_payment_rules.py:50-56` :
```python
invoice.paid_amount_cents += amount_cents
if payment_method:
    invoice.payment_method = payment_method
if payment_date:
    invoice.payment_date = payment_date
```

Le commentaire l. 51-52 dit "payment_method et payment_date vivent dans la table payments (source de verite)" — mais **aucune insertion** dans `payments`. La table Payment existe (mod. payment.py 67L) mais n'est jamais alimentée par cette fonction.

**Conséquence** :
- `SUM(payments.amount_cents) WHERE invoice_id=X` ≠ `invoices.paid_amount_cents`.
- L'historique des paiements multiples sur une facture est **perdu** (un seul `payment_method`/`payment_date` stocké en cache).
- `generate_tva_report` (l. 369-376) basé sur Invoice OK mais reporting comptable fin (audit fiscal) impossible sans table Payment cohérente.

**Action** : créer `Payment(invoice_id, amount_cents, payment_method, payment_date)` row à chaque appel.

---

#### F696 — `generate_invoice_number` `pg_advisory_xact_lock(0x494E56 ^ year ^ tenant_id)` collisions XOR

**Constat.** `services/invoice.py:96-97` :
```python
lock_key = 0x494E56 ^ (year & 0xFFFF) ^ (tenant_id & 0xFFFF)
await self.db.execute(text(f"SELECT pg_advisory_xact_lock({lock_key})"))
```

XOR de 16 bits + 16 bits + constante 24 bits. Collisions possibles : `(year=2026, tenant=1)` et `(year=2027, tenant=0)` peuvent donner le même `lock_key` selon les bits. Deux tenants peuvent se bloquer mutuellement sur la génération de numéros séparés.

**Action** : utiliser SEQUENCE PostgreSQL nommée `invoice_seq_{tenant_id}_{year}` ou table dédiée `invoice_counters`.

---

#### F697 — `add_charge` modifie `total_amount_cents` post-création (viole immutabilité fiscale)

**Constat.** `services/invoice.py:46-49, 348-350` :
```python
invoice.total_amount_cents += charge_amount_cents
if invoice.tva_rate is not None:
    invoice.tva_amount_cents = round(invoice.total_amount_cents * invoice.tva_rate)
    invoice.total_ttc_cents = invoice.total_amount_cents + invoice.tva_amount_cents
```

Une facture émise et envoyée au client peut être augmentée par ajout d'`InvoiceCharge`. **CGV France et code des impôts** : une facture émise est une pièce comptable immutable. Toute modification = nouvelle facture ou avoir.

**Action** : `add_charge` interdit sur `status IN (sent, paid, cancelled)`. Pour ajouts post-émission, créer une nouvelle facture "complement" liée.

---

#### F698 — Fallback `default_tva_rate = 0.20` hardcoded Marveline

**Constat.** `services/invoice.py:156-161` :
```python
if tenant_settings:
    default_tva_rate = tenant_settings.vat_rate
else:
    default_tva_rate = 0.20
    logger.warning(...)
```

Pattern systémique (F196 mod. 07, F487 mod. 15, F561 mod. 17). Restaurant 10% / Épicerie 5.5% facturé à 20% si tenant_settings absent.

---

#### F699 — `cancel_invoice` permet de canceller une facture avec paid_amount_cents = 0 mais status `paid`

**Constat.** `services/invoice.py:266-278` :
```python
if invoice.status == InvoiceStatus.PAID:
    raise HTTPException(400, INVOICE_PAID_NO_CANCEL)
if invoice.paid_amount_cents > 0:
    raise HTTPException(400, "credit-note avant d'annuler")
```

OK. Mais si `paid_amount_cents = total_amount_cents` (paid via apply_invoice_payment) sans status=`paid` synchronisé (race), bypass possible.

---

#### F700 — `update_invoice` modifie `total_amount_cents` hors statut `paid` (immutabilité violée)

**Constat.** `services/invoice.py:217-237` : seul check `status == PAID → 400`. Mais `status='sent'` permet de modifier le montant total → fraude potentielle (envoyer 1000€, ajuster à 500€ après paiement de 1000€).

---

### 3.2 P1

#### F701 — `Invoice.payments cascade="all, delete-orphan"` ORM **vs** `Payment.invoice_id ondelete=RESTRICT` DB

Contradiction. Côté ORM, supprimer Invoice supprime Payments. Côté DB, RESTRICT bloque la suppression si Payments existent. Comportement dépend du chemin (ORM `db.delete()` vs SQL direct).

---

#### F702 — `Invoice.tva_rate Optional[float]` (default NULL)

Une facture sans tva_rate générée (bug en amont) → `tva_amount_cents` non recalculé après charges → ttc faux.

---

#### F703 — `apply_invoice_payment` transition `DRAFT → SENT` à premier paiement (anti-sémantique)

`services/invoice_payment_rules.py:60-61`. Un paiement reçu n'implique pas que la facture a été envoyée. Auto-transition étrange.

---

#### F704 — `check_overdue_invoices` peut transiter `draft → overdue` (F705 implicite)

`services/invoice.py:253-256` : `if invoice.status not in (OVERDUE, CANCELLED)` → tous les autres acceptés y compris `DRAFT`. Une draft non envoyée passe overdue à l'échéance.

---

#### F705 — `generate_tva_report` filtre QUE `status=PAID` → reporting incomplet

`services/invoice.py:373`. Une facture partiellement payée (paid_amount_cents > 0 mais status ≠ paid) est exclue du rapport TVA.

**Action** : inclure aussi `OVERDUE` (encaissées mais non flippées par cron).

---

#### F706 — `_compute_tva_breakdown` ratio arrondi (l. 455-457)

```python
if total_lines_ht > 0 and total_ht != total_lines_ht:
    ratio = Decimal(total_ht) / Decimal(total_lines_ht)
    groups = {rate: round(int(base) * ratio) for rate, base in groups.items()}
```

Si discount global appliqué, le ratio < 1 → erreurs d'arrondi cumulées sur multi-taux. Test d'invariant `SUM(breakdown.tva_cents) == total_tva_cents` essentiel.

---

#### F707 — `Invoice.advance_rate float` (cf. F509 — précision)

---

#### F708 — `InvoiceCharge.charge_type` CHECK 3 valeurs (`DAMAGE`/`LABOR`/`DELIVERY`) couplé code

Si on ajoute `INSURANCE` ou `CLEANING_FEE`, modifier code + CHECK + tests + documentation.

---

#### F709 — `Payment.payment_method` CHECK 4 valeurs hardcoded (cohérent avec Invoice mais drift potentiel)

---

#### F710 — Pas de `signed_at` ni signature électronique sur Invoice (e-invoicing UE 2024/55 à venir)

À partir 2026-09, e-invoicing obligatoire B2B France. Bloquant à terme.

---

#### F711 — `Invoice.cancellation_reason Text` nullable mais commentaire l. 160 dit "obligatoire dès qu'on annule"

Pas de CHECK conditionnel `(status='cancelled' AND cancellation_reason IS NOT NULL)`.

---

#### F712 — `cancelled_at` set par cancel_invoice mais pas par cron (transition cancelled hors flow)

---

#### F713 — `Payment.payment_date Date` (pas timestamp) → impossible matching intraday

Pour rapprochement bancaire fin (deux paiements même jour, ordres différents), Date insuffisant.

---

#### F714 — `apply_invoice_payment` aucun audit log

---

#### F715 — `app/models/finance/invoice.py` (160L) **duplicate** de `app/models/invoice.py` (241L)

`app/models/finance/payment.py` (74L) duplicate de `app/models/payment.py` (67L). Quel est utilisé ? Probablement legacy non utilisé mais à confirmer.

---

#### F716 — `update_invoice_after_charge` recalcule TVA en flat (`total_amount_cents * tva_rate`) sans tenir compte du `tva_breakdown` multi-taux

Si la facture a un `tva_breakdown` multi-taux et qu'on ajoute une charge, le breakdown n'est pas mis à jour. Drift.

---

### 3.3 P2

#### F717 — `Invoice.tva_breakdown JSON nullable` sans schema validation runtime

#### F718 — Pas de CHECK `(status='cancelled' XOR cancelled_at IS NULL)`

#### F719 — `Payment.notes String(500)` au lieu de Text (cf. pattern)

#### F720 — Pas d'index `(tenant_id, status, due_date)` pour overdue scan

#### F721 — `Invoice.cancellation_reason` Text non chiffré (PII raison litige)

#### F722 — `apply_invoice_payment` log absent

#### F723 — `Payment.payment_method` CHECK vs PaymentMethod enum Python — drift potentiel

#### F724 — `Invoice.tva_rate` valide `Optional[float]` mais `tva_amount_cents` aussi `Optional` — coverage NULL incohérent

#### F725 — `cancel_invoice` n'invalide pas les Payments associés (ils restent `Payment.invoice_id` pointant sur facture cancelled)

---

### 3.4 P3

#### F726 — Format `INV-YYYY-NNNN` hardcoded

#### F727 — Comments "Option A" / "Option B" références à doc externe

---

## 4. Synthèse module 21

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 6 | F695 (Payment row pas créée), F696 (XOR collision lock), F697 (add_charge viole immutabilité), F698 (fallback tva 0.20), F699 (cancel race paid), F700 (update modif total) |
| P1 | 16 | F701 → F716 |
| P2 | 9 | F717 → F725 |
| P3 | 2 | F726, F727 |
| **Total** | **33** | F695 → F727 |

**Compteur cumulé après module 21** : ≈ 694 + 33 = **727 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) Créer Payment row à chaque `apply_invoice_payment` (F695) ; (2) SEQUENCE par tenant/year (F696) ; (3) immutabilité post-émission (F697 + F700) ; (4) supprimer fallback 0.20 (F698).
>
> **Refactor** : trancher `app/models/finance/*` duplicate (F715) ; e-invoicing UE prep (F710) ; CHECK conditionnel `cancellation_reason NOT NULL si cancelled` (F711, F718).
