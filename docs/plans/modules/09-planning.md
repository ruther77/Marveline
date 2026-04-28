# Module 09 — Agenda / Planning

> Roadmap L1→L5 — Audit réel 2026-02-25 | Source : fichiers lus + grep codebase

---

## État actuel — Synthèse audit

### Architecture réelle (différente de l'ancien audit)

| Composant | Route | Statut |
|-----------|-------|--------|
| `AgendaPage` (614L) | `/_app/agenda` | ✅ Vue principale — 3 modes internes mois/semaine/jour |
| `PlanningResourcesPage` (99L) | *(non routée)* | ⚠️ Page orpheline — complémentaire, à brancher |
| `PlanningAffectationPage` (177L) | *(non routée)* | ⚠️ Page orpheline — complémentaire, à brancher |
| `PlanningDayPage` (169L) | *(non routée)* | ⚠️ Doublon AgendaPage day view — à consolider |
| `PlanningWeekPage` (143L) | *(non routée)* | ⚠️ Doublon AgendaPage week view — à consolider |
| `PlanningMonthPage` (154L) | *(non routée)* | ⚠️ Doublon AgendaPage month view — à consolider |

### Ce qui fonctionne bien

- `AgendaPage` : calendrier 3 vues (mois/semaine/jour) dans un composant unique, `Loader2` spinner
  correct pour un calendrier (non une liste L1), navigation date fluide, légende événements
- `PlanningResourcesPage` : liste ressources actives du jour, navigation j±1, `DomainStatusBadge`-like
- `PlanningAffectationPage` : checklist hebdo des réservations (prêtes / à préparer), KPIs 3 compteurs

### Anti-patterns identifiés

| ID | Fichier | Problème | Priorité |
|----|---------|----------|----------|
| AP-01 | `routes/_app/agenda.tsx` | Layout route simple — pas de SubNav, pas d'`<Outlet />` | P0 |
| AP-02 | `AgendaPage.tsx:601` | `ReservationDetailsModal` sans URL (modale sans navigation) | P1 |
| AP-03 | `AgendaPage.tsx:607` | `MovementDetailModal` sans URL | P1 |
| AP-04 | `AgendaPage.tsx` | Accents français manquants : « Departs », « Reservations », « Selectionnez » | P2 |
| AP-05 | `PlanningResourcesPage.tsx:40,48,74,79` | Classes `text-body` non-standard | P2 |
| AP-06 | `PlanningAffectationPage.tsx:75,91,110,130` | Classes `text-body` non-standard | P2 |
| AP-07 | `PlanningDayPage.tsx:54,82,85,95,120,153` | Classes `text-body` non-standard | P2 |
| AP-08 | `PlanningMonthPage.tsx:69,77,90,93` | Classes `text-body` non-standard | P2 |
| AP-09 | `PlanningResourcesPage.tsx:63` | Loading = texte `"Chargement…"` | P1 |
| AP-10 | `PlanningAffectationPage.tsx:106` | Loading = texte `"Chargement…"` | P1 |
| AP-11 | `PlanningDayPage.tsx:91` | Loading = texte `"Chargement…"` | P1 |
| AP-12 | `PlanningMonthPage.tsx:98` | Loading = texte `"Chargement…"` | P1 |
| AP-13 | `PlanningAffectationPage.tsx:163` | Lien `/events` au lieu de `/events/$id` (navigation incomplète) | P1 |
| AP-14 | `PlanningTodayPage.tsx` | Design system `bg-neutral-*` / `text-neutral-*` — classes inexistantes dans le DS CaroCorp | P1 |
| AP-15 | `PlanningDayPage`, `PlanningWeekPage`, `PlanningMonthPage` | Pages orphelines doublonnant les vues d'AgendaPage | P2 |
| AP-16 | `AgendaMobilePage.tsx:201-204` | Loader2 spinner sur liste d'événements du jour → skeleton requis | P1 |
| AP-17 | `AgendaMobilePage.tsx:208` | Accent manquant : `"Aucun evenement ce jour"` | P2 |

**Note** : `AgendaPage` utilise `Loader2` (spinner) pour le calendrier — acceptable pour cette vue
complexe qui n'est pas une "liste L1". Le spinner est correct ici, pas besoin de skeleton.

