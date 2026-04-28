# Module 02 — Clients (CRM, Historique, RFM, Relances)

> Roadmap L1→L5 — Audit réel codebase 2026-02-25 | Source : fichiers lus + grep
> Référence architecture : `docs/plans/LAYER_ARCHITECTURE.md`
> Règles UX : `docs/ui-ux-front-rules.pdf`

---

## Périmètre

| Écran LAYER | ID | Niveau |
|-------------|-----|--------|
| Liste clients | `s-clients` | L1 |
| Fiche client (onglets) | `s-client-detail` | L2 |
| Historique réservations client | `s-client-reservations` | L2 |
| Historique factures client | `s-client-invoices` | L2 |
| Relances client | `s-client-relances` | L2 |
| Formulaire création/édition | `s-client-form` | L3 |
| Liste relances globale | `s-relances` | L3 |
| Analyse RFM | `s-rfm` | L3 |
| Export CSV | `s-export-clients` | L3 |

---

## État actuel — Anti-patterns identifiés (audit complet)

| ID | Fichier | Ligne | Problème | Priorité |
|----|---------|-------|----------|----------|
| AP-01 | `routes/_app/customers.tsx` | — | Layout absent → pas de SubNav module | P0 |
| AP-02 | `routes/_app/customers/$id.tsx` | — | Layout absent → `CustomerDetailPage` monolithique sans onglets | P0 |
| AP-03 | `CustomersPage.tsx` | L7-12 | `VENTES_NAV` cross-modules hardcodé dans la page | P0 |
| AP-04 | `CustomersPage.tsx` | L169-170 | Vue mobile : `isLoading` → `<Spinner>` au lieu de skeleton | P1 |
| AP-05 | `CustomersPage.tsx` | L237-241 | Vue desktop : `isLoading` → `<Spinner>` dans `<td>` au lieu de skeleton | P1 |
| AP-06 | `CustomerDetailPage.tsx` | L35-41 | `isLoading` → `<Loader2>` spinner centré au lieu de skeleton | P1 |
| AP-07 | `ClientsRelancesPage.tsx` | L94-95 | `isLoading` → texte `"Chargement…"` au lieu de skeleton | P1 |
| AP-08 | `ClientsRFMPage.tsx` | L32-33 | `isLoading` → texte `"Chargement…"` au lieu de skeleton | P1 |
| AP-09 | `CustomerDetailPage.tsx` | L163 | Lignes réservations non cliquables → `/events/$id` | P1 |
| AP-10 | `CustomerDetailPage.tsx` | L197 | Lignes factures non cliquables → `/invoices/$id` | P1 |
| AP-11 | `CustomersPage.tsx` | — | Pas de SwipeActions sur vue mobile | P1 |
| AP-12 | `CustomersPage.tsx` | — | Bottom-sheet absent pour formulaire mobile (modale classique) | P1 |
| AP-13 | `CustomerDetailPage.tsx` | L91,99,108,116,145,180,214 | `text-body` × 7 — classe non définie dans design system | P2 |
| AP-14 | `ClientsRFMPage.tsx` | L21,37,53,85 | `text-body` × 4 — classe non définie dans design system | P2 |
| AP-15 | `ClientsRelancesPage.tsx` | L116 | `text-body` × 1 — classe non définie dans design system | P2 |
| AP-16 | `ClientsRFMPage.tsx` | L18 | Padding `p-4 md:p-6` redondant (double après layout parent) | P2 |
| AP-17 | `CustomerDetailPage.tsx` | L239-249 | Mutations `markSentRelance` + `cancelRelance` sans `onError` | P2 |
| AP-18 | `ClientsRelancesPage.tsx` | — | Mutations `cancelMutation` + `markSentMutation` sans `onError` | P2 |
| AP-19 | `CustomersPage.tsx` | L37-41 | Filtres `page`, `searchQuery`, `typeFilter`, `relancesOnly` en useState → pas d'URL sync | P2 |
| AP-20 | `ClientsRelancesPage.tsx` | L25 | Filtre `statusFilter` en useState → pas d'URL sync | P2 |
| AP-21 | `ClientsRFMPage.tsx` | — | Pas de lien depuis table RFM vers fiche client `/customers/$id` | P2 |
| AP-22 | `CustomerDetailPage.tsx` | L64-68 | Bouton `<ArrowLeft>` retour inline (à supprimer après TASK-CLI-01/02) | P2 |

