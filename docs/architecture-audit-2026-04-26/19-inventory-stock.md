# Module 19 — Inventory / StockItem (Marveline)

> **Phase C.** Audit du système stock individuel par unité physique : `StockItem`, `InventoryMovement`, `MovementItem`, `MovementItemUnit`, `MovementDamage`, opérations reserve_n/release_n/transition_n, workflow départ/retour.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/stock_item.py` | 103 |
| `app/models/inventory_movement.py` | 295 |
| `app/models/movement_item_unit.py` | 103 (parcours) |
| `app/models/movement_damage.py` | 97 (parcours) |
| `app/models/stock_management.py` | 118 (parcours) |
| `app/services/inventory_movement.py` | 841 (parcours sections) |
| `app/services/stock_item.py` | 158 (parcours) |
| `app/repositories/stock_item.py` | 511 |
| `app/repositories/inventory_movement.py` | 555 (parcours) |
| `app/api/v1/endpoints/inventory_movements.py` | 406 (parcours) |
| `app/api/v1/endpoints/stock_management.py` | 536 (parcours) |
| `app/schemas/inventory_movement.py` | 330 (parcours) |
| `app/schemas/stock_management.py` | 121 (parcours) |

**Volume total** : ~4 175 LoC.

---

## 2. Architecture observée

```
StockItem (1 unité physique)
  status FSM : available → reserved → on_location → (available | damaged) → ...
                                                     ↓
                                                  in_repair → available
                                                     ↓
                                                  retired (terminal)
  current_reservation_id : FK reservations (SET NULL)
  variant_id : FK product_variants (RESTRICT)

InventoryMovement (départ/retour)
  type : departure | return  (CHECK 2 valeurs)
  status : scheduled → in_transit → completed | late | cancelled

