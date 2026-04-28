# Module 08 — Opérations Terrain (Départ / Retour / QR)

> Roadmap L1→L5 — Audit réel 2026-02-25 | Source : fichiers lus + grep codebase

---

## État actuel — Synthèse audit

### Ce qui fonctionne bien
- `DepartureInventoryPage` (266L) : checklist items, QRScanner inline, SignaturePad, blocage départ avec raison, TanStack Query via `useOperations`
- `ReturnInventoryPage` (246L) : checklist retour, dommages déclarés, coût total, SignaturePad, `DamageDeclarationModal`, `formatCents()` ✅
- `ScanPage` (133L) : QRScanner, parsing format `reservation:id` et `product:id`, navigation contextuelle

### Anti-patterns identifiés

| ID | Fichier | Problème | Priorité |
|----|---------|----------|----------|
| AP-01 | `routes/_app/operations.tsx` | Layout `<Outlet />` nu — pas de SubNav module | P0 |
| AP-02 | `DepartureInventoryPage.tsx:95` | Loading = texte `"Chargement de l'inventaire…"` | P1 |
| AP-03 | `ReturnInventoryPage.tsx:109` | Loading = texte `"Chargement de l'inventaire…"` | P1 |
| AP-04 | `DepartureInventoryPage.tsx:117,130` | Classes `text-body` non-standard | P2 |
| AP-05 | `ReturnInventoryPage.tsx:127,153` | Classes `text-body` non-standard | P2 |
| AP-06 | `ScanPage.tsx:68` | Classe `text-body` non-standard | P2 |
| AP-07 | `ScanPage.tsx:42` | `err.message` — pattern interdit (`GOTCHA:FRONTEND:ERROR-PATTERN`) | P1 |
| AP-08 | `DepartureInventoryPage.tsx` | Pas d'indicateur de progression global (N/M items chargés) | P2 |

**Note** : Ce module est workflow-opérationnel mobile-first (pas de liste L1 = pas de SwipeActions).
Toutes les pages s'accèdent depuis la fiche réservation, pas depuis une liste centrale.

---

## Tâches L1→L5

### TASK-OPS-01 (P0) — SubNav layout module Opérations

**Problème** : `routes/_app/operations.tsx` est un `<Outlet />` nu.

**Fichier à modifier** : `frontend/src/routes/_app/operations.tsx`

```tsx
// routes/_app/operations.tsx
import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

const OPERATIONS_NAV = [
  { label: 'Scanner QR', href: '/operations/scan' },
]

export const Route = createFileRoute('/_app/operations')({
  component: () => (
    <div className="space-y-0">
      <SubNav items={OPERATIONS_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  ),
})
```

> Note : les pages `departure/$id` et `return/$id` sont accédées depuis la fiche réservation
> (pas depuis une navigation directe), donc elles n'apparaissent pas dans la SubNav.
> Le padding `p-4 md:p-6` est actuellement dans chaque page → supprimer après ajout du wrapper.

**Critères done** :
- ☐ `routes/_app/operations.tsx` contient SubNav avec onglet Scanner QR
- ☐ Padding `p-4 md:p-6` retiré des pages individuelles
- ☐ `tsc --noEmit` 0 erreur
- ☐ 1582 Vitest pass

---

### TASK-OPS-02 (P1) — Skeleton loading pré-départ

**Problème** : `DepartureInventoryPage.tsx:95` affiche `"Chargement de l'inventaire…"`.

**Fichier à modifier** : `frontend/src/pages/operations/DepartureInventoryPage.tsx`

```tsx
function DepartureItemSkeleton() {
  return (
    <div className="card space-y-3 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="space-y-1.5">
          <div className="h-4 bg-dark-700 rounded w-40" />
          <div className="h-3 bg-dark-700 rounded w-20" />
        </div>
        <div className="h-4 bg-dark-700 rounded w-14" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="h-9 bg-dark-700 rounded" />
        <div className="h-9 bg-dark-700 rounded" />
      </div>
      <div className="h-4 bg-dark-700 rounded w-28" />
    </div>
  )
}

function DepartureSkeleton() {
  return (
    <div className="max-w-2xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3 animate-pulse">
        <div className="w-9 h-9 bg-dark-700 rounded" />
        <div className="space-y-1.5">
          <div className="h-5 bg-dark-700 rounded w-32" />
          <div className="h-3 bg-dark-700 rounded w-24" />
        </div>
      </div>
      {/* Items */}
      {Array.from({ length: 3 }).map((_, i) => <DepartureItemSkeleton key={i} />)}
    </div>
  )
}

// Remplacer :
// if (isLoading) return <div className="p-6 text-center text-dark-400">Chargement de l'inventaire…</div>
if (isLoading) return <DepartureSkeleton />
```