---

## Tâches

### TASK-CLI-01 (P0) — Créer layout parent `customers.tsx` avec SubNav

**Fichier :** `frontend/src/routes/_app/customers.tsx`

**Problème :** `VENTES_NAV` dans `CustomersPage` crée un nav cross-modules instable. Il faut extraire la navigation dans le layout parent.

```tsx
// frontend/src/routes/_app/customers.tsx
import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

const CUSTOMERS_NAV = [
  { label: 'Clients', href: '/customers' },
  { label: 'Relances', href: '/customers/relances' },
  { label: 'Analyse RFM', href: '/customers/rfm' },
]

export const Route = createFileRoute('/_app/customers')({
  component: () => (
    <div className="space-y-0">
      <SubNav items={CUSTOMERS_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  ),
})
```

**Dans `CustomersPage.tsx` :** supprimer `SubNav`, `VENTES_NAV`, et le padding `p-4 md:p-6` redondant.

**Critères done :**
- ☐ `routes/_app/customers.tsx` créé
- ☐ SubNav persistant sur `/customers/`, `/customers/relances`, `/customers/rfm`
- ☐ `VENTES_NAV` + `SubNav` supprimés de `CustomersPage`
- ☐ Padding retiré des pages individuelles (sinon double padding)
- ☐ `tsc --noEmit` 0 erreur
- ☐ 1582 Vitest pass

---

### TASK-CLI-02 (P0) — Layout fiche `customers/$id.tsx` avec SubNav 4 onglets

**Fichiers :** `routes/_app/customers/$id.tsx` (layout) + 4 sous-routes

**Problème :** `CustomerDetailPage` est monolithique (272L). Il faut un layout `$id.tsx` avec SubNav + 4 sous-routes.

```tsx
// frontend/src/routes/_app/customers/$id.tsx
import { createFileRoute, Outlet, useParams } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

function CustomerLayout() {
  const { id } = useParams({ strict: false })
  const base = `/customers/${id}`
  const tabs = [
    { label: 'Infos', href: `${base}` },
    { label: 'Réservations', href: `${base}/reservations` },
    { label: 'Factures', href: `${base}/invoices` },
    { label: 'Relances', href: `${base}/relances` },
  ]
  return (
    <div className="space-y-0">
      <SubNav items={tabs} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  )
}

export const Route = createFileRoute('/_app/customers/$id')({
  component: CustomerLayout,
})
```

Sous-routes à créer :
```
routes/_app/customers/$id/index.tsx        → CustomerInfoPage (infos + KPI)
routes/_app/customers/$id/reservations.tsx → CustomerReservationsPage
routes/_app/customers/$id/invoices.tsx     → CustomerInvoicesPage
routes/_app/customers/$id/relances.tsx     → CustomerRelancesPage
```

**Critères done :**
- ☐ Layout `$id.tsx` créé avec SubNav 4 onglets
- ☐ 4 sous-routes créées avec composants extraits de `CustomerDetailPage`
- ☐ Navigation entre onglets fonctionnelle
- ☐ `CustomerDetailPage.tsx` supprimé ou redirigé
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CLI-03 (P0) — Éclater `CustomerDetailPage` en 4 composants

**Priorité :** P0 — dépend de TASK-CLI-02
**Fichiers à créer :**

```
pages/customers/CustomerInfoPage.tsx         — infos dl + 3 KPI + bouton Modifier
pages/customers/CustomerReservationsPage.tsx — tableau réservations + lien → /events/$id
pages/customers/CustomerInvoicesPage.tsx     — tableau factures + lien → /invoices/$id
pages/customers/CustomerRelancesPage.tsx     — tableau relances + bouton "Planifier"
```

- `CustomerInfoPage` : skeleton loading pendant `isLoading`, retirer le bouton `<ArrowLeft>` (remplacé par SubNav du layout parent)
- `CustomerReservationsPage` : chaque ligne cliquable → `navigate({ to: '/events/$id' })` avec `DomainStatusBadge`
- `CustomerInvoicesPage` : chaque ligne cliquable → `navigate({ to: '/invoices/$id' })`, solde calculé (total − payé)
- `CustomerRelancesPage` : bouton "Planifier relance" → TASK-CLI-07

