# Module 03 — Devis

> Audit terrain — 2026-02-25 | Fichiers lus : DevisListPage (218L), DevisDetailPage (717L),
> DevisCreatePage (~250L), DevisModulesPage (235L), DevisPhasesPage (237L),
> DevisNegotiationPage (145L), DevisLineEditor (136L), DevisSendModal, DevisConvertModal,
> routes/_app/devis.tsx, routes/_app/devis/$id.tsx, routes/_app/devis/$id/modules.tsx, phases, negotiation, new.tsx

---

## Périmètre (écrans LAYER)

| Écran LAYER | Route TanStack | Page | Statut |
|-------------|---------------|------|--------|
| `s-devis-liste` | `/_app/devis/` | `DevisListPage` | ✅ Existe |
| `s-devis-detail` | `/_app/devis/$id` | `DevisDetailPage` | ✅ Existe — 717 lignes |
| `s-devis-creation` | `/_app/devis/new` | `DevisCreatePage` | ✅ Existe — stepper 3 étapes |
| `s-devis-modules` | `/_app/devis/$id/modules` | `DevisModulesPage` | ✅ Existe |
| `s-devis-phases` | `/_app/devis/$id/phases` | `DevisPhasesPage` | ✅ Existe |
| `s-devis-negociation` | `/_app/devis/$id/negotiation` | `DevisNegotiationPage` | ✅ Existe |
| `s-devis-pdf` | *inline* dans DetailPage | iframe + download | ✅ Existe |
| `s-devis-signature` | *inline* dans DetailPage | `SignaturePad` | ✅ Existe |

**Statuts devis (9)** :
`draft → sent → negotiation → accepted | refused | expired | converted | cancelled | version_pending`

---

## Audit routes

```
routes/_app/
  devis.tsx               ← Layout parent — <Outlet /> seul, PAS de SubNav
  devis/
    index.tsx             ← → DevisListPage
    new.tsx               ← → DevisCreatePage
    $id.tsx               ← → DevisDetailPage directement (pas layout !)
    $id/
      modules.tsx         ← → DevisModulesPage
      phases.tsx          ← → DevisPhasesPage
      negotiation.tsx     ← → DevisNegotiationPage
```

**Problème structurel clé** : `$id.tsx` pointe vers `DevisDetailPage` comme page terminale — pas un layout.
Les sous-routes `$id/modules`, `$id/phases`, `$id/negotiation` existent mais sont orphelines de leur layout parent.
`DevisDetailPage` navigue vers elles via `navigate()` — navigation hybride incohérente.

---

## Couverture L1→L5 — état actuel et gaps

### L1 — Liste des devis (`DevisListPage`, 218 lignes)

**Ce qui est fait ✅**
- Liste paginée + search debounce 300ms
- Filtre statut (9 statuts : all / draft / sent / negotiation / accepted / refused / expired / converted / cancelled)
- Vue desktop tableau (référence, client, montant, statut, date) + vue mobile cards
- Statut coloré avec badges

**Gaps ❌**
| Gap | Impact | Priorité |
|-----|--------|----------|
| Anti-pattern `VENTES_NAV` — SubNav cross-modules (Devis/Réservations/Ventes/Clients) embarqué dans la page | Navigation instable, couplage fort | **P0** |
| Loading = texte `"Chargement…"` | Pas de skeleton, CLS, 7 états UI non respectés | **P1** |
| Cards mobile sans SwipeActions | UX dégradée sur mobile, 44px touch targets non respectés | **P1** |

---

### L2 — Fiche devis (`DevisDetailPage`, 717 lignes)