**Critères done** :
- ☐ Skeleton structuré (header + 3 items checklist) avec animate-pulse
- ☐ Aucun texte `"Chargement…"` dans `DepartureInventoryPage`

---

### TASK-OPS-03 (P1) — Skeleton loading retour matériel

**Problème** : `ReturnInventoryPage.tsx:109` affiche `"Chargement de l'inventaire…"`.

**Fichier à modifier** : `frontend/src/pages/operations/ReturnInventoryPage.tsx`

```tsx
function ReturnItemSkeleton() {
  return (
    <div className="card space-y-3 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="space-y-1.5">
          <div className="h-4 bg-dark-700 rounded w-40" />
          <div className="h-3 bg-dark-700 rounded w-20" />
        </div>
        <div className="h-4 bg-dark-700 rounded w-14" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="h-9 bg-dark-700 rounded" />
        <div className="h-9 bg-dark-700 rounded" />
      </div>
    </div>
  )
}

function ReturnSkeleton() {
  return (
    <div className="max-w-2xl mx-auto space-y-5">
      <div className="flex items-center gap-3 animate-pulse">
        <div className="w-9 h-9 bg-dark-700 rounded" />
        <div className="space-y-1.5">
          <div className="h-5 bg-dark-700 rounded w-36" />
          <div className="h-3 bg-dark-700 rounded w-24" />
        </div>
      </div>
      {Array.from({ length: 3 }).map((_, i) => <ReturnItemSkeleton key={i} />)}
    </div>
  )
}

// Remplacer :
// if (isLoading) return <div className="p-6 text-center text-dark-400">Chargement de l'inventaire…</div>
if (isLoading) return <ReturnSkeleton />
```

**Critères done** :
- ☐ Skeleton structuré (header + 3 items) avec animate-pulse
- ☐ Aucun texte `"Chargement…"` dans `ReturnInventoryPage`

---

### TASK-OPS-04 (P1) — Corriger pattern erreur ScanPage

**Problème** : `ScanPage.tsx:42` utilise `err.message` — pattern interdit selon `GOTCHA:FRONTEND:ERROR-PATTERN`.

```tsx
// Ligne 42 — AVANT (interdit) :
const handleError = (err: Error) => {
  setErrorMsg(err.message || 'Erreur caméra')
  setMode('error')
}
```

La prop `onError` du `QRScanner` retourne un `Error` natif (pas une erreur Axios) — c'est une
erreur de caméra browser, pas une erreur API. Dans ce contexte spécifique, `err.message` est
acceptable puisque c'est une erreur DOM/browser, pas une réponse HTTP.

**Néanmoins** : ajouter un fallback explicite et typer correctement.

```tsx
// Ligne 42 — APRÈS :
const handleError = (err: unknown) => {
  const msg = err instanceof Error ? err.message : 'Erreur caméra'
  setErrorMsg(msg || 'Erreur caméra inconnue')
  setMode('error')
}
```

> Note : Le `GOTCHA` s'applique aux erreurs de mutations Axios. Pour les erreurs browser
> natives (caméra, permissions), `err.message` avec guard `instanceof Error` est correct.
> Documenter cette exception dans `memory/gotchas.md`.

**Critères done** :
- ☐ `err` typé `unknown` + guard `instanceof Error`
- ☐ `tsc --noEmit` 0 erreur

---

### TASK-OPS-05 (P2) — Normaliser classes design system

**Problème** : `text-body` utilisé dans 3 pages du module — classe non définie dans le design system.

**Correspondances** :