**Critères done :**
- ☐ 4 pages créées et connectées aux routes
- ☐ `CustomerDetailPage.tsx` supprimé
- ☐ Skeleton loading sur `CustomerInfoPage`
- ☐ Navigation réservation/facture → detail page
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CLI-04 (P1) — Skeleton loading liste L1 `CustomersPage`

**Fichier :** `frontend/src/pages/customers/CustomersPage.tsx`

**Problème :** `<Spinner>` utilisé pendant `isLoading` vue mobile (L169-170) ET vue desktop (L237-241).

```tsx
function CustomerRowSkeleton() {
  return (
    <tr className="animate-pulse border-b border-dark-700/50">
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-dark-700 shrink-0" />
          <div className="space-y-1.5">
            <div className="h-4 bg-dark-700 rounded w-36" />
            <div className="h-3 bg-dark-700 rounded w-24" />
          </div>
        </div>
      </td>
      <td className="px-4 py-3"><div className="h-4 bg-dark-700 rounded w-28" /></td>
      <td className="px-4 py-3"><div className="h-4 bg-dark-700 rounded w-20" /></td>
      <td className="px-4 py-3"><div className="h-5 bg-dark-700 rounded-full w-16" /></td>
      <td className="px-4 py-3"><div className="h-4 bg-dark-700 rounded w-24" /></td>
      <td className="px-4 py-3" />
    </tr>
  )
}

function CustomerCardSkeleton() {
  return (
    <div className="flex items-center gap-3 px-4 py-3 animate-pulse">
      <div className="w-9 h-9 rounded-full bg-dark-700 shrink-0" />
      <div className="flex-1 space-y-1.5">
        <div className="h-4 bg-dark-700 rounded w-1/2" />
        <div className="h-3 bg-dark-700 rounded w-1/3" />
      </div>
    </div>
  )
}

// Remplacer dans le tbody desktop :
{isLoading
  ? Array.from({ length: 8 }).map((_, i) => <CustomerRowSkeleton key={i} />)
  : /* lignes réelles */
}

// Remplacer dans la vue mobile :
{isLoading
  ? Array.from({ length: 5 }).map((_, i) => <CustomerCardSkeleton key={i} />)
  : /* cartes réelles */
}
```

**Critères done :**
- ☐ Skeleton desktop : 8 lignes `<tr>` animate-pulse
- ☐ Skeleton mobile : 5 cards animate-pulse
- ☐ Aucun `<Spinner>` ou texte `"Chargement…"` pendant `isLoading`

---

### TASK-CLI-05 (P1) — SwipeActions sur lignes mobiles

**Fichier :** `frontend/src/pages/customers/CustomersPage.tsx`

**Problème :** Actions (Modifier, Supprimer) dans `MoreVertical` menu contextuel = 2 taps. Swipe = 1 geste.

```tsx
import { SwipeActions } from '@/components/ui/SwipeActions'

// Wrapper chaque card mobile :
<SwipeActions
  key={customer.id}
  rightActions={[
    {
      label: 'Modifier',
      icon: <Edit className="w-4 h-4" />,
      color: 'bg-primary-600',
      onAction: () => handleOpenModal('edit', customer),
    },
    {
      label: 'Supprimer',
      icon: <Trash2 className="w-4 h-4" />,
      color: 'bg-red-600',
      onAction: () => handleOpenModal('delete', customer),
    },
  ]}
>
  <div
    className="flex items-center gap-3 px-4 py-3 min-h-[60px] cursor-pointer"
    onClick={() => navigate({ to: '/customers/$id', params: { id: String(customer.id) } })}
  >
    {/* contenu card inchangé, sans le CustomerMenu */}
  </div>
</SwipeActions>
```

**Critères done :**
- ☐ `SwipeActions` intégré sur vue mobile
- ☐ Swipe droit → Modifier + Supprimer (touch targets ≥ 44px)
- ☐ Tap sur la ligne → navigate vers fiche
- ☐ `MoreVertical` supprimé sur mobile (conservé desktop)

