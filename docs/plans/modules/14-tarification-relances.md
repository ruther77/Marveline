# Module 14 — Tarification & Relances

> Roadmap L1→L5 — Audit réel 2026-02-25 | Source : fichiers lus + grep codebase

---

## État actuel — Synthèse audit

### Ce qui fonctionne bien
- `TarificationPage` (322L) : liste des règles de tarification, CRUD complet, `RuleFormModal` + `PricingRuleBuilder`, `SimulatorPanel` avec `ComboboxAsync` + `usePricingSimulate` ✅
- `RelancesPlanifieesPage` (291L) : liste relances, filtres statut (all/scheduled/sent/cancelled), `ScheduleModal` avec sélection facture + canal + date, actions "Marquer envoyée" / "Annuler" ✅
- Pattern erreur `ScheduleModal:67` correct : `(err as {...})?.response?.data?.detail` ✅
- `formatCents()` utilisé dans le simulateur ✅

### Anti-patterns identifiés

| ID | Fichier | Problème | Priorité |
|----|---------|----------|----------|
| AP-01 | `routes/_app/tarification.tsx` | Route directe sans layout parent — pas de SubNav Tarification | P1 |
| AP-02 | `routes/_app/relances.tsx` | Route directe sans layout parent — pas de SubNav Relances | P1 |
| AP-03 | `TarificationPage.tsx:221-224` | `isLoading` → texte `"Chargement…"` dans `<td colSpan={6}>` | P1 |
| AP-04 | `RelancesPlanifieesPage.tsx:218-219` | `isLoading` → texte `"Chargement…"` | P1 |
| AP-05 | `RuleFormModal.tsx:58,60` | `onError: () => setError('...')` — erreur backend ignorée, pattern interdit | P1 |
| AP-06 | `TarificationPage.tsx:122,165,166,194,237` | Classe `text-body` non-standard (×5) | P2 |
| AP-07 | `RelancesPlanifieesPage.tsx:184,223,236` | Classe `text-body` non-standard (×3) | P2 |
| AP-08 | `RelancesPlanifieesPage.tsx` | Pas de `SwipeActions` mobile — actions "Marquer / Annuler" non accessibles en swipe | P2 |

**Note sur P1 vs P0 SubNav** : Tarification et Relances n'ont chacun qu'une seule page (pas de sous-navigation réelle). Le layout parent est noté P1 (cohérence visuelle) et non P0 comme pour Admin/Profil qui ont plusieurs sous-pages distinctes.

---

## Tâches L1→L5

### TASK-TAR-01 (P1) — Layout parent Tarification avec SubNav

**Problème** : `routes/_app/tarification.tsx` est une route directe vers `TarificationPage`. Pas de layout parent → pas de SubNav module.

**Fichier à modifier** : `frontend/src/routes/_app/tarification.tsx`

```tsx
// routes/_app/tarification.tsx
import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

const TARIFICATION_NAV = [
  { label: 'Règles de prix', href: '/tarification' },
]

export const Route = createFileRoute('/_app/tarification')({
  component: () => (
    <div className="space-y-0">
      <SubNav items={TARIFICATION_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  ),
})
```

> Après modification, créer `routes/_app/tarification/index.tsx` pointant vers `TarificationPage`
> (ou déplacer le `component: TarificationPage` dans la route index).
> Retirer le `p-4 md:p-6` redondant dans `TarificationPage` (ligne 191).

**Critères done** :
- ☐ `routes/_app/tarification.tsx` contient SubNav + Outlet
- ☐ `routes/_app/tarification/index.tsx` créé (ou route index configurée)
- ☐ Padding `p-4 md:p-6` retiré de `TarificationPage`
- ☐ `routeTree.gen.ts` regénéré sans erreur
- ☐ `tsc --noEmit` 0 erreur
- ☐ 1582 Vitest pass

---

### TASK-TAR-02 (P1) — Layout parent Relances avec SubNav

