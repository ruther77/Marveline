# Session P1 Fixes — 2026-02-15

## Objectif
Corriger les 2 premiers bugs P1 identifiés dans l'audit du 2026-02-15.

## Bugs Corrigés

### ✅ C6 — MFA UniqueConstraint (tenant_id, user_id) (P1)

**Problème :**
- Table `mfa_devices` sans contrainte unique sur (tenant_id, user_id)
- Un utilisateur pouvait avoir plusieurs MFADevice actifs
- Risque : confusion, incohérence état MFA, bugs métier

**Solution Implémentée :**
- Ajout `__table_args__` dans model MFADevice avec UniqueConstraint
- Création migration Alembic pour appliquer la contrainte en DB
- Contrainte nommée : `uq_mfa_device_tenant_user`

**Fichiers Modifiés :**
- `app/models/mfa.py` :
  - Ligne 14 : Ajout import `UniqueConstraint`
  - Lignes 33-38 : Ajout `__table_args__` avec contrainte unique

- `alembic/versions/b03b473d5966_add_mfa_unique_constraint_tenant_user.py` (nouveau) :
  - Migration upgrade/downgrade complète

**Validation :**
- ✅ 1183/1183 tests passent
- ✅ Contrainte DB empêche duplicata (tenant_id, user_id)
- ✅ Business rule "one MFA per user per tenant" maintenant appliquée au niveau DB

**Code Ajouté :**
```python
__table_args__ = (
    UniqueConstraint(
        'tenant_id',
        'user_id',
        name='uq_mfa_device_tenant_user'
    ),
)
```

---

### ✅ C7 — Indexes FK Manquants (P1)

**Problème :**
- 6 colonnes Foreign Key sans index explicite
- Risque : requêtes JOIN lentes, scans séquentiels
- Impact : dégradation performances sur tables volumineuses

**Colonnes Concernées :**
1. `bundle_items.bundle_id`
2. `bundle_items.product_id`
3. `categories.parent_id`
4. `reservations.customer_id`
5. `reservation_lines.reservation_id`
6. `reservation_lines.product_id`

**Solution Implémentée :**
- Ajout `index=True` dans les 6 définitions mapped_column
- Création migration Alembic pour créer les 6 indexes en DB
- Nommage convention : `ix_<table>_<column>`

**Fichiers Modifiés :**
- `app/models/bundle.py` :
  - Ligne 125 : `bundle_id` + `index=True`
  - Ligne 132 : `product_id` + `index=True`

- `app/models/category.py` :
  - Ligne 45 : `parent_id` + `index=True`

- `app/models/reservation.py` :
  - Ligne 38 : `customer_id` + `index=True`
  - Ligne 178 : `reservation_id` (ReservationLine) + `index=True`
  - Ligne 186 : `product_id` (ReservationLine) + `index=True`

- `alembic/versions/d40a9721cfa6_add_indexes_on_fk_columns.py` (nouveau) :
  - Migration avec 6 `op.create_index()` / `op.drop_index()`

**Validation :**
- ✅ 1183/1183 tests passent
- ✅ 6 indexes créés en DB
- ✅ Amélioration performances JOIN attendue

**Indexes Créés :**
```sql
CREATE INDEX ix_bundle_items_bundle_id ON bundle_items (bundle_id);
CREATE INDEX ix_bundle_items_product_id ON bundle_items (product_id);
CREATE INDEX ix_categories_parent_id ON categories (parent_id);
CREATE INDEX ix_reservations_customer_id ON reservations (customer_id);
CREATE INDEX ix_reservation_lines_reservation_id ON reservation_lines (reservation_id);
CREATE INDEX ix_reservation_lines_product_id ON reservation_lines (product_id);
```

---

## Résumé

**Effort Total :** ~45 minutes (estimé 45 min dans rapport d'audit)
- C6 : 15 min (réel: ~15 min)
- C7 : 30 min (réel: ~30 min)

**Résultats :**
- ✅ 2/2 bugs P1 corrigés
- ✅ 1183/1183 tests passent
- ✅ Aucune régression introduite
- ✅ 2 migrations Alembic créées
- ✅ Intégrité données améliorée (MFA constraint)
- ✅ Performances JOIN améliorées (6 indexes FK)

**Impact :**
- **Intégrité :** MFA constraint empêche états incohérents
- **Performances :** Indexes FK réduisent temps requêtes JOIN sur tables volumineuses
- **Maintenabilité :** Business rules appliquées au niveau DB (fail-safe)

**Migrations Créées :**
1. `b03b473d5966_add_mfa_unique_constraint_tenant_user.py`
2. `d40a9721cfa6_add_indexes_on_fk_columns.py`

**Prochaines Étapes :**
Session 3 (P1) — Selon plan d'audit :
- D8 : Audit middleware décode JWT 3x (45 min)
- B3 : request_id double génération (30 min)
- C3 : Constants hardcodées 11 emplacements (1h30)
- C10 : Redis keys non préfixées tenant_id (45 min)
- C11 : Cleanup sessions expirées (30 min)
- C13 : soft_delete pas dans BaseRepository (30 min)

---

**Date :** 2026-02-15
**Auteur :** Session de remédiation CaroCorp_new
**Statut :** ✅ Complète
**Tests :** ✅ 1183/1183 pass
