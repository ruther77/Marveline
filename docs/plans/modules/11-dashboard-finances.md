# Module 11 — Dashboard & Finances

> Roadmap L1→L5 — Audit réel 2026-02-25 | Source : fichiers lus + grep codebase

---

## État actuel — Synthèse audit

### Ce qui fonctionne bien
- `DashboardPage` (210L) : 11 StatCards organisées en 3 rows (réservations, factures, mouvements/stock), section "Planning du jour" conditionnelle avec TanStack Query (`useDashboardStats` + `usePlanningToday`), `ErrorState` sur erreur ✅
- `FinancesPage` (145L) : 4 KPIs, BarChart recharts (`ResponsiveContainer`), tableau mensuel, filtre `year` en state local, `formatCents`/`formatCurrency` ✅
- `NotificationsPage` (81L) : liste paginée, actions "marquer comme lu" / "tout marquer lu", `useNotifications` + `useMarkNotificationRead` + `useMarkAllNotificationsRead` ✅
- Backend `GET /dashboard/stats` et `GET /dashboard/finances?year=` fonctionnels ✅

### Anti-patterns identifiés

| ID | Fichier | Problème | Priorité |
|----|---------|----------|----------|
| AP-01 | `DashboardPage.tsx:39` | Loading = `<Loader2>` spinner — skeleton obligatoire (règle PDF #3) | P0 |
| AP-02 | `FinancesPage.tsx:57` | Loading = `<Loader2>` spinner — skeleton obligatoire | P0 |
| AP-03 | `DashboardPage.tsx:146,165,184` | `bg-dark-9002` — classe invalide (faute de frappe → `bg-dark-800`) | P1 |
| AP-04 | `DashboardPage.tsx:132,152,171,190` | Classes `text-body` non-standard | P1 |
| AP-05 | `DashboardPage.tsx:133,138,153,172` | Classes `text-accent` non-standard | P1 |
| AP-06 | `DashboardPage.tsx:147,154,158,166,173,177,192,196` | Classes `text-muted` non-standard | P1 |
| AP-07 | `FinancesPage.tsx:90,124` | Classes `text-body` non-standard | P1 |
| AP-08 | `NotificationsPage.tsx:36` | Loading = texte `"Chargement…"` | P1 |
| AP-09 | `NotificationsPage.tsx:47` | `bg-primary-50/40` — couleur light dans thème dark (invisible) | P1 |
| AP-10 | `DashboardPage.tsx:46,100,107` | Accents manquants : "Reservations actives", "Departs programmes", "Retours programmes" | P2 |

**Note** : Dashboard (`/_app/`) et Finances (`/_app/finances`) sont des pages autonomes — pas de layout parent commun avec SubNav (ce sont des entrées bottom nav distinctes). Pas de TASK SubNav pour ce module.

---

## Tâches L1→L5

### TASK-DASH-01 (P0) — Skeleton loading DashboardPage

**Problème** : `DashboardPage.tsx:39` affiche `<Loader2>` spinner pendant le chargement des stats.
Règle PDF #3 : skeleton obligatoire, pas de spinner.

**Fichier à modifier** : `frontend/src/pages/dashboard/DashboardPage.tsx`

```tsx
function StatCardSkeleton() {
  return (
    <div className="card p-5 animate-pulse">
      <div className="flex items-start justify-between mb-3">
        <div className="h-3 bg-dark-700 rounded w-28" />
        <div className="w-8 h-8 bg-dark-700 rounded-lg" />
      </div>
      <div className="h-7 bg-dark-700 rounded w-16" />
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      {/* Row 1 : 4 cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)}
      </div>
      {/* Row 2 : 3 cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => <StatCardSkeleton key={i} />)}
      </div>
      {/* Row 3 : 4 cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)}
      </div>
    </div>
  )
}

// Remplacer :
// isLoading ? <div ...><Loader2 .../></div>
// Par :
if (isLoading) return <DashboardSkeleton />
```

> Supprimer l'import `Loader2` de lucide-react si plus utilisé.

**Critères done** :
- ☐ Skeleton structuré (3 rows reproduisant la grille réelle)
- ☐ Aucun `Loader2` dans `DashboardPage`
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-DASH-02 (P0) — Skeleton loading FinancesPage

**Problème** : `FinancesPage.tsx:57` affiche `<Loader2>` spinner.

**Fichier à modifier** : `frontend/src/pages/dashboard/FinancesPage.tsx`

```tsx
function FinancesSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="card p-5">
            <div className="flex items-start justify-between mb-3">
              <div className="h-3 bg-dark-700 rounded w-28" />
              <div className="w-8 h-8 bg-dark-700 rounded-lg" />
            </div>
            <div className="h-7 bg-dark-700 rounded w-20" />
          </div>
        ))}
      </div>
      {/* BarChart placeholder */}
      <div className="card p-6">
        <div className="h-4 bg-dark-700 rounded w-40 mb-4" />
        <div className="h-[300px] bg-dark-700 rounded-xl" />
      </div>
      {/* Tableau mensuel */}
      <div className="card p-0 overflow-hidden">
        <div className="bg-dark-700 px-4 py-3">
          <div className="h-3 bg-dark-600 rounded w-1/4" />
        </div>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-dark-700">
            <div className="h-3 bg-dark-700 rounded w-12" />
            <div className="flex-1" />
            <div className="h-3 bg-dark-700 rounded w-16" />
            <div className="h-3 bg-dark-700 rounded w-8 ml-4" />
            <div className="h-3 bg-dark-700 rounded w-8 ml-4" />
          </div>
        ))}
      </div>
    </div>
  )
}

// Remplacer :
// isLoading ? <div ...><Loader2 .../></div>
// Par :
if (isLoading) return <FinancesSkeleton />
```

> Supprimer l'import `Loader2` de lucide-react.

**Critères done** :
- ☐ Skeleton structuré (KPIs + BarChart placeholder + tableau 6 lignes)
- ☐ Aucun `Loader2` dans `FinancesPage`

---

### TASK-DASH-03 (P1) — Corriger `bg-dark-9002` → `bg-dark-800`

**Problème** : `DashboardPage.tsx` lignes 146, 165, 184 utilisent `bg-dark-9002` — classe invalide
(faute de frappe, Tailwind génère rien). Visuellement : fond transparent au lieu du fond attendu.

**Fichier à modifier** : `frontend/src/pages/dashboard/DashboardPage.tsx`

```tsx
// AVANT (3 occurrences) :
<div className="bg-dark-9002 rounded-xl p-3">
<div className="bg-dark-9002 rounded-xl p-3">
<div className="bg-dark-9002 rounded-xl p-3 border border-red-500/20">

// APRÈS :
<div className="bg-dark-800 rounded-xl p-3">
<div className="bg-dark-800 rounded-xl p-3">
<div className="bg-dark-800 rounded-xl p-3 border border-red-500/20">
```

**Critères done** :
- ☐ Aucune occurrence de `bg-dark-9002` dans le codebase
- ☐ Section "Planning du jour" affiche le fond correct

---

### TASK-DASH-04 (P1) — Normaliser classes design system DashboardPage

**Problème** : `DashboardPage` utilise `text-body`, `text-accent`, `text-muted` — classes non définies
dans le design system Tailwind CaroCorp.

**Correspondances** :

| Classe actuelle | Remplacement |
|----------------|--------------|
| `text-body` | *(supprimer)* — héritage `text-white` via body |
| `text-accent` | `text-primary-400` |
| `text-muted` | `text-dark-400` |

**Lignes impactées** :

| Ligne | Contexte | Remplacement |
|-------|----------|--------------|
| 132 | `<h2>` "Planning du jour" | supprimer `text-body` |
| 133 | Icône `CalendarCheck` | `text-primary-400` |
| 138 | Lien "Voir tout" | `text-primary-400` |
| 146→184 | Voir TASK-DASH-03 (même edit) | — |
| 147 | `<p>` "Départs (N)" | `text-dark-400` |
| 152 | `<li>` référence | supprimer `text-body` |
| 153 | `<span>` référence | `text-primary-400` |
| 154 | `<span>` client | `text-dark-400` |
| 158 | `<li>` "+N autres" | `text-dark-400` |
| 166 | `<p>` "Retours (N)" | `text-dark-400` |
| 171 | `<li>` référence | supprimer `text-body` |
| 172 | `<span>` référence | `text-primary-400` |
| 173 | `<span>` client | `text-dark-400` |
| 177 | `<li>` "+N autres" | `text-dark-400` |
| 190 | `<li>` référence | supprimer `text-body` |
| 192 | `<span>` client | `text-dark-400` |
| 196 | `<li>` "+N autres" | `text-dark-400` |

**Critères done** :
- ☐ Aucune occurrence de `text-body`, `text-accent`, `text-muted` dans `DashboardPage`
- ☐ Rendu visuel identique

---

### TASK-DASH-05 (P1) — Normaliser classes design system FinancesPage

**Problème** : `FinancesPage` lignes 90 et 124 utilisent `text-body`.

**Fichier à modifier** : `frontend/src/pages/dashboard/FinancesPage.tsx`

```tsx
// Ligne 90 — AVANT :
<h2 className="mb-4 text-base font-semibold text-body">
// APRÈS :
<h2 className="mb-4 text-base font-semibold">

// Ligne 124 — AVANT :
<td className="px-4 py-3 font-medium text-body">{MONTHS[m.month - 1]}</td>
// APRÈS :
<td className="px-4 py-3 font-medium">{MONTHS[m.month - 1]}</td>
```

**Critères done** :
- ☐ Aucune occurrence de `text-body` dans `FinancesPage`

---

### TASK-DASH-06 (P1) — Skeleton loading NotificationsPage

**Problème** : `NotificationsPage.tsx:36` affiche `"Chargement…"` texte.

**Fichier à modifier** : `frontend/src/pages/dashboard/NotificationsPage.tsx`

```tsx
function NotificationItemSkeleton() {
  return (
    <div className="flex items-start gap-4 px-5 py-4 animate-pulse">
      <div className="mt-0.5 w-2 h-2 rounded-full bg-dark-700 shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="flex items-center gap-2">
          <div className="h-3.5 bg-dark-700 rounded w-48" />
          <div className="h-3 bg-dark-700 rounded w-16" />
        </div>
        <div className="h-3 bg-dark-700 rounded w-64" />
      </div>
    </div>
  )
}

// Remplacer :
// isLoading ? <div className="text-sm text-dark-400">Chargement…</div>
// Par :
if (isLoading) return (
  <div className="card p-0 divide-y divide-dark-700">
    {Array.from({ length: 5 }).map((_, i) => <NotificationItemSkeleton key={i} />)}
  </div>
)
```

**Critères done** :
- ☐ Skeleton 5 items reproduisant la structure (dot + titre + horodatage + message)
- ☐ Aucun texte `"Chargement…"` dans `NotificationsPage`

---

### TASK-DASH-07 (P1) — Corriger couleur `bg-primary-50/40` → `bg-primary-500/10`

**Problème** : `NotificationsPage.tsx:47` utilise `bg-primary-50/40` pour indiquer une notification
non lue. `primary-50` est une teinte très claire (quasi-blanc) qui est invisible sur fond sombre.

**Fichier à modifier** : `frontend/src/pages/dashboard/NotificationsPage.tsx`

```tsx
// Ligne 47 — AVANT :
className={`flex items-start gap-4 px-5 py-4 ${!n.is_read ? 'bg-primary-50/40' : ''}`}

// APRÈS :
className={`flex items-start gap-4 px-5 py-4 ${!n.is_read ? 'bg-primary-500/10' : ''}`}
```

**Critères done** :
- ☐ Fond notification non lue visible sur thème dark
- ☐ Cohérent avec autres indicateurs primary (badges, hover states)

---

### TASK-DASH-08 (P2) — Corriger accents StatCard DashboardPage

**Problème** : Plusieurs StatCards ont des titres sans accents français.

**Fichier à modifier** : `frontend/src/pages/dashboard/DashboardPage.tsx`

```tsx
// Ligne 46 — AVANT :
title="Reservations actives"
// APRÈS :
title="Réservations actives"

// Ligne 100 — AVANT :
title="Departs programmes"
// APRÈS :
title="Départs programmés"

// Ligne 107 — AVANT :
title="Retours programmes"
// APRÈS :
title="Retours programmés"
```

**Critères done** :
- ☐ Dashboard affiche les titres avec accents corrects
- ☐ Cohérent avec le reste de l'UI (FinancesPage utilise déjà les accents)

---

## Couverture LAYER.html — Mapping final

| Écran LAYER | Route | Composant | Backend | Statut cible |
|------------|-------|-----------|---------|--------------|
| `s-dashboard` | `/_app/` | `DashboardPage` | `GET /dashboard/stats` + `GET /planning/today` | ✅ → skeleton + design system |
| `s-finances` | `/_app/finances` | `FinancesPage` | `GET /dashboard/finances?year=` | ✅ → skeleton + design system |
| `s-notifications` | `/_app/notifications` | `NotificationsPage` | `GET /notifications` | ✅ → skeleton + couleur dark |
| `s-rapport-mensuel` | — | — | — | ⚠️ P2 futur (hors scope L1→L5) |
| `s-recherche` | `/_app/search` | `SearchPage` + `GlobalSearch` | `GET /search?q=` | ✅ implémenté |

---

## Ordre d'exécution recommandé

```
TASK-DASH-01  ← P0 Skeleton Dashboard
TASK-DASH-02  ← P0 Skeleton Finances
TASK-DASH-03  ← P1 bg-dark-9002 fix (indépendant)
TASK-DASH-04  ← P1 Design system Dashboard (indépendant)
TASK-DASH-05  ← P1 Design system Finances (indépendant)
TASK-DASH-06  ← P1 Skeleton Notifications (indépendant)
TASK-DASH-07  ← P1 Couleur notification non lue (indépendant)
TASK-DASH-08  ← P2 Accents StatCard (indépendant)
```

---

## Référence — Fichiers impactés

| Fichier | Action |
|---------|--------|
| `pages/dashboard/DashboardPage.tsx` | Modifier — skeleton, bg-dark-9002, design system, accents |
| `pages/dashboard/FinancesPage.tsx` | Modifier — skeleton, design system |
| `pages/dashboard/NotificationsPage.tsx` | Modifier — skeleton, couleur bg notification |