---

### TASK-CLI-06 (P1) — Formulaire création client adaptatif (bottom-sheet mobile)

**Fichier :** `frontend/src/pages/customers/components/CustomerFormModal.tsx`

**Problème :** Modale classique difficile avec le clavier mobile.

```tsx
// Approche simple : wrapper conditionnel
import { BottomSheet } from '@/components/ui/BottomSheet'
import { Modal } from '@/components/ui/Modal'

// Sur mobile (< 640px) → BottomSheet, sinon → Modal
// Utiliser CSS breakpoint ou hook useIsMobile()
// Extraire le formulaire dans CustomerFormContent (composant interne partagé)
```

**Critères done :**
- ☐ Formulaire accessible sur mobile (clavier ne masque pas les champs)
- ☐ Trap focus interne (Tab cycle, Escape ferme)
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CLI-07 (P2) — Planification relance depuis fiche L2

**Fichier :** `frontend/src/pages/customers/CustomerRelancesPage.tsx` (après TASK-CLI-03)

**Problème :** On peut voir/annuler des relances depuis la fiche, mais pas en créer.

```tsx
<button onClick={() => setPlanifierOpen(true)} className="btn-primary flex items-center gap-2">
  <Plus className="w-4 h-4" />
  Planifier une relance
</button>

<BottomSheet isOpen={planifierOpen} onClose={() => setPlanifierOpen(false)} title="Planifier une relance">
  <RelancePlanifierForm
    customerId={customerId}
    onSuccess={() => {
      setPlanifierOpen(false)
      qc.invalidateQueries({ queryKey: ['relances', 'customer', customerId] })
    }}
  />
</BottomSheet>
```

`RelancePlanifierForm` : sélecteur facture impayée + canal (email/SMS/push) + DatePicker + Textarea message.

**Critères done :**
- ☐ Bouton "Planifier relance" visible sur `CustomerRelancesPage`
- ☐ Bottom-sheet avec formulaire complet
- ☐ Création via `POST /relances` avec `customer_id` + `invoice_id`
- ☐ Invalidation query après succès

---

### TASK-CLI-08 (P2) — Export CSV clients

**Backend :** `GET /customers/export` → CSV utf-8-sig (prepare() obligatoire avant édition)
**Frontend :** bouton dans le header `CustomersPage` + download blob.

**Critères done :**
- ☐ Endpoint export retourne CSV valide
- ☐ Bouton export dans `CustomersPage`
- ☐ Téléchargement déclenché sans navigation
- ☐ Test backend `test_customer_export_csv`

---

### TASK-CLI-09 (P1) — Skeletons `CustomerDetailPage` + `ClientsRelancesPage` + `ClientsRFMPage`

**Problème :**
- `CustomerDetailPage.tsx:35-41` → `<Loader2>` spinner centré pendant `isLoading`
- `ClientsRelancesPage.tsx:94-95` → texte `"Chargement…"` pendant `isLoading`
- `ClientsRFMPage.tsx:32-33` → texte `"Chargement…"` pendant `isLoading`

**`CustomerDetailPage` — skeleton infos :**
```tsx
function CustomerDetailSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header client */}
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-full bg-dark-700" />
        <div className="space-y-2">
          <div className="h-5 bg-dark-700 rounded w-40" />
          <div className="h-3 bg-dark-700 rounded w-28" />
        </div>
      </div>
      {/* 3 StatCards */}
      <div className="grid grid-cols-3 gap-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="card p-4 space-y-2">
            <div className="h-3 bg-dark-700 rounded w-20" />
            <div className="h-6 bg-dark-700 rounded w-16" />
          </div>
        ))}
      </div>
      {/* Infos dl */}
      <div className="card p-4 space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex gap-4">
            <div className="h-3 bg-dark-700 rounded w-24" />
            <div className="h-3 bg-dark-700 rounded w-40" />
          </div>
        ))}
      </div>
    </div>
  )
}

if (isLoading) return <CustomerDetailSkeleton />
```

