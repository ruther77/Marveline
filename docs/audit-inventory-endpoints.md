# Audit Endpoints Inventory Movements
**Date**: 2026-02-16
**Tâche**: #59 - Auditer usage actuel endpoints inventory items
**Objectif**: Documenter l'état actuel avant refactoring (si nécessaire)

---

## Résumé Exécutif

**DÉCOUVERTE MAJEURE**: Les endpoints items sont **DÉJÀ en structure nested** dans le backend !
La tâche #60 "Refactor backend endpoints inventory items en nested" semble déjà implémentée.

**PROBLÈME IDENTIFIÉ**: L'endpoint `/inventory-movements/agenda` est appelé par le frontend mais **n'existe PAS** dans le backend.

---

## Backend - État Actuel

### Fichier: `app/api/v1/endpoints/inventory_movements.py` (359 lignes)

**Endpoints principaux (mouvements)**:
- ✅ `GET /inventory-movements` - Liste paginée avec filtres (ligne 35)
- ✅ `GET /inventory-movements/late` - Mouvements en retard (ligne 69)
- ✅ `GET /inventory-movements/pending-inspections` - Inspections pending (ligne 82)
- ✅ `GET /inventory-movements/statistics` - Statistiques (ligne 95)
- ❌ `GET /inventory-movements/agenda` - **N'EXISTE PAS** (appelé par frontend)
- ✅ `GET /inventory-movements/{id}` - Détails (ligne 115)
- ✅ `POST /inventory-movements` - Création (ligne 127)
- ✅ `PATCH /inventory-movements/{id}` - Update (ligne 161)
- ✅ `DELETE /inventory-movements/{id}` - Soft delete (ligne 200)
- ✅ `PATCH /inventory-movements/{id}/complete` - Marquer complété (ligne 225)

**Endpoints items (DÉJÀ nested !)**:
- ✅ `POST /inventory-movements/{movement_id}/items` - Ajouter item (ligne 252)
  - Permission: `INVENTORY_WRITE`
  - Service: `MovementService.add_item()`
  - Schéma: `MovementItemCreate` → `MovementItemResponse`

- ✅ `PATCH /inventory-movements/{movement_id}/items/{item_id}` - Update item (ligne 286)
  - Permission: `INVENTORY_WRITE`
  - Service: `MovementService.update_item()`
  - Validation: Vérifie que `item.movement_id == movement_id` (ligne 306)

- ✅ `DELETE /inventory-movements/{movement_id}/items/{item_id}` - Supprimer item (ligne 324)
  - Permission: `INVENTORY_WRITE`
  - Service: `MovementService.remove_item()`
  - Validation: Vérifie que `item.movement_id == movement_id` (ligne 344)

**Permissions utilisées**:
- Lecture: `get_current_user` (tous peuvent lire leurs mouvements tenant)
- Écriture: `require_permission(Permission.INVENTORY_WRITE)`

**Schémas utilisés** (`app/schemas/inventory_movement.py`):
- `MovementCreate`, `MovementUpdate`, `MovementResponse`, `MovementListItem`
- `MovementItemCreate`, `MovementItemUpdate`, `MovementItemResponse`
- `MovementStatistics`

---

## Frontend - État Actuel

### Fichier: `frontend/src/api/inventory.ts` (148 lignes)

**Appels API** (via `apiClient`):
```typescript
// Mouvements
getMovements()        → GET /inventory-movements (pagination)
getLateMovements()    → GET /inventory-movements/late
getPendingInspections() → GET /inventory-movements/pending-inspections
getAgenda()           → GET /inventory-movements/agenda ❌ N'EXISTE PAS
getStatistics()       → GET /inventory-movements/statistics
getMovement(id)       → GET /inventory-movements/{id}
createMovement()      → POST /inventory-movements
updateMovement()      → PATCH /inventory-movements/{id}
deleteMovement()      → DELETE /inventory-movements/{id}
completeMovement()    → PATCH /inventory-movements/{id}/complete

// Items (DÉJÀ nested)
addItem(movementId, item)     → POST /inventory-movements/{movementId}/items
updateItem(movementId, itemId, item) → PATCH /inventory-movements/{movementId}/items/{itemId}
removeItem(movementId, itemId) → DELETE /inventory-movements/{movementId}/items/{itemId}
```

**Types TypeScript** (`frontend/src/types/inventory.ts`, 130 lignes):
- `MovementType`, `MovementStatus`, `DeliveryMethod`, `InspectionStatus`, `ItemCondition`
- `MovementItem` (interface ligne 11-23)
- `InventoryMovement` (interface ligne 25-57)
- `InventoryMovementListItem`, `AgendaItem`, `AgendaView`, `MovementStats`
- `CreateMovementRequest`, `UpdateMovementRequest`

---

## Usages dans UI

