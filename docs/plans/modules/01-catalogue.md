# Module 01 — Stock & Catalogue (onglet 4)

> Roadmap L1→L5 — Audit réel 2026-02-25
> Source : lecture directe des fichiers `routes/`, `pages/products/`, `pages/inventory/`, `components/catalogue/`
> Enrichi 2026-02-25 : analyse approfondie de 10 fichiers de pages supplémentaires

---

## Périmètre

Onglet 4 de la bottom-nav (`Stock`). Deux lectures du même domaine via switcher pills :
- **Catalogue** → vue gérant : liste produits, fiches, création, édition, variantes, bundles, catégories
- **Stock** → vue opérationnelle : états globaux, unités physiques par série, mouvements, réassort

---

## État actuel — audit des routes

| Route | Fichier page | Statut |
|-------|-------------|--------|
| `/_app/products/` | `ProductsPage.tsx` | ✅ L1 liste existe — manque swipe + clic → L2 |
| `/_app/products.tsx` (layout parent) | — | ❌ **ABSENT** — pas de SubNav partagé |
| `/_app/products/$id.tsx` (layout fiche) | — | ❌ **ABSENT** — pas de SubNav onglets L2 |
| `/_app/products/$id/states` | `ProductStatesPage.tsx` | ✅ KPI + filter pills + liste items |
| `/_app/products/$id/editor` | `ProductEditorPage.tsx` | ✅ formulaire champs produit |
| `/_app/products/$id/audit` | `ProductAuditPage.tsx` | ✅ timeline audit |
| `/_app/products/$id/maintenance` | `MaintenancePage.tsx` | ✅ liste maintenances |
| `/_app/products/$id/availability` | `ProductAvailabilityCalendarPage.tsx` | ✅ calendrier dispo |
| `/_app/products/$id/photos` | `ProductPhotosPage.tsx` | ✅ galerie photos |
| `/_app/products/$id/variants` | `ProductVariantsPage.tsx` | ✅ variantes couleur |
| `/_app/products/bundles/` | `BundlesPage.tsx` | ✅ liste bundles |
| `/_app/products/bundles/$id` | `BundleDetailPage.tsx` | ✅ fiche bundle |
| `/_app/products/categories` | `CategoriesPage.tsx` | ✅ liste catégories |
| `/_app/products/import` | `ProductImportPage.tsx` | ✅ import CSV |
| `/_app/inventory/stock/` | `InventoryPage.tsx` | ✅ vue stock globale |
| `/_app/inventory/stock.tsx` (layout) | Outlet simple | ✅ (pas de SubNav) |
| `/_app/inventory/stock/$id` | `StockItemDetailPage.tsx` | ✅ fiche article L4 |
| `/_app/inventory/movements` | `MovementsPage.tsx` | ✅ liste mouvements |
| `/_app/inventory/adjustments` | `StockAdjustmentsPage.tsx` | ✅ ajustements |
| `/_app/inventory/reorder` | `StockReorderPage.tsx` | ✅ réassort |

---

## Anti-patterns consolidés (tous fichiers)