**`ClientsRelancesPage` — skeleton liste :**
```tsx
function RelanceSkeleton() {
  return (
    <div className="card animate-pulse space-y-2 p-4">
      <div className="flex items-center justify-between">
        <div className="h-4 bg-dark-700 rounded w-36" />
        <div className="h-5 bg-dark-700 rounded-full w-16" />
      </div>
      <div className="h-3 bg-dark-700 rounded w-48" />
      <div className="flex gap-2">
        <div className="h-7 bg-dark-700 rounded w-24" />
        <div className="h-7 bg-dark-700 rounded w-20" />
      </div>
    </div>
  )
}

if (isLoading) return (
  <div className="space-y-3">
    {Array.from({ length: 5 }).map((_, i) => <RelanceSkeleton key={i} />)}
  </div>
)
```

**`ClientsRFMPage` — skeleton :**
```tsx
function RFMSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Matrice RFM placeholder */}
      <div className="card p-4 h-48 bg-dark-700 rounded" />
      {/* Table skeleton */}
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex gap-4 py-2">
            <div className="h-4 bg-dark-700 rounded w-32" />
            <div className="h-4 bg-dark-700 rounded w-20" />
            <div className="h-4 bg-dark-700 rounded w-16" />
          </div>
        ))}
      </div>
    </div>
  )
}

if (isLoading) return <RFMSkeleton />
```

**Critères done :**
- ☐ Aucun `<Loader2>` `isLoading` dans `CustomerDetailPage`
- ☐ Aucun texte `"Chargement…"` dans `ClientsRelancesPage` et `ClientsRFMPage`
- ☐ Skeletons structurés (pas juste des rects vides)

---

### TASK-CLI-10 (P1) — Lignes réservations/factures cliquables dans `CustomerDetailPage`

> **Note :** Cette tâche sera réalisée dans `CustomerReservationsPage` et `CustomerInvoicesPage` lors de TASK-CLI-03.
> Elle est listée ici pour documentation et vérification.

**Problème :** `CustomerDetailPage.tsx:163` — lignes réservations sans `cursor-pointer` ni `onClick`.
`CustomerDetailPage.tsx:197` — lignes factures idem.

**Action (dans les nouvelles pages issues de TASK-CLI-03) :**
```tsx
// CustomerReservationsPage.tsx — chaque ligne cliquable
<tr
  key={resa.id}
  className="cursor-pointer hover:bg-dark-700/30 transition-colors"
  onClick={() => navigate({ to: '/events/$id', params: { id: String(resa.id) } })}
>

// CustomerInvoicesPage.tsx — chaque ligne cliquable
<tr
  key={inv.id}
  className="cursor-pointer hover:bg-dark-700/30 transition-colors"
  onClick={() => navigate({ to: '/invoices/$id', params: { id: String(inv.id) } })}
>
```

**Critères done :**
- ☐ Toutes les lignes réservations cliquables → `/events/$id`
- ☐ Toutes les lignes factures cliquables → `/invoices/$id`
- ☐ Hover state visible sur les lignes

---

### TASK-CLI-11 (P2) — Normaliser classes design system (`text-body`)

**Problème :** `text-body` utilisé × 12 dans le module — classe non définie dans `tailwind.config.js` CaroCorp.

**Fichiers et occurrences :**
- `CustomerDetailPage.tsx` L91, 99, 108, 116, 145, 180, 214 → × 7
- `ClientsRFMPage.tsx` L21, 37, 53, 85 → × 4
- `ClientsRelancesPage.tsx` L116 → × 1

**Action :** Supprimer `text-body` — le texte blanc hérite de `text-white` défini sur `body` dans `index.css`.

```bash
# Vérifier toutes les occurrences du module
grep -n "text-body" frontend/src/pages/customers/**/*.tsx
```

**Critères done :**
- ☐ Aucune occurrence de `text-body` dans le module customers
- ☐ Rendu visuel identique (couleur héritée)
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CLI-12 (P2) — Supprimer double padding `ClientsRFMPage`

**Problème :** `ClientsRFMPage.tsx:18` — `p-4 md:p-6` dans la page. Après TASK-CLI-01 (layout parent avec wrapper `p-4 md:p-6`), le padding sera doublé.

