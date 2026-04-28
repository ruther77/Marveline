# Investigation bugs — Produits / Devis / Commandes
Date : 2026-02-25 | Auteur : investigation réelle (lecture code + fichiers routes)

---

## Méthodologie
Chaque bug est documenté avec : fichier exact + ligne + cause racine + solution.

---

## BUG-01 — MaintenancePage : `Produit #NaN` + 500 sur "Ajouter"
**Sévérité : P0**

### Cause racine
`frontend/src/pages/products/MaintenancePage.tsx` L219 :
```ts
const { productId } = useParams({ strict: false }) as { productId: string }
const id = parseInt(productId, 10)
```
La route est `/_app/products/$id/maintenance` → param exposé = **`id`**, pas `productId`.
Résultat : `productId = undefined` → `parseInt(undefined, 10) = NaN`.

Conséquences :
- Titre L235 : `Produit #NaN` (fallback `product?.name ?? \`Produit #${id}\``)
- `AddMaintenanceForm` reçoit `productId={NaN}` → POST `/products/NaN/maintenances` → 422/500

### Solution
Changer L219 `productId` → `id` :
```ts
const { id: productId } = useParams({ strict: false }) as { id: string }
const id = parseInt(productId, 10)
```
Ou plus lisiblement :
```ts
const { id } = useParams({ strict: false }) as { id: string }
const productId = parseInt(id, 10)
// puis remplacer toutes les occurrences de `id` par `productId` dans la page
```

---

## BUG-02 — ProductStatesPage : données non rafraîchies / "Aucun article"
**Sévérité : P1**

### Cause racine
`frontend/src/pages/products/ProductStatesPage.tsx` L38-43 :
```ts
const { data: stockDetail, isLoading } = useQuery({
  queryKey: ['product-stock', productId],
  queryFn: () => inventoryApi.getProductStock(productId),
  staleTime: 30_000,  // 30s de cache = les états ne sont pas live
})
```
Problèmes :
1. `staleTime: 30_000` = les données expirent après 30s, sans trigger explicite
2. Aucun bouton de refresh manuel
3. `inventoryApi.getProductStock` doit retourner `{ items: StockItem[] }` — si le backend ne peuple pas `items`, filtered sera toujours vide → "Aucun article dans cet état"

### Vérification backend requise
GET `/inventory/products/{id}/stock` — vérifier que la réponse contient bien le champ `items` (liste de `StockItem` avec leur `status`, `serial_number`, etc.)

### Solution frontend
1. Réduire `staleTime: 0` ou `staleTime: 10_000`
2. Ajouter un bouton RefreshCw dans le header qui appelle `refetch()`
3. Importer `refetch` depuis `useQuery` : `const { data, isLoading, refetch } = useQuery(...)`

---

## BUG-03 — BundleCard transparent en light mode
**Sévérité : P1**

### Cause racine
`frontend/src/components/catalogue/BundleCard.tsx` L16 :
```tsx
<div className="bg-dark-900 rounded-xl border border-dark-700 ...">
```
`bg-dark-900` est une couleur custom du design system définie **uniquement pour le dark mode** dans tailwind.config.js. En light mode, cette classe ne matche rien → fond transparent.

Même problème sur d'autres cards avec `bg-dark-900` ou `bg-dark-800` utilisés comme fond de surface sans fallback light.

### Solution
Utiliser la classe utilitaire `card` (déjà définie dans le design system avec un fond adaptatif), ou ajouter un fond explicite :
```tsx
<div className="card rounded-xl p-4 ...">
```
Ou si on veut garder le contrôle :
```tsx
<div className="bg-white dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-xl ...">
```

**Pages à vérifier pour le même pattern** (bg-dark-800/900 sans dark: prefix en contexte light-mode possible) :
- Modales `CategoryFormModal`, `BundleFormModal`, `ProductFormModal`
- Cards dans `CategoriesPage`, `ProductsPage`

---

## BUG-04 — BundleDetailPage : Prix formule non recalculé après ajout d'articles
**Sévérité : P1**

### Cause racine
`frontend/src/api/queries/useProducts.ts` — `useAddBundleItem` :
```ts
onSuccess: (_r, { bundleId }) => {
  qc.invalidateQueries({ queryKey: queryKeys.bundles.detail(bundleId) })
  // MANQUE : invalidation de la query prix
}
```
La query prix utilise une clé distincte `[...queryKeys.bundles.detail(id!), 'price']`.
Quand on ajoute/supprime un article, le prix n'est pas recalculé.

### Solution
Dans `useAddBundleItem`, `useUpdateBundleItem`, `useRemoveBundleItem` : ajouter :
```ts
qc.invalidateQueries({ queryKey: [...queryKeys.bundles.detail(bundleId), 'price'] })
```

---

## BUG-05 — FormulasPage : pas de redirect vers détail après création
**Sévérité : P1**

### Cause racine
`frontend/src/pages/products/FormulasPage.tsx` — handler submit :
```ts
await create.mutateAsync(payload)
onClose()  // ferme modal, revient sur la liste — pas de redirect
```
L'utilisateur veut être redirigé vers `/products/bundles/$id` après création d'une formule pour pouvoir immédiatement ajouter des articles.

### Solution
Récupérer l'ID de la formule créée et naviguer vers son détail :
```ts
const result = await create.mutateAsync(payload)
onClose()
navigate({ to: '/products/bundles/$id', params: { id: String(result.id) } })
```

---

## BUG-06 — `/devis/create` → "Devis introuvable"
**Sévérité : P1**

### Cause racine
Il n'existe pas de route `/devis/create`. La structure de routes est :
- `/_app/devis/new.tsx` → page de création
- `/_app/devis/$id.tsx` → layout paramétré (capture tout segment non connu)