**Ce qui est fait ✅**
- Actions complètes : Envoyer (`DevisSendModal`), Accepter (confirm inline), Refuser (confirm inline), Convertir (`DevisConvertModal`), Dupliquer, Annuler (confirm inline)
- PDF : preview iframe plein écran + bouton download
- Signature électronique : `SignaturePad` visible si statut `sent`
- Onglet Versions : historique snapshots avec diff visuel (+ ajouté, − retiré, ~ modifié)
- Onglet Détails : infos grid + tableau lignes + sous-total/TVA/total + caution + résumé négociation
- `validateSearch: { send: fallback(number(), 0) }` → ouvre modal envoi automatiquement si `?send=1`

**Gaps ❌**
| Gap | Impact | Priorité |
|-----|--------|----------|
| **Tabs hybrides** : onglets Détails/Versions = `activeTab` state React ; onglets Modules/Phases = `navigate()` → incohérence, navigation non bookmarkable | UX cassée, back/forward brisé | **P0** |
| **717 lignes monolithiques** — 0 découpe en composants | Lisibilité, maintenabilité, testabilité | **P1** |
| Loading = texte simple `"Chargement…"` | 7 états UI non respectés | **P1** |

---

### L3 — Création devis (`DevisCreatePage`, ~250 lignes)

**Ce qui est fait ✅**
- Stepper 3 étapes avec état `step: 1 | 2 | 3`
  - Étape 1 : infos (ComboboxAsync client, dates début/fin, lieu, notes, conditions paiement, TVA)
  - Étape 2 : `DevisLineEditor` (table éditable, `CataloguePickerModal`)
  - Étape 3 : récap + message accompagnement + bouton Créer
- Initialisation lignes depuis `cartStore` (flux Catalogue → Devis)
- `DevisLineEditor` : table editable, quantité + prix unitaire, sous-total, `CataloguePickerModal`

**Gaps ❌**
| Gap | Impact | Priorité |
|-----|--------|----------|
| Stepper custom au lieu du composant `StepperForm` standard (`components/ui/StepperForm.tsx`) | Duplication, incohérence UX | **P2** |
| `DevisLineEditor` : prix unitaire = `input type=number step=0.01` raw (euros), pas `MoneyInput` | Pas de formatage euro, risque parsing float | **P2** |
| Pas de BottomSheet sur mobile pour la création | formulaire pleine page non optimisé mobile | **P2** |

---

### L4 — Sous-pages fiche

**Ce qui est fait ✅**
- `DevisModulesPage` : CRUD modules par type (socle/stock/facturation/sécurité/services), tabs par type, formulaire inline
- `DevisPhasesPage` : CRUD phases avec dates début/fin, timeline numérotée, validation dates
- `DevisNegotiationPage` : chat timeline + proposition montant, formulaire conditionnel (seulement statuts `sent`/`negotiation`), total actuel affiché

**Gaps ❌**
| Gap | Impact | Priorité |
|-----|--------|----------|
| Chaque sous-page a son propre bouton `ArrowLeft → navigate('/devis/$id')` — pas de SubNav persistant | Navigation sans contexte, pas de sens de la position dans la fiche | **P0** (résolu par TASK-DEV-02) |
| Loading dans sous-pages = texte `"Chargement…"` | Cohérence | **P1** |

---

### L5 — Granularité max (futurs)

| Fonctionnalité | État | Priorité |
|----------------|------|----------|
| Glisser-déposer pour réordonner les lignes de devis | ❌ | P3 |
| Aperçu PDF temps réel (hot reload) | ❌ | P3 |
| Commentaires par ligne devis | ❌ | P3 |
| Lien partage public devis (token temporaire) | ❌ | P3 |

---

## Tâches

---

### TASK-DEV-01 — Corriger anti-pattern VENTES_NAV dans la liste (P0)

**Contexte** : `DevisListPage` embarque `<SubNav items={VENTES_NAV} />` avec items cross-modules (Devis, Réservations, Ventes, Clients). Ce SubNav doit être dans chaque layout parent respectif, pas dans les pages filles.

**Fichiers touchés** :
- `frontend/src/routes/_app/devis.tsx` — ajout SubNav devis-level
- `frontend/src/pages/devis/DevisListPage.tsx` — suppression VENTES_NAV