**Problème** : `routes/_app/relances.tsx` est une route directe vers `RelancesPlanifieesPage`. Pas de layout parent.

**Fichier à modifier** : `frontend/src/routes/_app/relances.tsx`

```tsx
// routes/_app/relances.tsx
import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

const RELANCES_NAV = [
  { label: 'Relances planifiées', href: '/relances' },
]

export const Route = createFileRoute('/_app/relances')({
  component: () => (
    <div className="space-y-0">
      <SubNav items={RELANCES_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  ),
})
```

> Même pattern que TASK-TAR-01 : créer route index + retirer padding `p-4 md:p-6`
> de `RelancesPlanifieesPage` (ligne 179).

**Critères done** :
- ☐ `routes/_app/relances.tsx` contient SubNav + Outlet
- ☐ Route index créée pour `RelancesPlanifieesPage`
- ☐ Padding retiré de la page
- ☐ `tsc --noEmit` 0 erreur
- ☐ 1582 Vitest pass

---

### TASK-TAR-03 (P1) — Skeleton liste règles de tarification

**Problème** : `TarificationPage.tsx:221-224` affiche `"Chargement…"` dans un `<td>` pendant le chargement initial.

**Fichier à modifier** : `frontend/src/pages/tarification/TarificationPage.tsx`

```tsx
function PricingRuleRowSkeleton() {
  return (
    <tr className="animate-pulse border-b border-dark-700/50">
      {/* Nom */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="w-3.5 h-3.5 bg-dark-700 rounded" />
          <div className="h-4 bg-dark-700 rounded w-36" />
        </div>
      </td>
      {/* Type — hidden sm */}
      <td className="px-4 py-3 hidden sm:table-cell">
        <div className="h-3 bg-dark-700 rounded w-20" />
      </td>
      {/* Périmètre — hidden md */}
      <td className="px-4 py-3 hidden md:table-cell">
        <div className="h-3 bg-dark-700 rounded w-16" />
      </td>
      {/* Validité — hidden lg */}
      <td className="px-4 py-3 hidden lg:table-cell">
        <div className="h-3 bg-dark-700 rounded w-28" />
      </td>
      {/* Statut */}
      <td className="px-4 py-3">
        <div className="h-5 bg-dark-700 rounded-full w-14" />
      </td>
      {/* Actions */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-2 justify-end">
          <div className="w-4 h-4 bg-dark-700 rounded" />
          <div className="w-4 h-4 bg-dark-700 rounded" />
        </div>
      </td>
    </tr>
  )
}

// Remplacer dans le tbody :
// {isLoading ? (
//   <tr><td colSpan={6} className="px-4 py-8 text-center text-dark-400">Chargement…</td></tr>
{isLoading ? (
  Array.from({ length: 5 }).map((_, i) => <PricingRuleRowSkeleton key={i} />)
) : rules.length === 0 ? (
  <tr>
    <td colSpan={6} className="px-4 py-8 text-center text-dark-400">
      Aucune règle de tarification
    </td>
  </tr>
) : (
  rules.map((rule) => /* ... */)
)}
```

**Critères done** :
- ☐ Skeleton 5 lignes tableau avec colonnes responsive (hidden sm/md/lg respectées)
- ☐ Aucun texte `"Chargement…"` dans `TarificationPage`

---

### TASK-TAR-04 (P1) — Corriger pattern erreur onError RuleFormModal

**Problème** : `TarificationPage.tsx:58,60` — le callback `onError` de `update.mutate` et `create.mutate` ignore l'erreur backend et affiche un message hardcodé. Pattern interdit (`GOTCHA:FRONTEND:ERROR-PATTERN`).

```tsx
// AVANT (lignes 58, 60) :
update.mutate({ id: rule.id, data: payload }, {
  onSuccess: onClose,
  onError: () => setError('Erreur lors de la mise à jour'),
})
// ...
create.mutate(payload, {
  onSuccess: onClose,
  onError: () => setError('Erreur lors de la création'),
})
```