**Action :** Supprimer le padding externe de `ClientsRFMPage` (et de `ClientsRelancesPage` si présent) après création du layout parent.

> Dépend de TASK-CLI-01.

**Critères done :**
- ☐ `ClientsRFMPage` sans `p-4 md:p-6` outer wrapper
- ☐ Pas de double padding visible
- ☐ Vérifier aussi `ClientsRelancesPage` pour le même pattern

---

### TASK-CLI-13 (P2) — Ajouter `onError` aux mutations sans gestion d'erreur

**Problème :**
- `CustomerDetailPage.tsx:239-249` — mutations `markSentRelance.mutate()` et `cancelRelance.mutate()` sans `onError`
- `ClientsRelancesPage.tsx` — mutations `cancelMutation` et `markSentMutation` sans `onError`

Erreurs silencieuses = feedback absent pour l'utilisateur.

**Pattern à appliquer (GOTCHA:FRONTEND:ERROR-PATTERN) :**
```tsx
// Avant (incorrect)
markSentRelance.mutate(id)

// Après (correct)
markSentRelance.mutate(id, {
  onError: (err) => toast.error(
    (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    || 'Impossible de marquer comme envoyée'
  ),
})

cancelRelance.mutate(id, {
  onError: (err) => toast.error(
    (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    || 'Impossible d\'annuler la relance'
  ),
})
```

**Critères done :**
- ☐ Toutes les mutations du module ont un `onError` avec toast
- ☐ Aucun `(err as Error).message` utilisé
- ☐ Messages d'erreur explicites et distincts

---

### TASK-CLI-14 (P2) — URL sync filtres `CustomersPage` + `ClientsRelancesPage`

**Problème :**
- `CustomersPage.tsx:37-41` — `page`, `searchQuery`, `typeFilter`, `relancesOnly` en `useState` → perdus au retour depuis une fiche
- `ClientsRelancesPage.tsx:25` — `statusFilter` en `useState`

**Solution :** `validateSearch` TanStack Router.

```tsx
// routes/_app/customers/index.tsx
export const Route = createFileRoute('/_app/customers/')({
  validateSearch: (search) => ({
    q: (search.q as string) ?? '',
    type: (search.type as string) ?? '',
    relances: Boolean(search.relances),
    page: Number(search.page ?? 1),
  }),
  component: CustomersPage,
})

// Dans CustomersPage :
const search = useSearch({ from: '/_app/customers/' })
const navigate = useNavigate()

const setQ = (q: string) =>
  navigate({ search: (prev) => ({ ...prev, q: q || undefined, page: 1 }) })
const setType = (type: string) =>
  navigate({ search: (prev) => ({ ...prev, type: type || undefined, page: 1 }) })
const setPage = (p: number) =>
  navigate({ search: (prev) => ({ ...prev, page: p }) })
```

```tsx
// routes/_app/customers/relances.tsx
export const Route = createFileRoute('/_app/customers/relances')({
  validateSearch: (search) => ({
    status: (search.status as string) ?? '',
  }),
  component: ClientsRelancesPage,
})
```

**Critères done :**
- ☐ `CustomersPage` : filtres q/type/relances/page dans l'URL
- ☐ `ClientsRelancesPage` : filtre status dans l'URL
- ☐ Retour depuis fiche → filtres préservés
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-CLI-15 (P2) — Lien vers fiche client depuis table RFM

**Fichier :** `frontend/src/pages/customers/ClientsRFMPage.tsx`

**Problème :** La table RFM affiche les clients filtrés par segment mais les lignes ne sont pas cliquables.

```tsx
// Dans la table RFM, chaque ligne cliquable :
<tr
  key={client.id}
  className="cursor-pointer hover:bg-dark-700/30 transition-colors"
  onClick={() => navigate({ to: '/customers/$id', params: { id: String(client.id) } })}
>
  <td className="px-3 py-2 font-medium">{client.display_name}</td>
  {/* ... autres colonnes */}
  <td className="px-3 py-2">
    <ChevronRight className="w-4 h-4 text-dark-400 ml-auto" />
  </td>
</tr>
```

**Critères done :**
- ☐ Chaque ligne de la table RFM cliquable → `/customers/$id`
- ☐ Icône chevron sur chaque ligne
- ☐ Hover state visible

