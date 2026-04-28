# Module 16 — Pricing (Marveline)

> **Phase C — Domaines métier Marveline.** Audit du moteur de pricing : règles `PricingRule` (flat/per_day/tiered/volume/seasonal/custom), paliers `PricingTier`, moteur `PricingEngine`, endpoint simulation.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/pricing.py` | 51 |
| `app/services/pricing_engine.py` | 124 |
| `app/api/v1/endpoints/pricing.py` | 259 |
| `app/schemas/pricing.py` | 83 |

**Volume total** : 517 LoC.

---

## 2. Architecture observée

```
PricingRule (rule_type ∈ {flat, per_day, tiered, volume, seasonal, custom})
  │ applies_to ∈ {product, category, all} + target_id (Optional)
  │ discount_pct (Integer) + valid_from / valid_to + active (bool)
  └── 1:N ──► PricingTier (min_qty, max_qty, unit_price_cents)
              cascade="all, delete-orphan"

DEUX consommateurs en parallèle :
  ▸ PricingEngine.apply_rules (services/pricing_engine.py)
       cumule TOUTES les règles correspondantes
       discount_pct interprété en /100
  ▸ POST /pricing/simulate (endpoints/pricing.py)
       prend la PREMIÈRE règle correspondante
       discount_pct interprété en /10000
```

---

## 3. Frictions identifiées — module 16

> Compteur cumulé (mod. 01-15) ≈ 529. Module 16 ouvre à **F530**.

### 3.1 P0 — Bloquant

#### F530 — `discount_pct` interprété **différemment** entre engine (÷100) et simulate (÷10000)

**Constat.** Deux interprétations contradictoires :

`services/pricing_engine.py:107` :
```python
if rule.rule_type in ("custom", "seasonal") and rule.discount_pct:
    discount = int(amount_cents * rule.discount_pct / 100)  # ÷ 100
    return -discount
```

`endpoints/pricing.py:244` :
```python
elif rule.discount_pct is not None:
    final_price = round(base_price * (1 - rule.discount_pct / 10000))  # ÷ 10000
```

Une même règle avec `discount_pct=10` :
- Via engine (utilisé par devis/reservation/invoice) → **10% remise**.
- Via `/pricing/simulate` (utilisé par UI admin) → **0.1% remise**.

**Conséquence** : l'admin simule "10% remise" affichée correctement (s'il a bien saisi `1000` en backend), puis crée un devis avec la même règle → la remise réelle appliquée est **100×** l'affichée. Catastrophe facturation.

**Action** : choisir une convention unique (préférer `÷ 100` lisible) + migration des rows existants + test d'invariant "engine == simulate sur la même règle".

---

#### F531 — Aucune validation `rule_type` / `applies_to` (typo silencieux)

**Constat.** `schemas/pricing.py:26-27` accepte `rule_type: str` et `applies_to: str` libres. Aucun pattern, aucun enum. Les commentaires en disent les valeurs valides (l. 26-27 model + l. 18-20 schema).

`PricingEngine._compute_adjustment` (l. 102-116) :
```python
if rule.rule_type in ("flat", "per_day"):       return 0
if rule.rule_type in ("custom", "seasonal"):    ...
if rule.rule_type in ("tiered", "volume"):      ...
return 0  # ← typo "custm" → silently retourne 0
```

Une règle créée avec `rule_type="custm"` (typo) est acceptée à la création, ne raise jamais, mais ne s'applique jamais → admin ne comprend pas pourquoi sa règle n'a pas d'effet.

**Action** : `Literal["flat","per_day","tiered","volume","seasonal","custom"]` Pydantic + ENUM PostgreSQL natif.

---

#### F532 — `apply_rules` **cumule** toutes les règles, `simulate` prend la **première** → comportements divergents

**Constat.**

`PricingEngine.apply_rules` (l. 50-64) :
```python
for rule in rules:
    if not self._rule_applies(rule, ...): continue
    adjustment = self._compute_adjustment(rule, amount, quantity)
    if adjustment == 0: continue
    amount += adjustment  # ← CUMULE
    applied.append(...)
```

`simulate_pricing` (l. 228-245) :
```python
for rule in rules:
    if rule.rule_type == "tiered" and rule.tiers:
        ...
        applied_rule = rule
        final_price = matching_tier.unit_price_cents
        break  # ← PREMIÈRE
    elif rule.discount_pct is not None:
        applied_rule = rule
        ...
        break  # ← PREMIÈRE
```

**Conséquence** : si un tenant a 3 règles actives "all" (saisonnier -10%, fidélité -5%, été -15%), le devis applique -30% cumulé alors que la simulation montre -10%. Drift confiance/réalité.

**Action** : fusion `apply_rules` + `simulate` derrière un même service `PricingService.calculate(...)`. Décider du modèle (cumulatif vs exclusif) + documenter via l'enum `rule_type`.

---

#### F533 — Endpoint `/pricing/simulate` exige `Scope.PRICING_WRITE` alors que c'est une lecture pure

**Constat.** `endpoints/pricing.py:182` :
```python
current_user: UserCompat = Depends(require_scope(Scope.PRICING_WRITE)),
```

Aucune écriture DB dans `simulate_pricing` (uniquement SELECT). Un user `staff` avec `pricing:read` ne peut pas simuler un prix avant de proposer un devis client → workflow vente bloqué.

**Action** : `Scope.PRICING_READ` au lieu de `WRITE`.

---

#### F534 — `applies_to="category"` cassé (pas de mapping vers `Product.category` string)

**Constat.** `_rule_applies` (l. 97-99) :
```python
elif rule.applies_to == "category" and rule.target_id:
    if category_id != rule.target_id:
        return False