**Implémentation** :

```tsx
// routes/_app/devis.tsx
import { Outlet, Link, useRouter } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

const DEVIS_NAV = [
  { label: 'Liste', href: '/devis' },
  { label: 'Nouveau devis', href: '/devis/new' },
]

export default function DevisLayout() {
  return (
    <div className="space-y-0">
      <SubNav items={DEVIS_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  )
}
```

```tsx
// DevisListPage.tsx — supprimer :
// import { SubNav } from '@/components/layout/SubNav'
// const VENTES_NAV = [...]
// <SubNav items={VENTES_NAV} />
```

**Critères done** :
- ☐ `SubNav` présent dans `devis.tsx` layout avec 2 items (Liste | Nouveau devis)
- ☐ `VENTES_NAV` et son `<SubNav>` supprimés de `DevisListPage`
- ☐ `tsc` 0 erreur
- ☐ Navigation Liste ↔ Nouveau fonctionne, onglet actif correct

---

### TASK-DEV-02 — Unifier navigation fiche en layout SubNav (P0)

**Contexte** : `routes/_app/devis/$id.tsx` pointe vers `DevisDetailPage` comme page finale.
Les sous-routes `$id/modules`, `$id/phases`, `$id/negotiation` existent mais sans layout commun.
`DevisDetailPage` navigue vers elles via `navigate()` et gère Détails/Versions en state React local.

**Cible** : transformer `$id.tsx` en layout avec SubNav (6 onglets), déplacer le contenu Détails+Versions dans `$id/index.tsx`.

**Fichiers touchés** :
- `frontend/src/routes/_app/devis/$id.tsx` — devient layout
- `frontend/src/routes/_app/devis/$id/index.tsx` — nouveau (contenu Détails+Versions)
- `frontend/src/pages/devis/DevisDetailPage.tsx` — extraire le contenu L4 ; le L2 pur reste
- Sous-routes `$id/modules.tsx`, `$id/phases.tsx`, `$id/negotiation.tsx` — inchangées

**Implémentation** :

```tsx
// routes/_app/devis/$id.tsx — devient layout
import { Outlet, useParams } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

export default function DevisDetailLayout() {
  const { id } = useParams({ strict: false })

  const FICHE_NAV = [
    { label: 'Détails', href: `/devis/${id}` },
    { label: 'Modules', href: `/devis/${id}/modules` },
    { label: 'Phases', href: `/devis/${id}/phases` },
    { label: 'Négociation', href: `/devis/${id}/negotiation` },
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
```

```tsx
// routes/_app/devis/$id/index.tsx — nouveau
export { default } from '@/pages/devis/DevisDetailPage'
```

```tsx
// DevisDetailPage.tsx — supprimer :
// - const [activeTab, setActiveTab] = useState<'details' | 'versions'>('details')
// - Les boutons navigate('/devis/$id/modules'), navigate('/devis/$id/phases')
// - Les boutons "Modules" et "Phases" du header (remplacés par SubNav)
// Garder : actions (Envoyer/Accepter/etc.), onglets Détails/Versions, PDF, Signature
```

**Note** : les onglets `Détails` / `Versions` **dans** DevisDetailPage peuvent rester en state React local (ce sont des vues du même endpoint GET /devis/{id}, pas des routes séparées). Seuls Modules/Phases/Négociation passent en SubNav.

**Critères done** :
- ☐ `routes/_app/devis/$id.tsx` = layout `<Outlet />` + `<SubNav>` 4 onglets
- ☐ `routes/_app/devis/$id/index.tsx` créé et fonctionnel
- ☐ Boutons navigate() pour Modules/Phases supprimés de `DevisDetailPage`
- ☐ URL directe `/devis/42/modules` affiche `DevisModulesPage` dans le layout
- ☐ Bouton ArrowLeft dans sous-pages peut rester (retour rapide) mais SubNav permet navigation directe
- ☐ `validateSearch: { send: ... }` migré vers `$id/index.tsx`
- ☐ `tsc` 0 erreur

