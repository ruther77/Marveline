# Module 07 — Événements terrain (Suivi opérationnel)

> Roadmap L1→L5 — Audit réel 2026-02-25 | Source : fichiers lus + grep codebase

---

## État actuel — Synthèse audit

### Ce qui fonctionne bien
- `EvenementsListPage` (169L) : liste paginée, filtre statut + search, dual view desktop/mobile, pagination, `DomainStatusBadge`, navigation vers fiche — **pas de modal** ✅
- `EvenementDetailPage` (314L) : **fiche en page dédiée** (pas de modal), machine d'états visuelle, incidents actifs/résolus, plan d'action par incident, SLA badge, modals d'action (`DeclareIncident`, `CreateActionPlan`, `MarkReturned`)
- Machine d'états 8 statuts complète côté frontend + backend

### Anti-patterns identifiés

| ID | Fichier | Problème | Priorité |
|----|---------|----------|----------|
| AP-01 | `routes/_app/evenements.tsx` | Layout `<Outlet />` nu — pas de SubNav module | P0 |
| AP-02 | `EvenementsListPage.tsx:80,116` | Loading = texte `"Chargement…"` desktop ET mobile | P1 |
| AP-03 | `EvenementDetailPage.tsx:112` | Loading = texte `"Chargement…"` fiche | P1 |
| AP-04 | `EvenementsListPage.tsx` | Cards mobile sans `SwipeActions` | P1 |
| AP-05 | `EvenementsListPage.tsx:39,91,129,131` | Classes non-standard `text-body` (non défini dans design system) | P2 |
| AP-06 | `EvenementsListPage.tsx` | Filtres statut + search non persistés dans l'URL | P2 |
| AP-07 | `EvenementDetailPage.tsx` | Pas de SubNav fiche (si onglets à venir : détail / plan d'action) | P2 |

**Note positive** : Ce module utilise déjà la bonne architecture (fiche = page, pas modal).
Pas de cross-module anti-pattern VENTES_NAV.

---

## Tâches L1→L5

### TASK-EVN-01 (P0) — SubNav layout module Événements

**Problème** : `routes/_app/evenements.tsx` est un `<Outlet />` nu.
Ce module est autonome (pas de VENTES_NAV cross-module), mais la SubNav reste nécessaire
pour préparer les onglets futurs (ex: `Agenda`).

**Fichier à modifier** : `frontend/src/routes/_app/evenements.tsx`

```tsx
// routes/_app/evenements.tsx
import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

const EVENEMENTS_NAV = [
  { label: 'Événements', href: '/evenements' },
]

export const Route = createFileRoute('/_app/evenements')({
  component: () => (
    <div className="space-y-0">
      <SubNav items={EVENEMENTS_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  ),
})
```

> Note : le `p-4 md:p-6` est actuellement dans chaque page (`EvenementsListPage`, `EvenementDetailPage`).
> Après ajout du wrapper, supprimer le padding redondant dans chaque page.

**Critères done** :
- ☐ `routes/_app/evenements.tsx` contient SubNav
- ☐ Padding `p-4 md:p-6` retiré des pages individuelles (sinon double padding)
- ☐ `tsc --noEmit` 0 erreur
- ☐ 1582 Vitest pass

---

### TASK-EVN-02 (P1) — Skeleton loading L1 liste événements

**Problème** : `EvenementsListPage` affiche le texte `"Chargement…"` côté desktop (dans `<td>`)
et côté mobile (dans `<p>`). Règle UI/UX PDF #3 : skeleton obligatoire sur liste L1.

**Fichier à modifier** : `frontend/src/pages/evenements/EvenementsListPage.tsx`

**Skeleton tableau desktop** :

```tsx
function EvenementRowSkeleton() {
  return (
    <tr className="animate-pulse border-b border-dark-700/50">
      <td className="px-4 py-3">
        <div className="h-4 bg-dark-700 rounded w-40" />
      </td>
      <td className="px-4 py-3">
        <div className="h-4 bg-dark-700 rounded w-28" />
      </td>
      <td className="px-4 py-3">
        <div className="h-4 bg-dark-700 rounded w-20" />
      </td>
      <td className="px-4 py-3">
        <div className="h-5 bg-dark-700 rounded-full w-16" />
      </td>
      <td className="px-4 py-3">
        <div className="h-4 bg-dark-700 rounded w-24" />
      </td>
      <td className="px-4 py-3" />
    </tr>
  )
}

// Remplacer dans le tbody :
{isLoading ? (
  Array.from({ length: 8 }).map((_, i) => <EvenementRowSkeleton key={i} />)
) : items.length === 0 ? (
  <tr><td colSpan={6} className="px-4 py-8 text-center text-dark-400">Aucun événement trouvé</td></tr>
) : (
  items.map((ev) => /* ... */)
)}
```

**Skeleton cards mobile** :

```tsx
function EvenementCardSkeleton() {
  return (
    <div className="card animate-pulse">
      <div className="flex items-start justify-between mb-2">
        <div className="space-y-2 flex-1">
          <div className="h-4 bg-dark-700 rounded w-1/2" />
          <div className="h-3 bg-dark-700 rounded w-1/3" />
          <div className="h-3 bg-dark-700 rounded w-2/3" />
        </div>
        <div className="h-5 bg-dark-700 rounded-full w-16 ml-3" />
      </div>
    </div>
  )
}

// Remplacer dans le rendu mobile :
{isLoading ? (
  Array.from({ length: 6 }).map((_, i) => <EvenementCardSkeleton key={i} />)
) : /* ... */}
```

**Critères done** :
- ☐ Desktop : skeleton 8 lignes tableau
- ☐ Mobile : skeleton 6 cards
- ☐ Aucun texte `"Chargement…"` dans `EvenementsListPage`

---

### TASK-EVN-03 (P1) — Skeleton loading fiche événement

**Problème** : `EvenementDetailPage.tsx:112` affiche `"Chargement…"` texte.

**Fichier à modifier** : `frontend/src/pages/evenements/EvenementDetailPage.tsx`

```tsx
function EvenementDetailSkeleton() {
  return (
    <div className="max-w-3xl mx-auto space-y-5 animate-pulse">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 bg-dark-700 rounded shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-2">
            <div className="h-6 bg-dark-700 rounded w-48" />
            <div className="h-5 bg-dark-700 rounded-full w-16" />
          </div>
          <div className="flex gap-3">
            <div className="h-3 bg-dark-700 rounded w-20" />
            <div className="h-3 bg-dark-700 rounded w-24" />
          </div>
        </div>
      </div>
      {/* Transitions card */}
      <div className="card">
        <div className="h-3 bg-dark-700 rounded w-32 mb-3" />
        <div className="flex gap-2">
          <div className="h-8 bg-dark-700 rounded-lg w-24" />
          <div className="h-8 bg-dark-700 rounded-lg w-28" />
        </div>
      </div>
      {/* Incidents card */}
      <div className="card space-y-3">
        <div className="h-4 bg-dark-700 rounded w-36" />
        <div className="h-16 bg-dark-700 rounded-xl" />
        <div className="h-16 bg-dark-700 rounded-xl" />
      </div>
    </div>
  )
}

// Remplacer :
// if (isLoading) return <div className="p-6 text-center text-dark-400">Chargement…</div>
if (isLoading) return <EvenementDetailSkeleton />
```

**Critères done** :
- ☐ Fiche : skeleton structuré (header + transitions card + incidents card)
- ☐ Aucun texte `"Chargement…"` dans `EvenementDetailPage`

---

### TASK-EVN-04 (P1) — SwipeActions mobile L1

**Problème** : Cards mobile dans `EvenementsListPage` navigent via `onClick` sans swipe.
PDF règle #5 : swipe-right = action principale, swipe-left = actions secondaires.

**Fichier à modifier** : `frontend/src/pages/evenements/EvenementsListPage.tsx`

```tsx
import { SwipeActions } from '@/components/ui/SwipeActions'
import { Play, Flag, XCircle } from 'lucide-react'

// Remplacer les cards mobiles par :
{items.map((ev) => (
  <SwipeActions
    key={ev.id}
    rightActions={[
      {
        label: 'Annuler',
        icon: <XCircle className="w-4 h-4" />,
        color: 'bg-red-500',
        onAction: () => navigate({ to: '/evenements/$id', params: { id: String(ev.id) } }),
        // Note : annulation depuis la liste redirige vers la fiche pour confirmation
        hidden: !['planned', 'risk', 'in_progress'].includes(ev.status),
      },
    ]}
    leftActions={[
      {
        label: 'Démarrer',
        icon: <Play className="w-4 h-4" />,
        color: 'bg-green-600',
        onAction: () => navigate({ to: '/evenements/$id', params: { id: String(ev.id) } }),
        hidden: ev.status !== 'planned',
      },
    ]}
  >
    <div
      className="card cursor-pointer"
      onClick={() => navigate({ to: '/evenements/$id', params: { id: String(ev.id) } })}
    >
      {/* ... contenu card inchangé */}
    </div>
  </SwipeActions>
))}
```

> Note : les actions swipe redirigent vers la fiche plutôt qu'exécuter directement,
> pour respecter la confirmation utilisateur sur les transitions irréversibles.

**Critères done** :
- ☐ Swipe-left → bouton Démarrer (statut `planned` uniquement)
- ☐ Swipe-right → bouton Annuler (statuts `planned`, `risk`, `in_progress`)
- ☐ Touch target cards ≥ 44px hauteur
- ☐ Uniquement sur viewport mobile

---

### TASK-EVN-05 (P2) — Normaliser classes design system

**Problème** : `EvenementsListPage` et `EvenementDetailPage` utilisent `text-body` — classe
non définie dans le design system Tailwind (ni dans `tailwind.config.js` CaroCorp).
Conséquence : couleur de texte inconnue en production, dépendante d'un CSS externe incohérent.

**Correspondances à appliquer** :

| Classe actuelle | Remplacement |
|----------------|--------------|
| `text-body` | *(supprimer)* — le texte blanc par défaut est `text-white` ou hérité |
| `text-muted` | `text-dark-400` |
| `text-accent` | `text-primary-400` ou `text-gold-400` selon contexte |

**Fichiers à modifier** :
- `frontend/src/pages/evenements/EvenementsListPage.tsx` (lignes 39, 91, 129, 131)
- `frontend/src/pages/evenements/EvenementDetailPage.tsx` (lignes 131, 219)

**Méthode** : grep + replace, vérifier rendu visuel après chaque remplacement.

```bash
# Vérifier toutes les occurrences dans le module
grep -n "text-body\|text-muted\|text-accent" \
  frontend/src/pages/evenements/**/*.tsx
```

**Critères done** :
- ☐ Aucune occurrence de `text-body`, `text-muted`, `text-accent` dans le module
- ☐ Rendu visuel identique (vérifier dans le navigateur)
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-EVN-06 (P2) — Filtres persistés dans l'URL

**Problème** : Statut et texte de recherche dans `EvenementsListPage` sont en state React local
(`useState`). Au retour depuis une fiche, les filtres sont perdus.

**Solution** : Utiliser `validateSearch` TanStack Router.

```tsx
// routes/_app/evenements/index.tsx
export const Route = createFileRoute('/_app/evenements/')({
  validateSearch: (search) => ({
    status: (search.status as string) ?? '',
    q: (search.q as string) ?? '',
    page: Number(search.page ?? 1),
  }),
  component: EvenementsListPage,
})
```

```tsx
// Dans EvenementsListPage :
import { useSearch, useNavigate } from '@tanstack/react-router'

const search = useSearch({ from: '/_app/evenements/' })
const navigate = useNavigate()

const status = (search.status ?? '') as EventStatus | ''
const searchText = search.q ?? ''
const page = search.page ?? 1

const setStatus = (s: string) =>
  navigate({ search: (prev) => ({ ...prev, status: s || undefined, page: 1 }) })

const setSearchText = (q: string) =>
  navigate({ search: (prev) => ({ ...prev, q: q || undefined, page: 1 }) })

const setPage = (p: number) =>
  navigate({ search: (prev) => ({ ...prev, page: p }) })
```

**Critères done** :
- ☐ URL `?status=incident&q=dupont&page=2` fonctionne
- ☐ Retour depuis fiche → filtres préservés
- ☐ URL partageable avec filtres pré-appliqués
- ☐ `tsc --noEmit` 0 erreur

---

## Couverture LAYER.html — Mapping final

| Écran LAYER | Route | Composant | Backend | Statut cible |
|------------|-------|-----------|---------|--------------|
| `s-evenements` | `/evenements` | `EvenementsListPage` | `GET /evenements` | ✅ → skeleton + swipe |
| `s-evenement-detail` | `/evenements/$id` | `EvenementDetailPage` | `GET /evenements/{id}` | ✅ → skeleton |
| `s-evenement-incident` | Fiche | `DeclareIncidentModal` | `POST /incidents` | ✅ |
| `s-evenement-action-plan` | Fiche | `CreateActionPlanModal` | `POST /action-plan` | ✅ |
| `s-evenement-risque` | Fiche | Bouton machine d'états | `POST /flag-risk` | ✅ |
| `s-evenement-cancel` | Fiche | Bouton machine d'états | `POST /cancel` | ✅ |
| `s-evenement-returned` | Fiche | `MarkReturnedModal` | `POST /mark-returned` | ✅ |

---

## Ordre d'exécution recommandé

```
TASK-EVN-01  ← P0 SubNav layout
TASK-EVN-02  ← P1 Skeleton L1 (indépendant)
TASK-EVN-03  ← P1 Skeleton fiche (indépendant)
TASK-EVN-04  ← P1 SwipeActions mobile (indépendant)
TASK-EVN-05  ← P2 Design system (indépendant)
TASK-EVN-06  ← P2 Filtres URL (indépendant)
```

---

## Référence — Fichiers impactés

| Fichier | Action |
|---------|--------|
| `routes/_app/evenements.tsx` | Modifier — ajouter SubNav |
| `pages/evenements/EvenementsListPage.tsx` | Modifier — skeleton, swipe, classes, filtres URL |
| `pages/evenements/EvenementDetailPage.tsx` | Modifier — skeleton, classes |