Donc `/devis/create` est capturé par `$id.tsx` avec `$id = 'create'`.
`DevisIdLayout` → `devisId = parseInt('create', 10) = NaN` → `useDevisDetail(null)` → `data = undefined` → message "Devis introuvable".

### Solution
S'assurer que **tous** les boutons et liens utilisant `/devis/create` soient corrigés en `/devis/new` :
- `frontend/src/pages/commandes/CommandesListPage.tsx` L83, L136

---

## BUG-07 — CommandesListPage : route `/devis/create` invalide
**Sévérité : P1** (même cause que BUG-06)

### Cause racine
`frontend/src/pages/commandes/CommandesListPage.tsx` L83 et L136 :
```ts
navigate({ to: '/devis/create' as never })
```
La route correcte est `/devis/new`.

### Solution
```ts
navigate({ to: '/devis/new' })
```

---

## BUG-08 — CollectionDetailPage : actions manquantes
**Sévérité : P1**

### Cause racine
`frontend/src/pages/products/CollectionDetailPage.tsx` ne dispose d'aucune action de gestion :
- Pas de bouton "Modifier" (nom, description, is_active)
- Pas de bouton "Ajouter des produits" à la collection
- Pas de bouton "Supprimer la collection"

Seul `useRemoveProductFromCollection` est importé.

### Solution
Implémenter en deux temps :
1. **Bouton "Modifier"** → modal ou inline edit avec `useUpdateCollection`
2. **Bouton "Ajouter produits"** → `CataloguePickerModal` existant (déjà dans `/components/catalogue/CataloguePickerModal.tsx`) → `useAddProductToCollection`
3. **Bouton "Supprimer"** → confirmation + `useDeleteCollection` → redirect `/products/collections`

---

## BUG-09 — ProductAuditPage : audit auto-généré non différencié
**Sévérité : P2**

### Cause racine
`frontend/src/pages/products/ProductAuditPage.tsx` — tous les logs s'affichent identiquement, qu'ils soient auto-générés (création produit, mise à jour système) ou manuels (actions utilisateur).

### Solution
Si le backend retourne un champ `is_auto: boolean` ou `source: 'system' | 'user'` dans l'objet log, ajouter un badge :
```tsx
{log.is_auto && (
  <span className="text-[10px] bg-dark-700 text-dark-400 px-1.5 py-0.5 rounded">Auto</span>
)}
```
**À vérifier d'abord** : structure exacte de `AuditLog` côté backend.

---

## BUG-10 — ProductPhotosPage : affiche "Aucune photo" malgré photos existantes
**Sévérité : P1**

### Cause racine à investiguer
Le frontend est structurellement correct. `useProductImages(productId)` appelle GET `/products/{id}/images`.

Piste 1 : L'URL stockée dans `img.url` est un chemin relatif (`/uploads/...`) qui n'est pas résolu correctement par nginx en production.
Piste 2 : L'upload via `api.post<ProductImage>(\`/products/${productId}/images\`, form)` utilise un `FormData` — vérifier que `fetchClient` envoie bien `Content-Type: multipart/form-data`.

### Vérification
```bash
curl -s http://localhost:8001/api/v1/products/1/images -H "Authorization: Bearer TOKEN"
```
Si retourne tableau non vide → bug URL/rendu frontend.
Si retourne tableau vide → bug upload (fichier non sauvegardé) ou tenant isolation.

---

## BUG-11 — ProductAvailabilityCalendarPage : tout "disponible"
**Sévérité : P1**

### Cause racine probable
`getDayStatus` → si `totalQty = 0` ET `reserved = 0` → retourne `'available'`.
Mais si `availability?.total_quantity` est `0` ou `undefined`, **tout** est "disponible" car `reserved >= total` ne peut jamais être vrai.

Vérification : GET `/products/{id}/availability?from=...&to=...` doit retourner `total_quantity > 0` pour les produits avec stock.

### Solution frontend (défensive)
```ts
if (totalQty === 0) return 'past'  // ou un nouvel état 'no_stock'
```

---

## BUG-12 — Devis "Voir détail" comportement bizarre
**Sévérité : P2**

### À confirmer
Le bouton est dans un menu contextuel. L'action fait `setOpenMenuId(null)` puis `navigate()`. Le comportement "bizarre" peut être dû à la fermeture du menu qui déclenche un `onBlur` ou `onClickOutside` qui entre en conflit avec le navigate.

### Investigation
Lire `DevisListPage.tsx` complet pour voir comment le menu se ferme.

---

## Plan d'exécution

### Sprint 1 — P0 (immédiat)
- [x] BUG-01 : Fix `useParams` dans `MaintenancePage` (`productId` → `id`)

### Sprint 2 — P1 (cette session)
- [x] BUG-06+07 : Fix `/devis/create` → `/devis/new` dans `CommandesListPage`
- [x] BUG-03 : Fix `BundleCard` transparent en light mode
- [x] BUG-04 : Fix invalidation query prix dans `useProducts.ts`
- [x] BUG-05 : Fix redirect après création formule (onCreated → ré-ouvre en mode édition)
- [x] BUG-02 : Fix staleTime 10s + bouton RefreshCw dans `ProductStatesPage`
- [x] BUG-08 : Implémenter actions Edit/Delete/AddProducts dans `CollectionDetailPage`

### Sprint 3 — P1 à vérifier backend
- [ ] BUG-10 : Vérifier upload photos (URL + multipart)
- [ ] BUG-11 : Vérifier endpoint availability retourne `total_quantity` correct

### Sprint 4 — P2
- [ ] BUG-09 : Badge "Auto" dans `ProductAuditPage`
- [ ] BUG-12 : Confirmer bug "Voir détail" devis