| ID | Fichier | Problème | Priorité |
|----|---------|----------|----------|
| AP-01 | `routes/_app/products.tsx` | Absent — pas de SubNav Catalogue | P0 |
| AP-02 | `routes/_app/products/$id.tsx` | Absent — pas de SubNav fiche L2 | P0 |
| AP-03 | `ProductsPage.tsx:162` | `<Spinner>` isLoading → skeleton requis | P1 |
| AP-04 | `InventoryPage.tsx:206` | `<Spinner>` isLoading → skeleton requis | P1 |
| AP-05 | `ProductEditorPage.tsx:88` | texte `"Chargement…"` isLoading → skeleton | P1 |
| AP-06 | `ProductVariantsPage.tsx:74` | texte `"Chargement..."` isLoading → skeleton | P1 |
| AP-07 | `ProductPhotosPage.tsx:63` | texte `"Chargement…"` isLoading → skeleton | P1 |
| AP-08 | `MaintenancePage.tsx:251` | texte `"Chargement…"` isLoading → skeleton | P1 |
| AP-09 | `ProductAuditPage.tsx:37` | texte `"Chargement…"` isLoading → skeleton | P1 |
| AP-10 | `MovementsPage.tsx:267` | texte `"Chargement..."` isLoading → skeleton mobile | P1 |
| AP-11 | `MovementsPage.tsx:341` | `<td>"Chargement..."` isLoading → skeleton desktop | P1 |
| AP-12 | `ProductStatesPage.tsx:45` | `useProductsList({page_size:1000})` pour nom produit → N+1 | P1 |
| AP-13 | `ProductAvailabilityCalendarPage.tsx:88` | `useProductsList({page_size:500})` → N+1 | P1 |
| AP-14 | `InventoryPage.tsx:39` | `useProductsList({page_size:1000})` pour stats globales → N+1 | P1 |
| AP-15 | `ProductEditorPage.tsx:15` | `PRODUCT_CATEGORIES` hardcodé (12 entrées) → doit utiliser `useCategoriesList()` | P1 |
| AP-16 | `ProductAvailabilityCalendarPage.tsx:83` | fetch impératif + useState au lieu de TanStack Query | P1 |
| AP-17 | `ProductAvailabilityCalendarPage.tsx:209` | bouton "Charger le mois" manuel → auto-load requis | P1 |
| AP-18 | `ProductPhotosPage.tsx:27` | `p-4 md:p-6` padding redondant après TASK-CAT-02 | P1 |
| AP-19 | `MaintenancePage.tsx:227` | `p-4 md:p-6` padding redondant après TASK-CAT-02 | P1 |
| AP-20 | `ProductAuditPage.tsx:26` | `p-4 md:p-6` padding redondant après TASK-CAT-02 | P1 |
| AP-21 | `ProductStatesPage.tsx:65,80,128,182` | `bg-dark-9002` × 3, `text-muted` × 5, `text-body` × 5, `bg-accent` × 3, `text-accent` × 2 | P2 |
| AP-22 | `ProductAvailabilityCalendarPage.tsx:61+` | `text-muted2`, `text-body`, `text-muted`, `text-accent`, `bg-accent`, `ring-accent`, `bg-dark-9002` — classes non définies × nombreuses | P2 |
| AP-23 | `ProductPhotosPage.tsx:39` | `text-body` — classe non standard | P2 |
| AP-24 | `MaintenancePage.tsx:71,153,234,256` | `text-body` × 4 — classe non standard | P2 |
| AP-25 | `ProductAuditPage.tsx:33,42,59` | `text-body` × 3 — classe non standard | P2 |
| AP-26 | `ProductsPage.tsx:37` | `page`, `search`, `filterValues` en useState → pas d'URL sync | P2 |
| AP-27 | `MovementsPage.tsx:59` | filtres en useState (6 vars) → pas d'URL sync | P2 |
| AP-28 | `MaintenancePage.tsx:51` | `<input type="number" step="0.01">` pour `costCents` → `MoneyInput` requis | P2 |
| AP-29 | `MaintenancePage.tsx:206` | `deleteMutation.mutate(id)` sans confirmation modale | P2 |
| AP-30 | `MaintenancePage.tsx:58` | `createMutation` sans `onError` → erreur silencieuse | P2 |
| AP-31 | `InventoryPage.tsx:48` | `handleStatusChange` catch avec `console.error` silencieux → toast requis | P2 |
| AP-32 | `MovementsPage.tsx:226` | `<input type="date">` natif → `DatePicker` requis | P2 |
| AP-33 | `ProductsPage.tsx:69` | filtrage stock client-side après fetch → incohérent avec pagination | P2 |
| AP-34 | `ProductEditorPage.tsx:38` | 7 useState séparés → pas de react-hook-form + zod → pas de validation | P2 |

---

## Tâches

### TASK-CAT-01 — Layout parent `products.tsx` avec SubNav Catalogue (P0)

**Problème** : les routes `products/*` sont des silos. `BundlesPage`, `CategoriesPage`, `ProductsPage` n'ont aucun lien de navigation entre elles.

**À créer** : `frontend/src/routes/_app/products.tsx`

```tsx
import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'
import { Package, Layers, Tag, Grid } from 'lucide-react'

const PRODUCTS_NAV = [
  { label: 'Produits', href: '/products', icon: <Package /> },
  { label: 'Bundles', href: '/products/bundles', icon: <Layers /> },
  { label: 'Catégories', href: '/products/categories', icon: <Tag /> },
  { label: 'Collections', href: '/products/collections', icon: <Grid /> },
]

function ProductsLayout() {
  return (
    <div className="space-y-0">
      <SubNav items={PRODUCTS_NAV} className="sticky top-0 z-30 bg-dark-950 border-b border-layer-border" />
      <div className="p-4">
        <Outlet />
      </div>
    </div>
  )
}

export const Route = createFileRoute('/_app/products')({
  component: ProductsLayout,
})
```

**Critères done** :
- ☐ SubNav "Produits / Bundles / Catégories / Collections" visible sur toutes les routes `products/*`
- ☐ Pill active change selon pathname via `useRouterState` (déjà géré par `SubNav.tsx`)
- ☐ `SubNav` sticky en haut (z-index 30) — ne pas casser le scroll des pages
- ☐ `routeTree.gen.ts` régénéré (auto via Vite)
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CAT-02 — Layout fiche produit L2 avec SubNav 7 onglets (P0)

**Problème** : `products/$id/states`, `products/$id/editor`, `products/$id/audit`, etc. sont des routes sœurs sans parent commun. L'utilisateur ne peut pas naviguer entre onglets sans passer par la liste.

**À créer** : `frontend/src/routes/_app/products/$id.tsx`

```tsx
import { createFileRoute, Outlet, useParams, Link } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'
import { ArrowLeft } from 'lucide-react'

function ProductDetailLayout() {
  const { id } = useParams({ from: '/_app/products/$id' })
  const base = `/products/${id}`

  const NAV = [
    { label: 'États', href: `${base}/states` },
    { label: 'Éditeur', href: `${base}/editor` },
    { label: 'Disponibilité', href: `${base}/availability` },
    { label: 'Variantes', href: `${base}/variants` },
    { label: 'Maintenance', href: `${base}/maintenance` },
    { label: 'Photos', href: `${base}/photos` },
    { label: 'Audit', href: `${base}/audit` },
  ]

  return (
    <div>
      <div className="flex items-center gap-3 px-4 py-3 border-b border-layer-border">
        <Link to="/products" className="p-1.5 rounded-lg hover:bg-dark-900 text-dark-400">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <SubNav items={NAV} className="flex-1" />
      </div>
      <Outlet />
    </div>
  )
}

export const Route = createFileRoute('/_app/products/$id')({
  component: ProductDetailLayout,
})
```

