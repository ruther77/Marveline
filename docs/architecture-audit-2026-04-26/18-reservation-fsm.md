# Module 18 — Reservation FSM (Marveline)

> **Phase C.** Audit du domaine Reservation : modèle (10 statuts), 8 sous-entités (lines, risks, precheck, extensions, return_inspection, dispute_logs, deposits, invoices), workflow inventory, conversion devis, livraison, retour, litige.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/reservation.py` | 649 (Reservation + ReservationLine + ReservationRisk + ReservationPreCheckItem + ReservationExtension + ReservationReturnInspectionItem + ReservationDisputeLog) |
| `app/models/reservation_version.py` | 40 |
| `app/services/reservation.py` | 1648 (parcours sections clés) |
| `app/services/reservation_workflow.py` | 274 |
| `app/repositories/reservation.py` | 576 (parcours) |
| `app/api/v1/endpoints/reservations.py` | 1016 (parcours) |
| `app/schemas/reservation.py` | 885 (parcours) |

**Volume total** : ~5 100 LoC.

---

## 2. Architecture observée

```
FSM Reservation (10 statuts) :
  draft → confirmed → pre_check → delivered → returned → completed
                  ↓                       ↓               ↓
              confirmed_risk         extended       returned_dispute
                  ↓                       ↓               ↓
                                     (toutes peuvent → cancelled)

Reservation
  ├── ReservationLine (XOR product_id | bundle_id, variant optional)
  ├── ReservationRisk (cascade) — type, severity, blocking
  ├── ReservationPreCheckItem (cascade) — checklist pré-départ
  ├── ReservationExtension (cascade) — prolongation
  ├── ReservationReturnInspectionItem (cascade) — constats good/damaged/missing
  ├── ReservationDisputeLog (cascade) — append-only opened/note/charge/resolved
  ├── Deposits (cascade) — cautions
  ├── Invoices (cascade) — facturation
  └── InventoryMovements (FK) — orchestration stock

ReservationWorkflowService :
  - assert_delivery_guards (acompte + signature)
  - auto_generate_departure_movement
  - update_reservation_on_movement_complete (RETURN only)
  - detect_risks (deposit_missing J-7, overdue_invoice)
```

---

## 3. Frictions identifiées — module 18

> Compteur cumulé (mod. 01-17) ≈ 597. Module 18 ouvre à **F598**.

### 3.1 P0

#### F598 — `Reservation.devis_id Integer nullable=True` **sans FK SQL** (cf. F569 mod. 17)

**Constat.** `models/reservation.py:153-156` :
```python
# FK sans contrainte ORM pour éviter dépendance circulaire devis↔reservations
devis_id: Mapped[Optional[int]] = mapped_column(
    Integer, nullable=True, comment="Devis source (optionnel)"
)
```

Le pattern miroir de F569 mod. 17. Pas d'intégrité référentielle. La résolution proposée (lazy string ref SQLAlchemy) reste possible.

---

#### F599 — `confirm_reservation` réserve le stock **avant** de vérifier signature/acompte → stock bloqué pour rien

**Constat.** `services/reservation.py:481-557` :
```python
# 1. Reserve stock (lignes 499-535)
for line in reservation.lines:
    await self._reserve_stock(...)

# 2. Calcule deposit (l. 542)
# 3. status = CONFIRMED (l. 544)
# 4. _auto_generate_invoice (l. 548)
# 5. auto_generate_departure_movement (l. 552)
```

Aucun `assert_delivery_guards` ici. Les guards sont dans `deliver_reservation` (l. 878). Donc :
- Confirm reserve le stock sans vérifier signature.
- Si client signe jamais → stock immobilisé.
- L'opérateur doit `cancel_reservation` manuellement pour libérer.

**Conséquence** : pour 100 réservations confirmées non signées, 100 lots de matériel bloqués jusqu'au timeout d'expiration manuel.

**Action** : (a) ajouter assert_delivery_guards à confirm OU (b) auto-cancel/release après timeout (Celery `expire_unsigned_reservations`).

---

#### F600 — `_auto_generate_invoice` à la confirmation — facture créée AVANT signature/livraison

**Constat.** `services/reservation.py:548` appelle `_auto_generate_invoice` immédiatement après `status=CONFIRMED`. La facture est générée alors que la livraison n'a pas eu lieu, le client peut encore se rétracter, etc.

Si le client annule → `_cancel_linked_invoices` (l. 946-976) annule la facture si `paid=0`. Mais si l'acompte a déjà été versé (l. 583 `advance_cents = total × 0.40`), la facture ne peut pas être annulée → "credit note needed" log.warning sans action automatique.

**Conséquence** : facturation prématurée + reporting comptable distordu (factures émises pour réservations qui n'auront jamais lieu).

**Action** : générer facture à `delivered` (livraison effective) ou faire factures pré-event distincte (avoir).

---

#### F601 — `confirm_reservation` n'a pas `SELECT FOR UPDATE` (cf. F559 mod. 17)

Double confirm = double reserve_stock = stock négatif. Pattern récurrent.

---

#### F602 — `auto_resolve variant` choisit silencieusement la seule variante existante

**Constat.** `services/reservation.py:507-515` :
```python
if not variant_id and line.product_id:
    variants = await self.variant_repo.list_by_product(line.product_id, tenant_id)
    if len(variants) == 1:
        variant_id = variants[0].id
        line.variant_id = variant_id