MovementItem (ligne d'un mouvement)
  ↓ 1:N
MovementItemUnit (lien vers stock_item physique)

Trois sources de stock :
  ▸ products.available_quantity (mod 15 — colonne dénormalisée)
  ▸ SUM(product_variants.available_quantity) (mod 15 — sync)
  ▸ stock_items.status='available' (mod 19 — réalité physique)
  cf. F497 (mod 15) — drift garanti
```

---

## 3. Frictions identifiées — module 19

> Compteur cumulé (mod. 01-18) ≈ 639. Module 19 ouvre à **F640**.

### 3.1 P0

#### F640 — `StockItem` FSM **non gardée** par le code (CHECK seul, pas de guards transition)

**Constat.** `models/stock_item.py:91-100` : CHECK 6 valeurs valides. Docstring l. 28-36 documente les transitions valides. **Mais** `repositories/stock_item.py:263-279` (`transition_status`) accepte **n'importe quel `new_status`** :

```python
def transition_status(self, stock_item_id: int, new_status: str, tenant_id: int) -> StockItem:
    item = self.db.query(StockItem)...
    item.status = new_status   # ← pas de vérification transitions
```

L'API stock_management permet probablement de passer un item directement de `retired` → `available`. Les transitions `available → on_location` (sans passer par `reserved`) sont possibles silencieusement.

**Action** : `STOCK_ITEM_TRANSITIONS` dict + `_assert_transition` (pattern mod. 17 DEVIS_TRANSITIONS).

---

#### F641 — `release_n` sans `reservation_id` libère des items **d'autres réservations** (warning seul)

**Constat.** `repositories/stock_item.py:188-195` (sync) + l. 435-442 (async) :
```python
if reservation_id is not None:
    q = q.filter(StockItem.current_reservation_id == reservation_id)
else:
    logger.warning(
        "release_n called without reservation_id ... "
        "— may release items belonging to other reservations"
    )
```

Le commentaire `BUG-FIX 2026-04-25` (cf. mémoire `bug-stock-release-aveugle.md`) a partiellement corrigé en propageant `reservation_id` mais le pattern non-sûr **reste appelable** (signature accepte `None`). Tout call site qui omet le param libère aveuglément.

**Action** : faire `reservation_id` obligatoire (positional) ou raise `ValueError` si None.

---

#### F642 — `transition_n` accepte n'importe quels `(from_status, to_status)` sans matrice FSM

**Constat.** `repositories/stock_item.py:216-261`. Acceptation bouton `damaged → reserved` (incohérent métier) → silence. Test d'invariant absent.

---

#### F643 — `MovementItem.product_id` `Integer` **sans `ondelete`** (default NO ACTION)

`models/inventory_movement.py:214-219`. Cf. F490/F491 (pattern récurrent). Hard-delete d'un produit référencé crash IntegrityError silencieuse.

---

#### F644 — `InventoryMovement.event_id Integer nullable sans FK` — table events EXISTE (mod 24)

**Constat.** `models/inventory_movement.py:54-58` :
```python
event_id: Mapped[Optional[int]] = mapped_column(
    Integer, nullable=True,
    comment="Référence événement (pas de FK)",
)
```

Comment dit "pas de FK" mais `app/models/evenement.py` (à vérifier mod 24) existe. Référence orpheline = pas d'intégrité. Code mort historique ?

---

#### F645 — `auto_generate_departure_movement skip_stock_check=True` repose sur F599 — risque cascade

Cf. F599 mod 18. Si confirm_reservation rate la réservation stock pour cause de race, le movement passe quand même → stock physique négatif au departure.

---

### 3.2 P1

#### F646 — Pas de Celery job `mark_late_movements` (`scheduled → late`)

`MovementStatus.LATE` existe en CHECK (l. 155) mais aucun code n'auto-transite. Manuel obligatoire.

---

#### F647 — `MovementType.DEPARTURE/RETURN` 2 valeurs vs workflow mod 18 référence aussi `EXTRA/INSPECTION/ADJUST` (F617)

Drift entre constantes et code business.

---

#### F648 — `InventoryMovement.scheduled_date: Mapped[str]` typé `str` (annotation)

`models/inventory_movement.py:73-77` : `Mapped[str]` mais `DateTime(timezone=True)`. Bug typing — IDE et mypy raise sur usage `scheduled_date.date()`.

---

#### F649 — Idem `actual_date: Mapped[Optional[str]]` (l. 79)

---

#### F650 — `MovementItem.condition` 4 valeurs (`perfect/good/damaged/missing`) **vs** `Product.condition` 4 valeurs (`neuf/bon/use/hors_service`) — drift sémantique

`damaged` ≠ `use`. `missing` n'existe pas côté Product. Conditions hétérogènes.

---

#### F651 — `StockItem.notes` Text non chiffré (PII commentaires opérationnels)

---

#### F652 — `MovementItem.event_item_id Integer nullable sans FK` (cf. F644 pattern)

---

#### F653 — `MovementDamage` (97 LoC) **vs** `ReservationReturnInspectionItem` (mod. 18) — deux tables tracking dégâts

Si l'opérateur saisit un dégât via inspection retour, est-ce que MovementDamage est aussi écrit ? Probablement non → drift reporting.

---

#### F654 — Pas de notification client à `completed` movement (livraison effective)

`update_reservation_on_movement_complete` (mod 18 F617) traite seulement RETURN. DEPARTURE complete = livré → pas d'email "votre matériel a été livré".

---

#### F655 — `reserve_n` sans variant_id sur produit multi-variants → comportement ambigu

`_variant_filter(None) = None` → toutes variantes mélangées. Si produit a 3 variants (rouge/bleu/vert) et qu'on demande `reserve_n(product_id, 5)` sans variant_id, on prend les 5 premiers IDs sans choix → couleurs aléatoires.

---

#### F656 — `handled_by_user_id` FK accounts.id mais `Reservation.assigned_user_id` Integer sans FK (F613 mod. 18)

Inconsistance dans le même domaine.

---

#### F657 — `MovementItem.product_id Integer` (vs Product.id BigInteger — F668)

---

#### F658 — `damage_fee_cents` (Movement) **vs** `charge_cents` (ReservationReturnInspectionItem mod 18) — duplication

Lequel facture-t-on ? Pas documenté.

---

#### F659 — `MovementItem.quantity_actual nullable=True` — distinction "non inspecté" vs "0 retourné" ambiguë

---

#### F660 — `current_reservation_id ondelete=SET NULL` → item reste en status `reserved` orphelin

Si reservation hard-deleted (rare mais possible), `current_reservation_id=NULL` mais `status='reserved'` → item bloqué jusqu'à correction admin.

---

### 3.3 P2

#### F661 — `StockItem.serial_number` pas UNIQUE — doublons silencieux

#### F662 — `StockItem` pas de `SoftDeleteMixin` — `retired` est un état permanent

#### F663 — Pas d'index `(tenant_id, status)` sur StockItem (dashboards par status)

#### F664 — `_variant_filter` accepte `variant_id IS NULL` items mélangés à `variant_id = X` — comportement opaque

#### F665 — `InventoryMovement.delivery_method` (`delivery/pickup/shipping`) ≠ `Reservation.delivery_method` (`self/carrier/pickup`) — vocabulaire divergent

#### F666 — Pas de schéma Pydantic pour bulk transition stock items

#### F667 — `MovementItem.condition_notes` Text non chiffré (PII)

#### F668 — `MovementItemUnit` 103L pas lu — couplage stock_item probable mais à confirmer

#### F669 — `InventoryMovement.delivery_address` Text alors que `Reservation` a colonnes structurées (`delivery_address` + `delivery_city` + `delivery_postal_code`) — drift

#### F670 — Pas d'audit log structurel sur transitions stock_item

---

### 3.4 P3

#### F671 — `event_id` comment "table events inexistante" obsolète (Evenements existe mod. 24)

---

## 4. Synthèse module 19

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 6 | F640 (FSM stock pas gardée), F641 (release_n aveugle légal), F642 (transition_n libre), F643 (no ondelete product), F644 (event_id no FK), F645 (skip_stock_check cascade F599) |
| P1 | 15 | F646 → F660 |
| P2 | 10 | F661 → F670 |
| P3 | 1 | F671 |
| **Total** | **32** | F640 → F671 |

**Compteur cumulé après module 19** : ≈ 639 + 32 = **671 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) `STOCK_ITEM_TRANSITIONS` matrice + guard `_assert_transition` (F640) ; (2) `release_n` rendre `reservation_id` obligatoire (F641) ; (3) Celery job late_movements (F646) ; (4) `ondelete=RESTRICT` sur MovementItem.product_id (F643).
>
> **Refactor** : unifier vocabulaire condition (Product/MovementItem), trancher drift damage_fee/charge, fixer typing `Mapped[datetime]` au lieu de `Mapped[str]` sur scheduled_date/actual_date.