---

### TASK-DEV-03 — Skeleton loading L1 (P1)

**Contexte** : `DevisListPage` affiche un texte `"Chargement…"` pendant le fetch. Règle PDF = skeleton sur toutes les listes L1.

**Fichiers touchés** :
- `frontend/src/pages/devis/DevisListPage.tsx`

**Implémentation** :

```tsx
// Composant skeleton à ajouter dans DevisListPage.tsx

function DevisListSkeleton() {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Chargement des devis">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="card flex items-center gap-4 animate-pulse">
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-dark-700 rounded w-1/3" />
            <div className="h-3 bg-dark-800 rounded w-1/2" />
          </div>
          <div className="h-6 w-20 bg-dark-700 rounded-full" />
          <div className="h-4 w-24 bg-dark-800 rounded" />
        </div>
      ))}
    </div>
  )
}

// Remplacer dans le JSX :
// {isLoading ? <div>Chargement…</div> : ...}
// → {isLoading ? <DevisListSkeleton /> : ...}
```

**Critères done** :
- ☐ `DevisListSkeleton` affiché pendant `isLoading === true`
- ☐ 6 lignes skeleton avec animate-pulse
- ☐ `aria-busy="true"` présent (accessibilité)
- ☐ `tsc` 0 erreur

---

### TASK-DEV-04 — SwipeActions sur cards mobile L1 (P1)

**Contexte** : sur mobile, les cards devis n'ont pas d'actions swipe. Règle PDF = touch targets 44×44px, SwipeActions sur listes mobiles.

**Fichiers touchés** :
- `frontend/src/pages/devis/DevisListPage.tsx`

**Implémentation** :

```tsx
import { SwipeActions } from '@/components/ui/SwipeActions'

// Dans la vue mobile cards, wrapper chaque card :
<SwipeActions
  key={devis.id}
  leftActions={[
    {
      label: 'Dupliquer',
      icon: <Copy className="w-5 h-5" />,
      color: 'bg-blue-600',
      onAction: () => handleDuplicate(devis.id),
    },
  ]}
  rightActions={[
    {
      label: 'Annuler',
      icon: <X className="w-5 h-5" />,
      color: 'bg-red-600',
      onAction: () => handleCancel(devis.id),
      disabled: !['draft', 'sent'].includes(devis.status),
    },
  ]}
>
  <div className="card" onClick={() => navigate(...)}>
    {/* contenu card existant */}
  </div>
</SwipeActions>
```

**Critères done** :
- ☐ SwipeActions sur toutes les cards mobile (vue `md:hidden`)
- ☐ Action gauche : Dupliquer (bleu)
- ☐ Action droite : Annuler (rouge, désactivée si statut hors [draft, sent])
- ☐ Touch targets ≥ 44px sur les zones d'action
- ☐ `tsc` 0 erreur

---

### TASK-DEV-05 — Éclater DevisDetailPage 717 lignes en composants (P1)

**Contexte** : `DevisDetailPage.tsx` fait 717 lignes — tout dans un seul fichier. Règle = fonctions < 40 lignes, 1 responsabilité.

**Découpe proposée** :

| Composant | Contenu actuel | Lignes estimées |
|-----------|---------------|-----------------|
| `DevisActionsBar.tsx` | Barre d'actions (Envoyer/Accepter/Refuser/Convertir/Dupliquer/Annuler/PDF) | ~120L |
| `DevisInfosCard.tsx` | Bloc infos (référence, client, dates, lieu, statut, totaux, caution) | ~80L |
| `DevisLignesTable.tsx` | Tableau lignes (produit, qté, prix, sous-total, TVA, total) | ~80L |
| `DevisSignatureSection.tsx` | Section signature électronique + `SignaturePad` | ~60L |
| `DevisVersionsList.tsx` | Onglet versions avec diff visuel | ~80L |
| `DevisNegotiationSummary.tsx` | Résumé 3 derniers messages négociation | ~40L |
| `DevisDetailPage.tsx` (résidu) | Orchestration + tabs Détails/Versions | < 150L |

