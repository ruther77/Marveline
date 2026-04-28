# Module 04 — Ventes

> Audit terrain — 2026-02-25 | Fichiers lus : VentesListPage (267L), VenteDetailPage (272L),
> VenteCreatePage (242L), AddVentePaymentModal, VenteRefundModal,
> routes/_app/ventes.tsx, ventes/index.tsx, ventes/$id.tsx, ventes/new.tsx

---

## Périmètre (écrans LAYER)

| Écran LAYER | Route TanStack | Page | Statut |
|-------------|---------------|------|--------|
| `s-ventes-liste` | `/_app/ventes/` | `VentesListPage` | ✅ Existe |
| `s-ventes-detail` | `/_app/ventes/$id` | `VenteDetailPage` | ✅ Existe |
| `s-ventes-creation` | `/_app/ventes/new` | `VenteCreatePage` | ✅ Existe |
| `s-ventes-paiement` | *modal* dans DetailPage | `AddVentePaymentModal` | ✅ Existe |
| `s-ventes-remboursement` | *modal* dans DetailPage | `VenteRefundModal` | ✅ Existe |
| `s-ventes-pdf` | *inline* dans DetailPage | download blob | ✅ Existe |

**Statuts vente (7)** :
`draft → pending → deposit_paid → fully_paid | overdue | refunded | cancelled`

---

## Audit routes

```
routes/_app/
  ventes.tsx               ← Layout parent — <Outlet /> seul, PAS de SubNav
  ventes/
    index.tsx              ← → VentesListPage
    new.tsx                ← → VenteCreatePage
    $id.tsx                ← → VenteDetailPage (page terminale — OK ici, pas de sous-routes)
```

**Observation** : module plus simple que Devis — pas de sous-routes métier. La structure `$id.tsx` comme page terminale est acceptable. Seul le VENTES_NAV est problématique.

---

## Couverture L1→L5 — état actuel et gaps

### L1 — Liste des ventes (`VentesListPage`, 267 lignes)

**Ce qui est fait ✅**
- Liste paginée (page_size 20) + search debounce
- Filtre statut (7 statuts)
- Filtres date : presets Aujourd'hui / Cette semaine / Ce mois + range date custom avec bouton reset
- Vue desktop tableau (référence, client, date, statut, total, restant) + vue mobile cards
- Colonne "Restant" avec alerte rouge si statut `overdue` (icône AlertTriangle + couleur)
- Menu MoreVertical par ligne (Voir détail)

**Gaps ❌**
| Gap | Impact | Priorité |
|-----|--------|----------|
| Anti-pattern `VENTES_NAV` — SubNav cross-modules (Devis/Réservations/Ventes/Clients) embarqué dans la page | Navigation instable, couplage fort | **P0** |
| Loading desktop = texte `"Chargement…"` dans `<td>` / mobile = `<p>` texte | 7 états UI non respectés, pas de skeleton | **P1** |
| Cards mobile sans SwipeActions | UX dégradée sur mobile, 44px touch targets non respectés | **P1** |

---

### L2 — Fiche vente (`VenteDetailPage`, 272 lignes)

**Ce qui est fait ✅**
- Header : référence, statut badge, badge jours de retard si `overdue_days > 0`
- Barre de progression paiement (% payé, barre colorée vert/or)
- Totaux : total HT, payé, restant (coloré amber si restant > 0, vert si soldé)
- Tableau articles : nom, qté × PU, sous-total
- Sous-total HT + TVA + Total TTC
- Historique paiements avec indicateur dépôt vs paiement + méthode + date + notes
- Actions contextuelles intelligentes :
  - "Enregistrer un paiement" → `AddVentePaymentModal` (si pas `fully_paid` ou `refunded`)
  - "Rembourser" → `VenteRefundModal` (si paiements > 0 et pas `refunded`)
  - "Annuler" avec confirm inline (si pas `fully_paid` ou `refunded`)
- PDF download (blob + `<a>` click)
- Notes si présentes