---

## Tâches L1→L5

### TASK-PLN-01 (P0) — SubNav layout module Agenda

**Problème** : `routes/_app/agenda.tsx` est une route directe (pas de layout Outlet).
Les pages complémentaires `PlanningResourcesPage` et `PlanningAffectationPage` ne sont pas
branchées — elles sont orphelines malgré leur implémentation complète.

**Fichier à modifier** : `frontend/src/routes/_app/agenda.tsx`

```tsx
// routes/_app/agenda.tsx — AVANT
import { createFileRoute } from '@tanstack/react-router'
import AgendaPage from '@/pages/agenda/AgendaPage'
export const Route = createFileRoute('/_app/agenda')({ component: AgendaPage })
```

```tsx
// routes/_app/agenda.tsx — APRÈS
import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

const AGENDA_NAV = [
  { label: 'Calendrier', href: '/agenda' },
  { label: 'Ressources', href: '/agenda/resources' },
  { label: 'Affectation', href: '/agenda/affectation' },
]

export const Route = createFileRoute('/_app/agenda')({
  component: () => (
    <div className="space-y-0">
      <SubNav items={AGENDA_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  ),
})
```

> Note : AgendaPage ajoute son propre `space-y-6` interne — le padding `p-4 md:p-6` du
> layout est suffisant. Supprimer tout padding redondant dans les sous-pages après ajout du wrapper.

**Critères done** :
- ☐ `routes/_app/agenda.tsx` contient SubNav avec 3 onglets
- ☐ Padding `p-4 md:p-6` retiré des pages individuelles (sinon double padding)
- ☐ `tsc --noEmit` 0 erreur
- ☐ 1582 Vitest pass

---

### TASK-PLN-02 (P1) — Brancher les pages complémentaires Planning

**Problème** : `PlanningResourcesPage` et `PlanningAffectationPage` existent et sont
fonctionnelles mais ne sont pas dans les routes TanStack Router.

**Fichiers à créer** :

```
frontend/src/routes/_app/agenda/
  index.tsx       ← AgendaPage (déjà OK — renommer ou déplacer)
  resources.tsx   ← PlanningResourcesPage
  affectation.tsx ← PlanningAffectationPage
```

```tsx
// routes/_app/agenda/index.tsx
import { createFileRoute } from '@tanstack/react-router'
import AgendaPage from '@/pages/agenda/AgendaPage'
export const Route = createFileRoute('/_app/agenda/')({ component: AgendaPage })
```

```tsx
// routes/_app/agenda/resources.tsx
import { createFileRoute } from '@tanstack/react-router'
import PlanningResourcesPage from '@/pages/planning/PlanningResourcesPage'
export const Route = createFileRoute('/_app/agenda/resources')({ component: PlanningResourcesPage })
```

```tsx
// routes/_app/agenda/affectation.tsx
import { createFileRoute } from '@tanstack/react-router'
import PlanningAffectationPage from '@/pages/planning/PlanningAffectationPage'
export const Route = createFileRoute('/_app/agenda/affectation')({ component: PlanningAffectationPage })
```

> Note GOTCHA:ROUTER:INDEX-TRAILING-SLASH : la route index doit être `'/_app/agenda/'`
> (avec trailing slash) pour que SubNav détecte correctement l'onglet actif.

**Critères done** :
- ☐ `/agenda` → AgendaPage ✅
- ☐ `/agenda/resources` → PlanningResourcesPage ✅
- ☐ `/agenda/affectation` → PlanningAffectationPage ✅
- ☐ SubNav onglet actif cohérent sur chaque route
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-PLN-03 (P1) — Corriger skeletons loading pages Planning

**Problème** : `PlanningResourcesPage`, `PlanningAffectationPage`, `PlanningDayPage`,
`PlanningMonthPage` affichent du texte `"Chargement…"`. Règle UI/UX PDF #3 : skeleton obligatoire.

**Skeleton PlanningResourcesPage** :

