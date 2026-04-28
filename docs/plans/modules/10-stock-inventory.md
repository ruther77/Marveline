# Module 10 — Stock & Inventaire (Parc)

> Roadmap L1→L5 — Audit réel 2026-02-25 | Source : fichiers lus + grep codebase

---

## État actuel — Synthèse audit

### Architecture réelle

| Composant | Route | Statut |
|-----------|-------|--------|
| `InventoryPage` | `/_app/inventory/stock` | ✅ Vue stock par produit + stock items |
| `MovementsPage` | `/_app/inventory/movements` | ✅ Liste mouvements paginée |
| `PhysicalInventoryPage` | `/_app/inventory/inventaire` | ✅ Inventaire physique |
| `StockAdjustmentsPage` | `/_app/inventory/adjustments` | ✅ Ajustements manuels |
| `StockReorderPage` | `/_app/inventory/reorder` | ✅ Réassort |
| `StockCoveragePage` | `/_app/inventory/coverage` | ✅ Couverture stock |
| `StockItemDetailPage` | `/_app/inventory/stock/$id` | ✅ Fiche unité stock |
| `DamageTypesPage` | `/_app/inventory/damage-types` | ✅ Types de dommages |
| `routes/_app/parc.tsx` | `/_app/parc` | ⚠️ Placeholder → redirige vers `/products` |
| `routes/_app/inventory/stock.tsx` | layout parent stock | ⚠️ `<Outlet />` nu |

