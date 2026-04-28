# Module 06 — Réservations (Events)

> Roadmap L1→L5 — Audit réel 2026-02-25 | Source : fichiers lus + grep codebase

---

## État actuel — Synthèse audit

### Ce qui fonctionne
- `EventsPage` (435L) : liste paginée, filtre statut, dual view desktop/mobile, onglets Actives/Archives, menu contextuel Confirmer/Annuler, pagination
- `EventDetailsModal` : fiche détail volumineuse (≈900L, 21 hooks), pré-check ✅, extension ✅, risques ✅, dépôts ✅, paiements ✅, signature ✅
- `ReservationCreatePage` : react-hook-form + zodResolver, ComboboxAsync client, CataloguePickerModal
- `ReservationLinesPage` : ajout/suppression lignes, guard isDraft, search produits debounce
- `SignaturePage` : canvas signature touch events, couleurs design system
- Machine d'états 13 statuts backend : draft → confirmed → delivered → completed

### Anti-patterns identifiés

| ID | Fichier | Problème | Priorité |
|----|---------|----------|----------|
| AP-01 | `EventsPage.tsx:8-14` | `VENTES_NAV` cross-module embarqué dans la page (SubNav devrait être dans le layout parent `events.tsx`) | P0 |
| AP-02 | `EventsPage.tsx` | Loading = `<Spinner>` — skeleton obligatoire selon PDF UI/UX règle #3 | P1 |
| AP-03 | `EventsPage.tsx` | Cards mobile sans `SwipeActions` — PDF règle #5 | P1 |
| AP-04 | `EventDetailsModal` | Fiche sans URL propre — pas navigable, pas partageable, pas bookmarkable | P0 |
| AP-05 | `ReservationLinesPage` | Loading = texte "Chargement…" — skeleton obligatoire | P1 |
| AP-06 | `routes/_app/events.tsx` | Layout `<Outlet />` nu — pas de SubNav module | P0 |
| AP-07 | `EventDetailsModal` | 900L + 21 hooks dans un seul composant — non maintenable | P1 |

---

## Tâches L1→L5

### TASK-RES-01 (P0) — SubNav layout module Réservations

**Problème** : `routes/_app/events.tsx` est un `<Outlet />` nu. L'anti-pattern `VENTES_NAV` est défini
dans `EventsPage.tsx` et inclut des liens cross-modules (Devis, Clients, Ventes) — il doit disparaître.

**Solution** : Ajouter SubNav propre au module dans le layout parent. Les onglets cross-modules
seront gérés par chaque layout respectif (cf. TASK-DEV-01, TASK-VEN-01, TASK-CLI-01).

**Fichier à modifier** : `frontend/src/routes/_app/events.tsx`

```tsx
// routes/_app/events.tsx
import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

const EVENTS_NAV = [
  { label: 'Réservations', href: '/events' },
  { label: 'Agenda',       href: '/agenda' },
]

export const Route = createFileRoute('/_app/events')({
  component: () => (
    <div className="space-y-0">
      <SubNav items={EVENTS_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  ),
})
```

**Fichier à modifier** : `frontend/src/pages/events/EventsPage.tsx`

```tsx
// Supprimer ces lignes (AP-01) :
// const VENTES_NAV = [...]
// <SubNav items={VENTES_NAV} />  (et le import SubNav si plus utilisé ailleurs)

// Garder uniquement le contenu métier :
export default function EventsPage() {
  // ... état local, hooks, filtres — sans SubNav
}
```

**Critères done** :
- ☐ `routes/_app/events.tsx` contient SubNav `[Réservations | Agenda]`
- ☐ `EventsPage` ne contient plus `VENTES_NAV` ni import `SubNav`
- ☐ Navigation `/events` → SubNav visible, onglet actif correct
- ☐ `tsc --noEmit` 0 erreur
- ☐ 1582 Vitest pass

---

### TASK-RES-02 (P0) — Modal → Page : fiche réservation avec URL propre

**Problème** : `EventDetailsModal` (≈900L, 21 hooks) s'ouvre en overlay depuis la liste.
La fiche n'a pas d'URL — non navigable, non partageable, back button casse le flow.

