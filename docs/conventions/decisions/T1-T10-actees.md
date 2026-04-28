# Décisions Actées — T1 à T10

Ces décisions sont **actées et non réversibles** sans processus ADR explicite.

---

## T1 — Montants en Centimes (BigInteger)

**Décision** : Tous les montants monétaires stockés en `BigInteger` centimes.
**Raison** : Éviter les erreurs d'arrondi float en arithmétique financière.
**Impact** : Tous les modèles, schemas, et l'API.
**Règle** : `250 = 2.50€`. Jamais de `Float` ou `Decimal` pour les montants.

---

## T2 — Multi-Tenant Row-Level Isolation

**Décision** : `tenant_id NOT NULL` sur toute table métier. Filtre obligatoire dans tous les repos.
**Raison** : Isolation stricte des données entre clients.
**Impact** : Violation = P0 bloquant.
**Règle** : Index composite `(tenant_id, id)` sur toutes les tables métier.

---

## T3 — Soft Delete via is_active

**Décision** : Jamais de `DELETE` physique. Soft delete via `is_active = False`.
**Raison** : Traçabilité, RGPD (audit trail), intégrité référentielle.
**Impact** : `SoftDeleteMixin` sur tous les modèles. Tous les repos filtrent `is_active == True`.

---

## T4 — Timestamps Automatiques

**Décision** : `created_at` et `updated_at` sur toutes les tables via `TimestampMixin`.
**Raison** : Audit trail, debugging, RGPD.
**Impact** : Tous les nouveaux modèles héritent de `TimestampMixin`.

---

## T5 — Migrations Expand/Contract

**Décision** : Toutes les migrations suivent le pattern expand/contract.
**Raison** : Déploiements sans interruption de service, rollback sûr.
**Impact** : Pas de `DROP COLUMN` direct. CI bloque si migration destructive détectée.

---

## T6 — Exceptions Métier Standardisées

**Décision** : `NotFound` (pas `NotFoundError`, pas `HTTPException`) depuis `app.core.exceptions`.
**Raison** : Cohérence, middleware de traduction HTTP centralisé.
**Impact** : Services lèvent `NotFound` / `BusinessError`. Endpoints ne gèrent pas les 404 manuellement.

---

## T7 — Constantes dans app/constants/

**Décision** : Zéro magic string ou magic number pour les concepts métier.
**Raison** : Maintenabilité, refactoring sûr.
**Impact** : `app/constants/business.py`, `limits.py`, `errors.py`, `security.py`, `http.py`.

---

## T8 — db.flush() Explicite (autoflush=False)

**Décision** : Session de test avec `autoflush=False`. `db.flush()` explicite après toute mutation ORM.
**Raison** : Tests déterministes, comportement prévisible.
**Impact** : Tous les tests d'intégration et tous les repos doivent appeler `db.flush()` après mutation.

---

## T9 — RBAC Backend (Jamais Frontend-Only)

**Décision** : Les vérifications de permissions RBAC sont toujours validées côté backend.
**Raison** : Sécurité — le frontend est untrusted.
**Impact** : `Depends(require_role(...))` ou `Depends(require_permission(...))` sur tous les endpoints sensibles.

---

## T10 — prepare() Obligatoire Avant Édition Python

**Décision** : `mcp__context-engine__prepare(file_path)` avant toute édition de fichier Python.
**Raison** : Prévenir les violations d'architecture (imports circulaires, violations de couches).
**Impact** : Hook PreToolUse bloque les éditions non préparées.
**Exception** : Nouveaux fichiers n'existant pas encore (le hook l'autorise automatiquement).

---

## Décisions Architecturales Spécifiques au Projet

Ces décisions concernent l'état actuel de la base de données Marveline.

### D5 — Champs événement sur reservations
`event_type`, `event_name`, `guest_count` sur la table `reservations` (pas de table séparée `events`).

### D6 — Table stock_items
Tracking individuel par unité de stock. `available_quantity` = cache dénormalisé.

### D7 — Table payments
Multi-paiements par facture. `invoice.paid_amount` = SUM des payments.

### D8 — Table deposits
Cautions avec statuts `held` / `released` / `retained`.

### D10 — Table damage_types
Références de dommages avec FK optionnelle sur `invoice_charges`.

### D11 — Colonne image_url sur product
`image_url VARCHAR(500)` sur la table `product`.
