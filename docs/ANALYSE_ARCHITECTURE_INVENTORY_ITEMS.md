# Analyse Architecture — Inventory Movement Items

**Date**: 2026-02-16
**Contexte**: Erreur détectée lors de l'écriture des tests frontend API
**Sévérité**: 🟠 Incohérence architecturale (non bloquante mais à corriger)

---

## Problème Identifié

### Incohérence RESTful dans les endpoints items

| Action | Endpoint actuel | Pattern |
|--------|----------------|---------|
| **Add item** | `POST /inventory-movements/{movement_id}/items` | **Nested** (movement_id dans URL) |
| **Update item** | `PATCH /inventory-movements/items/{item_id}` | **Flat** (pas de movement_id) |
| **Delete item** | `DELETE /inventory-movements/items/{item_id}` | **Flat** (pas de movement_id) |

Le backend **mélange deux approches** :
- POST utilise une **nested resource** (RESTful classique)
- PATCH/DELETE utilisent une **flat resource** (pragmatique mais incohérent)

---

## Analyse Détaillée

### Code Backend

**Fichier**: `app/api/v1/endpoints/inventory_movements.py`

```python
# Ligne 263 — POST (nested)
@router.post("/{movement_id}/items", ...)
def add_item(movement_id: int, data: MovementItemCreate, ...):
    service.add_item(movement_id=movement_id, tenant_id=current_user.tenant_id, ...)

# Ligne 297 — PATCH (flat)
@router.patch("/items/{item_id}", ...)
def update_item(item_id: int, data: MovementItemUpdate, ...):
    service.update_item(item_id=item_id, tenant_id=current_user.tenant_id, ...)

# Ligne 328 — DELETE (flat)
@router.delete("/items/{item_id}", ...)
def remove_item(item_id: int, ...):
    service.remove_item(item_id, current_user.tenant_id)
```

### Vérification Sécurité

✅ **Isolation multi-tenant OK** :
- `update_item` (ligne 440) : `item_repo.get_by_id(item_id, tenant_id)` → Vérifie ownership
- `remove_item` (ligne 467) : idem
- Pas de faille sécurité, mais incohérence d'API design

### Code Frontend

**Fichier**: `frontend/src/api/inventory.ts`

```typescript
// Ligne 110-126 — addItem (nested)
addItem: async (movementId: number, item: {...}) => {
  const { data } = await apiClient.post(
    `/inventory-movements/${movementId}/items`,  // ← movement_id dans URL
    item
  )
  return data.data || data
},

// Ligne 128-141 — updateItem (flat)
updateItem: async (itemId: number, item: {...}) => {
  const { data } = await apiClient.patch(
    `/inventory-movements/items/${itemId}`,  // ← PAS de movement_id dans URL
    item
  )
  return data.data || data
},

// Ligne 143-145 — removeItem (flat)
removeItem: async (itemId: number) => {
  await apiClient.delete(`/inventory-movements/items/${itemId}`)
},
```

---

## Impact & Conséquences

### Problèmes causés

1. **Confusion développeur**
   Pourquoi POST nécessite `movement_id` dans l'URL mais pas PATCH/DELETE ?
   → Développeur doit mémoriser deux patterns différents

2. **Incohérence RESTful**
   REST convention : si une ressource est **nested**, toutes ses opérations doivent l'être
   → Actuel : POST nested, PATCH/DELETE flat = violation de convention

3. **Symétrie brisée**
   Comparaison avec autres endpoints inventory-movements :
   - `POST /{id}/complete` → nested ✅
   - `POST /{movement_id}/items` → nested ✅
   - `PATCH /items/{item_id}` → flat ❌ (incohérent)

4. **Tests frontend**
   Erreur détectée lors de l'écriture de `inventory.test.ts` :
   - Test écrit avec pattern nested (attendu)
   - Implémentation utilise pattern flat (réel)
   - → Test échoue, révèle l'incohérence

---

## Solutions Proposées

### Option A : Nested Resource (Recommandé ✅)

**Avantage** : RESTful pur, cohérent avec POST existant
**Changements** : Modifier PATCH/DELETE pour inclure movement_id

```diff
  POST   /inventory-movements/{movement_id}/items          ← Inchangé
- PATCH  /inventory-movements/items/{item_id}
+ PATCH  /inventory-movements/{movement_id}/items/{item_id}  ← CORRIGER
- DELETE /inventory-movements/items/{item_id}
+ DELETE /inventory-movements/{movement_id}/items/{item_id}  ← CORRIGER
```

**Backend** (2 lignes à modifier) :
```python
# inventory_movements.py ligne 297
@router.patch("/{movement_id}/items/{item_id}", ...)
def update_item(movement_id: int, item_id: int, ...):
    # Service peut ignorer movement_id si item_id suffit (déjà vérifié par tenant_id)
    # OU vérifier que item.movement_id == movement_id (validation stricte)
    ...

# inventory_movements.py ligne 328
@router.delete("/{movement_id}/items/{item_id}", ...)
def remove_item(movement_id: int, item_id: int, ...):
    ...
```