**Gaps ❌**
| Gap | Impact | Priorité |
|-----|--------|----------|
| Loading = texte `"Chargement…"` | 7 états UI non respectés | **P1** |
| Pas de lien vers le devis source (si vente créée depuis un devis converti) | Traçabilité workflow Devis → Vente | **P2** |
| Pas de lien vers la réservation liée (si `reservation_id` existe) | Traçabilité cross-module | **P2** |

---

### L3 — Création vente (`VenteCreatePage`, 242 lignes)

**Ce qui est fait ✅**
- `ComboboxAsync` client avec debounce 300ms
- Date de vente (défaut aujourd'hui)
- Acompte % (optionnel)
- Échéance de paiement (optionnel)
- Notes (optionnel)
- `CataloguePickerModal` pour sélectionner articles
- Ligne dashed "Sélectionner depuis le catalogue" si aucun article
- Quantité éditable par ligne + sous-total calculé en temps réel
- Total estimé avec formatCents
- Validation : client requis + au moins 1 article

**Gaps ❌**
| Gap | Impact | Priorité |
|-----|--------|----------|
| Formulaire plat (une seule page) — OK pour ce module, acceptable | Léger (Devis a stepper, Vente n'en a pas besoin) | P3 |
| Prix non éditable par ligne dans la création (prix du catalogue figé) | Impossible d'appliquer une remise à la création | **P2** |

---

### L4/L5 — Granularité fine

| Fonctionnalité | État | Priorité |
|----------------|------|----------|
| Édition prix unitaire à la création (remise) | ❌ | P2 |
| Facture automatique depuis vente soldée | ❌ | P2 |
| Export CSV ventes filtrées | ❌ | P2 |
| Lien réservation ↔ vente dans les deux sens | ❌ | P2 |

---

## Tâches

---

### TASK-VTE-01 — Corriger anti-pattern VENTES_NAV (P0)

**Contexte** : `VentesListPage` embarque `<SubNav items={VENTES_NAV} />` avec items cross-modules (Devis/Réservations/Ventes/Clients). Même anti-pattern que Clients et Devis.

**Fichiers touchés** :
- `frontend/src/routes/_app/ventes.tsx` — ajout SubNav ventes-level
- `frontend/src/pages/ventes/VentesListPage.tsx` — suppression VENTES_NAV

**Implémentation** :

```tsx
// routes/_app/ventes.tsx
import { Outlet } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

const VENTES_NAV = [
  { label: 'Ventes', href: '/ventes' },
  { label: 'Nouvelle vente', href: '/ventes/new' },
]

export default function VentesLayout() {
  return (
    <div className="space-y-0">
      <SubNav items={VENTES_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  )
}
```

```tsx
// VentesListPage.tsx — supprimer :
// import { SubNav } from '@/components/layout/SubNav'
// const VENTES_NAV = [{ label: 'Devis', href: '/devis' }, ...]
// <SubNav items={VENTES_NAV} className="-mx-4 md:-mx-6 -mt-4 md:-mt-6 mb-1" />
// Et retirer le padding top -mt qui compensait le SubNav intégré
```

**Note** : le bouton "+ Nouvelle vente" en header peut rester ou être retiré si la SubNav contient déjà le lien.

**Critères done** :
- ☐ `SubNav` dans `ventes.tsx` layout avec 2 items
- ☐ `VENTES_NAV` cross-modules supprimé de `VentesListPage`
- ☐ Padding `-mt-4 md:-mt-6` supprimé (plus nécessaire)
- ☐ `tsc` 0 erreur

---

### TASK-VTE-02 — Skeleton loading L1 (P1)

**Contexte** : `VentesListPage` affiche du texte dans `<td>` pour le chargement desktop et `<p>` pour mobile. Règle PDF = skeleton sur toutes les listes L1.

**Fichiers touchés** :
- `frontend/src/pages/ventes/VentesListPage.tsx`

**Implémentation** :

```tsx
// Skeleton desktop — à insérer dans <tbody> quand isLoading :
function VentesTableSkeleton() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <tr key={i} className="border-b border-dark-700/50 animate-pulse">
          <td className="px-4 py-3"><div className="h-3 bg-dark-700 rounded w-24" /></td>
          <td className="px-4 py-3"><div className="h-3 bg-dark-700 rounded w-32" /></td>
          <td className="px-4 py-3"><div className="h-3 bg-dark-700 rounded w-20" /></td>
          <td className="px-4 py-3"><div className="h-5 bg-dark-700 rounded-full w-20" /></td>
          <td className="px-4 py-3 text-right"><div className="h-3 bg-dark-700 rounded w-16 ml-auto" /></td>
          <td className="px-4 py-3 text-right"><div className="h-3 bg-dark-700 rounded w-16 ml-auto" /></td>
          <td className="px-4 py-3" />
        </tr>
      ))}
    </>
  )
}

// Skeleton mobile :
function VentesCardsSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="card">
          <div className="flex items-start justify-between mb-2">
            <div className="space-y-1.5">
              <div className="h-3 bg-dark-700 rounded w-20" />
              <div className="h-4 bg-dark-700 rounded w-36" />
              <div className="h-3 bg-dark-800 rounded w-16" />
            </div>
            <div className="h-5 bg-dark-700 rounded-full w-20" />
          </div>
          <div className="flex justify-between">
            <div className="h-3 bg-dark-700 rounded w-28" />
            <div className="h-3 bg-dark-700 rounded w-24" />
          </div>
        </div>
      ))}
    </div>
  )
}
```

**Critères done** :
- ☐ Skeleton desktop dans `<tbody>` quand `isLoading`
- ☐ Skeleton mobile cards quand `isLoading`
- ☐ Textes "Chargement…" supprimés
- ☐ `tsc` 0 erreur

---

### TASK-VTE-03 — SwipeActions sur cards mobile L1 (P1)

**Contexte** : les cards mobile n'ont pas d'actions swipe. Les ventes ont 2 actions naturelles pour mobile.

**Fichiers touchés** :
- `frontend/src/pages/ventes/VentesListPage.tsx`

**Implémentation** :

```tsx
import { SwipeActions } from '@/components/ui/SwipeActions'
import { CreditCard, XCircle } from 'lucide-react'

// Dans la vue mobile, wrapper chaque card :
<SwipeActions
  key={v.id}
  leftActions={[
    {
      label: 'Payer',
      icon: <CreditCard className="w-5 h-5" />,
      color: 'bg-green-600',
      onAction: () => navigate({ to: '/ventes/$id', params: { id: String(v.id) }, search: { pay: 1 } }),
      disabled: ['fully_paid', 'refunded'].includes(v.status),
    },
  ]}
  rightActions={[
    {
      label: 'Annuler',
      icon: <XCircle className="w-5 h-5" />,
      color: 'bg-red-600',
      onAction: () => handleCancel(v.id),
      disabled: ['fully_paid', 'refunded'].includes(v.status),
    },
  ]}
>
  <div className="card cursor-pointer" onClick={() => navigate(...)}>
    {/* contenu card existant */}
  </div>
</SwipeActions>
```

**Note** : `handleCancel` nécessite d'extraire la mutation `useCancelVente` dans la ListPage (appel direct depuis la liste).

**Critères done** :
- ☐ SwipeActions sur toutes les cards mobile
- ☐ Action gauche : Payer → navigate vers fiche avec param `pay=1` (optionnel)
- ☐ Action droite : Annuler avec mutation inline
- ☐ Actions désactivées selon statut
- ☐ `tsc` 0 erreur

---

### TASK-VTE-04 — Skeleton loading L2 (P1)

**Contexte** : `VenteDetailPage` affiche `"Chargement…"` pendant le fetch.

**Fichiers touchés** :
- `frontend/src/pages/ventes/VenteDetailPage.tsx`

**Implémentation** :

```tsx
function VenteDetailSkeleton() {
  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto space-y-5 animate-pulse">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-dark-700 rounded" />
          <div className="space-y-1.5">
            <div className="flex gap-2">
              <div className="h-6 bg-dark-700 rounded w-32" />
              <div className="h-5 bg-dark-700 rounded-full w-20" />
            </div>
            <div className="h-3 bg-dark-800 rounded w-40" />
          </div>
        </div>
        <div className="h-9 bg-dark-700 rounded w-20" />
      </div>
      {/* Progression */}
      <div className="card space-y-3">
        <div className="h-2 bg-dark-700 rounded-full" />
        <div className="grid grid-cols-3 gap-4">
          {[0,1,2].map((i) => (
            <div key={i} className="space-y-1 text-center">
              <div className="h-3 bg-dark-800 rounded w-12 mx-auto" />
              <div className="h-5 bg-dark-700 rounded w-16 mx-auto" />
            </div>
          ))}
        </div>
      </div>
      {/* Articles */}
      <div className="card space-y-3">
        <div className="h-4 bg-dark-700 rounded w-20" />
        {[0,1,2].map((i) => (
          <div key={i} className="flex justify-between">
            <div className="h-4 bg-dark-700 rounded w-40" />
            <div className="h-4 bg-dark-700 rounded w-20" />
          </div>
        ))}
      </div>
    </div>
  )
}

// Remplacer :
// if (isLoading) return <div className="p-6 text-center text-dark-400">Chargement…</div>
// → if (isLoading) return <VenteDetailSkeleton />
```

**Critères done** :
- ☐ Skeleton affiché pendant `isLoading === true`
- ☐ Structure skeleton reflète la mise en page réelle (header + progression + articles)
- ☐ `tsc` 0 erreur

---

### TASK-VTE-05 — Lien vers devis source et réservation liée (P2)

**Contexte** : une vente peut être créée depuis un devis converti. La traçabilité demande de pouvoir naviguer vers le devis source depuis la fiche vente (et vers la réservation liée si applicable).

**Prérequis** : vérifier si le backend retourne `source_devis_id` et/ou `reservation_id` dans `VenteDetail`.

**Fichiers touchés** :
- `frontend/src/pages/ventes/VenteDetailPage.tsx`
- `frontend/src/types/vente.ts` (ajout champs si absents)

**Implémentation** :

```tsx
// Dans VenteDetailPage, sous le header :
{data.source_devis_id && (
  <Link
    to="/devis/$id"
    params={{ id: String(data.source_devis_id) }}
    className="flex items-center gap-2 text-sm text-dark-400 hover:text-primary-400 transition-colors"
  >
    <FileText className="w-4 h-4" />
    Devis source : #{data.source_devis_id}
  </Link>
)}
{data.reservation_id && (
  <Link
    to="/events/$id"
    params={{ id: String(data.reservation_id) }}
    className="flex items-center gap-2 text-sm text-dark-400 hover:text-primary-400 transition-colors"
  >
    <CalendarDays className="w-4 h-4" />
    Réservation liée : #{data.reservation_id}
  </Link>
)}
```

**Critères done** :
- ☐ Vérifier que `source_devis_id` et `reservation_id` existent dans le type `VenteDetail`
- ☐ Liens affichés conditionnellement si champs non null
- ☐ Navigation vers la fiche correspondante fonctionnelle
- ☐ `tsc` 0 erreur

---

### TASK-VTE-06 — Normaliser classes design system (P2)

**Problème** : `VentesListPage.tsx` L73 contient la classe `text-body` non définie dans le design system Tailwind configuré.

**Fichiers concernés** :
- `VentesListPage.tsx:73` — probable dans un label/titre de section

**Correction** :

| Classe actuelle | Remplacement |
|----------------|--------------|
| `text-body` | *(supprimer)* — le texte hérite déjà de la couleur parent `text-white` |

**Critères done** :
- ☐ Aucune occurrence de `text-body` dans le module Ventes
- ☐ Rendu visuel identique (héritage couleur)
- ☐ `tsc` 0 erreur

---

### TASK-VTE-07 — URL sync filtres L1 (P1)

**Problème** : Les filtres de `VentesListPage` sont en `useState` local (L29-33) :
- `page` (numéro de page)
- `search` (recherche texte)
- `status` (filtre statut)
- `dateFrom` + `dateTo` (plage de dates)

Ces filtres sont perdus à chaque navigation (retour depuis une fiche vente → retour à la page 1 sans filtre).

**Fichiers touchés** :
- `frontend/src/pages/ventes/VentesListPage.tsx`
- `frontend/src/routes/_app/ventes/index.tsx` — ajouter `validateSearch`

**Implémentation** :

```tsx
// routes/_app/ventes/index.tsx
export const Route = createFileRoute('/_app/ventes/')({
  validateSearch: (search) => ({
    page:     typeof search.page === 'number'  ? search.page  : 1,
    q:        typeof search.q    === 'string'  ? search.q     : '',
    status:   typeof search.status === 'string' ? search.status : 'all',
    dateFrom: typeof search.dateFrom === 'string' ? search.dateFrom : '',
    dateTo:   typeof search.dateTo   === 'string' ? search.dateTo   : '',
  }),
  component: VentesListPage,
})
```

```tsx
// VentesListPage.tsx — remplacer les useState par les searchParams
import { useSearch, useNavigate } from '@tanstack/react-router'

const search = useSearch({ from: '/_app/ventes/' })
const navigate = useNavigate()

const page     = search.page     ?? 1
const query    = search.q        ?? ''
const status   = search.status   ?? 'all'
const dateFrom = search.dateFrom ?? ''
const dateTo   = search.dateTo   ?? ''

const setPage  = (p: number) => navigate({ search: (prev) => ({ ...prev, page: p }) })
const setQuery = (q: string) => navigate({ search: (prev) => ({ ...prev, q: q || undefined, page: 1 }) })
// etc.
```

**Critères done** :
- ☐ `validateSearch` dans `routes/_app/ventes/index.tsx`
- ☐ `useState` pour page/search/status/dateFrom/dateTo supprimés de `VentesListPage`
- ☐ Retour depuis fiche → filtres restaurés
- ☐ URL partageable avec filtres pré-appliqués
- ☐ `tsc` 0 erreur

---

## Composants partagés identifiés

| Composant | Fichier | Utilisé dans |
|-----------|---------|--------------|
| `AddVentePaymentModal` | `pages/ventes/components/AddVentePaymentModal.tsx` | `VenteDetailPage` |
| `VenteRefundModal` | `pages/ventes/components/VenteRefundModal.tsx` | `VenteDetailPage` |
| `CataloguePickerModal` | `components/catalogue/CataloguePickerModal.tsx` | `VenteCreatePage` |
| `ComboboxAsync` | `components/ui/ComboboxAsync.tsx` | `VenteCreatePage` |
| `DomainStatusBadge` | `components/ui/DomainStatusBadge.tsx` | L1 + L2 |
| `SwipeActions` | `components/ui/SwipeActions.tsx` | À utiliser dans L1 (TASK-VTE-03) |

---

## Endpoints backend (référence)

| Méthode | Path | Description |
|---------|------|-------------|
| GET | `/ventes` | Liste paginée (filtres : status, search, date_from, date_to) |
| POST | `/ventes` | Créer vente (lignes, client, date, acompte %, échéance) |
| GET | `/ventes/{id}` | Détail complet (lignes + paiements) |
| POST | `/ventes/{id}/payments` | Enregistrer paiement |
| POST | `/ventes/{id}/refund` | Rembourser |
| POST | `/ventes/{id}/cancel` | Annuler |
| GET | `/ventes/{id}/pdf` | StreamingResponse PDF |

---

## Ordre d'implémentation recommandé

```
P0 (bloquant UX/navigation)
  TASK-VTE-01  Corriger VENTES_NAV dans VentesListPage

P1 (qualité — à faire avant livraison)
  TASK-VTE-02  Skeleton loading L1
  TASK-VTE-03  SwipeActions mobile L1
  TASK-VTE-04  Skeleton loading L2

P1 (UX et cohérence)
  TASK-VTE-07  URL sync filtres L1

P2 (amélioration traçabilité et design)
  TASK-VTE-05  Liens devis source + réservation liée
  TASK-VTE-06  Normaliser classes text-body
```

---

## Critères done globaux du module

- ☐ Anti-pattern VENTES_NAV éliminé (TASK-VTE-01)
- ☐ Skeleton loading sur L1 et L2 (TASK-VTE-02 + TASK-VTE-04)
- ☐ SwipeActions mobile L1 (TASK-VTE-03)
- ☐ URL sync filtres L1 (TASK-VTE-07)
- ☐ Aucune classe `text-body` dans le module (TASK-VTE-06)
- ☐ `tsc` 0 erreur sur tout le module
- ☐ `vitest run` — 0 régression