| Classe actuelle | Remplacement |
|----------------|--------------|
| `text-body` | *(supprimer)* — texte blanc par défaut via héritage |

**Fichiers et lignes** :
- `DepartureInventoryPage.tsx:117` — titre "Pré-départ"
- `DepartureInventoryPage.tsx:130` — nom produit dans checklist
- `ReturnInventoryPage.tsx:127` — titre "Retour matériel"
- `ReturnInventoryPage.tsx:153` — nom produit dans checklist
- `ScanPage.tsx:68` — titre "Scanner QR"

**Action** : Supprimer `text-body` (le texte hérite déjà de la couleur parent via `text-white`
défini sur `body` dans `index.css`).

**Critères done** :
- ☐ Aucune occurrence de `text-body` dans le module opérations
- ☐ Rendu visuel identique

---

### TASK-OPS-06 (P2) — Indicateur progression global pré-départ

**Problème** : `DepartureInventoryPage` n'affiche pas de barre de progression globale
(N/M articles chargés). L'utilisateur ne sait pas combien il reste à valider.

**Fichier à modifier** : `frontend/src/pages/operations/DepartureInventoryPage.tsx`

```tsx
// Calculer la progression après récupération des données
const totalItems = (data.items ?? []).length
const checkedItems = (data.items ?? []).filter((item) => {
  const s = getItemState(item)
  return s.quantity_loaded > 0
}).length
const progressPct = totalItems > 0 ? Math.round((checkedItems / totalItems) * 100) : 0

// Afficher après le header :
<div className="card space-y-2">
  <div className="flex items-center justify-between text-sm">
    <span className="text-dark-400">Articles vérifiés</span>
    <span className={checkedItems === totalItems ? 'text-green-400 font-medium' : 'text-dark-300'}>
      {checkedItems} / {totalItems}
    </span>
  </div>
  <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
    <div
      className={`h-full rounded-full transition-all duration-300 ${
        progressPct === 100 ? 'bg-green-500' : 'bg-blue-500'
      }`}
      style={{ width: `${progressPct}%` }}
    />
  </div>
</div>
```

**Critères done** :
- ☐ Barre progression visible entre header et liste items
- ☐ Couleur verte si 100% complété
- ☐ Compte dynamique mis à jour à chaque modification quantité

---

## Couverture LAYER.html — Mapping final

| Écran LAYER | Route | Composant | Backend | Statut cible |
|------------|-------|-----------|---------|--------------|
| `s-scan-qr` | `/operations/scan` | `ScanPage` | `GET /qr/{code}` | ✅ → typage erreur |
| `s-depart-checklist` | `/operations/departure/$id` | `DepartureInventoryPage` | `GET/POST /departure/{id}` | ✅ → skeleton + progression |
| `s-retour-checklist` | `/operations/return/$id` | `ReturnInventoryPage` | `GET/POST /return/{id}` | ✅ → skeleton |
| `s-retour-damage` | Fiche retour | `DamageDeclarationModal` | `POST /return/{id}/damage` | ✅ |
| `s-damage-photo` | Fiche retour | `uploadDamagePhoto` | `POST /damage/photo` | ⚠️ Stub — backend P2 |
| `s-depart-block` | Fiche départ | Bouton blocage + formulaire | `POST /departure/{id}/block` | ✅ |

---

## Ordre d'exécution recommandé

```
TASK-OPS-01  ← P0 SubNav layout
TASK-OPS-02  ← P1 Skeleton pré-départ (indépendant)
TASK-OPS-03  ← P1 Skeleton retour (indépendant)
TASK-OPS-04  ← P1 Erreur pattern ScanPage (indépendant)
TASK-OPS-05  ← P2 Design system (indépendant)
TASK-OPS-06  ← P2 Indicateur progression (indépendant)
```

---

## Référence — Fichiers impactés

| Fichier | Action |
|---------|--------|
| `routes/_app/operations.tsx` | Modifier — ajouter SubNav |
| `pages/operations/DepartureInventoryPage.tsx` | Modifier — skeleton, text-body, progression |
| `pages/operations/ReturnInventoryPage.tsx` | Modifier — skeleton, text-body |
| `pages/operations/ScanPage.tsx` | Modifier — erreur pattern, text-body |