**Important** : après création du layout, supprimer le padding `p-4 md:p-6` redondant dans :
- `ProductPhotosPage.tsx:27` (AP-18)
- `MaintenancePage.tsx:227` (AP-19)
- `ProductAuditPage.tsx:26` (AP-20)
- Et tout `<ArrowLeft>` ou `<Link to="/products">` dupliqué dans les pages enfants

**Critères done** :
- ☐ Navigation entre les 7 onglets sans passer par la liste
- ☐ Pill active change au changement de route
- ☐ Breadcrumb `← Produits` fonctionnel
- ☐ Padding `p-4 md:p-6` retiré des 3 pages enfants (sinon double padding)
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CAT-03 — Swipe-to-reveal + clic card → L2 (P0)

**Problème** : `ProductCard.tsx` n'est pas cliquable vers la fiche L2. Le seul accès L2 passe par le menu `MoreVertical` de la vue table (pas visible en vue grille).

**Modifications** :

**`ProductCard.tsx`** — ajouter :
- Wrapper `<Link to="/products/$id/states" params={{ id: String(product.id) }}>` autour du card body (hors actions)
- Composant `SwipeActions` (`frontend/src/components/ui/SwipeActions.tsx` — existe) wrappant chaque card en vue liste
- Actions swipe : [Modifier → modale edit] [Supprimer → modale delete]

**`ProductsPage.tsx`** vue grille — remplacer les 3 boutons actions par :
- Clic sur la carte → `/products/$id/states` (navigation)
- Actions de survol (hover overlay) : icône Edit + Trash uniquement

**Canevas SwipeActions** (déjà dans le projet) :
```tsx
<SwipeActions
  leftActions={[{ label: 'Modifier', color: 'blue', onAction: () => onEdit(product) }]}
  rightActions={[{ label: 'Supprimer', color: 'red', onAction: () => onDelete(product) }]}
>
  <ProductCard ... />
</SwipeActions>
```

**Critères done** :
- ☐ Clic sur une carte grille → navigate vers `/products/$id/states`
- ☐ Swipe gauche → "Modifier" (ouvre modale edit)
- ☐ Swipe droit → "Supprimer" (ouvre modale delete)
- ☐ Actions du menu `MoreVertical` (vue table) conservées telles quelles
- ☐ Touch target ≥ 44×44px sur les swipe actions
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CAT-04 — Skeleton loading L1 ProductsPage + InventoryPage (P1)

**Problème** : `ProductsPage.tsx:162` et `InventoryPage.tsx:206` affichent un `<Spinner>` centré pendant le chargement. Règle UI/UX PDF #3 : skeleton obligatoire sur toutes les listes L1.

**`ProductsPage.tsx`** — remplacer le `<Spinner>` par :
```tsx
function ProductCardSkeleton() {
  return (
    <div className="bg-dark-900 rounded-xl border border-dark-700 overflow-hidden animate-pulse">
      <div className="h-36 bg-dark-700" />
      <div className="p-4 space-y-3">
        <div className="h-4 bg-dark-700 rounded w-3/4" />
        <div className="h-3 bg-dark-700 rounded w-1/2" />
        <div className="h-6 bg-dark-700 rounded w-1/3" />
      </div>
    </div>
  )
}

// Vue grille — 8 cards skeleton
// Vue table — 8 lignes skeleton (même structure que les lignes existantes)
```

**`InventoryPage.tsx`** — skeleton 6 cards produit (même structure que `ProductCardSkeleton` avec badge stock).

**Critères done** :
- ☐ Skeleton grille 8 cards visible pendant `isLoading` (ProductsPage)
- ☐ Skeleton table 8 lignes visible pendant `isLoading` (ProductsPage)
- ☐ Skeleton InventoryPage 6 cards pendant `isLoading`
- ☐ Aucun `<Spinner>` ou texte `"Chargement…"` sur `isLoading` (les `isPending` boutons submit restent)
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CAT-05 — SubNav layout `inventory.tsx` (P1)

**Contexte** : routes `inventory/*` (stock, adjustments, movements, reorder, coverage, damage-types, inventaire) sont sans SubNav. L'utilisateur ne peut pas naviguer entre sections stock sans revenir au menu principal.

**À créer** : `frontend/src/routes/_app/inventory.tsx`

SubNav inventory :
```
Stock | Mouvements | Réassort | Ajustements | Inventaire physique
```

**Structure** :
```tsx
const INVENTORY_NAV = [
  { label: 'Stock', href: '/inventory/stock' },
  { label: 'Mouvements', href: '/inventory/movements' },
  { label: 'Réassort', href: '/inventory/reorder' },
  { label: 'Ajustements', href: '/inventory/adjustments' },
  { label: 'Inventaire', href: '/inventory/inventaire' },
]
```