```

Si l'admin a créé un produit avec une seule variante après la création de la réservation (sans variant_id), on assigne aveuglément. Si l'admin ajoute une 2e variante avant confirm, on bascule sur erreur "variant_id required" (cf. F506 mod. 15).

**Action** : forcer `variant_id` obligatoire à la création de ligne quand le produit a `>=1` variant.

---

#### F603 — `cancel_reservation` non transactionnelle entre `release_stock` et `status=CANCELLED`

**Constat.** `services/reservation.py:925-944`. Si `release_stock_for_lines` plante au milieu de l'itération, certaines lignes libèrent leur stock, d'autres non, et le status n'est pas mis à jour. Aucun `try/except` rollback explicite.

**Action** : `async with self.db.begin_nested()` pour garantir l'atomicité.

---

#### F604 — `_revert_linked_devis` force `Devis.CONVERTED → ACCEPTED` hors FSM

**Constat.** `services/reservation.py:998` :
```python
devis.status = DevisStatus.ACCEPTED
devis.converted_reservation_id = None
```

`DEVIS_TRANSITIONS` (mod. 17) : `converted → ∅` (terminal). Cette ligne contourne la FSM. Si demain on ajoute un guard `_assert_transition` global, ce code casse.

**Action** : ajouter explicitement la transition `converted → accepted` (sur cancel reservation) dans `DEVIS_TRANSITIONS`.

---

#### F605 — `Reservation.reference UNIQUE` global (pas par tenant) — info disclosure cross-tenant

**Constat.** `models/reservation.py:48-53` :
```python
reference: Mapped[str] = mapped_column(
    String(50), nullable=False, unique=True,
    comment="Référence unique de réservation (RES-2026-0001)"
)
```

Format `RES-YYYY-NNNN` séquentiel par tenant (`generate_reference` interne). Mais la contrainte SQL est **globale** (tenant_id absent). Si tenant A crée `RES-2026-0001` et tenant B veut aussi `RES-2026-0001`, **conflit**.

`_generate_res_reference` (mod. 17 l. 537-553) `WHERE tenant_id=` filtre la recherche, donc tenant B partira aussi de 0001 → IntegrityError → retry max 3.

**Conséquence** : (a) UNIQUE global cause des collisions inutiles tenant↔tenant ; (b) info disclosure : tenant A peut savoir si `RES-2026-0042` existe (404 vs 401) chez un autre tenant via timing.

**Action** : `UniqueConstraint("tenant_id", "reference")` au lieu de `unique=True` global.

---

### 3.2 P1

#### F606 — `tva_rate float` (cf. F509 mod. 15)

`ReservationLine.tva_rate Mapped[float] default=0.20` (l. 423-427). Pattern récurrent.

---

#### F607 — `assigned_user_id Integer nullable sans FK accounts` mais `checked_by`/`inspected_by`/`created_by_extension` ont FK

Inconsistance dans le même fichier (`Reservation.assigned_user_id` l. 235 sans FK ; `ReservationPreCheckItem.checked_by` l. 519 avec FK ; `ReservationExtension.created_by` l. 551 avec FK). Justification "table users supprimée" obsolète depuis IAM v2 (`accounts`).

---

#### F608 — `delivery_zone_id Integer` (cf. F614 mod 15 même pattern)

---

#### F609 — `Reservation.is_archived` flag mais pas de `SoftDeleteMixin` — convention split

Customer/Product/Bundle/Category utilisent `is_active` via `SoftDeleteMixin`. Reservation utilise `is_archived` ad hoc.

---

#### F610 — `Reservation.movements` cascade ORM mais relation `foreign_keys="InventoryMovement.reservation_id"` string — couplage circulaire

---

#### F611 — `_auto_generate_invoice` `try/except 400 "Invoice already exists"` silently skipped

`services/reservation.py:609-616` : warning log mais pas d'erreur visible. Confirm exécuté 2× → 1 invoice. Mais si l'invoice est dans un état non-cancelled, le 2e appel ne fait rien (silencieux).

---

#### F612 — `total_amount_cents` figé à la création — pas recalculé à confirm

Si l'admin modifie une ligne (qty, price) entre `create` et `confirm`, le total ne reflète pas. Aucun recalcul à `confirm_reservation`.

---

#### F613 — `_calculate_deposit` lit `tenant_settings.deposit_rate` ou default `0.40` (à confirmer mod 09)

Cohérent avec `advance_rate=0.40` mais magic number Marveline-specific.

---

#### F614 — `_notify_reservation_confirmed` Celery `try/except` silencieux

`services/reservation.py:786-798`. Si Celery broker down, notification perdue silencieusement (logger.exception OK mais pas de retry visible).

---

#### F615 — `_generate_precheck_items` lazy load `bundle.items` → N+1 sur grosses résa

Pour une résa avec 5 bundles × 10 items chacun, 5 SELECT supplémentaires.

---

#### F616 — `auto_generate_departure_movement skip_stock_check=True` — risque latent

`services/reservation_workflow.py:170` skip car "déjà réservé". Si pour une raison quelconque la première reserve ne s'est pas faite (race + ignored exception), le movement passe quand même → stock négatif au departure.

---

#### F617 — `update_reservation_on_movement_complete` ne gère que `RETURN` (pas EXTRA, INSPECTION, ADJUST)

Workflow incomplet. Si on ajoute un type movement, status reservation ne suit pas.

---

#### F618 — `detect_risks` hardcoded 7 jours (`days_until <= 7`)

Pas configurable. Tenant Splendid pourrait vouloir J-14.

---

#### F619 — `start_precheck` accepte aussi statut `pre_check` (re-entry no-op) — ambiguïté FSM

`services/reservation.py:715` "Required: confirmed or pre_check". Idempotence partielle.

---

#### F620 — `cancel_reservation` n'invalide pas les `Deposits` (uniquement `Invoices`)

`services/reservation.py:937 _cancel_linked_invoices` mais aucun `_release_held_deposits`. Une caution `held` reste active après annulation → fonds bloqués sur compte client jusqu'à action manuelle.

---

#### F621 — `ReservationStatus` 10 valeurs vs `DevisStatus` 9 — drift cross-domain

Ne sont pas comparables 1:1. Documenter les correspondances.

---

#### F622 — `ReservationRisk.severity String(20)` libre, pas d'enum CHECK

Un admin peut insérer `severity="critical"` ou `"CRITIQUE"` ou `"high"` indifféremment.

---

#### F623 — `event_date NOT NULL` mais devis-converted peut transmettre fallback `delivery_date` (mod 17)

Si l'admin oublie event_date sur le devis, fallback `event_date = delivery_date`. Ces deux champs ont des sémantiques différentes.

---

### 3.3 P2

#### F624 — `ReservationReturnInspectionItem` pas de `tenant_id` cross-validation sur `reservation_line_id`

#### F625 — `ReservationDisputeLog` 4 actions hardcoded `opened/note_added/charge_applied/resolved`

#### F626 — `Reservation.delivery_postal_code String(20)` (cf. F474)

#### F627 — `Reservation.event_type` 4 valeurs documentées en comment mais aucun CHECK

#### F628 — `Reservation.notes` Text non chiffré (PII)

#### F629 — `ReservationExtension.created_at server_default="NOW()"` string (vs `func.now()`)

#### F630 — Pas de schema OpenAPI pour la matrice de transitions FSM

#### F631 — `_cancel_linked_invoices` warning "credit note needed" mais aucune action automatique

#### F632 — `amend_reservation _in_amend bypass guards` flag non typé (anti-pattern)

#### F633 — `assigned_user_id` index présent mais pas de filtre par membership

#### F634 — `ReservationLine.bundle.items` ne valide pas le tenant_id propagé

#### F635 — Pas d'index `(tenant_id, status, event_date)` pour dashboards

---

### 3.4 P3

#### F636 — Format reference `RES-YYYY-NNNN` hardcoded (cf. F595)

#### F637 — `Reservation.invoices cascade="all, delete-orphan"` — soft-delete reservation purgerait les factures (heureusement pas de soft-delete)

#### F638 — `_revert_linked_devis` modifie `devis.notes` par concaténation (pas structuré)

#### F639 — `ReservationDisputeLog` pas exposée en endpoint API GET dispute logs

---

## 4. Synthèse module 18

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 8 | F598 (devis_id no FK), F599 (reserve stock avant guards), F600 (invoice avant signature), F601 (no FOR UPDATE), F602 (variant auto-resolve aveugle), F603 (cancel non atomique), F604 (force-update FSM devis), F605 (reference UNIQUE global) |
| P1 | 18 | F606 → F623 |
| P2 | 12 | F624 → F635 |
| P3 | 4 | F636 → F639 |
| **Total** | **42** | F598 → F639 |

**Compteur cumulé après module 18** : ≈ 597 + 42 = **639 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) `assert_delivery_guards` à confirm OU auto-expire (F599) ; (2) facture déplacée à delivered (F600) ; (3) `FOR UPDATE` confirm (F601) ; (4) variant_id obligatoire à create (F602) ; (5) atomicité cancel (F603) ; (6) ajouter `converted → accepted` à FSM devis (F604) ; (7) `UniqueConstraint(tenant_id, reference)` (F605).
>
> **Refactor** : extraire `ReservationFSM` class avec matrice transitions explicite + tests d'invariants sur chaque transition.