**Solution** : Créer une route `$id.tsx` (layout fiche) + `$id/index.tsx` (page détail).
Supprimer l'ouverture modal depuis la liste, remplacer par `navigate({ to: '/events/$id' })`.

**Fichiers à créer** :

```
frontend/src/routes/_app/events/
  $id.tsx          ← layout fiche avec SubNav [Détails | Articles | Signature]
  $id/
    index.tsx      ← page principale fiche (contenu actuel de EventDetailsModal)
    lines.tsx      ← déjà existant → ReservationLinesPage (rattacher ici)
    signature.$reservationId.tsx  ← déjà existant → SignaturePage
```

```tsx
// routes/_app/events/$id.tsx — layout fiche réservation
import { createFileRoute, Outlet, useParams } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

function ReservationDetailLayout() {
  const { id } = useParams({ strict: false })
  const FICHE_NAV = [
    { label: 'Détails',   href: `/events/${id}` },
    { label: 'Articles',  href: `/events/${id}/lines` },
    { label: 'Signature', href: `/events/${id}/signature/${id}` },
  ]
  return (
    <div className="space-y-0">
      <SubNav items={FICHE_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  )
}

export const Route = createFileRoute('/_app/events/$id')({
  component: ReservationDetailLayout,
})
```

```tsx
// routes/_app/events/$id/index.tsx — page fiche
import { createFileRoute } from '@tanstack/react-router'
import ReservationDetailPage from '@/pages/events/ReservationDetailPage'

export const Route = createFileRoute('/_app/events/$id/')({
  component: ReservationDetailPage,
})
```

**`EventsPage` — remplacer onClick modal par navigation** :

```tsx
// Avant (modal) :
<button onClick={() => setSelectedReservation(r)}>…</button>

// Après (navigation) :
<Link to="/events/$id" params={{ id: String(r.id) }}>…</Link>
// ou dans un handler :
navigate({ to: '/events/$id', params: { id: String(r.id) } })
```

**Nouveau fichier** `pages/events/ReservationDetailPage.tsx` :
- Reprend le contenu de `EventDetailsModal` (sections infos, dépôts, paiements, pré-check, risques, extension, audit)
- Supprime les props `isOpen/onClose` du modal
- Ajoute bouton retour `<Link to="/events">←</Link>` en header

**Critères done** :
- ☐ Route `/_app/events/$id/` accessible via URL `/events/42`
- ☐ `EventsPage` ne contient plus `selectedReservation` state ni `EventDetailsModal`
- ☐ Toutes les sections (pré-check, risques, dépôts, paiements, extension) fonctionnelles en page
- ☐ Back button navigateur → retour liste `/events`
- ☐ `tsc --noEmit` 0 erreur
- ☐ 1582 Vitest pass

---

### TASK-RES-03 (P1) — Skeleton loading L1 liste réservations

**Problème** : `EventsPage` affiche `<Spinner size="lg" />` pendant le chargement.
Selon PDF règle #3, le skeleton est obligatoire sur toute liste L1 (premier affichage perçu 40% plus rapide).

**Fichier à modifier** : `frontend/src/pages/events/EventsPage.tsx`

```tsx
// Composant skeleton carte réservation (à extraire en composant)
function ReservationCardSkeleton() {
  return (
    <div className="card animate-pulse">
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 bg-dark-700 rounded-lg shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="h-4 bg-dark-700 rounded w-1/2" />
          <div className="h-3 bg-dark-700 rounded w-1/3" />
          <div className="h-3 bg-dark-700 rounded w-2/3 mt-2" />
        </div>
        <div className="w-16 h-5 bg-dark-700 rounded-full shrink-0" />
      </div>
    </div>
  )
}

// Dans EventsPage, remplacer :
// if (isLoading) return <Spinner />
// Par :
{isLoading ? (
  Array.from({ length: 6 }).map((_, i) => <ReservationCardSkeleton key={i} />)
) : (
  // ... liste réelle
)}
```

**Version tableau desktop** (si dual view) :

```tsx
function ReservationRowSkeleton() {
  return (
    <tr className="animate-pulse">
      {Array.from({ length: 7 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 bg-dark-700 rounded w-full" />
        </td>
      ))}
    </tr>
  )
}
```