**Fichiers touchés** :
- `frontend/src/pages/devis/DevisDetailPage.tsx` — réduit à < 150L
- `frontend/src/pages/devis/components/DevisActionsBar.tsx` — nouveau
- `frontend/src/pages/devis/components/DevisInfosCard.tsx` — nouveau
- `frontend/src/pages/devis/components/DevisLignesTable.tsx` — nouveau
- `frontend/src/pages/devis/components/DevisSignatureSection.tsx` — nouveau
- `frontend/src/pages/devis/components/DevisVersionsList.tsx` — nouveau
- `frontend/src/pages/devis/components/DevisNegotiationSummary.tsx` — nouveau
- `frontend/src/pages/devis/components/index.ts` — exports

**Critères done** :
- ☐ `DevisDetailPage.tsx` < 200 lignes
- ☐ 6 composants créés avec types explicites
- ☐ `components/index.ts` exporte tous les composants
- ☐ Comportement fonctionnel identique (aucune régression)
- ☐ `tsc` 0 erreur

---

### TASK-DEV-06 — Skeleton loading dans les sous-pages fiche (P1)

**Contexte** : `DevisModulesPage`, `DevisPhasesPage`, `DevisNegotiationPage` affichent du texte `"Chargement…"`.

**Fichiers touchés** :
- `frontend/src/pages/devis/DevisModulesPage.tsx`
- `frontend/src/pages/devis/DevisPhasesPage.tsx`
- `frontend/src/pages/devis/DevisNegotiationPage.tsx`

**Implémentation** :

```tsx
// Skeleton générique réutilisable — ajouter dans chaque page :
function CardSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2 animate-pulse">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="card flex items-center justify-between">
          <div className="space-y-1.5 flex-1">
            <div className="h-4 bg-dark-700 rounded w-2/3" />
            <div className="h-3 bg-dark-800 rounded w-1/3" />
          </div>
          <div className="flex gap-2">
            <div className="w-7 h-7 bg-dark-700 rounded" />
            <div className="w-7 h-7 bg-dark-700 rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}

// Remplacer :
// if (isLoading) return <div className="p-6 text-center text-dark-400">Chargement…</div>
// → if (isLoading) return <CardSkeleton lines={4} />
```

**Critères done** :
- ☐ Skeleton avec animate-pulse dans les 3 sous-pages
- ☐ `tsc` 0 erreur

---

### TASK-DEV-07 — MoneyInput dans DevisLineEditor (P2)

**Contexte** : `DevisLineEditor` utilise `input type=number step=0.01` pour les prix unitaires — format euros raw, risque de parsing float.

**Fichiers touchés** :
- `frontend/src/pages/devis/components/DevisLineEditor.tsx`

**Implémentation** :

```tsx
import { MoneyInput } from '@/components/ui/MoneyInput'

// Remplacer dans la colonne PU HT :
// <input type="number" step="0.01" ... value={(line.unit_price_cents / 100).toFixed(2)} ... />
// → :
<MoneyInput
  value={line.unit_price_cents}
  onChange={(cents) => handlePriceChangeCents(idx, cents)}
  className="w-24 py-1 text-right text-sm"
/>

// Adapter handlePriceChange → handlePriceChangeCents (reçoit directement des centimes)
const handlePriceChangeCents = (idx: number, cents: number) => {
  onChange(lines.map((l, i) => (i === idx ? { ...l, unit_price_cents: cents } : l)))
}
```