```

`category_id` est un `int | None` passé en argument. Mais `Product.category` est une **string** (cf. F485 mod. 15) ; aucune table `Category` mappée à des produits ; aucun helper ne convertit la string `Product.category="assiettes"` en `category_id`.

**Conséquence** : toutes les règles `applies_to="category"` ne matchent jamais (sauf si l'appelant injecte un `category_id` magique). Inutilisable en production.

**Action** : dépend du choix F485 — soit Category devient FK de Product et tout devient cohérent, soit `applies_to="category"` doit comparer `Product.category` string.

---

### 3.2 P1

#### F535 — `flat` et `per_day` rule_types **non implémentés**

**Constat.** `_compute_adjustment:103-104` retourne 0. Les commentaires l. 18 + l. 26 listent ces types comme supportés.

**Action** : implémenter ou retirer du schema.

---

#### F536 — Aucun CHECK `discount_pct >= 0` ni borne max

**Constat.** `models/pricing.py:22` `Integer nullable=True` sans contrainte. `discount_pct=-50` (=> -50% = +50% augmentation) accepté. `discount_pct=99999` accepté.

**Action** : `CHECK (discount_pct IS NULL OR discount_pct BETWEEN 0 AND 10000)` selon convention.

---

#### F537 — `final_cents = max(0, amount)` clamp positif mais aucune protection borne haute

Une règle buggée multipliant le prix par 10 = facturation absurde, aucun garde-fou.

---

#### F538 — Aucun CHECK `valid_from <= valid_to`

Insertion `valid_from=2026-12-31, valid_to=2026-01-01` accepté → règle qui ne match jamais.

---

#### F539 — `simulate` order_by `(applies_to == 'all').asc()` non portable PostgreSQL → SQLite tests drift

---

#### F540 — `PricingRule.active` colonne ad hoc (pas `SoftDeleteMixin.is_active`)

Convention CaroCorp utilise `is_active`. `delete_pricing_rule` fait `rule.active = False`. Drift convention.

---

#### F541 — Aucun audit log sur create/update/delete (changement de prix = action critique)

---

#### F542 — `target_id` `Integer` au lieu de `BigInteger` (drift `Product.id` BigInteger)

---

#### F543 — `_get_active_rules` recharge à chaque appel (pas de cache Redis sur hot path catalogue)

---

#### F544 — Pas de gestion overlapping rules (deux `applies_to="all"` actives → ordre indéterminé)

---

#### F545 — `PricingTier` pas de `TimestampMixin` (uniquement `tenant_id`)

---

#### F546 — `simulate` duplique la logique de `PricingEngine` (cf. F532)

---

#### F547 — `PricingRuleCreate.tiers: List = []` default vide alors qu'obligatoire pour `tiered`/`volume`

Aucun `model_validator` ne vérifie cette cohérence.

---

### 3.3 P2

#### F548 — Pas de validation `(applies_to, target_id)` couplée (target_id peut être null pour applies_to=product)

#### F549 — Pas de CHECK `min_qty <= max_qty` ni `unit_price_cents >= 0` sur `PricingTier`

#### F550 — Pas de schema Pydantic `PricingTierUpdate` (PATCH tier impossible)

#### F551 — Aucun endpoint `GET /pricing/rules/category/{cat}` (asymétrie avec product)

#### F552 — `simulate` retourne `discount_pct=0` quand `applied_rule None` au lieu de `None` (mensonger)

#### F553 — `PricingRuleResponse.tenant_id` exposé (info disclosure mineure)

#### F554 — String(30) `rule_type` arbitraire ; String(20) `applies_to` arbitraire

---

### 3.4 P3

#### F555 — Comments lignes 18-20 énumèrent les valeurs valides (drift code/comments)

#### F556 — Aucun test d'invariant `engine.apply_rules == simulate.calculate` sur la même règle

#### F557 — `PricingTier.id` Integer (vs Product BigInteger)

---

## 4. Synthèse module 16

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 5 | F530 (÷100 vs ÷10000), F531 (no enum), F532 (cumul vs first), F533 (scope WRITE pour simulate), F534 (category cassé) |
| P1 | 13 | F535 → F547 |
| P2 | 7 | F548 → F554 |
| P3 | 3 | F555 → F557 |
| **Total** | **28** | F530 → F557 |

**Compteur cumulé après module 16** : ≈ 529 + 28 = **557 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : unifier `discount_pct` (F530) — facturation à risque ; fusionner engine+simulate (F532) ; corriger scope simulate (F533) ; câbler category après décision F485.
>
> **Refactor** : `PricingService` unique class (read+simulate+apply), enum DB pour rule_type/applies_to, cache Redis 5 min sur `_get_active_rules`.