```tsx
function ResourcesSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="card flex items-start justify-between gap-3">
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-dark-700 rounded w-48" />
            <div className="h-3 bg-dark-700 rounded w-64" />
          </div>
          <div className="h-5 bg-dark-700 rounded-full w-16 shrink-0" />
        </div>
      ))}
    </div>
  )
}

// Remplacer :
// <p className="text-center text-dark-400 py-10">Chargement…</p>
if (isLoading) return <ResourcesSkeleton />
```

**Skeleton PlanningAffectationPage** :

```tsx
function AffectationSkeleton() {
  return (
    <div className="animate-pulse space-y-5">
      {/* KPIs */}
      <div className="grid grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="card p-4 text-center">
            <div className="h-8 bg-dark-700 rounded w-12 mx-auto mb-1" />
            <div className="h-3 bg-dark-700 rounded w-20 mx-auto" />
          </div>
        ))}
      </div>
      {/* Liste */}
      <div className="card divide-y divide-dark-700">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="px-4 py-3 flex items-center gap-4">
            <div className="w-5 h-5 bg-dark-700 rounded-full shrink-0" />
            <div className="flex-1 space-y-1.5">
              <div className="h-4 bg-dark-700 rounded w-32" />
              <div className="h-3 bg-dark-700 rounded w-24" />
            </div>
            <div className="h-5 bg-dark-700 rounded-full w-16 shrink-0" />
          </div>
        ))}
      </div>
    </div>
  )
}

// Remplacer :
// <div className="p-10 text-center text-dark-400">Chargement…</div>
if (isLoading) return <AffectationSkeleton />
```

**Critères done** :
- ☐ `PlanningResourcesPage` : skeleton 4 cards avec animate-pulse
- ☐ `PlanningAffectationPage` : skeleton KPIs + liste 5 lignes
- ☐ Aucun texte `"Chargement…"` dans ces fichiers

---

### TASK-PLN-04 (P1) — Migrer design system PlanningTodayPage

**Problème** : `PlanningTodayPage.tsx` utilise des classes `bg-neutral-900`, `bg-neutral-800`,
`text-neutral-*`, `divide-neutral-*` — le design system CaroCorp n'utilise **pas** `neutral-*`,
il utilise `dark-*`. Ces classes sont des no-ops en production (Tailwind purge).

**Correspondances** :

| Classe actuelle | Remplacement |
|----------------|--------------|
| `bg-neutral-900` | `bg-dark-900` |
| `bg-neutral-800` | `bg-dark-800` |
| `bg-neutral-700` | `bg-dark-700` |
| `text-neutral-400` | `text-dark-400` |
| `text-neutral-300` | `text-dark-300` |
| `divide-neutral-700` | `divide-dark-700` |
| `border-neutral-700` | `border-dark-700` |

**Méthode** :

```bash
# Vérifier toutes les occurrences
grep -n "neutral-" frontend/src/pages/planning/PlanningTodayPage.tsx
```

Remplacer `neutral-` → `dark-` (remplaçage global dans le fichier).

> Note : vérifier rendu visuel dans le navigateur après remplacement — les couleurs `dark-*`
> sont légèrement différentes des couleurs `neutral-*` de Tailwind standard.

**Critères done** :
- ☐ Aucune occurrence de `neutral-` dans `PlanningTodayPage.tsx`
- ☐ Rendu visuel cohérent avec le reste de l'application
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-PLN-05 (P1) — Corriger lien navigation PlanningAffectationPage

**Problème** : `PlanningAffectationPage.tsx:163` — le bouton "Détail →" navigue vers `/events`
(liste) au lieu de `/events/$id` (fiche réservation). L'utilisateur clique sur "Détail" et se
retrouve sur la liste des réservations au lieu de la fiche.

```tsx
// AVANT (ligne 163) :
<Link to="/events" className="text-xs text-primary-400 hover:underline">
  Détail →
</Link>
```

```tsx
// APRÈS :
<Link
  to="/events/$id"
  params={{ id: String(r.id) }}
  className="text-xs text-primary-400 hover:underline"
>
  Détail →
</Link>
```

**Critères done** :
- ☐ Clic "Détail →" navigue vers la fiche réservation `/events/$id`
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-PLN-06 (P2) — Normaliser classes `text-body` module Planning