**Critères done** :
- ☐ SubNav visible sur toutes les routes `inventory/*` sauf `inventory/stock/$id`
- ☐ `inventory/stock/$id` (fiche article) n'affiche PAS le SubNav inventory (layout spécifique)
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CAT-06 — Page de création produit steppée L3 (P1)

**Contexte** : la création se fait actuellement via `ProductFormModal` (modale multi-champs). Selon LAYER `s-produit-create` = page dédiée multi-sections, pas modale.

**À créer** : `frontend/src/pages/products/ProductCreatePage.tsx`

Structure steppée 3 étapes :
1. **Identité** — Nom, SKU (auto-généré, modifiable), Catégorie (via `useCategoriesList()`)
2. **Tarification** — Prix/jour (`MoneyInput`), Caution (`MoneyInput`), TVA (si applicable)
3. **Stock** — Quantité totale, État initial (`condition`), Image principale

**Stepper composant** (`StepperForm.tsx` existe dans `components/ui/`) :
```tsx
<StepperForm
  steps={['Identité', 'Tarification', 'Stock']}
  currentStep={step}
  onStepClick={setStep}
/>
```

**Validation par étape** : ne pas permettre "Suivant" si champ requis vide. Erreurs inline sous chaque champ.

**Route** : `frontend/src/routes/_app/products/new.tsx` (ajouter)

**Conserver** `ProductFormModal` pour le cas d'édition rapide depuis la liste — la page `new` est le flux complet.

**Critères done** :
- ☐ Route `/_app/products/new` accessible
- ☐ 3 étapes avec validation par étape
- ☐ `MoneyInput` utilisé (jamais `<input type="number">` pour les montants)
- ☐ Catégorie via `useCategoriesList()` (pas hardcodé)
- ☐ SKU auto-généré `CAT-XXXXX` modifiable
- ☐ Submit → redirect vers `/products/$newId/states`
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CAT-07 — Bottom-sheet édition statut article L4 (P1)

**Contexte** : dans `InventoryPage`, l'édition statut d'un article (`available → damaged` etc.) se fait via un `<select>` inline affiché au click. C'est fonctionnel mais fragile (lose focus = annule). `StockItemDetailPage` permet de voir le détail mais pas d'éditer.

**À créer** : `frontend/src/components/ui/StockItemStatusSheet.tsx`

Bottom-sheet 5 options statut avec :
- Pastille colorée par statut (reprendre `STATUS_COLORS` de `InventoryPage`)
- Champ optionnel "Note" (max 200 chars) affiché si statut `damaged` ou `in_repair`
- Bouton "Valider" → `PATCH /products/{id}/stock-items/{itemId}` (vérifier endpoint backend)
- Bouton "Annuler" → ferme sans mutation

**Usage depuis** `StockItemDetailPage` : bouton "Changer statut" → ouvre le sheet.
**Usage depuis** `InventoryPage` : remplacer le `<select>` inline par ce sheet.
- Corriger simultanément AP-31 (`handleStatusChange` catch silencieux → toast erreur).

**Critères done** :
- ☐ Bottom-sheet 5 options statut + note optionnelle
- ☐ Trap focus actif (Tab cycle dans le sheet, Escape ferme)
- ☐ Mutation invalidate `['product-stock', productId]` après succès
- ☐ Toast succès/erreur (plus de `console.error` silencieux)
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CAT-08 — Détail mouvement en bottom-sheet L5 (P2)

**Contexte** : `MovementDetailModal.tsx` existe comme modale. Selon LAYER `s-stock-mouvement-detail` = bottom-sheet contextuel depuis la liste des mouvements.

**Migration** : transformer `MovementDetailModal` en `MovementDetailSheet` (bottom-sheet) :
- Champs : type mouvement, date, réservation liée (lien clickable), articles impactés, état avant/après, signataire, notes
- Actions : lien "Voir la réservation" si `reservation_id` présent
- Conserver les props interface identique pour ne pas casser `MovementsPage`

**Critères done** :
- ☐ Bottom-sheet remplace la modale
- ☐ Trap focus + Escape ferme
- ☐ Lien réservation fonctionnel si `reservation_id`
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CAT-09 — Skeletons loading pages fiche produit (P1)

**Problème** : 5 pages de la fiche produit affichent un texte `"Chargement…"` pendant `isLoading`. Règle UI/UX PDF #3 : skeleton obligatoire.

**Fichiers à modifier** :

**`ProductEditorPage.tsx:88`** :
```tsx
function EditorSkeleton() {
  return (
    <div className="max-w-2xl mx-auto space-y-5 animate-pulse p-4">
      <div className="h-6 bg-dark-700 rounded w-40" />
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="space-y-1.5">
          <div className="h-3 bg-dark-700 rounded w-24" />
          <div className="h-9 bg-dark-700 rounded" />
        </div>
      ))}
      <div className="h-10 bg-dark-700 rounded w-32" />
    </div>
  )
}
// Remplacer : if (isLoading) return <div>Chargement…</div>
if (isLoading) return <EditorSkeleton />
```

**`ProductVariantsPage.tsx:74`** :
```tsx
function VariantsSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="card flex items-center justify-between p-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-dark-700 rounded-full" />
            <div className="h-4 bg-dark-700 rounded w-28" />
          </div>
          <div className="h-3 bg-dark-700 rounded w-20" />
        </div>
      ))}
    </div>
  )
}
if (isLoading) return <VariantsSkeleton />
```