**Critères done** :
- ☐ Desktop : tableau skeleton 6 lignes (7 colonnes chacune)
- ☐ Mobile : cards skeleton 6 items avec animate-pulse
- ☐ Plus aucun `<Spinner>` dans EventsPage (ni dans les sous-pages)
- ☐ Skeleton visible même sur réseau rapide (prévoir délai 300ms si nécessaire pour valider visuellement)

---

### TASK-RES-04 (P1) — SwipeActions mobile L1

**Problème** : Cards mobile dans `EventsPage` n'ont pas de gestes swipe.
Selon PDF règle #5, les listes mobiles doivent supporter swipe-left (actions contextuelles).

**Fichier à modifier** : `frontend/src/pages/events/EventsPage.tsx`

Le composant `SwipeActions` existe dans `frontend/src/components/ui/SwipeActions.tsx`.

```tsx
import { SwipeActions } from '@/components/ui/SwipeActions'

// Dans le rendu mobile (cards), wrapper chaque card :
{filteredReservations.map((r) => (
  <SwipeActions
    key={r.id}
    leftActions={[
      {
        label: 'Confirmer',
        icon: <CheckCircle className="w-4 h-4" />,
        color: 'bg-green-500',
        onAction: () => handleConfirm(r.id),
        hidden: r.status !== 'draft',
      },
    ]}
    rightActions={[
      {
        label: 'Annuler',
        icon: <XCircle className="w-4 h-4" />,
        color: 'bg-red-500',
        onAction: () => handleCancel(r.id),
        hidden: !['draft', 'confirmed'].includes(r.status),
      },
    ]}
  >
    <ReservationCard reservation={r} />
  </SwipeActions>
))}
```