```tsx
// APRÈS :
update.mutate({ id: rule.id, data: payload }, {
  onSuccess: onClose,
  onError: (err) =>
    setError(
      (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Erreur lors de la mise à jour'
    ),
})
// ...
create.mutate(payload, {
  onSuccess: onClose,
  onError: (err) =>
    setError(
      (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Erreur lors de la création'
    ),
})
```

> `ScheduleModal` dans `RelancesPlanifieesPage` utilise déjà le bon pattern (`mutateAsync` +
> `catch` avec `.response?.data?.detail`) — ne pas modifier.

**Critères done** :
- ☐ `onError` dans `RuleFormModal` utilise `.response?.data?.detail || fallback`
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-TAR-05 (P1) — Skeleton liste relances

**Problème** : `RelancesPlanifieesPage.tsx:218-219` affiche `"Chargement…"` texte centré pendant le chargement.

**Fichier à modifier** : `frontend/src/pages/relances/RelancesPlanifieesPage.tsx`

```tsx
function RelanceItemSkeleton() {
  return (
    <div className="flex items-start justify-between px-4 py-3 gap-4 animate-pulse">
      <div className="flex-1 space-y-2">
        <div className="flex items-center gap-2">
          <div className="h-4 bg-dark-700 rounded w-28" />
          <div className="h-5 bg-dark-700 rounded-full w-16" />
          <div className="h-3 bg-dark-700 rounded w-10" />
        </div>
        <div className="h-3 bg-dark-700 rounded w-40" />
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <div className="h-4 bg-dark-700 rounded w-24" />
        <div className="w-4 h-4 bg-dark-700 rounded" />
      </div>
    </div>
  )
}

function RelancesSkeleton() {
  return (
    <div className="card divide-y divide-dark-700">
      {Array.from({ length: 5 }).map((_, i) => (
        <RelanceItemSkeleton key={i} />
      ))}
    </div>
  )
}

// Remplacer :
// {isLoading ? (
//   <div className="p-8 text-center text-dark-400">Chargement…</div>
{isLoading ? (
  <RelancesSkeleton />
) : filtered.length === 0 ? (
  /* ... empty state inchangé */
) : (
  /* ... liste inchangée */
)}
```

**Critères done** :
- ☐ Skeleton 5 items (texte facture + badge statut + canal + date + boutons fantômes)
- ☐ Aucun texte `"Chargement…"` dans `RelancesPlanifieesPage`

---

### TASK-TAR-06 (P2) — Normaliser classes design system TarificationPage

**Problème** : `text-body` utilisé 5 fois dans `TarificationPage` — classe non définie dans le DS.

**Occurrences** :
- L122 — `SimulatorPanel` titre h2
- L165, L166 — résultat simulateur (prix unitaire + total)
- L194 — header `<h1>Tarification</h1>`
- L237 — nom règle dans le tableau

**Action** : Supprimer `text-body` (le blanc par défaut est hérité).

| Classe actuelle | Remplacement |
|----------------|--------------|
| `text-body` | *(supprimer)* — hérite `text-white` du body |

**Critères done** :
- ☐ 0 occurrence de `text-body` dans `TarificationPage.tsx`
- ☐ Rendu visuel identique (blanc par défaut)

---

### TASK-TAR-07 (P2) — Normaliser classes design system RelancesPlanifieesPage

**Problème** : `text-body` utilisé 3 fois dans `RelancesPlanifieesPage`.

**Occurrences** :
- L184 — `<h1>Relances</h1>` dans le header
- L223 — empty state `"Aucune relance"` (dans `.card`)
- L236 — `"Facture #{r.invoice_id}"` dans les items liste

**Action** : Supprimer `text-body`.

**Critères done** :
- ☐ 0 occurrence de `text-body` dans `RelancesPlanifieesPage.tsx`

---

### TASK-TAR-08 (P2) — SwipeActions mobile sur items relances