**Critères done** :
- ☐ `MoneyInput` utilisé pour prix unitaire dans `DevisLineEditor`
- ☐ Plus d'input `type=number step=0.01` pour les montants
- ☐ Calcul total et sous-total inchangé
- ☐ `tsc` 0 erreur

---

### TASK-DEV-08 — Migrer DevisCreatePage vers StepperForm UI (P2)

**Contexte** : `DevisCreatePage` utilise un stepper custom avec state `step: 1 | 2 | 3`. Le composant `StepperForm` (`components/ui/StepperForm.tsx`) est le standard du projet.

**Fichiers touchés** :
- `frontend/src/pages/devis/DevisCreatePage.tsx`

**Implémentation** :

```tsx
import { StepperForm } from '@/components/ui/StepperForm'

const STEPS = [
  { id: 'infos', label: 'Informations' },
  { id: 'lignes', label: 'Articles' },
  { id: 'recap', label: 'Récapitulatif' },
]

// Remplacer le state step + boutons Précédent/Suivant custom par :
<StepperForm
  steps={STEPS}
  currentStep={step - 1}     // StepperForm est 0-indexed
  onNext={handleNext}
  onBack={handleBack}
  onSubmit={handleSubmit}
  isSubmitting={createMutation.isPending}
>
  {step === 1 && <DevisInfosStep ... />}
  {step === 2 && <DevisLignesStep ... />}
  {step === 3 && <DevisRecapStep ... />}
</StepperForm>
```

**Note** : nécessite de vérifier l'API exacte de `StepperForm` avant d'implémenter.

**Critères done** :
- ☐ `StepperForm` UI utilisé (pas de stepper custom)
- ☐ 3 étapes fonctionnelles : Infos → Articles → Récapitulatif
- ☐ `cartStore` initialisation lignes préservée
- ☐ `tsc` 0 erreur

---

### TASK-DEV-09 (P1) — URL sync filtres `DevisListPage`

**Problème :** `DevisListPage.tsx:37` — `status` et `search` en `useState` local → perdus au retour depuis une fiche.

```tsx
// routes/_app/devis/index.tsx
export const Route = createFileRoute('/_app/devis/')({
  validateSearch: (search) => ({
    status: (search.status as string) ?? '',
    q: (search.q as string) ?? '',
    page: Number(search.page ?? 1),
  }),
  component: DevisListPage,
})

// Dans DevisListPage :
const search = useSearch({ from: '/_app/devis/' })
const navigate = useNavigate()

const setStatus = (s: string) =>
  navigate({ search: (prev) => ({ ...prev, status: s || undefined, page: 1 }) })
const setQ = (q: string) =>
  navigate({ search: (prev) => ({ ...prev, q: q || undefined, page: 1 }) })
```

**Critères done :**
- ☐ URL `?status=draft&q=dupont&page=2` fonctionne
- ☐ Retour depuis fiche → filtres préservés
- ☐ `tsc` 0 erreur

---

### TASK-DEV-10 (P1) — MoneyInput dans `DevisNegotiationPage`

**Problème :** `DevisNegotiationPage.tsx:120` — `input type="number" step="0.01"` pour saisir la proposition de montant (euros). Anti-pattern fondamental — risque de parsing float + pas de formatage euro.

**Fichier :** `frontend/src/pages/devis/DevisNegotiationPage.tsx`

```tsx
import { MoneyInput } from '@/components/ui/MoneyInput'

// État : stocker en centimes directement
const [proposedCents, setProposedCents] = useState<number>(0)

// Remplacer :
// <input type="number" step="0.01" value={proposedEuros} onChange={...} />
// Par :
<MoneyInput
  value={proposedCents}
  onChange={setProposedCents}
  placeholder="0.00 €"
  className="w-full"
/>

// Adapter la mutation :
// Avant : Math.round(parseFloat(proposedEuros) * 100)
// Après : proposedCents (déjà en centimes)
onSubmit: () => proposalMutation.mutate({ amount_cents: proposedCents })
```