**Note architecture** : `routes/_app/parc.tsx` est le point d'entrée de l'onglet bottom nav
"Parc" (SESSION A). Il redirige vers `/products`. La SESSION F prévoit de créer un layout
Parc avec SubNav Catalogue/Stock/Fournisseurs. En attendant, les routes inventory/* sont
accessibles directement mais sans SubNav module.

### Ce qui fonctionne bien

- `InventoryPage` : stock par produit avec `useQueries` batch, filtre statut, `StockItemHistoryModal`
- `MovementsPage` : liste paginée complète (dual view desktop/mobile), filtres type + statut
- `PhysicalInventoryPage` : workflow inventaire physique (démarrer session → saisir → valider)
- `StockAdjustmentsPage` : ajustements manuels avec sélecteur produit
- `StockCoveragePage` : couverture stock avec indicateurs
- `DamageTypesPage` : CRUD complet types de dommages
- Modals : `MovementFormModal`, `MovementDetailModal`, `MovementDeleteModal` ✅

### Anti-patterns identifiés

| ID | Fichier | Problème | Priorité |
|----|---------|----------|----------|
| AP-01 | `routes/_app/inventory/stock.tsx` | Layout `<Outlet />` nu — pas de SubNav module | P0 |
| AP-02 | `InventoryPage.tsx:208` | Loading = `<Spinner>` au lieu de skeleton | P1 |
| AP-03 | `MovementsPage.tsx:268,344` | Loading = texte `"Chargement..."` desktop ET mobile | P1 |
| AP-04 | `StockReorderPage.tsx:84` | Loading = texte `"Chargement…"` | P1 |
| AP-05 | `StockAdjustmentsPage.tsx:179` | Loading = texte `"Chargement…"` | P1 |
| AP-06 | `StockItemDetailPage.tsx:122` | Loading = texte `"Chargement..."` | P1 |
| AP-07 | `DamageTypesPage.tsx:98` | Loading = texte `"Chargement…"` | P1 |
| AP-08 | `StockCoveragePage.tsx:93` | Loading = texte `"Chargement..."` | P1 |
| AP-09 | `StockReorderPage.tsx:48,88,107` | Classes `text-body` non-standard | P2 |
| AP-10 | `StockAdjustmentsPage.tsx:153,183,191` | Classes `text-body` non-standard | P2 |
| AP-11 | `StockItemDetailPage.tsx:100,136,155,161,190,288` | Classes `text-body` non-standard | P2 |
| AP-12 | `PhysicalInventoryPage.tsx:82,106,166` | Classes `text-body` non-standard | P2 |
| AP-13 | `DamageTypesPage.tsx:139,207,241` | Classes `text-body` non-standard | P2 |
| AP-14 | `StockItemHistoryModal.tsx:146` | Classes `text-body` non-standard | P2 |
| AP-15 | `MovementsPage.tsx` | Cards mobile sans `SwipeActions` | P1 |
| AP-16 | `InventoryPage.tsx:19` | `STOCK_DETAIL_LIMIT = 50` — scalabilité limitée > 50 produits | P2 |

---

## Tâches L1→L5

### TASK-STK-01 (P0) — SubNav layout module Stock/Inventaire

**Problème** : `routes/_app/inventory/stock.tsx` est un `<Outlet />` nu. Les 8 pages du
module sont accessibles mais sans navigation entre elles.

**Fichier à modifier** : `frontend/src/routes/_app/inventory/stock.tsx`

```tsx
// routes/_app/inventory/stock.tsx — AVANT
import { createFileRoute, Outlet } from '@tanstack/react-router'
export const Route = createFileRoute('/_app/inventory/stock')({
  component: () => <Outlet />,
})
```

```tsx
// routes/_app/inventory/stock.tsx — APRÈS
import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

const STOCK_NAV = [
  { label: 'Stock',       href: '/inventory/stock' },
  { label: 'Mouvements',  href: '/inventory/movements' },
  { label: 'Inventaire',  href: '/inventory/inventaire' },
  { label: 'Ajustements', href: '/inventory/adjustments' },
  { label: 'Réassort',    href: '/inventory/reorder' },
]

export const Route = createFileRoute('/_app/inventory/stock')({
  component: () => (
    <div className="space-y-0">
      <SubNav items={STOCK_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  ),
})
```

> Note : `DamageTypesPage` (`/inventory/damage-types`) et `StockCoveragePage`
> (`/inventory/coverage`) sont des sous-pages moins fréquentes — les ajouter dans la SubNav
> uniquement si pertinent. Sinon les laisser accessibles via liens contextuels.
>
> Supprimer le padding `p-4 md:p-6` dans les pages individuelles après ajout du wrapper.

**Critères done** :
- ☐ `routes/_app/inventory/stock.tsx` contient SubNav avec 5 onglets
- ☐ Padding `p-4 md:p-6` retiré des pages individuelles
- ☐ `tsc --noEmit` 0 erreur
- ☐ 1582 Vitest pass

---

### TASK-STK-02 (P1) — Skeleton loading InventoryPage

**Problème** : `InventoryPage.tsx:208` affiche `<Spinner size="lg" label="Chargement du stock..." />`.
Règle UI/UX PDF #3 : skeleton obligatoire sur liste L1.

```tsx
function StockRowSkeleton() {
  return (
    <div className="card animate-pulse">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-dark-700 rounded-lg shrink-0" />
          <div className="space-y-1.5">
            <div className="h-4 bg-dark-700 rounded w-36" />
            <div className="h-3 bg-dark-700 rounded w-20" />
          </div>
        </div>
        <div className="h-5 bg-dark-700 rounded-full w-20" />
      </div>
      <div className="flex gap-2">
        <div className="h-7 bg-dark-700 rounded-full w-16" />
        <div className="h-7 bg-dark-700 rounded-full w-16" />
        <div className="h-7 bg-dark-700 rounded-full w-20" />
      </div>
    </div>
  )
}

function InventorySkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 6 }).map((_, i) => <StockRowSkeleton key={i} />)}
    </div>
  )
}

// Remplacer :
// {isLoading ? (<div className="..."><Spinner ... /></div>) : ...}
if (isLoading) return <InventorySkeleton />
```

**Critères done** :
- ☐ Skeleton 6 cards produit avec animate-pulse
- ☐ `<Spinner>` supprimé de `InventoryPage`

---

### TASK-STK-03 (P1) — Skeleton loading MovementsPage

**Problème** : `MovementsPage.tsx` affiche du texte `"Chargement..."` côté desktop (ligne 268,
dans `<td>`) et côté mobile (ligne 344, dans `<p>`).

**Skeleton tableau desktop** :

```tsx
function MovementRowSkeleton() {
  return (
    <tr className="animate-pulse border-b border-dark-700/50">
      <td className="px-4 py-3"><div className="h-4 bg-dark-700 rounded w-8" /></td>
      <td className="px-4 py-3"><div className="h-5 bg-dark-700 rounded-full w-16" /></td>
      <td className="px-4 py-3"><div className="h-4 bg-dark-700 rounded w-28" /></td>
      <td className="px-4 py-3"><div className="h-4 bg-dark-700 rounded w-20" /></td>
      <td className="px-4 py-3"><div className="h-4 bg-dark-700 rounded w-24" /></td>
      <td className="px-4 py-3"><div className="h-4 bg-dark-700 rounded w-16" /></td>
      <td className="px-4 py-3" />
    </tr>
  )
}
```

**Skeleton cards mobile** :

```tsx
function MovementCardSkeleton() {
  return (
    <div className="card animate-pulse space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 bg-dark-700 rounded" />
          <div className="h-4 bg-dark-700 rounded w-20" />
        </div>
        <div className="h-5 bg-dark-700 rounded-full w-16" />
      </div>
      <div className="h-3 bg-dark-700 rounded w-32" />
      <div className="h-3 bg-dark-700 rounded w-24" />
    </div>
  )
}
```

**Critères done** :
- ☐ Desktop : skeleton 8 lignes tableau
- ☐ Mobile : skeleton 6 cards
- ☐ Aucun texte `"Chargement..."` dans `MovementsPage`

---

### TASK-STK-04 (P1) — Skeletons loading pages Stock secondaires

**Problème** : `StockReorderPage`, `StockAdjustmentsPage`, `StockItemDetailPage`,
`DamageTypesPage`, `StockCoveragePage` affichent du texte `"Chargement…"`.

**StockReorderPage** — skeleton liste réassort :

```tsx
function ReorderSkeleton() {
  return (
    <div className="card divide-y divide-dark-700 animate-pulse">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="px-4 py-3 flex items-center justify-between gap-3">
          <div className="flex-1 space-y-1.5">
            <div className="h-4 bg-dark-700 rounded w-40" />
            <div className="h-3 bg-dark-700 rounded w-24" />
          </div>
          <div className="flex items-center gap-3">
            <div className="h-5 bg-dark-700 rounded-full w-14" />
            <div className="h-8 bg-dark-700 rounded-lg w-20" />
          </div>
        </div>
      ))}
    </div>
  )
}
if (isLoading) return <ReorderSkeleton />
```

**StockAdjustmentsPage** — skeleton liste ajustements :

```tsx
function AdjustmentsSkeleton() {
  return (
    <div className="card divide-y divide-dark-700 animate-pulse">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="px-4 py-3 flex items-center justify-between gap-3">
          <div className="space-y-1.5 flex-1">
            <div className="h-4 bg-dark-700 rounded w-36" />
            <div className="h-3 bg-dark-700 rounded w-24" />
          </div>
          <div className="h-4 bg-dark-700 rounded w-16" />
        </div>
      ))}
    </div>
  )
}
if (isLoading) return <AdjustmentsSkeleton />
```

**StockItemDetailPage** — skeleton fiche unité :

```tsx
function StockItemSkeleton() {
  return (
    <div className="max-w-2xl mx-auto space-y-5 animate-pulse">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 bg-dark-700 rounded" />
        <div className="space-y-1.5">
          <div className="h-5 bg-dark-700 rounded w-40" />
          <div className="h-3 bg-dark-700 rounded w-28" />
        </div>
      </div>
      <div className="card space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex justify-between">
            <div className="h-3 bg-dark-700 rounded w-24" />
            <div className="h-3 bg-dark-700 rounded w-32" />
          </div>
        ))}
      </div>
    </div>
  )
}
if (isLoading) return <StockItemSkeleton />
```

**Critères done** :
- ☐ `StockReorderPage` : skeleton liste avec animate-pulse
- ☐ `StockAdjustmentsPage` : skeleton liste avec animate-pulse
- ☐ `StockItemDetailPage` : skeleton fiche avec animate-pulse
- ☐ `DamageTypesPage` : skeleton liste
- ☐ `StockCoveragePage` : skeleton tableau
- ☐ Aucun texte `"Chargement…"` dans ces fichiers

---

### TASK-STK-05 (P1) — SwipeActions mobile MovementsPage

**Problème** : Cards mobile `MovementsPage` naviguent sans swipe. PDF règle #5 :
swipe-right = voir détail, swipe-left = actions secondaires (supprimer).

```tsx
import { SwipeActions } from '@/components/ui/SwipeActions'
import { Eye, Trash2 } from 'lucide-react'

// Remplacer les cards mobiles par :
{items.map((movement) => (
  <SwipeActions
    key={movement.id}
    rightActions={[
      {
        label: 'Supprimer',
        icon: <Trash2 className="w-4 h-4" />,
        color: 'bg-red-500',
        onAction: () => openModal('delete', movement),
      },
    ]}
    leftActions={[
      {
        label: 'Détail',
        icon: <Eye className="w-4 h-4" />,
        color: 'bg-blue-600',
        onAction: () => openModal('details', movement),
      },
    ]}
  >
    <div className="card cursor-pointer" onClick={() => openModal('details', movement)}>
      {/* ... contenu card inchangé */}
    </div>
  </SwipeActions>
))}
```

**Critères done** :
- ☐ Swipe-left → modal détail
- ☐ Swipe-right → confirmation suppression
- ☐ Touch target ≥ 44px hauteur
- ☐ Uniquement sur viewport mobile

---

### TASK-STK-06 (P2) — Normaliser classes `text-body` module Stock

**Problème** : `text-body` utilisé dans de nombreux composants du module.

**Fichiers et occurrences** :
- `StockReorderPage.tsx` : lignes 48, 88, 107
- `StockAdjustmentsPage.tsx` : lignes 153, 183, 191
- `StockItemDetailPage.tsx` : lignes 100, 136, 155, 161, 190, 288
- `PhysicalInventoryPage.tsx` : lignes 82, 106, 166
- `DamageTypesPage.tsx` : lignes 139, 207, 241
- `StockItemHistoryModal.tsx` : ligne 146

**Action** : Supprimer `text-body` (héritage par défaut).

**Critères done** :
- ☐ Aucune occurrence de `text-body` dans le module inventory
- ☐ Rendu visuel identique

---

### TASK-STK-07 (P2) — Extraire constante `STOCK_DETAIL_LIMIT` hardcodée

**Problème** : `InventoryPage.tsx:19` — `const STOCK_DETAIL_LIMIT = 50` est une constante
hardcodée directement dans la page. Au-delà de 50 produits actifs, le stock affiché est tronqué
sans indication à l'utilisateur (scalabilité silencieusement limitée).

```tsx
// InventoryPage.tsx:19 — AVANT
const STOCK_DETAIL_LIMIT = 50
```

**Actions requises** :

1. **Déplacer la constante** vers `frontend/src/constants/inventory.ts` (ou `limits.ts`) :

```ts
// frontend/src/constants/inventory.ts
export const STOCK_DETAIL_LIMIT = 50
```

2. **Importer dans `InventoryPage`** :

```tsx
import { STOCK_DETAIL_LIMIT } from '@/constants/inventory'
```

3. **Ajouter un indicateur** si le résultat est tronqué (optionnel P3) :

```tsx
{products && products.length >= STOCK_DETAIL_LIMIT && (
  <p className="text-center text-xs text-dark-500 pt-2">
    {`Affichage limité à ${STOCK_DETAIL_LIMIT} produits — utilisez le filtre pour affiner`}
  </p>
)}
```

> Note : augmenter la valeur à 200 ou 500 si les performances le permettent, ou implémenter
> une pagination virtuelle si le catalogue dépasse 500 produits actifs.

**Critères done** :
- ☐ `STOCK_DETAIL_LIMIT` déplacée dans `frontend/src/constants/inventory.ts`
- ☐ Import mis à jour dans `InventoryPage.tsx`
- ☐ Aucune constante numérique hardcodée restante dans `InventoryPage`
- ☐ `tsc --noEmit` 0 erreur

---

## Couverture LAYER.html — Mapping final

| Écran LAYER | Route | Composant | Backend | Statut cible |
|------------|-------|-----------|---------|--------------|
| `s-stock` | `/inventory/stock` | `InventoryPage` | `GET /products/{id}/stock` | ✅ → skeleton |
| `s-mouvements` | `/inventory/movements` | `MovementsPage` | `GET /inventory-movements` | ✅ → skeleton + swipe |
| `s-inventaire-physique` | `/inventory/inventaire` | `PhysicalInventoryPage` | `POST/GET /stock/inventaire` | ✅ → text-body |
| `s-ajustements` | `/inventory/adjustments` | `StockAdjustmentsPage` | `GET/POST /stock/adjustments` | ✅ → skeleton |
| `s-reorder` | `/inventory/reorder` | `StockReorderPage` | `GET /stock/reorder` | ✅ → skeleton |
| `s-stock-coverage` | `/inventory/coverage` | `StockCoveragePage` | `GET /stock/coverage` | ✅ → skeleton |
| `s-stock-item` | `/inventory/stock/$id` | `StockItemDetailPage` | `GET /products/{id}/stock-items` | ✅ → skeleton |
| `s-damage-types` | `/inventory/damage-types` | `DamageTypesPage` | `GET/POST /damage-types` | ✅ → skeleton |

---

## Ordre d'exécution recommandé

```
TASK-STK-01  ← P0 SubNav layout
TASK-STK-02  ← P1 Skeleton InventoryPage (indépendant)
TASK-STK-03  ← P1 Skeleton MovementsPage (indépendant)
TASK-STK-04  ← P1 Skeletons pages secondaires (indépendant)
TASK-STK-05  ← P1 SwipeActions mobile MovementsPage (indépendant)
TASK-STK-06  ← P2 Design system text-body (indépendant)
TASK-STK-07  ← P2 Extraire STOCK_DETAIL_LIMIT constante hardcodée (indépendant)
```

---

## Référence — Fichiers impactés

| Fichier | Action |
|---------|--------|
| `routes/_app/inventory/stock.tsx` | Modifier — ajouter SubNav |
| `pages/inventory/InventoryPage.tsx` | Modifier — skeleton loading |
| `pages/inventory/MovementsPage.tsx` | Modifier — skeleton + SwipeActions |
| `pages/inventory/StockReorderPage.tsx` | Modifier — skeleton, text-body |
| `pages/inventory/StockAdjustmentsPage.tsx` | Modifier — skeleton, text-body |
| `pages/inventory/StockItemDetailPage.tsx` | Modifier — skeleton, text-body |
| `pages/inventory/DamageTypesPage.tsx` | Modifier — skeleton, text-body |
| `pages/inventory/StockCoveragePage.tsx` | Modifier — skeleton |
| `pages/inventory/PhysicalInventoryPage.tsx` | Modifier — text-body |
| `pages/inventory/components/StockItemHistoryModal.tsx` | Modifier — text-body |