**`ProductPhotosPage.tsx:63`** :
```tsx
function PhotosSkeleton() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 animate-pulse">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="aspect-square bg-dark-700 rounded-xl" />
      ))}
    </div>
  )
}
if (isLoading) return <PhotosSkeleton />
```

**`MaintenancePage.tsx:251`** :
```tsx
function MaintenanceSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="card p-4 space-y-2">
          <div className="flex items-center justify-between">
            <div className="h-4 bg-dark-700 rounded w-40" />
            <div className="h-3 bg-dark-700 rounded w-20" />
          </div>
          <div className="h-3 bg-dark-700 rounded w-full" />
        </div>
      ))}
    </div>
  )
}
if (isLoading) return <MaintenanceSkeleton />
```

**`ProductAuditPage.tsx:37`** :
```tsx
function AuditSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex gap-3">
          <div className="w-2 h-2 bg-dark-700 rounded-full mt-2 shrink-0" />
          <div className="flex-1 space-y-1.5">
            <div className="h-3 bg-dark-700 rounded w-32" />
            <div className="h-4 bg-dark-700 rounded w-3/4" />
          </div>
        </div>
      ))}
    </div>
  )
}
if (isLoading) return <AuditSkeleton />
```

**Critères done** :
- ☐ Aucun texte `"Chargement…"` dans les 5 pages (les `isPending` boutons submit restent)
- ☐ Chaque skeleton reflète la structure réelle de la page (pas un rectangle générique)
- ☐ `animate-pulse` présent sur chaque skeleton
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CAT-10 — Skeleton loading MovementsPage (P1)

**Problème** : `MovementsPage.tsx:267` (vue mobile) et `:341` (vue desktop) affichent du texte `"Chargement..."` pendant `isLoading`.

**Fichier à modifier** : `frontend/src/pages/inventory/MovementsPage.tsx`

```tsx
function MovementRowSkeleton() {
  return (
    <tr className="animate-pulse border-b border-dark-700/50">
      <td className="px-4 py-3"><div className="h-4 bg-dark-700 rounded w-24" /></td>
      <td className="px-4 py-3"><div className="h-4 bg-dark-700 rounded w-20" /></td>
      <td className="px-4 py-3"><div className="h-5 bg-dark-700 rounded-full w-16" /></td>
      <td className="px-4 py-3"><div className="h-4 bg-dark-700 rounded w-28" /></td>
      <td className="px-4 py-3"><div className="h-4 bg-dark-700 rounded w-16" /></td>
      <td className="px-4 py-3"><div className="h-5 bg-dark-700 rounded-full w-16" /></td>
      <td className="px-4 py-3" />
    </tr>
  )
}

function MovementCardSkeleton() {
  return (
    <div className="card animate-pulse space-y-2 p-3">
      <div className="flex justify-between">
        <div className="h-4 bg-dark-700 rounded w-28" />
        <div className="h-5 bg-dark-700 rounded-full w-16" />
      </div>
      <div className="h-3 bg-dark-700 rounded w-1/2" />
    </div>
  )
}

// Desktop tbody :
{isLoading
  ? Array.from({ length: 8 }).map((_, i) => <MovementRowSkeleton key={i} />)
  : /* contenu normal */}

// Mobile :
{isLoading
  ? Array.from({ length: 6 }).map((_, i) => <MovementCardSkeleton key={i} />)
  : /* contenu normal */}
```

**Critères done** :
- ☐ Skeleton desktop 8 lignes tableau
- ☐ Skeleton mobile 6 cards
- ☐ Aucun texte `"Chargement..."` dans `MovementsPage`

---

### TASK-CAT-11 — Corriger N+1 queries (P1)

**Problème** : 3 pages chargent toute la liste produits (500–1000 items) uniquement pour récupérer le nom ou les données d'un seul produit par son ID.

**`ProductStatesPage.tsx:45`** :
```tsx
// AVANT (interdit) :
const { data: allProducts } = useProductsList({ page: 1, page_size: 1000, active_only: false })
const product = allProducts?.items.find((p) => p.id === Number(productId))

// APRÈS :
const { data: product } = useProductDetail(productId) // hook existant dans queries/
```

**`ProductAvailabilityCalendarPage.tsx:88`** :
```tsx
// AVANT (interdit) :
const { data: products } = useProductsList({ page: 1, page_size: 500, active_only: true })
const product = products?.items.find((p) => p.id === Number(id))

// APRÈS :
const { data: product } = useProductDetail(id)
```

**`InventoryPage.tsx:39`** :
```tsx
// AVANT (interdit) :
const { data: allProducts } = useProductsList({ page: 1, page_size: 1000, active_only: true })
// utilisé uniquement pour afficher "X produits actifs" dans les KPI

// APRÈS : utiliser useInventoryStats() ou déduit du count de l'endpoint stock
// Alternative : GET /products?page_size=1&active_only=true → count dans la réponse paginée
```

> Vérifier que `useProductDetail(id)` existe dans `frontend/src/api/queries/`.
> Si absent, l'ajouter : `queryFn: () => fetchClient.get('/products/{id}')`.