**Frontend** (2 méthodes à modifier) :
```typescript
// inventory.ts
updateItem: async (movementId: number, itemId: number, item: {...}) => {
  const { data } = await apiClient.patch(
    `/inventory-movements/${movementId}/items/${itemId}`,
    item
  )
  return data.data || data
},

removeItem: async (movementId: number, itemId: number) => {
  await apiClient.delete(`/inventory-movements/${movementId}/items/${itemId}`)
},
```

---

### Option B : Flat Resource (Alternative)

**Avantage** : Pragmatique, item_id suffit (tenant_id vérifié)
**Inconvénient** : Moins RESTful, nécessite de renommer POST

```diff
- POST   /inventory-movements/{movement_id}/items
+ POST   /inventory-movement-items  (movement_id dans body)  ← CORRIGER
  PATCH  /inventory-movement-items/{item_id}                 ← Renommer
  DELETE /inventory-movement-items/{item_id}                 ← Renommer
```

**Rejet** : Nécessite plus de changements (3 routes au lieu de 2), moins standard.

---

## Recommandation Finale

### ✅ Adopter Option A (Nested Resource)

**Raisons** :
1. **RESTful standard** : Convention largement adoptée
2. **Cohérence** : POST déjà nested, continuer dans cette direction
3. **Explicite** : URL indique clairement la hiérarchie parent/child
4. **Moindre changement** : 2 routes backend + 2 méthodes frontend à modifier

**Scope minimal** :
- Backend : `inventory_movements.py` lignes 297, 328 (2 decorators `@router`)
- Frontend : `inventory.ts` lignes 128-145 (2 méthodes updateItem, removeItem)
- Tests backend : Vérifier que tests existants passent avec nouvelle signature
- Tests frontend : `inventory.test.ts` déjà écrit avec pattern nested (prêt)

**Breaking change** : ⚠️ OUI (API change)
- Clients existants doivent mettre à jour leurs appels
- Migration : Documenter dans CHANGELOG, incrémenter version API (v1 → v2 ?)
- OU : Supporter les deux patterns temporairement (deprecated warning sur flat)

---

## Vérification Multi-Tenant

✅ **Sécurité préservée** :
- `MovementService.update_item()` ligne 440 : `item_repo.get_by_id(item_id, tenant_id)`
- `MovementService.remove_item()` ligne 467 : idem
- Même après correction nested, `tenant_id` vérifié → Pas de régression sécurité

✅ **Tests anti-cross-tenant** :
- À vérifier : `tests/security/test_multi_tenant_isolation.py`
- Doit inclure tests pour updateItem/removeItem avec tenant_id différent → 404

---

## Action Items

### P1 — Correction Architecture (breaking change)

1. **Backend** : Modifier routes PATCH/DELETE pour nested pattern
   - Fichier : `app/api/v1/endpoints/inventory_movements.py` lignes 297, 328
   - Ajouter paramètre `movement_id: int` dans signature
   - Service peut ignorer movement_id (item_id + tenant_id suffisent)
   - OU validation stricte : vérifier `item.movement_id == movement_id`

2. **Frontend** : Modifier signatures updateItem/removeItem
   - Fichier : `frontend/src/api/inventory.ts` lignes 128-145
   - Ajouter paramètre `movementId` en premier argument
   - Mettre à jour endpoints vers pattern nested

3. **Tests frontend** : Vérifier que `inventory.test.ts` passe
   - Test déjà écrit avec pattern nested (prêt pour migration)
   - Doit passer après correction backend/frontend

4. **Tests backend** : Vérifier isolation multi-tenant
   - Fichier : `tests/security/test_multi_tenant_isolation.py`
   - Ajouter si manquant : tests updateItem/removeItem cross-tenant → 404

5. **Documentation** : CHANGELOG + migration guide
   - Breaking change v1 → v2 (ou deprecated warning v1)
   - Exemples avant/après pour clients existants

### P2 — Complétion (après P1)

6. **Audit global** : Vérifier autres endpoints pour incohérences similaires
   - Chercher pattern : POST nested + PATCH/DELETE flat ailleurs dans le codebase
   - Appliquer correction uniforme si trouvé

---

## Leçon Apprise

> **"Les tests révèlent les incohérences d'architecture"**

L'erreur dans `inventory.test.ts` n'était pas un bug de test, mais un **symptôme d'incohérence architecturale**.

**Avant** : Code fonctionnel mais incohérent (pas de tests → incohérence invisible)
**Après** : Tests écrits → incohérence détectée → correction architecture → codebase cohérent

**Principe** : Ne jamais corriger un test sans analyser pourquoi il échoue.
Si le test échoue parce que l'architecture est incohérente, corriger l'architecture, pas le test.

---

**Analyse effectuée le** : 2026-02-16
**Fichiers analysés** :
- `app/api/v1/endpoints/inventory_movements.py`
- `app/services/inventory_movement.py`
- `frontend/src/api/inventory.ts`
- `frontend/src/api/__tests__/inventory.test.ts`

**Next steps** : Décision utilisateur sur timing correction (immédiat vs planifié)