**Critères done :**
- ☐ `MoneyInput` utilisé pour la saisie du montant de proposition
- ☐ Plus d'`input type=number step=0.01`
- ☐ Valeur envoyée en centimes directement
- ☐ `tsc` 0 erreur

---

### TASK-DEV-11 (P2) — `formatCents()` dans `DevisCreatePage`

**Problème :** `DevisCreatePage.tsx:284,290` — affichage montants via `(val / 100).toFixed(2) €` au lieu de `formatCents()`.

```tsx
// Avant :
{((subtotal) / 100).toFixed(2)} €

// Après :
import { formatCents } from '@/utils/money'
{formatCents(subtotal)}
```

Vérifier tous les affichages de montants dans la page et normaliser.

**Critères done :**
- ☐ Aucun `.toFixed(2) €` manuel dans `DevisCreatePage`
- ☐ `formatCents()` utilisé systématiquement

---

### TASK-DEV-12 (P2) — Skeleton loading `DevisDetailPage`

**Problème :** `DevisDetailPage.tsx:128` — texte `"Chargement…"` pendant `isLoading` de la fiche (couvert par TASK-DEV-06 uniquement pour les sous-pages).

```tsx
function DevisDetailSkeleton() {
  return (
    <div className="max-w-3xl mx-auto space-y-5 animate-pulse">
      {/* Header actions */}
      <div className="flex items-center justify-between">
        <div className="h-6 bg-dark-700 rounded w-40" />
        <div className="flex gap-2">
          <div className="h-8 bg-dark-700 rounded w-24" />
          <div className="h-8 bg-dark-700 rounded w-24" />
        </div>
      </div>
      {/* Infos card */}
      <div className="card p-5 space-y-3">
        <div className="h-5 bg-dark-700 rounded w-32" />
        <div className="grid grid-cols-2 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="space-y-1">
              <div className="h-3 bg-dark-700 rounded w-20" />
              <div className="h-4 bg-dark-700 rounded w-32" />
            </div>
          ))}
        </div>
      </div>
      {/* Lignes skeleton */}
      <div className="card p-4 space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="flex gap-4">
            <div className="h-4 bg-dark-700 rounded flex-1" />
            <div className="h-4 bg-dark-700 rounded w-12" />
            <div className="h-4 bg-dark-700 rounded w-20" />
          </div>
        ))}
      </div>
    </div>
  )
}

// Remplacer :
// if (isLoading) return <div className="p-6 text-center text-dark-400">Chargement…</div>
if (isLoading) return <DevisDetailSkeleton />
```

**Critères done :**
- ☐ Skeleton structuré (header + infos card + lignes) avec animate-pulse
- ☐ Aucun texte `"Chargement…"` dans `DevisDetailPage`

---

## Composants partagés identifiés

| Composant | Fichier | Utilisé dans |
|-----------|---------|--------------|
| `DevisLineEditor` | `pages/devis/components/DevisLineEditor.tsx` | `DevisCreatePage` |
| `DevisSendModal` | `pages/devis/components/DevisSendModal.tsx` | `DevisDetailPage` |
| `DevisConvertModal` | `pages/devis/components/DevisConvertModal.tsx` | `DevisDetailPage` |
| `CataloguePickerModal` | `components/catalogue/CataloguePickerModal.tsx` | `DevisLineEditor` |
| `SignaturePad` | `components/ui/SignaturePad.tsx` | `DevisDetailPage` |
| `MoneyInput` | `components/ui/MoneyInput.tsx` | À utiliser dans `DevisLineEditor` (TASK-DEV-07) |
| `StepperForm` | `components/ui/StepperForm.tsx` | À utiliser dans `DevisCreatePage` (TASK-DEV-08) |
| `SwipeActions` | `components/ui/SwipeActions.tsx` | À utiliser dans `DevisListPage` (TASK-DEV-04) |

---

