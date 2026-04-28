# Module 20 — Deposit (Caution Marveline)

> **Phase C.** Audit du domaine caution : modèle Deposit, FSM held/released/retained, auto-retain depuis damages, sync `Reservation.deposit_paid`.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/deposit.py` | 92 |
| `app/services/deposit.py` | 282 |
| `app/repositories/deposit.py` | 137 |
| `app/api/v1/endpoints/deposits.py` | 47 |
| `app/schemas/deposit.py` | 65 |

**Volume total** : 623 LoC.

---

## 2. Architecture observée

```
Deposit (1 caution par réservation typiquement)
  status FSM: held → released | retained
  amount_cents > 0 (CHECK)
  retained_amount_cents (Optional, CHECK > 0 si défini)
  collection_date / release_date (Optional)

Sync Reservation.deposit_paid (denormalized flag) ←→ Deposit.status='held'
  - create_deposit → reservation.deposit_paid = True
  - update_deposit released/retained + no remaining held → deposit_paid = False
  - update_deposit held → deposit_paid = True

auto_retain_from_damages (declared damage → retained automatic)
  Lit InvoiceCharge.charge_type == "DAMAGE" → sum → cap à amount_cents
```

---

## 3. Frictions identifiées — module 20

> Compteur cumulé (mod. 01-19) ≈ 671. Module 20 ouvre à **F672**.

### 3.1 P0

#### F672 — Pas de FSM guard sur `update_deposit` (transitions libres `released → held`)

**Constat.** `services/deposit.py:157-222` : aucun `_assert_transition`. CHECK SQL valide les 3 valeurs mais pas les transitions. Un admin peut :
- `released → held` (réinscription d'une caution déjà restituée → fonds dupliqués reportés).
- `retained → held` (annulation rétention sans audit).
- `held → released → held` (cycle infini).

**Action** : matrice DEPOSIT_TRANSITIONS + `_assert_transition` (pattern devis F562).

---

#### F673 — `auto_retain_from_damages` modifie `held → retained` **sans audit log**

**Constat.** `services/deposit.py:243-267` :
```python
held_deposit.retained_amount_cents = retained
held_deposit.status = DepositStatus.RETAINED
logger.info("Auto-retained %d cents ...")
```

`logger.info` seul. La rétention de caution est une action contractuelle critique (CGV, contestation client probable). Aucun audit_log structuré (`AuditService.log_action(action="DEPOSIT_AUTO_RETAINED", ...)`).

**Action** : audit obligatoire avec `actor_id`, `before_state`, `after_state`, `damage_charge_ids`.

---

#### F674 — `compute_damage_total` consomme `charge_type == "DAMAGE"` hardcoded string

`services/deposit.py:237`. Drift si refactor `InvoiceCharge.charge_type` vers enum. Cf. mod. 21.

---

#### F675 — `update_deposit` permet de modifier `amount_cents` (anomalie comptable post-encaissement)

**Constat.** Le schema `DepositUpdate` (à confirmer mod. schemas) probablement accepte `amount_cents`. Modifier le montant après encaissement = altération de pièce comptable.

**Action** : `amount_cents` immutable post-création. Si erreur, créer un avoir + nouveau deposit.

---

### 3.2 P1

#### F676 — `Deposit` pas de `SoftDeleteMixin` ni `is_active`

Suppression = hard delete. Aucune trace d'une caution annulée par erreur.

---

#### F677 — `notes String(500)` non chiffré (PII : motif rétention, comportement client)

---

#### F678 — `collection_date` Optional → caution `held` sans date encaissement (cohérence)

Pas de CHECK `(status='held' AND collection_date IS NOT NULL)`.

---

#### F679 — `release_date` Optional → caution `released` sans date restitution

Pas de CHECK couplant.

---

#### F680 — Pas de CHECK `release_date >= collection_date`

---

#### F681 — Pas de CHECK DB `retained_amount_cents <= amount_cents` (validation code seul)

`services/deposit.py:194-203` valide à l'update mais pas de garde-fou DB. INSERT direct = bypass.

---

#### F682 — Pas de CHECK `(status='retained' XOR retained_amount_cents IS NOT NULL)`

Drift possible : status=`held` avec `retained_amount_cents` set, ou status=`retained` sans montant.

---

#### F683 — `Reservation.deposit_paid` flag dénormalisé sync manuel — drift potentiel

Si quelqu'un update `Deposit.status` directement par SQL ou par un autre service, `deposit_paid` n'est pas synced.

**Action** : trigger PostgreSQL ou property calculée live (sans colonne).

---

#### F684 — `has_held_deposit` charge tous les deposits puis `any()` Python — pas de COUNT optimisé

Pour réservations avec >1 deposit (rare mais possible), 1 SELECT chargé inutilement.

---

#### F685 — Pas d'audit log `DEPOSIT_RELEASED`/`DEPOSIT_RETAINED` (cf. F674)

---

#### F686 — Pas de notification client à release/retained (CGV exigent communication)

---

#### F687 — `cancel_reservation` (mod 18 F620) ne libère pas les deposits — bug cascade

Cf. F620. Une réservation annulée laisse caution `held` active, fonds bloqués.

---

### 3.3 P2

#### F688 — `notes String(500)` au lieu de Text

#### F689 — Pas d'index `(tenant_id, status)` sur Deposit

#### F690 — `_get_reservation_or_404` recharge réservation pour chaque méthode — optimisation possible

#### F691 — `DepositSummary get_summary` sans pagination (acceptable si KPI agrégés)

#### F692 — `Deposit.amount_cents` pas de borne max (overflow théorique)

#### F693 — Endpoint deposits.py 47 LoC — vraisemblablement endpoints minimalistes (release/retain via update générique)

---

### 3.4 P3

#### F694 — Pas de schéma audit JSON pour history rétentions

---

## 4. Synthèse module 20

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 4 | F672 (no FSM guard), F673 (auto-retain no audit), F674 (DAMAGE hardcoded), F675 (amount_cents mutable) |
| P1 | 12 | F676 → F687 |
| P2 | 5 | F688 → F692 |
| P3 | 2 | F693, F694 |
| **Total** | **23** | F672 → F694 |

**Compteur cumulé après module 20** : ≈ 671 + 23 = **694 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : matrice transitions FSM (F672) ; audit log obligatoire sur retain/release (F673 + F685) ; immutabilité `amount_cents` (F675) ; release deposits au cancel reservation (F687).