---

## Couverture LAYER.html — Mapping final

| Écran LAYER | Route | Composant | Backend | Statut cible |
|------------|-------|-----------|---------|--------------|
| `s-clients` | `/customers` | `CustomersPage` | `GET /customers` | ✅ → skeleton + swipe |
| `s-client-detail` | `/customers/$id` | `CustomerInfoPage` | `GET /customers/{id}` | ✅ → skeleton + onglets |
| `s-client-reservations` | `/customers/$id/reservations` | `CustomerReservationsPage` | `GET /customers/{id}/history` | ✅ → cliquable |
| `s-client-invoices` | `/customers/$id/invoices` | `CustomerInvoicesPage` | `GET /customers/{id}/history` | ✅ → cliquable |
| `s-client-relances` | `/customers/$id/relances` | `CustomerRelancesPage` | `GET /relances?customer_id` | ✅ → planifier |
| `s-client-form` | Modal/BottomSheet | `CustomerFormModal` | `POST/PATCH /customers` | ✅ → bottom-sheet |
| `s-relances` | `/customers/relances` | `ClientsRelancesPage` | `GET /relances` | ✅ → skeleton + URL sync |
| `s-rfm` | `/customers/rfm` | `ClientsRFMPage` | `GET /customers/rfm` | ✅ → skeleton + lien fiche |
| `s-export-clients` | Bouton dans `/customers` | — | `GET /customers/export` | ⚠️ backend P2 |

---

## Ordre d'exécution recommandé

```
TASK-CLI-01  ← P0 Layout parent + SubNav
TASK-CLI-02  ← P0 Layout fiche + sous-routes (dépend CLI-01)
TASK-CLI-03  ← P0 Éclater CustomerDetailPage (dépend CLI-02)
TASK-CLI-04  ← P1 Skeleton liste L1 (indépendant)
TASK-CLI-05  ← P1 SwipeActions mobile (indépendant)
TASK-CLI-06  ← P1 Formulaire bottom-sheet (indépendant)
TASK-CLI-09  ← P1 Skeletons Detail + Relances + RFM (indépendant)
TASK-CLI-10  ← P1 Lignes cliquables (fait dans CLI-03)
TASK-CLI-07  ← P2 Planification relance (dépend CLI-03)
TASK-CLI-08  ← P2 Export CSV (indépendant)
TASK-CLI-11  ← P2 text-body design system (indépendant)
TASK-CLI-12  ← P2 Double padding (dépend CLI-01)
TASK-CLI-13  ← P2 onError mutations (indépendant)
TASK-CLI-14  ← P2 URL sync filtres (indépendant)
TASK-CLI-15  ← P2 Lien fiche depuis RFM (indépendant)
```

---

## Référence — Fichiers impactés

| Fichier | Action |
|---------|--------|
| `routes/_app/customers.tsx` | **Créer** — layout parent + SubNav |
| `routes/_app/customers/$id.tsx` | **Créer** — layout fiche + SubNav 4 onglets |
| `routes/_app/customers/index.tsx` | Modifier — validateSearch |
| `routes/_app/customers/relances.tsx` | Modifier — validateSearch |
| `pages/customers/CustomersPage.tsx` | Modifier — skeleton, swipe, retirer SubNav/VENTES_NAV/padding |
| `pages/customers/CustomerDetailPage.tsx` | **Supprimer** (remplacé par 4 pages) |
| `pages/customers/CustomerInfoPage.tsx` | **Créer** — infos + KPI + skeleton |
| `pages/customers/CustomerReservationsPage.tsx` | **Créer** — tableau cliquable |
| `pages/customers/CustomerInvoicesPage.tsx` | **Créer** — tableau cliquable |
| `pages/customers/CustomerRelancesPage.tsx` | **Créer** — relances + planifier |
| `pages/customers/ClientsRelancesPage.tsx` | Modifier — skeleton, onError, URL sync, text-body |
| `pages/customers/ClientsRFMPage.tsx` | Modifier — skeleton, text-body, lien fiche, padding |
| `pages/customers/components/CustomerFormModal.tsx` | Modifier — bottom-sheet mobile |