**Problème** : Les relances "Planifiées" ont deux actions (Marquer envoyée / Annuler) affichées
en boutons texte inline. Sur mobile, la zone de touch est petite et les actions peu visibles.
PDF règle #5 : swipe-right = action principale, swipe-left = secondaire.

**Fichier à modifier** : `frontend/src/pages/relances/RelancesPlanifieesPage.tsx`

```tsx
import { SwipeActions } from '@/components/ui/SwipeActions'
import { Send, XCircle } from 'lucide-react'

// Dans la liste filtrée :
{filtered.map((r) => (
  <SwipeActions
    key={r.id}
    leftActions={
      r.status === 'scheduled'
        ? [
            {
              label: 'Envoyée',
              icon: <Send className="w-4 h-4" />,
              color: 'bg-green-600',
              onAction: () => handleMarkSent(r.id),
            },
          ]
        : []
    }
    rightActions={
      r.status === 'scheduled'
        ? [
            {
              label: 'Annuler',
              icon: <XCircle className="w-4 h-4" />,
              color: 'bg-red-500',
              onAction: () => handleCancel(r.id),
            },
          ]
        : []
    }
  >
    <div className="flex items-start justify-between px-4 py-3 gap-4">
      {/* ... contenu item inchangé */}
    </div>
  </SwipeActions>
))}
```

> Les boutons actions inline restent visibles sur desktop.
> Sur mobile les SwipeActions sont la voie principale.

**Critères done** :
- ☐ Swipe-left → "Marquer envoyée" (vert) — statut `scheduled` uniquement
- ☐ Swipe-right → "Annuler" (rouge) — statut `scheduled` uniquement
- ☐ Touch target ≥ 44px (hauteur item liste)
- ☐ Items `sent`/`cancelled` sans actions swipe

---

## Couverture LAYER.html — Mapping final

| Écran LAYER | Route | Composant | Backend | Statut cible |
|------------|-------|-----------|---------|--------------|
| `s-tarification` | `/tarification` | `TarificationPage` | `GET /pricing/rules` | ✅ → SubNav + skeleton |
| `s-tarification-simulateur` | `/tarification` | `SimulatorPanel` | `GET /pricing/simulate` | ✅ → design system |
| `s-relances` | `/relances` | `RelancesPlanifieesPage` | `GET /relances` | ✅ → SubNav + skeleton + swipe |
| `s-relance-new` | `/relances` modal | `ScheduleModal` | `POST /relances` | ✅ |
| `s-relance-mark-sent` | `/relances` action | bouton Marquer envoyée | `POST /relances/{id}/send` | ✅ |
| `s-relance-cancel` | `/relances` action | bouton Annuler | `DELETE /relances/{id}` | ✅ |

---

## Ordre d'exécution recommandé

```
TASK-TAR-01  ← P1 Layout Tarification + SubNav
TASK-TAR-02  ← P1 Layout Relances + SubNav (indépendant)
TASK-TAR-03  ← P1 Skeleton tableau règles (indépendant)
TASK-TAR-04  ← P1 onError pattern RuleFormModal (indépendant)
TASK-TAR-05  ← P1 Skeleton liste relances (indépendant)
TASK-TAR-06  ← P2 Design system Tarification (indépendant)
TASK-TAR-07  ← P2 Design system Relances (indépendant)
TASK-TAR-08  ← P2 SwipeActions mobile relances (indépendant)
```

---

## Référence — Fichiers impactés

| Fichier | Action |
|---------|--------|
| `routes/_app/tarification.tsx` | Modifier — layout parent + SubNav + Outlet |
| `routes/_app/relances.tsx` | Modifier — layout parent + SubNav + Outlet |
| `routes/_app/tarification/index.tsx` | **Créer** — route index → `TarificationPage` |
| `routes/_app/relances/index.tsx` | **Créer** — route index → `RelancesPlanifieesPage` |
| `pages/tarification/TarificationPage.tsx` | Modifier — skeleton, onError, text-body, padding |
| `pages/relances/RelancesPlanifieesPage.tsx` | Modifier — skeleton, swipe, text-body, padding |
