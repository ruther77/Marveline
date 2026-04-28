# Module 25 — Loyalty (Programmes fidélité)

> **Phase C.** Audit du domaine fidélité : 11 tables (LoyaltyProgram, LoyaltyMember, PointsLedger, RevenueLedger, TierHistory, WalletPass, RewardsCatalog, RewardRedemption, ReferralLink, FlashOffer, LoyaltyNotificationLog), 2 programmes (L'Incontournable points / Marveline tiered).

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/loyalty.py` | 736 (11 classes) |
| `app/services/loyalty.py` | 743 (parcours sections clés) |
| `app/repositories/loyalty.py` | 580 (parcours) |
| `app/api/v1/endpoints/loyalty.py` | 639 (parcours) |
| `app/schemas/loyalty.py` | 307 (parcours) |
| `app/constants/loyalty.py` | 301 |
| `app/tasks/loyalty.py` | 280 (parcours) |

**Volume total** : ~3 590 LoC.

---

## 2. Architecture observée

```
LoyaltyProgram (2 instances : L'Incontournable=points, Marveline=tiered_discount)
  ↓ 1:N
LoyaltyMember (UNIQUE tenant + phone + program)
  current_tier (String libre)
  transaction_count denormalized
  referral_code unique per tenant
  ↓ 1:N
  ├── PointsLedger (immuable, expires_at 12 mois EARN, 6 mois BONUS)
  ├── RevenueLedger (immuable, cumulative_after_cents)
  ├── TierHistory (audit changements)
  ├── RewardRedemption (1:N rewards)
  └── (parrainage via ReferralLink)

WalletPass : Apple/Google passes
RewardsCatalog : récompenses par tier
FlashOffer : multiplicateurs temporaires
LoyaltyNotificationLog : log notifications

credit_points : VIP × FlashOffer multipliers cumulatifs
credit_revenue : append RevenueLedger + transaction_count++
```

---

## 3. Frictions identifiées — module 25

> Compteur cumulé (mod. 01-24) ≈ 791. Module 25 ouvre à **F792**.

### 3.1 P0

#### F792 — `credit_points` calcule `balance_after` **sans `with_for_update`** → race condition

**Constat.** `services/loyalty.py:352-369` :
```python
last_entry = await self.points_repo.get_last_entry(member.id, tenant_id)
current_balance = last_entry.balance_after if last_entry else 0
new_balance = current_balance + points
entry = PointsLedger(
    ..., balance_after=new_balance, ...
)
await self.points_repo.append(entry)
```

Deux transactions concurrentes pour le même `member_id` :
1. T1 lit `last_entry.balance_after = 100`.
2. T2 lit `last_entry.balance_after = 100` (avant T1 commit).
3. T1 INSERT `balance_after = 100 + 50 = 150`.
4. T2 INSERT `balance_after = 100 + 30 = 130`. **Mauvais** — devrait être `180`.

Le ledger devient incohérent. Le solde réel `SUM(amount)` diverge de `MAX(balance_after)`.

**Action** : `with_for_update()` sur le SELECT du dernier entry (ou row member), ou `pg_advisory_xact_lock(member_id)`.

---

#### F793 — `credit_revenue` même race (cumulative_after_cents)

`services/loyalty.py:443-457`. Pattern identique. Un client qui paye 2 réservations en parallèle peut perdre du CA dans le ledger.

---

#### F794 — `member.transaction_count += 1` sans lock (race counter)

L. 372, 459. Read-modify-write classique sans atomicité.

**Action** : `UPDATE loyalty_members SET transaction_count = transaction_count + 1 WHERE id = :id`.

---

#### F795 — "JAMAIS d'UPDATE ou DELETE" promesse code-only (pas de trigger DB)

**Constat.** `models/loyalty.py:215-217` (PointsLedger) :
```
- JAMAIS d'UPDATE ou DELETE sur cette table
- Corrections via nouvelle ligne de type ADJUST
```

Aucun trigger PostgreSQL `BEFORE UPDATE/DELETE` n'enforce. Un admin connecté à psql peut altérer l'historique sans laisser de trace. Discipline reposant sur la confiance.

**Action** : trigger `RAISE EXCEPTION` sur UPDATE/DELETE.

---

#### F796 — Pas de Celery task pour **expirer les points** (`expires_at` index défini mais consommation absente)

`models/loyalty.py:281-282` index partial sur `expires_at IS NOT NULL`. Mais aucune task `expire_points_task` listée dans `app/tasks/loyalty.py:280` (à vérifier précisément). Si absente, points expirés restent comptés dans `balance_after` cumulatif → solde réel ne décroît jamais.

---

#### F797 — `expires_at = now + timedelta(days=POINTS_EXPIRY_MONTHS * 30)` approximation

`services/loyalty.py:350`. 30 jours/mois × 12 = 360 jours, soit -5 jours sur une année réelle. Cumulé sur plusieurs renouvellements → drift visible.

**Action** : `relativedelta(months=N)` (dateutil) au lieu de `timedelta(days=30*N)`.

---

### 3.2 P1

#### F798 — `LoyaltyProgram.config JSONB nullable` sans schema validation runtime

#### F799 — `referral_code (PRENOM + 4 chiffres)` collisions probables sur prénoms courts (Jo, Bo, Lu)

`models/loyalty.py:134-137`. Pour "JO" + 0001..9999 = 9 999 combos. Si on dépasse, IntegrityError ou bug dans le générateur.

#### F800 — `LoyaltyMember.phone` pas de validation E.164 (cf. F475)

#### F801 — `LoyaltyMember.current_tier String(20)` libre, pas de CHECK enum

`current_tier` pas listé en CHECK. Un admin peut passer `"PLATINUM"` (typo) → tier inconnu, multipliers ne s'appliquent pas.

#### F802 — `RevenueLedger.cumulative_after_cents` non recalculé depuis SUM (drift potentiel)

#### F803 — `_evaluate_revenue_tier` fenêtre glissante non recalculée si historique change

`services/loyalty.py:613`. Si on insère un `entry_type=adjust` avec date passée, la fenêtre `REVENUE_WINDOW_MONTHS` ne suit pas (re-évaluer tous les members chaque jour ?).

#### F804 — `cancel_transaction` (l. 532) crée probablement entry inverse — cohérent avec immutable rule, à confirmer

#### F805 — `adjust_points` (l. 682) admin sans audit log spécifique

#### F806 — `barcode` HMAC SHA256 tronqué 7 bytes (services/loyalty.py:91)

7 bytes = 56 bits. Collisions improbables mais pas zéro pour millions d'utilisateurs.

#### F807 — Multipliers VIP × FlashOffer cumulatifs (services/loyalty.py:333-345)

Pas de cap. VIP × 1.5 × Flash × 3 → ×4.5 multiplier sur points → fraude potentielle.

#### F808 — `metadata_json JSONB` sans schema Pydantic validation

#### F809 — `LoyaltyNotificationLog` pas de `TenantMixin` (cf. l. 700)

#### F810 — Pas de cap journalier/mensuel sur `earn` points (anti-fraude)

#### F811 — `WalletPass` pas de `SoftDeleteMixin` — si user supprime côté Apple, désynchro

---

### 3.3 P2

#### F812 — `birth_month` seul (MM) — pas année. Acceptable pour anniversaire mais limite marketing.

#### F813 — `wallet_serial_number` String(100) pas UNIQUE

#### F814 — `LoyaltyProgram.program_type` 2 valeurs dur (extensible difficile)

#### F815 — `RewardsCatalog.cost_points` Integer sans borne

#### F816 — `ReferralLink` pas `TenantMixin` (583-)

#### F817 — `FlashOffer` start/end probablement pas validés `start <= end` (à confirmer)

#### F818 — `transaction_count` dénormalisé sans trigger

#### F819 — `LoyaltyNotificationLog` pas de retry policy push iOS/Android

#### F820 — `RewardRedemption.code` HMAC à confirmer (pattern barcode F806)

#### F821 — `LoyaltyMember.first_name` + `last_name` duplique `Customer.first_name/last_name` via customer_id

---

### 3.4 P3

#### F822 — Comments models sans accents (`evaluation` au lieu d'`évaluation`)

#### F823 — Format `referral_code` documenté en code mais pas en model comment

#### F824 — `LoyaltyMember.email demande apres 2 transactions` règle non enforced (commentaire seul)

#### F825 — `LoyaltyNotificationLog` schemas non typés strict

---

## 4. Synthèse module 25

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 6 | F792 (race credit_points), F793 (race credit_revenue), F794 (race transaction_count), F795 (immutability code-only), F796 (no expiry task), F797 (timedelta×30 approximation) |
| P1 | 14 | F798 → F811 |
| P2 | 10 | F812 → F821 |
| P3 | 4 | F822 → F825 |
| **Total** | **34** | F792 → F825 |

**Compteur cumulé après module 25** : ≈ 791 + 34 = **825 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) `with_for_update` sur ledger reads (F792, F793) ; (2) atomic counter (F794) ; (3) trigger DB immutability (F795) ; (4) Celery `expire_points_task` (F796) ; (5) `relativedelta(months=N)` (F797).
>
> **Refactor** : cap journalier/mensuel earn (F810) ; cap multiplier (F807) ; CHECK enum tier (F801) ; trigger sync `transaction_count` (F818).