**Problème** : `text-body` utilisé dans toutes les pages planning — classe non définie dans
le design system Tailwind CaroCorp.

**Fichiers et occurrences** :
- `PlanningResourcesPage.tsx` : lignes 40, 48, 74, 79
- `PlanningAffectationPage.tsx` : lignes 75, 91, 110, 130
- `PlanningDayPage.tsx` : lignes 54, 82, 85, 95, 120, 153
- `PlanningMonthPage.tsx` : lignes 69, 77, 90, 93

**Action** : Supprimer `text-body` (le texte hérite du blanc par défaut via `text-white`
défini sur `body` dans `index.css`).

**Critères done** :
- ☐ Aucune occurrence de `text-body` dans le module planning
- ☐ Rendu visuel identique

---

### TASK-PLN-07 (P2) — Corriger accents français AgendaPage

**Problème** : `AgendaPage.tsx` contient des strings sans accents (probablement copiés depuis
un contexte ASCII) : « Departs », « Reservations », « Selectionnez un jour », « Aucun evenement »,
« Depart ».

**Corrections** :

| Ligne | Actuel | Correct |
|-------|--------|---------|
| 343 | `"Departs"` | `"Départs"` |
| 348 | `"Retours"` | `"Retours"` ✅ |
| 353 | `"Reservations"` | `"Réservations"` |
| 429 | `"Selectionnez un jour"` | `"Sélectionnez un jour"` |
| 431 | `"Aucun evenement ce jour"` | `"Aucun événement ce jour"` |
| 558 | `"Aucun evenement ce jour"` | `"Aucun événement ce jour"` |
| 592 | `"Depart"` | `"Départ"` |
| 309 | `"Reservations et mouvements"` | `"Réservations et mouvements"` |

**Critères done** :
- ☐ Tous les labels en français correct avec accents
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-PLN-09 (P1) — Skeleton loading + accents AgendaMobilePage

**Problème** : `AgendaMobilePage.tsx` (vue agenda optimisée mobile) n'est pas couverte par les
tâches planning existantes. Elle présente deux anti-patterns :

