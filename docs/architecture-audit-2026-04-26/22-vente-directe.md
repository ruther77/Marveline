# Module 22 — Vente directe (POS Marveline)

> **Phase C.** Audit du domaine vente directe : Vente (FSM 7 statuts), VenteLine, VentePayment, sans réservation préalable.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/vente.py` | 158 (Vente + VenteLine + VentePayment) |
| `app/services/vente.py` | 202 |
| `app/services/vente_pdf.py` | 137 (parcours) |
| `app/repositories/vente.py` | 366 (parcours) |
| `app/api/v1/endpoints/ventes.py` | 159 (parcours) |
| `app/schemas/vente.py` | 143 (parcours) |

**Volume total** : ~1 165 LoC.

---

## 2. Architecture observée

```
Vente (FSM 7 statuts)
  draft → pending → deposit_paid → fully_paid → refunded
                  → overdue
                  → cancelled
  Unique (tenant_id, reference)

VenteLine (cascade)
  product_id Optional (SET NULL, F579 pattern récurrent)

VentePayment (cascade, is_deposit flag)

VENTE_TRANSITIONS matrice définie (services/vente.py:14-22)
  ⚠ add_payment bypass cette matrice (cf. F729)
```

---

## 3. Frictions identifiées — module 22

> Compteur cumulé (mod. 01-21) ≈ 727. Module 22 ouvre à **F728**.

### 3.1 P0

#### F728 — `Vente` stocke `tva_cents` sans `tva_rate` capturé

**Constat.** `models/vente.py:47-48` :
```python
subtotal_cents: Mapped[int] = mapped_column(BigInteger(), default=0)
tva_cents: Mapped[int] = mapped_column(BigInteger(), default=0)
total_cents: Mapped[int] = mapped_column(BigInteger(), default=0)
```

**Aucun champ `tva_rate`**. Le taux appliqué est perdu après création. Impossible de reproduire le calcul, impossible de générer un rapport TVA fiable, impossible de re-vérifier en cas de litige.

**Action** : ajouter `tva_rate Numeric(5,4)` capturé à la création (cf. Invoice mod. 21).

---

#### F729 — `add_payment` bypass la matrice `VENTE_TRANSITIONS`

**Constat.** `services/vente.py:153-159` :
```python
if vente.paid_cents >= vente.total_cents:
    vente.status = VenteStatus.FULLY_PAID
elif data.is_deposit and vente.status == VenteStatus.PENDING:
    vente.status = VenteStatus.DEPOSIT_PAID
elif vente.status == VenteStatus.DRAFT:
    vente.status = VenteStatus.PENDING
```

**Aucun appel à `_assert_transition`**. Si vente est `OVERDUE` et qu'un paiement complet arrive, transition `OVERDUE → FULLY_PAID` — pourtant listée dans la matrice (l. 19 : `OVERDUE: [FULLY_PAID, REFUNDED, CANCELLED]`) donc OK. Mais transition `DRAFT → FULLY_PAID` directement (saute PENDING) n'est **pas** dans la matrice (l. 15 : `DRAFT: [PENDING, REFUNDED, CANCELLED]`).

Avec un paiement total sur DRAFT, on saute PENDING → bypass matrice silencieux.

**Action** : utiliser `_assert_transition` à chaque transition + cohérence matrice.

---

#### F730 — Pas de TVA détaillée par ligne (multi-TVA impossible)

**Constat.** Cf. F567 (mod. 17) : Vente n'a pas non plus de `VenteLine.tva_rate`. Une vente mixte Restaurant+Marveline → un seul taux global → reporting comptable cassé.

---

#### F731 — `VenteLine.product_id ondelete=SET NULL` (cf. F579 pattern)

Vente historique perd la référence produit si suppression.

---

### 3.2 P1

#### F732 — Comment l. 58 "FKs optionnelles sans contrainte ORM" mais les FKs SQL sont déclarées

`models/vente.py:58` ment : `invoice_id` et `reservation_id` ont `ForeignKey(...)` explicites avec `ondelete=SET NULL`. Comment trompeur.

---

#### F733 — `add_payment` aucun audit log

---

#### F734 — `_refresh_overdue_statuses` mass-update sans `with_for_update` (race possible)

`services/vente.py:32-55`. Si 2 workers exécutent simultanément, conflits possibles (mais idempotent puisque même résultat).

---

#### F735 — `Vente.notes Text` non chiffré (PII)

---

#### F736 — `update_vente` check hardcoded `(DRAFT, PENDING)` au lieu de matrice

`services/vente.py:119`. Pour évoluer (autoriser update sur OVERDUE par ex.), modifier la liste hardcoded.

---

#### F737 — `payment_method String(30)` libre — pas de CHECK enum

Vs Invoice/Payment qui ont CHECK 4 valeurs. Drift cohérence cross-module.

---

#### F738 — `created_by BigInteger` sur VentePayment sans FK accounts

Pattern récurrent (cf. F613, F656).

---

#### F739 — Pas de CHECK `total_cents = subtotal_cents + tva_cents`

Drift mathématique possible sans guard DB.

---

#### F740 — `paid_cents` dénormalisé (SUM payments) sans trigger sync (drift potentiel)

Si quelqu'un insert un VentePayment direct par SQL, `Vente.paid_cents` ne s'update pas.

---

#### F741 — Pas de notification client à `FULLY_PAID` / `REFUNDED`

---

#### F742 — `Vente.deposit_pct Integer` sans CHECK borne 0-100

Un admin peut entrer `deposit_pct=200` (200%) → drift logique métier.

---

### 3.3 P2

#### F743 — `VenteLine.created_at server_default="NOW()"` string (vs `func.now()`)

#### F744 — `VentePayment.payment_date Date` au lieu de timestamp (cf. F713)

#### F745 — Pas d'index `(tenant_id, payment_due_date)` pour scan overdue

#### F746 — `payments order_by="VentePayment.payment_date"` lazy default — chargement complet

#### F747 — Pas de `Vente.cancellation_reason` (vs Invoice F711)

---

### 3.4 P3

#### F748 — Format `VTE-YYYY-NNNN` hardcoded (pattern référencé F595/F636/F726)

#### F749 — `Vente` schemas et endpoints parcourus rapidement (probablement OK pour usages basiques)

---

## 4. Synthèse module 22

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 4 | F728 (no tva_rate captured), F729 (bypass FSM), F730 (no multi-TVA), F731 (SET NULL product_id) |
| P1 | 11 | F732 → F742 |
| P2 | 5 | F743 → F747 |
| P3 | 2 | F748, F749 |
| **Total** | **22** | F728 → F749 |

**Compteur cumulé après module 22** : ≈ 727 + 22 = **749 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : ajouter `tva_rate` capture (F728) ; aligner `add_payment` sur `VENTE_TRANSITIONS` matrice (F729) ; tva par ligne (F730).
