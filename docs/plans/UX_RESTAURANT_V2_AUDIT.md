# UX Restaurant V2 — Audit Phase 0

Date : 2026-04-14
Scope : App Restaurant (backend + frontend) — état actuel
Document parent : `docs/plans/UX_RESTAURANT_V2.md`

---

## 1. Inventaire code

### Backend

| Composant | Fichiers | Lignes |
|-----------|----------|--------|
| Endpoints | 6 (`bar`, `commandes`, `cuisine`, `dashboard`, `historique`, `ingredients`) | 1 201 |
| Services | 14 | 2 157 |
| Modèles | 13 | - |
| Repositories | 13 | - |
| **Tests unitaires** | **0** | **0** |

**Métriques endpoints** :
- 64 endpoints total
- 29 require `restaurant:read`
- 37 require `restaurant:write` (dont 27 mutations POST/PUT/PATCH/DELETE)
- 100 % des endpoints ont `require_scope`

### Frontend

- 47 fichiers `.tsx`/`.ts`
- ~10 946 lignes total
- 12 pages (dont 6 volumineuses > 500 lignes)
- 10 composants

**Pages les plus grosses** :

| Page | Lignes | Commentaire |
|------|--------|-------------|
| `IngredientsPage.tsx` | 1 531 | 🚨 Trop gros, à splitter |
| `CuisinePage.tsx` | 857 | À découper en KDS + filtres |
| `MenuPage.tsx` | 835 | Carte + dispos mélangées |
| `PreparationsPage.tsx` | 727 | Recettes + modales |
| `CataloguePage.tsx` | 572 | |
| `HistoriquePage.tsx` | 459 | |

---

## 2. Bugs identifiés

### 🚨 P0 — ISO-VARSIDE-01 : fuite multi-tenant `VarianteSide`

**Fichier** : `app/repositories/restaurant/variante_side.py`

**Problème** : Les 4 méthodes (`list_by_variante`, `get`, `create`, `delete`) n'appliquent **aucun filtre `tenant_id`** alors que le modèle `VarianteSide` possède la colonne.

**Conséquence** :
- Un tenant A peut **lire** les associations plat↔side du tenant B (fuite donnée)
- Un tenant A peut **créer** un `VarianteSide` attaché à un plat du tenant B (corruption)
- Un tenant A peut **supprimer** des associations du tenant B (destruction croisée)

**Cadre** : viole la règle **A1** (contraintes globales) : "¬ donnée cross-tenant".

**Remédiation** :
```python
# Ajouter partout :
.where(VarianteSide.tenant_id == tenant_id, ...)

# Signature à changer :
async def list_by_variante(self, variante_plat_id: int, tenant_id: int) -> list[dict]
async def get(self, variante_plat_id: int, side_id: int, tenant_id: int) -> Optional[VarianteSide]
async def create(self, tenant_id: int, **kwargs) -> VarianteSide  # force tenant_id
async def delete(self, variante_plat_id: int, side_id: int, tenant_id: int) -> bool
```

**Test anti-régression requis** : test d'isolation cross-tenant (tentative de CRUD cross-tenant → 404 ou erreur).

---

### 🟠 P1 — TEST-RESTO-01 : zéro couverture tests

**Problème** : Le module Restaurant (~3 400 lignes backend) n'a **aucun test unitaire**.

**Impact** :
- Refactoring risqué
- Régressions non détectables
- Cas limites non vérifiés (transitions de statut, race conditions, isolation tenant)

**Remédiation** (minimum) :
- Tests unitaire `CommandeService` (transitions OUVERTE → SERVIE → PAYEE / ANNULEE)
- Tests unitaire `MouvementStockService` (decrement stock + alertes)
- Test intégration isolation tenant (tous les CRUD)
- Test anti-régression pour ISO-VARSIDE-01

---

### 🟠 P1 — FIN-RESTO-01 : aucune intégration Finance

**Problème** : Les ventes Restaurant ne produisent **aucune `FinanceInvoice`**.

**Vérification** :
```
grep "FinanceInvoice" app/services/restaurant/ → 0 résultat
```

**Impact** :
- Pas de réconciliation comptable
- Pas de facturation automatique (hors obligation fiscale France > 150€)
- D2 (décision actée) non implémentée

**Remédiation** : Phase 5c du plan V2 (2-3 j) — implémenter ticket + agrégat.

---

### 🟠 P1 — LOYAL-RESTO-01 : flow fidélité incomplet

**Problème** :
- `LoyaltyScanner` frontend existe et est utilisé dans `OngletPaiement.tsx:135`
- **Mais** : aucun endpoint restaurant n'appelle `/loyalty/ledger/accrue`
- La fidélité passe **directement** du frontend au service loyalty sans validation côté commande

**Conséquence potentielle** :
- Client peut cumuler des points sans avoir réellement payé (si le scan se fait avant la clôture effective)
- Pas d'audit trail lien commande ↔ accrual

**Remédiation** :
- Soit : endpoint `POST /restaurant/commandes/{id}/cloturer` qui inclut `customer_id_fidelite` optionnel → crédite en atomique
- Soit : valider que l'accrual référence bien l'ID de commande et vérifier statut avant

---

### 🟡 P2 — UI-THEME-01 : incohérence thème clair/sombre

**Problème** : mélange `bg-stone-*` (SallePage clair) et `bg-dark-*` (IngredientsPage sombre) dans la même app.