## Endpoints backend (référence)

| Méthode | Path | Description |
|---------|------|-------------|
| GET | `/devis` | Liste paginée (filtres : status, customer_id, date_from, date_to) |
| POST | `/devis` | Créer (statut draft) |
| GET | `/devis/{id}` | Détail complet (lignes + modules + phases + négociations + change_requests) |
| PATCH | `/devis/{id}` | Modifier (seulement draft) |
| POST | `/devis/{id}/send` | draft → sent (snapshot v1) |
| POST | `/devis/{id}/accept` | sent → accepted |
| POST | `/devis/{id}/refuse` | → refused |
| POST | `/devis/{id}/cancel` | → cancelled |
| POST | `/devis/{id}/renew` | expired → draft nouveau |
| POST | `/devis/{id}/convert` | accepted → converted + création réservation |
| GET | `/devis/{id}/versions` | Historique versions (snapshots) |
| POST | `/devis/{id}/negotiation` | Ajouter message négociation |
| GET | `/devis/{id}/modules` | Modules devis |
| POST | `/devis/{id}/modules` | Ajouter module |
| PATCH | `/devis/{id}/modules/{mid}` | Modifier module |
| DELETE | `/devis/{id}/modules/{mid}` | Supprimer module |
| GET | `/devis/{id}/phases` | Phases planning |
| POST | `/devis/{id}/phases` | Ajouter phase |
| PATCH | `/devis/{id}/phases/{pid}` | Modifier phase |
| DELETE | `/devis/{id}/phases/{pid}` | Supprimer phase |
| GET | `/devis/{id}/pdf` | StreamingResponse PDF |
| POST | `/devis/{id}/duplicate` | Clone draft (nouvelle référence) |

---

## Ordre d'implémentation recommandé

```
P0 (bloquant UX/navigation)
  TASK-DEV-01  Corriger VENTES_NAV dans DevisListPage
  TASK-DEV-02  Layout fiche SubNav + unifier navigation

P1 (qualité — à faire avant livraison)
  TASK-DEV-03  Skeleton loading L1
  TASK-DEV-04  SwipeActions mobile L1
  TASK-DEV-05  Éclater DevisDetailPage 717L
  TASK-DEV-06  Skeleton sous-pages fiche

P1 (qualité supplémentaire)
  TASK-DEV-09  URL sync filtres DevisListPage
  TASK-DEV-10  MoneyInput DevisNegotiationPage

P2 (amélioration)
  TASK-DEV-07  MoneyInput dans DevisLineEditor
  TASK-DEV-08  Migrer vers StepperForm UI
  TASK-DEV-11  formatCents() dans DevisCreatePage
  TASK-DEV-12  Skeleton DevisDetailPage
```

---

## Critères done globaux du module

- ☐ Anti-pattern VENTES_NAV éliminé (TASK-DEV-01)
- ☐ Navigation fiche unifiée via layout SubNav (TASK-DEV-02)
- ☐ Skeleton loading sur L1 et sous-pages (TASK-DEV-03 + TASK-DEV-06)
- ☐ SwipeActions mobile sur liste (TASK-DEV-04)
- ☐ `DevisDetailPage` < 200 lignes (TASK-DEV-05)
- ☐ `tsc` 0 erreur sur tout le module
- ☐ `vitest run` — 0 régression

---

## Gaps résolus (historique — ne pas retoucher)

| Gap | Résolution | Date |
|-----|-----------|------|
| PDF devis | `GET /devis/{id}/pdf` — StreamingResponse weasyprint | 2026-02-22 |
| Duplicate devis | `POST /devis/{id}/duplicate` — clone + nouvelle référence | 2026-02-22 |
| Onglet Versions | Implémenté dans `DevisDetailPage` avec diff visuel | 2026-02-22 |
| Signature électronique | `SignaturePad` visible si statut `sent`, stockage base64 | 2026-02-22 |