**Critères done** :
- ☐ Aucune occurrence `useProductsList({ page_size: ≥500 })` pour lookup par ID
- ☐ `useProductDetail(id)` utilisé dans les 3 pages
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CAT-12 — PRODUCT_CATEGORIES hardcodé → `useCategoriesList()` (P1)

**Problème** : `ProductEditorPage.tsx:15-28` définit un tableau `PRODUCT_CATEGORIES` hardcodé avec 12 catégories fixes. Si les catégories changent en base, l'éditeur ne le reflète pas.

**Fichier à modifier** : `frontend/src/pages/products/ProductEditorPage.tsx`

```tsx
// AVANT (interdit) :
const PRODUCT_CATEGORIES = [
  { value: 'son', label: 'Son' },
  { value: 'lumiere', label: 'Lumière' },
  // ... 10 autres catégories hardcodées
]

// APRÈS :
const { data: categoriesData } = useCategoriesList({ limit: 1000 })
const categoryOptions = (categoriesData?.items ?? []).map((c) => ({
  value: c.id,
  label: c.name,
}))
// → utiliser categoryOptions dans le <Select> catégorie
```

> `useCategoriesList` existe déjà dans `frontend/src/api/queries/`.
> Rappel gotcha : `limit: 1000` obligatoire (`GOTCHA:FRONTEND:CATEGORIES-LIMIT`).

**Critères done** :
- ☐ Aucune constante `PRODUCT_CATEGORIES` dans `ProductEditorPage`
- ☐ Catégories chargées depuis l'API
- ☐ Loading state pendant chargement catégories (Select disabled)
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CAT-13 — ProductAvailabilityCalendarPage : TanStack Query + auto-load (P1)

**Problème** : `ProductAvailabilityCalendarPage.tsx:83-113` utilise fetch impératif avec `useState(loading/error/loaded)` pour charger les disponibilités. Pas de cache, pas de refetch auto. De plus, un bouton manuel "Charger le mois" (`:209`) force l'utilisateur à déclencher le chargement.

**Fichier à modifier** : `frontend/src/pages/products/ProductAvailabilityCalendarPage.tsx`

```tsx
// AVANT (interdit) :
const [loading, setLoading] = useState(false)
const [availabilityData, setAvailabilityData] = useState(null)
const handleLoadMonth = async () => {
  setLoading(true)
  const res = await fetch(`/api/v1/products/${id}/availability?month=${selectedMonth}`)
  // ...
}

// APRÈS :
const { data: availabilityData, isLoading: availLoading } = useQuery({
  queryKey: ['product-availability', id, selectedMonth],
  queryFn: () => fetchClient.get(`/products/${id}/availability`, { params: { month: selectedMonth } }),
  enabled: !!id && !!selectedMonth,
})
// → supprimer le bouton "Charger le mois" — chargement automatique via enabled
// → supprimer aussi le N+1 (AP-13) en même temps que cette correction
```

**Critères done** :
- ☐ Aucun `useState(loading)` fetch impératif dans cette page
- ☐ Chargement automatique dès sélection d'un mois
- ☐ Cache TanStack Query (navigation mois → retour → pas de re-fetch inutile)
- ☐ Skeleton pendant `isLoading`
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CAT-14 — Normaliser classes design system (P2)

**Problème** : 5 pages du module utilisent des classes Tailwind non définies dans `tailwind.config.js` CaroCorp. En production, ces classes produisent des couleurs inattendues ou invisibles.

**Classes invalides et remplacements** :

| Classe invalide | Remplacement |
|----------------|--------------|
| `text-body` | *(supprimer)* — texte blanc hérité par défaut |
| `text-muted` | `text-dark-400` |
| `text-muted2` | `text-dark-500` |
| `text-accent` | `text-primary-400` ou `text-gold-400` selon contexte |
| `bg-accent` | `bg-primary-500` |
| `ring-accent` | `ring-primary-500` |
| `bg-dark-9002` | `bg-dark-800` (faute de frappe) |
| `hover:bg-dark-9002` | `hover:bg-dark-800` |

**Fichiers et occurrences** :

- `ProductStatesPage.tsx` :
  - L65,67 : `bg-dark-9002` × 3 → `bg-dark-800`
  - L80,82,83,86,89,90 : `text-muted` × 5 → `text-dark-400`
  - L80,82,86,89 : `text-body` × 5 → *(supprimer)*
  - L128,182 : `bg-accent` × 2, `text-accent` → remplacer
- `ProductAvailabilityCalendarPage.tsx` (nombreuses occurrences) :
  - `text-muted2` → `text-dark-500`
  - `text-body` → *(supprimer)*
  - `text-muted` → `text-dark-400`
  - `text-accent` → `text-primary-400`
  - `bg-accent` → `bg-primary-500`
  - `ring-accent` → `ring-primary-500`
  - `bg-dark-9002`, `hover:bg-dark-9002` → `bg-dark-800`
- `ProductPhotosPage.tsx:39` : `text-body` → *(supprimer)*
- `MaintenancePage.tsx:71,153,234,256` : `text-body` × 4 → *(supprimer)*
- `ProductAuditPage.tsx:33,42,59` : `text-body` × 3 → *(supprimer)*

**Méthode** :
```bash
grep -rn "text-body\|text-muted\|text-accent\|bg-accent\|ring-accent\|bg-dark-9002" \
  frontend/src/pages/products/ frontend/src/pages/inventory/
```