**Fichiers concernés** :
```bash
grep -l "bg-dark-" frontend/apps/restaurant/src/pages/
# → IngredientsPage.tsx (probablement d'autres)
```

**Remédiation** : Phase 6 polish — migration vers thème clair amber unifié.

---

### 🟡 P2 — UI-TOUCH-01 : boutons sous 44×44 sur modal ouverture commande

**Fichier** : `frontend/apps/restaurant/src/pages/SallePage.tsx:62-66`

**Problème** : boutons nombre de couverts en **40×40px** (règle `ui-ux.md` §V : minimum **44×44px** tactile).

**Remédiation** : Phase 3 — refonte SallePage tactile.

---

### 🟡 P2 — UI-SIZE-01 : pages trop volumineuses

Cf. tableau ci-dessus. 6 pages > 500 lignes.

**Remédiation** : Phase 4 — split `IngredientsPage` en composants. Phase 3 — split `CuisinePage` en KDS modulaire.

---

### 🟡 P2 — UI-NAV-01 : role-tabs dupliqués

**Problème** : `SallePage.tsx:11-16` redéfinit `NAV_TABS = [Salle, Cuisine, Stock, Menu]` alors que la sidebar fait déjà le job.

**Remédiation** : Phase 2 — nav adaptative, suppression des tabs internes.

---

### ℹ️ P3 — RBAC-WRITE-01 : frontend ne masque pas les actions write pour staff

**Problème** : le frontend affiche tous les boutons CRUD à tous les utilisateurs. Un `staff` voit "Ajouter plat" et se prend un 403 au clic.

**Remédiation** : Phase 1 — hook `useRestaurantScopes` + `<RequireScope>`.

---

## 3. Intégrations cross-modules — état actuel

| Flow | Backend | Frontend | Opérationnel ? |
|------|---------|----------|----------------|
| **Épicerie → Restaurant (transfert stock)** | ✅ `app/services/epicerie/transfert.py` | ✅ `/epicerie/transferts` | ✅ Fonctionnel |
| **Restaurant → Épicerie (demande transfert)** | ❌ Inexistant | ❌ Pas d'UI | ❌ À créer (Phase 5b) |
| **Restaurant → Loyalty (accrual)** | ⚠️ Via `/loyalty/ledger/accrue` direct | ✅ `LoyaltyScanner` dans `OngletPaiement` | ⚠️ Fonctionne, mais pas wired dans endpoint commande |
| **Restaurant → Finance (ticket)** | ❌ Inexistant | ❌ | ❌ À créer (Phase 5c) |
| **Restaurant → Finance (agrégat journalier)** | ❌ Inexistant (pas de Celery task) | ❌ | ❌ À créer (Phase 5c) |
| **Restaurant ↔ Catalogue produits** | ❌ Tables séparées | - | ❌ À unifier (Phase 5bis) |

---

## 4. Statuts & transitions commande

**Statuts actuels** (`commande_restaurant.py:29`) : `OUVERTE → SERVIE → PAYEE` ou `ANNULEE`

**Transitions à auditer** :
- `OUVERTE → ANNULEE` : qui peut annuler ? (staff ? manager only ?)
- `SERVIE → PAYEE` : trigger loyalty + finance ici
- Pas d'état `PREPARATION` (tracking KDS côté `instance_preparation`)

**À ajouter dans Phase 5c** : hook `after_transition_to_PAYEE` → crée FinanceInvoice ticket + propose scan fidélité.

---

## 5. Décisions d'audit

### Bugs à corriger AVANT refonte UX

**Must fix** (bloque Phase 3+) :
1. **ISO-VARSIDE-01** (P0) — faille multi-tenant 🚨

**Should fix** (parallèle aux phases UX) :
2. **TEST-RESTO-01** (P1) — au minimum tests de non-régression sur ISO-VARSIDE-01
3. **LOYAL-RESTO-01** (P1) — clarifier le flow et ajouter audit trail

**Can fix** (dans les phases de refonte) :
- FIN-RESTO-01 → Phase 5c
- UI-THEME-01 → Phase 6
- UI-TOUCH-01 → Phase 3
- UI-SIZE-01 → Phases 3-4
- UI-NAV-01 → Phase 2
- RBAC-WRITE-01 → Phase 1

### Ordre d'exécution proposé

```
1. Fix P0 ISO-VARSIDE-01 (1-2h) + test non-régression (1h) ← IMMÉDIAT
2. Phase 1 — Fondations rôles (1-2j)
3. Phase 2 — Navigation adaptative (1j)
4. Phase 3 — Service tactile (3-5j)
5. Phase 4 — Gestion (2-3j)
6. Phase 5a/b/c — Intégrations (4-6j)
7. Phase 5bis — Unification catalogue (3-5j) [optionnel, après stabilité]
8. Phase 6 — Polish (2j)
```

---

## 6. Prochaine action

**Corriger immédiatement ISO-VARSIDE-01** :
1. Modifier `app/repositories/restaurant/variante_side.py` (4 méthodes)
2. Modifier les appelants côté service (`app/services/restaurant/variante_side.py`)
3. Modifier les endpoints appelants (`app/api/v1/endpoints/restaurant/commandes.py`)
4. Écrire test d'isolation tenant dans `tests/unit/restaurant/test_variante_side_tenant_isolation.py`
5. Commit avec message explicite : `security(P0): fix cross-tenant leak in VarianteSide repository (ISO-VARSIDE-01)`

Tu veux que je l'attaque maintenant ?