**Touch target** : Chaque card ≥ 44px de hauteur (PDF règle #1).
Vérifier que `padding-y` du card est suffisant : `py-4` minimum.

**Critères done** :
- ☐ Swipe-right → bouton Confirmer visible (uniquement si statut `draft`)
- ☐ Swipe-left → bouton Annuler visible (statuts `draft` ou `confirmed`)
- ☐ Actions cachées (`hidden: true`) selon statut — pas de swipe vide
- ☐ Touch target cards ≥ 44px hauteur
- ☐ Comportement uniquement sur viewport mobile (pas desktop)

---

### TASK-RES-05 (P1) — Découpe ReservationDetailPage (ex-EventDetailsModal)

**Problème** : `EventDetailsModal` ≈ 900L avec 21 hooks. Non maintenable, non testable,
rechargement complet à chaque mutation.

**Solution** : Extraire 7 sections en composants autonomes avec props minimales.

**Architecture cible** :

```
pages/events/
  ReservationDetailPage.tsx          ← résidu < 150L (header + assembly)
  components/
    ReservationInfoSection.tsx       ← infos client, dates, type, nb invités (~80L)
    ReservationDepositsSection.tsx   ← cautions held/released/retained (~100L)
    ReservationPaymentsSection.tsx   ← paiements + solde restant (~100L)
    ReservationPreCheckSection.tsx   ← pré-check items + progression (~120L)
    ReservationRisksSection.tsx      ← risques déclarés/résolus (~120L)
    ReservationExtendSection.tsx     ← formulaire extension date retour (~80L)
    ReservationAuditSection.tsx      ← timeline audit trail (~60L)
```

**Contrat de chaque section** :

```tsx
// Interface commune : recevoir reservationId, pas l'objet entier
// Chaque section fetch ses propres données avec useQuery

interface ReservationSectionProps {
  reservationId: number
}

// Exemple — ReservationPreCheckSection.tsx
export function ReservationPreCheckSection({ reservationId }: ReservationSectionProps) {
  const { data: preCheck, isLoading } = usePreCheckItems(reservationId)
  const completeMutation = useCompletePreCheck(reservationId)

  if (isLoading) return <SectionSkeleton rows={4} />
  // ...
}
```

**ReservationDetailPage résidu** :

```tsx
export default function ReservationDetailPage() {
  const { id } = useParams({ strict: false })
  const reservationId = Number(id)
  const { data: reservation, isLoading } = useReservationDetail(reservationId)

  if (isLoading) return <ReservationDetailSkeleton />
  if (!reservation) return <NotFound />

  return (
    <div className="space-y-4">
      <ReservationHeader reservation={reservation} />
      <ReservationInfoSection reservationId={reservationId} />
      <ReservationDepositsSection reservationId={reservationId} />
      <ReservationPaymentsSection reservationId={reservationId} />
      {['confirmed', 'pre_check'].includes(reservation.status) && (
        <ReservationPreCheckSection reservationId={reservationId} />
      )}
      {['confirmed', 'confirmed_risk', 'delivered', 'in_progress'].includes(reservation.status) && (
        <ReservationRisksSection reservationId={reservationId} />
      )}
      {['delivered', 'in_progress', 'extended'].includes(reservation.status) && (
        <ReservationExtendSection reservationId={reservationId} />
      )}
      <ReservationAuditSection reservationId={reservationId} />
    </div>
  )
}
```

**Critères done** :
- ☐ `ReservationDetailPage` ≤ 150L
- ☐ 7 composants sections créés, chacun ≤ 130L
- ☐ Chaque section a son propre `useQuery` (pas de prop drilling)
- ☐ Skeleton section individuel (pas spinner global)
- ☐ `tsc --noEmit` 0 erreur
- ☐ 1582 Vitest pass

---

### TASK-RES-06 (P1) — Skeleton loading sous-pages (Lines, Signature)

**Problème** : `ReservationLinesPage` affiche `"Chargement…"` texte pendant le fetch.
Toutes les sous-pages doivent respecter le standard skeleton du module.

**Fichier à modifier** : `frontend/src/pages/events/ReservationLinesPage.tsx`

```tsx
// Skeleton ligne article
function ReservationLineSkeleton() {
  return (
    <div className="flex items-center gap-3 py-3 border-b border-dark-700 animate-pulse">
      <div className="w-10 h-10 bg-dark-700 rounded-lg shrink-0" />
      <div className="flex-1 space-y-1.5">
        <div className="h-4 bg-dark-700 rounded w-1/2" />
        <div className="h-3 bg-dark-700 rounded w-1/4" />
      </div>
      <div className="w-20 h-8 bg-dark-700 rounded" />
    </div>
  )
}

// Remplacer le loading texte :
{isLoading ? (
  Array.from({ length: 4 }).map((_, i) => <ReservationLineSkeleton key={i} />)
) : (
  // ... lignes réelles
)}
```

**Critères done** :
- ☐ `ReservationLinesPage` : skeleton animate-pulse 4 lignes
- ☐ `SignaturePage` : pas de loading bloquant (canvas immédiat)
- ☐ Aucun texte "Chargement…" dans les sous-pages réservation

---

### TASK-RES-07 (P2) — Search & filtres persistants L1

**Problème** : Les filtres statut dans `EventsPage` se réinitialisent à la navigation.
Sur mobile, la zone de recherche est visible mais non persistante.

**Solution** : Persister le filtre statut et la recherche dans l'URL (searchParams).

```tsx
// Utiliser les searchParams TanStack Router
import { useSearch, useNavigate } from '@tanstack/react-router'

// Dans EventsPage :
const search = useSearch({ from: '/_app/events/' })
const navigate = useNavigate()

const statusFilter = search.status ?? 'all'
const searchText = search.q ?? ''

const setStatusFilter = (s: string) =>
  navigate({ search: (prev) => ({ ...prev, status: s }) })

const setSearchText = (q: string) =>
  navigate({ search: (prev) => ({ ...prev, q: q || undefined }) })
```

**Validation du schéma route** :

```tsx
// Dans routes/_app/events/index.tsx
export const Route = createFileRoute('/_app/events/')({
  validateSearch: (search) => ({
    status: (search.status as string) ?? 'all',
    q: (search.q as string) ?? '',
  }),
  component: EventsPage,
})
```

**Critères done** :
- ☐ Filtre statut persisté dans l'URL `?status=confirmed`
- ☐ Recherche persistée `?q=dupont`
- ☐ Back button → filtres restaurés (UX mobile critique)
- ☐ Navigation vers fiche puis retour → même filtres actifs
- ☐ URL partageable avec filtres pré-appliqués

---

### TASK-RES-08 (P2) — Normaliser classe `text-body` dans EventsPage

**Problème** : `EventsPage.tsx:168` utilise la classe `text-body` qui n'est pas définie dans le
design system Tailwind configuré du projet.

**Fichier à modifier** : `frontend/src/pages/events/EventsPage.tsx`

**Correction** :

| Ligne | Classe actuelle | Remplacement |
|-------|----------------|--------------|
| L168 | `text-body` | *(supprimer)* — héritage `text-white` du parent |

**Critères done** :
- ☐ Aucune occurrence de `text-body` dans `EventsPage`
- ☐ Rendu visuel identique

---

### TASK-RES-09 (P2) — Ajouter `onSuccess` aux mutations EventsPage

**Problème** : Les mutations `confirmMutation` (L122) et `cancelMutation` (L133) dans `EventsPage`
n'ont pas de `onSuccess`. Les données ne sont pas invalidées après l'action → la liste reste périmée
jusqu'au prochain refetch automatique.

**Fichier à modifier** : `frontend/src/pages/events/EventsPage.tsx`

```tsx
// Avant — confirmMutation sans onSuccess :
const confirmMutation = useMutation({
  mutationFn: (id: number) => reservationsApi.confirm(id),
  onError: (err) => showError(/* ... */),
})

// Après — avec onSuccess :
const confirmMutation = useMutation({
  mutationFn: (id: number) => reservationsApi.confirm(id),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['reservations'] })
    showSuccess('Réservation confirmée')
  },
  onError: (err) => showError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Erreur confirmation'),
})

// Pareil pour cancelMutation :
const cancelMutation = useMutation({
  mutationFn: (id: number) => reservationsApi.cancel(id),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['reservations'] })
    showSuccess('Réservation annulée')
  },
  onError: (err) => showError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Erreur annulation'),
})
```

**Critères done** :
- ☐ `confirmMutation` a un `onSuccess` invalidant `['reservations']`
- ☐ `cancelMutation` a un `onSuccess` invalidant `['reservations']`
- ☐ Feedback utilisateur (toast ou état visuel) sur chaque succès
- ☐ `tsc` 0 erreur

---

### TASK-RES-10 (P1) — URL sync tab et pagination dans EventsPage

**Problème** : `EventsPage.tsx:52-54` gère les filtres en `useState` local :
- `page` : pagination, réinitialisée à chaque navigation
- `tab` : onglet Actives / Archives, perdu au retour
- `openMenuId` + `menuPosition` : état UI local — ceux-ci sont OK en local (UI state),
  mais `page` et `tab` doivent être dans l'URL.

> Note : `status` et `q` sont partiellement couverts par TASK-RES-07, mais `page` et `tab`
> ne l'étaient pas. Cette tâche complète TASK-RES-07.

**Fichier à modifier** :
- `frontend/src/routes/_app/events/index.tsx` — compléter `validateSearch`
- `frontend/src/pages/events/EventsPage.tsx` — migrer `page` + `tab` vers searchParams

```tsx
// routes/_app/events/index.tsx — validateSearch complet
export const Route = createFileRoute('/_app/events/')({
  validateSearch: (search) => ({
    status: typeof search.status === 'string' ? search.status : 'all',
    q:      typeof search.q      === 'string' ? search.q      : '',
    page:   typeof search.page   === 'number' ? search.page   : 1,
    tab:    search.tab === 'archives' ? 'archives' : 'actives',
  }),
  component: EventsPage,
})
```

```tsx
// EventsPage.tsx — remplacer useState par searchParams
const search = useSearch({ from: '/_app/events/' })
const page   = search.page ?? 1
const tab    = search.tab  ?? 'actives'

const setPage = (p: number) => navigate({ search: (prev) => ({ ...prev, page: p }) })
const setTab  = (t: string) => navigate({ search: (prev) => ({ ...prev, tab: t, page: 1 }) })
// openMenuId / menuPosition restent en useState (UI state pur, pas besoin d'URL)
```

**Critères done** :
- ☐ `validateSearch` inclut `page` et `tab` (en plus de TASK-RES-07 pour status/q)
- ☐ `useState` pour `page` et `tab` supprimés de `EventsPage`
- ☐ Retour depuis fiche → onglet actif + page restaurés
- ☐ URL `/events?tab=archives&page=2` fonctionne directement
- ☐ `tsc` 0 erreur

---

## Couverture LAYER.html — Mapping final

| Écran LAYER | Route | Composant | Backend | Statut cible |
|------------|-------|-----------|---------|--------------|
| `s-reservations` | `/events` | `EventsPage` | `GET /reservations` | ✅ → améliorer (skeleton, swipe) |
| `s-reservation-detail` | `/events/$id` | `ReservationDetailPage` | `GET /reservations/{id}` | ⚡ TASK-RES-02 |
| `s-reservation-form` | `/events/new` | `ReservationCreatePage` | `POST /reservations` | ✅ |
| `s-reservation-lines` | `/events/$id/lines` | `ReservationLinesPage` | `GET /reservations/{id}/lines` | ✅ → skeleton TASK-RES-06 |
| `s-reservation-signature` | `/events/$id/signature/$id` | `SignaturePage` | `POST signature` | ✅ |
| `s-reservation-caution` | Onglet fiche | `ReservationDepositsSection` | `/deposits` CRUD | ✅ |
| `s-pre-check` | Onglet fiche | `ReservationPreCheckSection` | `/pre-check` | ✅ → découpe TASK-RES-05 |
| `s-extension` | Onglet fiche | `ReservationExtendSection` | `POST /extend` | ✅ → découpe TASK-RES-05 |
| `s-risques` | Onglet fiche | `ReservationRisksSection` | `/risks` CRUD | ✅ → découpe TASK-RES-05 |
| `s-agenda` | `/agenda` | `AgendaPage` | `/planning/week` | ✅ |

---

## Ordre d'exécution recommandé

```
TASK-RES-01  ← P0 SubNav (supprimer VENTES_NAV)
TASK-RES-02  ← P0 Modal→Page (URL propre fiche)
TASK-RES-05  ← P1 Découpe composants (dépend de RES-02)
TASK-RES-03  ← P1 Skeleton L1 (indépendant)
TASK-RES-04  ← P1 SwipeActions mobile (indépendant)
TASK-RES-06  ← P1 Skeleton sous-pages (dépend de RES-02)
TASK-RES-07  ← P2 URL sync status + q (indépendant)
TASK-RES-10  ← P1 URL sync page + tab (complète RES-07)
TASK-RES-09  ← P2 onSuccess mutations confirmMutation/cancelMutation (indépendant)
TASK-RES-08  ← P2 Classe text-body (indépendant)
```

---

## Référence — Fichiers impactés

| Fichier | Action |
|---------|--------|
| `routes/_app/events.tsx` | Modifier — ajouter SubNav |
| `routes/_app/events/$id.tsx` | **Créer** — layout fiche |
| `routes/_app/events/$id/index.tsx` | **Créer** — route page fiche |
| `pages/events/EventsPage.tsx` | Modifier — supprimer VENTES_NAV, skeleton, swipe |
| `pages/events/EventDetailsModal.tsx` | **Supprimer** — contenu migré vers ReservationDetailPage |
| `pages/events/ReservationDetailPage.tsx` | **Créer** — page fiche (ex-modal) |
| `pages/events/ReservationLinesPage.tsx` | Modifier — skeleton loading |
| `pages/events/components/ReservationInfoSection.tsx` | **Créer** |
| `pages/events/components/ReservationDepositsSection.tsx` | **Créer** |
| `pages/events/components/ReservationPaymentsSection.tsx` | **Créer** |
| `pages/events/components/ReservationPreCheckSection.tsx` | **Créer** |
| `pages/events/components/ReservationRisksSection.tsx` | **Créer** |
| `pages/events/components/ReservationExtendSection.tsx` | **Créer** |
| `pages/events/components/ReservationAuditSection.tsx` | **Créer** |