**Critères done** :
- ☐ Aucune occurrence de `text-body`, `text-muted`, `text-muted2`, `text-accent`, `bg-accent`, `ring-accent`, `bg-dark-9002` dans le module
- ☐ Rendu visuel identique après remplacement (vérifier navigateur)
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CAT-15 — URL sync filtres ProductsPage + MovementsPage (P2)

**Problème** : les filtres (search, statut, type, pagination, dates) sont en `useState` local dans `ProductsPage.tsx:37` et `MovementsPage.tsx:59`. Au retour depuis une fiche, les filtres sont perdus. L'URL n'est pas partageable avec filtres pré-appliqués.

**Solution** : `validateSearch` TanStack Router.

**`routes/_app/products/index.tsx`** :
```tsx
export const Route = createFileRoute('/_app/products/')({
  validateSearch: (search) => ({
    q: (search.q as string) ?? '',
    category: (search.category as string) ?? '',
    stock_filter: (search.stock_filter as string) ?? '',
    view: (search.view as 'grid' | 'table') ?? 'grid',
    page: Number(search.page ?? 1),
  }),
  component: ProductsPage,
})
```

**`routes/_app/inventory/movements/index.tsx`** :
```tsx
export const Route = createFileRoute('/_app/inventory/movements/')({
  validateSearch: (search) => ({
    type: (search.type as string) ?? '',
    status: (search.status as string) ?? '',
    reservation_id: (search.reservation_id as string) ?? '',
    date_from: (search.date_from as string) ?? '',
    date_to: (search.date_to as string) ?? '',
    page: Number(search.page ?? 1),
  }),
  component: MovementsPage,
})
```

> Remplacer les 6 `useState` filtres par `useSearch` + `useNavigate` dans chaque page.
> Corriger simultanément AP-33 (filtrage stock client-side → ajouter paramètre au query backend).

**Critères done** :
- ☐ URL `?q=sono&category=son&page=2` fonctionne sur ProductsPage
- ☐ URL `?type=departure&date_from=2026-01-01` fonctionne sur MovementsPage
- ☐ Retour depuis fiche → filtres préservés
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CAT-16 — Corrections MaintenancePage : MoneyInput, onError, confirmation suppression (P2)

**Problème** : 3 anti-patterns dans `MaintenancePage.tsx` :
- AP-28 : `<input type="number" step="0.01">` pour `costCents` (montant en euros)
- AP-30 : `createMutation.mutate()` sans `onError` → erreur silencieuse
- AP-29 : `deleteMutation.mutate(id)` sans confirmation → suppression immédiate

**Fichier à modifier** : `frontend/src/pages/products/MaintenancePage.tsx`

```tsx
// 1. MoneyInput pour costCents (AP-28)
// AVANT : <input type="number" step="0.01" value={costEuros} onChange={...} />
// APRÈS :
import { MoneyInput } from '@/components/ui/MoneyInput'
// MoneyInput travaille en centimes directement
<MoneyInput
  value={costCents}
  onChange={(cents) => setCostCents(cents)}
  placeholder="0,00 €"
/>

// 2. onError sur createMutation (AP-30)
createMutation.mutate(payload, {
  onSuccess: () => { /* reset form + toast */ },
  onError: (err) => {
    const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Erreur lors de l\'ajout'
    setError(msg)
  },
})

// 3. Confirmation avant suppression (AP-29)
// Ajouter state : const [deleteTarget, setDeleteTarget] = useState<number | null>(null)
// Bouton supprimer → setDeleteTarget(item.id) (ouvre modal confirmation)
// Modal : "Supprimer cette maintenance ?" → confirmer → deleteMutation.mutate(deleteTarget)
```

**Critères done** :
- ☐ `MoneyInput` pour le coût de maintenance (centimes)
- ☐ `onError` sur `createMutation` avec message d'erreur affiché
- ☐ Confirmation modale avant suppression
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CAT-17 — Corrections MovementsPage : DatePicker natif → composant (P2)

**Problème** : `MovementsPage.tsx:226-240` utilise `<input type="date">` natif pour les filtres de dates. Le design system dispose d'un composant `DatePicker` dédié (`components/ui/DatePicker.tsx`).

**Fichier à modifier** : `frontend/src/pages/inventory/MovementsPage.tsx`

```tsx
// AVANT :
<input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="..." />

// APRÈS :
import { DatePicker } from '@/components/ui/DatePicker'
<DatePicker
  value={dateFrom}
  onChange={setDateFrom}
  placeholder="Date début"
/>
```

Appliquer aux deux champs : `dateFrom` et `dateTo`.

**Critères done** :
- ☐ `DatePicker` utilisé pour les 2 filtres de date
- ☐ Aucun `<input type="date">` natif dans `MovementsPage`
- ☐ `tsc --noEmit` 0 erreur

---

## Composants partagés nécessaires