**Pages identifiées** (via Grep):
1. `src/pages/inventory/MovementsPage.tsx` - Liste principale mouvements
2. `src/pages/inventory/components/MovementFormModal.tsx` - Formulaire création/édition
3. `src/pages/inventory/components/MovementDetailModal.tsx` - Détails mouvement
4. `src/pages/inventory/components/MovementDeleteModal.tsx` - Confirmation suppression
5. `src/pages/agenda/AgendaPage.tsx` - **Utilise `getAgenda()`** ❌
6. `src/pages/agenda/AgendaMobilePage.tsx` - **Utilise `getAgenda()`** ❌

**Tests frontend**:
- `src/api/__tests__/inventory.test.ts` - Tests unitaires API calls

---

## Analyse de Discordance

### ✅ Endpoints DÉJÀ en structure nested
Les endpoints items utilisent DÉJÀ la structure nested recommandée:
- `POST /inventory-movements/{movement_id}/items`
- `PATCH /inventory-movements/{movement_id}/items/{item_id}`
- `DELETE /inventory-movements/{movement_id}/items/{item_id}`

**Validation de cohérence**:
- Ligne 306: `if item.movement_id != movement_id` (update)
- Ligne 344: `if item.movement_id != movement_id` (delete)

**Conclusion**: ✅ Pas de refactoring backend nécessaire, la structure est déjà conforme.

### ❌ Endpoint manquant: `/inventory-movements/agenda`

**Problème**:
- Frontend appelle `GET /inventory-movements/agenda` (ligne 64 de `inventory.ts`)
- Utilisé dans `AgendaPage.tsx` et `AgendaMobilePage.tsx`
- **N'existe PAS** dans le backend

**Impact**:
- Erreur 404 lors de l'accès aux pages Agenda
- Fonctionnalité bloquée pour les utilisateurs

**Action requise**:
1. Créer l'endpoint backend `GET /inventory-movements/agenda`
2. OU supprimer les appels frontend si la feature n'est pas prioritaire
3. OU utiliser un endpoint existant (ex: `/inventory-movements/statistics`)

---

## Recommandations

### 1. Mettre à jour Task #60 ✅
**Titre actuel**: "Refactor backend endpoints inventory items en nested"
**Nouveau statut**: DÉJÀ FAIT - Marquer comme `completed`
**Raison**: Les endpoints sont déjà nested depuis leur création.

### 2. Créer endpoint `/agenda` OU cleanup frontend ⚠️
**Option A**: Implémenter backend
```python
@router.get("/agenda", response_model=AgendaView)
def get_agenda(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgendaView:
    """Retourne la vue agenda avec départs/retours par événement."""
    service = MovementService(db)
    # Implémenter logique
```

**Option B**: Supprimer du frontend si non utilisé
- Retirer `getAgenda()` de `inventory.ts`
- Adapter `AgendaPage.tsx` et `AgendaMobilePage.tsx`

### 3. Valider tests existants 📋
- Vérifier que `src/api/__tests__/inventory.test.ts` couvre items nested
- Ajouter tests backend pour validation `item.movement_id != movement_id`

### 4. Documentation API 📝
- Vérifier que OpenAPI spec (`frontend/openapi.json`) reflète structure nested
- Ajouter exemples dans docstrings

---

## Fichiers Concernés

**Backend**:
- ✅ `app/api/v1/endpoints/inventory_movements.py` (359 lignes)
- `app/services/inventory_movement.py` (MovementService)
- `app/schemas/inventory_movement.py` (schémas Pydantic)
- `app/repositories/inventory_movement.py` (probablement)
- `app/models/inventory_movement.py` (probablement)

**Frontend**:
- ✅ `frontend/src/api/inventory.ts` (148 lignes)
- ✅ `frontend/src/types/inventory.ts` (130 lignes)
- ⚠️ `frontend/src/pages/agenda/AgendaPage.tsx` (appelle `/agenda`)
- ⚠️ `frontend/src/pages/agenda/AgendaMobilePage.tsx` (appelle `/agenda`)
- `frontend/src/pages/inventory/MovementsPage.tsx`
- `frontend/src/pages/inventory/components/MovementFormModal.tsx`
- `frontend/src/pages/inventory/components/MovementDetailModal.tsx`
- `frontend/src/pages/inventory/components/MovementDeleteModal.tsx`
- `frontend/src/api/__tests__/inventory.test.ts`

**Total estimé**: ~12 fichiers

---

## Conclusion

**État actuel**: ✅ Structure nested DÉJÀ implémentée
**Problème bloquant**: ❌ Endpoint `/agenda` manquant
**Action immédiate**: Décider du sort de `/agenda` (implémenter OU retirer)
**Tasks à mettre à jour**:
- #60: Marquer comme completed (déjà fait)
- #61: Ajuster scope (pas de refactor API nécessaire, juste cleanup `/agenda`)
- #62: Idem
- #63: Idem (pas d'endpoints dépréciés à supprimer)

**Prochaine étape recommandée**: Consulter utilisateur sur priorité endpoint `/agenda`.