1. **Loader2 spinner** L201-204 : affiche un spinner centré pour la liste d'événements du jour
   sélectionné → doit être remplacé par un skeleton (règle UI/UX PDF #3)
2. **Accent manquant** L208 : `"Aucun evenement ce jour"` → `"Aucun événement ce jour"`

**Correction skeleton** :

```tsx
// AgendaMobilePage.tsx — remplacer L201-204 :
// AVANT :
{isLoading ? (
  <div className="flex items-center justify-center py-12">
    <Loader2 className="w-6 h-6 animate-spin text-primary-500" />
  </div>
) : ...}

// APRÈS :
function DayEventsSkeleton() {
  return (
    <div className="space-y-2 animate-pulse">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="card flex items-center gap-3 p-3 border border-dark-700/50">
          <div className="w-8 h-8 bg-dark-700 rounded-lg shrink-0" />
          <div className="flex-1 space-y-1.5">
            <div className="h-4 bg-dark-700 rounded w-32" />
            <div className="h-3 bg-dark-700 rounded w-20" />
          </div>
        </div>
      ))}
    </div>
  )
}

{isLoading ? <DayEventsSkeleton /> : ...}
```

**Correction accent** :

```tsx
// L208 — AVANT :
<p className="text-dark-500 text-sm">Aucun evenement ce jour</p>

// APRÈS :
<p className="text-dark-500 text-sm">Aucun événement ce jour</p>
```

**Critères done** :
- ☐ `AgendaMobilePage` : skeleton 3 cards avec animate-pulse
- ☐ `Loader2` import supprimé si non utilisé ailleurs
- ☐ Accent corrigé L208 : `"événement"` avec è
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-PLN-08 (P2) — Consolider pages Planning orphelines doublons

**Problème** : `PlanningDayPage`, `PlanningWeekPage`, `PlanningMonthPage` sont des pages
orphelines qui **doublonnent** les 3 vues internes d'`AgendaPage`. Deux implémentations
parallèles pour le même périmètre fonctionnel = dette de maintenance.

**Analyse** :

| Page orpheline | Vue AgendaPage | Endpoint utilisé | Verdict |
|----------------|----------------|-----------------|---------|
| `PlanningDayPage` | `viewMode === 'day'` | `/planning/day` vs `/agenda` | Doublon — supprimer |
| `PlanningWeekPage` | `viewMode === 'week'` | `/planning/week` vs `/agenda` | Doublon — supprimer |
| `PlanningMonthPage` | `viewMode === 'month'` | `/planning/month` vs `/agenda` | Doublon — supprimer |

> Note : les endpoints `/planning/*` et `/agenda` retournent des données légèrement différentes
> (planning enrichit avec `movement_type`, agenda agrège départs/retours/réservations).
> Avant suppression, vérifier que AgendaPage couvre bien les besoins fonctionnels de ces pages.

**Action recommandée** : Supprimer les 3 fichiers orphelins après validation que AgendaPage
couvre le périmètre fonctionnel.

**Critères done** :
- ☐ `PlanningDayPage.tsx`, `PlanningWeekPage.tsx`, `PlanningMonthPage.tsx` supprimés
- ☐ Aucune import orpheline vers ces fichiers
- ☐ `tsc --noEmit` 0 erreur

---

## Couverture LAYER.html — Mapping final

| Écran LAYER | Route | Composant | Backend | Statut cible |
|------------|-------|-----------|---------|--------------|
| `s-agenda-mois` | `/agenda` (mode mois) | `AgendaPage` | `GET /agenda` | ✅ → accents |
| `s-agenda-semaine` | `/agenda` (mode semaine) | `AgendaPage` | `GET /agenda` | ✅ |
| `s-agenda-jour` | `/agenda` (mode jour) | `AgendaPage` | `GET /agenda` | ✅ |
| `s-planning-ressources` | `/agenda/resources` | `PlanningResourcesPage` | `GET /planning/resources` | ⚠️ → à router |
| `s-planning-affectation` | `/agenda/affectation` | `PlanningAffectationPage` | `GET /planning/week` | ⚠️ → à router |

---

## Ordre d'exécution recommandé

```
TASK-PLN-01  ← P0 SubNav layout agenda.tsx
TASK-PLN-02  ← P1 Brancher routes Resources + Affectation (dépend de PLN-01)
TASK-PLN-03  ← P1 Skeletons loading (indépendant)
TASK-PLN-04  ← P1 Design system neutral→dark PlanningTodayPage (indépendant)
TASK-PLN-05  ← P1 Corriger lien navigation PlanningAffectationPage (indépendant)
TASK-PLN-09  ← P1 Skeleton + accent AgendaMobilePage (indépendant)
TASK-PLN-06  ← P2 Normaliser text-body (indépendant)
TASK-PLN-07  ← P2 Accents français AgendaPage (indépendant)
TASK-PLN-08  ← P2 Consolider pages doublons (après PLN-02 validé)
```

---

## Référence — Fichiers impactés

| Fichier | Action |
|---------|--------|
| `routes/_app/agenda.tsx` | Modifier — ajouter SubNav + Outlet |
| `routes/_app/agenda/index.tsx` | Créer — route AgendaPage |
| `routes/_app/agenda/resources.tsx` | Créer — route PlanningResourcesPage |
| `routes/_app/agenda/affectation.tsx` | Créer — route PlanningAffectationPage |
| `pages/planning/PlanningResourcesPage.tsx` | Modifier — skeleton, text-body |
| `pages/planning/PlanningAffectationPage.tsx` | Modifier — skeleton, text-body, lien détail |
| `pages/planning/PlanningTodayPage.tsx` | Modifier — neutral→dark design system |
| `pages/planning/PlanningDayPage.tsx` | Modifier (text-body) puis supprimer si doublon |
| `pages/planning/PlanningWeekPage.tsx` | Modifier (text-body) puis supprimer si doublon |
| `pages/planning/PlanningMonthPage.tsx` | Modifier (text-body) puis supprimer si doublon |
| `pages/agenda/AgendaPage.tsx` | Modifier — accents français |
| `pages/agenda/AgendaMobilePage.tsx` | Modifier — skeleton loading + accent |