| Composant | Fichier | Statut |
|-----------|---------|--------|
| `SwipeActions` | `components/ui/SwipeActions.tsx` | ✅ existe |
| `StepperForm` | `components/ui/StepperForm.tsx` | ✅ existe |
| `MoneyInput` | `components/ui/MoneyInput.tsx` | ✅ existe |
| `DatePicker` | `components/ui/DatePicker.tsx` | ✅ existe |
| `StockItemStatusSheet` | `components/ui/StockItemStatusSheet.tsx` | ❌ à créer (TASK-CAT-07) |
| `SubNav` | `components/layout/SubNav.tsx` | ✅ existe |
| `SkeletonProductCard` | inline dans ProductsPage | ❌ à créer (TASK-CAT-04) |

---

## Ordre d'exécution recommandé

```
TASK-CAT-01  ← P0 Layout parent products.tsx + SubNav Catalogue
TASK-CAT-02  ← P0 Layout fiche $id.tsx + SubNav 7 onglets (supprimer paddings redondants)
TASK-CAT-03  ← P0 Swipe + clic card → L2
TASK-CAT-04  ← P1 Skeleton L1 ProductsPage + InventoryPage
TASK-CAT-05  ← P1 SubNav inventory.tsx
TASK-CAT-09  ← P1 Skeletons pages fiche (5 pages)
TASK-CAT-10  ← P1 Skeleton MovementsPage
TASK-CAT-11  ← P1 Corriger N+1 queries (3 pages)
TASK-CAT-12  ← P1 PRODUCT_CATEGORIES hardcodé → useCategoriesList()
TASK-CAT-13  ← P1 ProductAvailabilityCalendarPage TanStack Query + auto-load
TASK-CAT-06  ← P1 Page création steppée L3
TASK-CAT-07  ← P1 Bottom-sheet statut article L4
TASK-CAT-08  ← P2 Bottom-sheet mouvement L5
TASK-CAT-14  ← P2 Normaliser classes design system
TASK-CAT-15  ← P2 URL sync filtres ProductsPage + MovementsPage
TASK-CAT-16  ← P2 MaintenancePage : MoneyInput + onError + confirmation
TASK-CAT-17  ← P2 MovementsPage : DatePicker natif → composant
```

---

## Couverture LAYER — Mapping final

| Écran LAYER | Route | Composant | Statut cible |
|-------------|-------|-----------|--------------|
| `s-catalogue` | `/products` | `ProductsPage` | ✅ → skeleton + swipe |
| `s-stock` | `/inventory/stock` | `InventoryPage` | ✅ → skeleton + SubNav |
| `s-catalogue-produit` | `/products/$id/states` | `ProductStatesPage` | ✅ → SubNav onglets + N+1 fix |
| `s-produit-create` | `/products/new` | `ProductCreatePage` | ❌ à créer (TASK-CAT-06) |
| `s-produit-edit` | `/products/$id/editor` | `ProductEditorPage` | ✅ → skeleton + catégories API |
| `s-catalogue-packs` | `/products/bundles` | `BundlesPage` | ✅ |
| `s-catalogue-variantes` | `/products/$id/variants` | `ProductVariantsPage` | ✅ → skeleton |
| `s-catalogue-disponibilite` | `/products/$id/availability` | `ProductAvailabilityCalendarPage` | ✅ → TanStack Query + auto-load |
| `s-catalogue-maintenance` | `/products/$id/maintenance` | `MaintenancePage` | ✅ → skeleton + MoneyInput |
| `s-catalogue-photos` | `/products/$id/photos` | `ProductPhotosPage` | ✅ → skeleton |
| `s-catalogue-audit` | `/products/$id/audit` | `ProductAuditPage` | ✅ → skeleton |
| `s-stock-historique` | `/inventory/movements` | `MovementsPage` | ✅ → skeleton + URL sync |
| `s-stock-item-detail` | `/inventory/stock/$id` | `StockItemDetailPage` | ✅ |

---

## Critères de done global (module)

- ☐ TASK-CAT-01 : layout parent `products.tsx` + SubNav
- ☐ TASK-CAT-02 : layout fiche produit `products/$id.tsx` + SubNav 7 onglets
- ☐ TASK-CAT-03 : swipe-to-reveal + clic card → L2
- ☐ TASK-CAT-04 : skeleton loading L1 (ProductsPage + InventoryPage)
- ☐ TASK-CAT-05 : layout `inventory.tsx` + SubNav
- ☐ TASK-CAT-06 : page création steppée L3
- ☐ TASK-CAT-07 : bottom-sheet statut article L4
- ☐ TASK-CAT-08 : bottom-sheet mouvement L5 (P2)
- ☐ TASK-CAT-09 : skeletons 5 pages fiche produit
- ☐ TASK-CAT-10 : skeleton MovementsPage desktop + mobile
- ☐ TASK-CAT-11 : N+1 queries corrigés (3 pages)
- ☐ TASK-CAT-12 : PRODUCT_CATEGORIES → useCategoriesList()
- ☐ TASK-CAT-13 : ProductAvailabilityCalendarPage TanStack Query
- ☐ TASK-CAT-14 : classes design system normalisées (P2)
- ☐ TASK-CAT-15 : URL sync filtres ProductsPage + MovementsPage (P2)
- ☐ TASK-CAT-16 : MaintenancePage MoneyInput + onError + confirmation (P2)
- ☐ TASK-CAT-17 : MovementsPage DatePicker (P2)
- ☐ `tsc --noEmit` 0 erreur sur tous les fichiers modifiés
- ☐ 1582 Vitest pass
