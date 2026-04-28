# Module 05 — Factures & Avoirs
# Roadmap L1→L5 — Audit réel 2026-02-25

---

## Périmètre LAYER

| Écran LAYER | Route actuelle | Statut |
|---|---|---|
| Liste factures | `/invoices` | ✅ Partiel — pas SubNav, Spinner loading |
| Nouvelle facture | `/invoices/new` | ✅ Fonctionnel |
| Fiche facture | *(modal)* | ⚠️ Modal sans URL — pas navigable |
| Avoirs / Notes de crédit | `/invoices/$id/avoir` | ✅ Partiel — classes custom hors design system |
| Audit trail facture | `/invoices/$id/audit` | ✅ Existe |
| Cautions / Dépôts | `/invoices/cautions` | ✅ Partiel — sans SubNav |
| Rapport mensuel | `/invoices/rapport-mensuel` | ✅ Partiel — sans SubNav |
| Rapport TVA | `/invoices/tva-report` | ✅ Partiel — sans SubNav |
| Rapprochement | `/invoices/rapprochement` | ✅ Partiel — sans SubNav |

---

## Audit routes actuelles

```
routes/_app/
  invoices.tsx           ← layout <Outlet /> simple — PAS de SubNav
  invoices/
    index.tsx            ← InvoicesPage (liste L1)
    new.tsx              ← InvoiceCreatePage (création L3)
    cautions.tsx         ← CautionsPage (liste dépôts)
    rapport-mensuel.tsx  ← RapportMensuelPage
    tva-report.tsx       ← TvaReportPage
    rapprochement.tsx    ← RapprochementPage
    $id/
      avoir.tsx          ← AvoirsPage (avoirs par facture)
      audit.tsx          ← InvoiceAuditPage
```

**Problème structurel critique** : il n'existe **pas** de `$id/index.tsx` ni de `$id.tsx`.
La fiche facture est une `InvoiceDetailModal` (923L) ouverte depuis la liste.
→ Pas d'URL directe vers une fiche, pas de navigation profonde, pas de lien partageable.

---

## Couverture L1 → L5

### L1 — Liste factures (`InvoicesPage`)

**État actuel :**
- ✅ Pagination (page/total_pages)
- ✅ Filtre statut via `filterStore`
- ✅ Dual view : tableau desktop / cards mobile
- ✅ Bandeau trous de séquence (feature unique et précieuse)
- ✅ `DomainStatusBadge` + colonne Payé/Restant
- ✅ Menu contextuel (Voir, Envoyer, Annuler) avec touch target 44px
- ✅ `ActionError` + `InvoiceSendModal`
- ❌ **Pas de SubNav** — layout `invoices.tsx` = Outlet nu
- ❌ Loading = `<Spinner>` dans `<td>` et `<div>` (pas skeleton)
- ❌ Cards mobile sans `SwipeActions`
- ❌ Pas de search texte (filtre statut uniquement)

### L2 — Fiche facture (`InvoiceDetailModal`)

**État actuel :**
- ✅ Progress bar paiement animée
- ✅ Échéances CGV 40%/60% calculées dynamiquement
- ✅ Formulaire paiement inline (méthode, date, notes)
- ✅ Historique paiements trié
- ✅ Frais supplémentaires DAMAGE/LABOR avec calcul heures
- ✅ Avoirs inline (liste + formulaire création)
- ✅ Lien réservation liée
- ✅ `TimelineAudit` + lien vers audit complet
- ✅ PDF download blob
- ✅ `InvoiceSendModal` (marquer envoyée)
- ❌ **Modal sans URL** — pas de route `$id/index.tsx`
- ❌ 923 lignes — trop volumineuse, gestion d'état dispersée
- ❌ Loading = texte "Chargement..." (pas skeleton)
- ❌ Montants en `input type=number step=0.01` euros — doit être `MoneyInput`
- ❌ Pas de navigation fiche précédente/suivante

### L3 — Création facture (`InvoiceCreatePage`)

**État actuel :**
- ✅ Sélection réservation confirmée avec search inline
- ✅ Feedback réservation sélectionnée (client, dates livraison/retour)
- ✅ Dates émission + échéance (défaut J / J+30)
- ✅ Pattern erreur mutation correct
- ❌ Charge 50 réservations confirmées en mémoire sans pagination — si catalogue large, risque
- ❌ Pas de `StepperForm` (simple, acceptable pour 2 étapes)

### L4 — Pages opérationnelles (Avoirs, Audit, Cautions)

**Avoirs (`AvoirsPage`) :**
- ✅ Liste avoirs avec cards visuelles (hero purple, statut badge)
- ✅ Formulaire création avec validation (motif min 5 chars)
- ✅ Récap facture source + total avoirs
- ✅ Skeleton loading inline (`animate-pulse`)
- ❌ Classes non-standard : `bg-dark-9002`, `text-body`, `text-muted` (pas dans le design system)
- ❌ ArrowLeft → `/invoices` (rompt la navigation si on arrive via URL directe)

**Cautions (`CautionsPage`) :**
- ✅ Liste dépôts avec filtre statut (held/retained/released)
- ✅ Dates encaissement et restitution
- ❌ Sans SubNav persistant — ArrowLeft seulement

**RapportMensuelPage :**
- ✅ Sélecteur année/mois, mini bar chart
- ✅ Données depuis `dashboardApi.getFinances`
- ❌ Sans SubNav persistant

**TvaReportPage :**
- ✅ Rapport TVA par taux pour un mois
- ❌ Pas de TanStack Query (`useState + async fetch` direct) — inconsistant avec le reste
- ❌ Sans SubNav persistant

### L5 — Granularité max

- ❌ Pas de page `/invoices/tresorerie` (planifiée dans LAYER)
- ❌ Pas de page `/invoices/rapprochement` bancaire complète
- ❌ Pas de génération/envoi PDF email (seulement marquer "envoyée")

---

## Tâches d'implémentation

### TASK-FAC-01 — SubNav dans layout principal (P0)

**Problème** : `invoices.tsx` est un Outlet nu. Navigation entre liste, cautions et rapports = via breadcrumb/ArrowLeft seulement.

**Solution** : Ajouter `SubNav` dans le layout avec les 4 destinations de niveau module.

```tsx
// routes/_app/invoices.tsx
import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

const INVOICE_NAV = [
  { label: 'Factures',      href: '/invoices' },
  { label: 'Cautions',      href: '/invoices/cautions' },
  { label: 'Rapport',       href: '/invoices/rapport-mensuel' },
  { label: 'TVA',           href: '/invoices/tva-report' },
]

export const Route = createFileRoute('/_app/invoices')({
  component: () => (
    <div className="space-y-0">
      <SubNav items={INVOICE_NAV} />
      <div className="p-4 md:p-6"><Outlet /></div>
    </div>
  ),
})
```

**Critères done** :
- ☐ SubNav visible sur `/invoices`, `/invoices/cautions`, `/invoices/rapport-mensuel`, `/invoices/tva-report`
- ☐ Onglet actif mis en évidence via `pathname.startsWith(href)`
- ☐ Aucun `ArrowLeft` redondant dans les pages de reporting

---

### TASK-FAC-02 — Transformer modal → page dédiée avec SubNav fiche (P0)

**Problème** : `InvoiceDetailModal` (923L) = pas d'URL directe, pas de lien partageable, navigation profonde impossible. La fiche doit être une page à part entière avec ses propres onglets.

**Solution** : Créer `$id.tsx` comme layout SubNav + `$id/index.tsx` comme fiche principale.

```tsx
// routes/_app/invoices/$id.tsx — layout fiche
import { createFileRoute, Outlet, useParams } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

function InvoiceDetailLayout() {
  const { id } = useParams({ strict: false })
  const FICHE_NAV = [
    { label: 'Détails',  href: `/invoices/${id}` },
    { label: 'Avoirs',   href: `/invoices/${id}/avoir` },
    { label: 'Audit',    href: `/invoices/${id}/audit` },
  ]
  return (
    <div className="space-y-0">
      <SubNav items={FICHE_NAV} />
      <div className="p-4 md:p-6"><Outlet /></div>
    </div>
  )
}

export const Route = createFileRoute('/_app/invoices/$id')({
  component: InvoiceDetailLayout,
})
```

```tsx
// routes/_app/invoices/$id/index.tsx → extrait de InvoiceDetailModal
// Contenu : header, progress bar, CGV 40/60, paiements, charges, avoirs résumé
```

**Impact** : `InvoicesPage` retire le `<InvoiceDetailModal>` et navigue vers la fiche via `navigate({ to: '/invoices/$id', params: { id: String(invoice.id) } })`.

**Critères done** :
- ☐ Route `/invoices/123` accessible directement (URL partageable)
- ☐ SubNav Détails / Avoirs / Audit fonctionnel
- ☐ `InvoiceDetailModal` désactivée ou supprimée de `InvoicesPage`
- ☐ Menu contextuel L1 navigue vers la page (pas modal)
- ☐ Composant résiduel < 300L

---

### TASK-FAC-03 — Skeleton loading L1 (P1)

**Problème** : Loading = `<Spinner>` dans `<td colspan=8>` desktop et `<div>` mobile. Standard projet : skeleton animé.

```tsx
// components skeleton inline dans InvoicesPage

// Desktop
function InvoiceTableSkeleton() {
  return (
    <>
      {[...Array(8)].map((_, i) => (
        <tr key={i} className="border-b border-dark-700">
          <td className="py-3 px-4"><div className="h-4 w-24 bg-dark-800 rounded animate-pulse" /></td>
          <td className="py-3 px-4"><div className="h-4 w-32 bg-dark-800 rounded animate-pulse" /></td>
          <td className="py-3 px-4"><div className="h-4 w-20 bg-dark-800 rounded animate-pulse" /></td>
          <td className="py-3 px-4"><div className="h-4 w-20 bg-dark-800 rounded animate-pulse" /></td>
          <td className="py-3 px-4"><div className="h-5 w-16 bg-dark-800 rounded-full animate-pulse" /></td>
          <td className="py-3 px-4 text-right"><div className="h-4 w-16 bg-dark-800 rounded animate-pulse ml-auto" /></td>
          <td className="py-3 px-4 text-right"><div className="h-4 w-14 bg-dark-800 rounded animate-pulse ml-auto" /></td>
          <td className="py-3 px-4"><div className="h-8 w-8 bg-dark-800 rounded animate-pulse ml-auto" /></td>
        </tr>
      ))}
    </>
  )
}

// Mobile
function InvoiceMobileSkeleton() {
  return (
    <>
      {[...Array(5)].map((_, i) => (
        <div key={i} className="flex items-center justify-between px-4 py-3 border-b border-dark-700">
          <div className="space-y-2 flex-1">
            <div className="flex gap-2">
              <div className="h-4 w-28 bg-dark-800 rounded animate-pulse" />
              <div className="h-4 w-16 bg-dark-800 rounded-full animate-pulse" />
            </div>
            <div className="h-3 w-36 bg-dark-800 rounded animate-pulse" />
            <div className="h-3 w-24 bg-dark-800 rounded animate-pulse" />
          </div>
          <div className="w-8 h-8 bg-dark-800 rounded animate-pulse shrink-0" />
        </div>
      ))}
    </>
  )
}
```

**Critères done** :
- ☐ Skeleton desktop affiché dans `<tbody>` quand `isLoading`
- ☐ Skeleton mobile affiché dans `<div.sm:hidden>` quand `isLoading`
- ☐ Aucun `<Spinner>` dans la liste

---

### TASK-FAC-04 — SwipeActions mobile L1 (P1)

**Problème** : Cards mobiles sans gestes swipe. Standard projet défini.

```tsx
// Dans InvoicesPage, remplacer le div card mobile par SwipeActions
import { SwipeActions } from '@/components/ui/SwipeActions'

// Pour chaque invoice dans vue mobile :
<SwipeActions
  key={invoice.id}
  leftAction={invoice.status !== 'paid' && invoice.status !== 'cancelled'
    ? { label: 'Payer', icon: <CreditCard className="w-5 h-5" />, color: 'bg-green-600',
        onAction: () => navigate({ to: '/invoices/$id', params: { id: String(invoice.id) } }) }
    : undefined
  }
  rightAction={invoice.status !== 'paid' && invoice.status !== 'cancelled'
    ? { label: 'Annuler', icon: <XCircle className="w-5 h-5" />, color: 'bg-red-600',
        onAction: () => cancelMutation.mutate(invoice.id) }
    : undefined
  }
>
  {/* card content existant */}
</SwipeActions>
```

**Critères done** :
- ☐ Swipe gauche → naviguer vers fiche (action Payer)
- ☐ Swipe droit → annuler (si statut compatible)
- ☐ Touch targets ≥ 44px respectés

---

### TASK-FAC-05 — Découper `InvoiceDetailModal` en composants (P1)

**Contexte** : 923L dans un seul fichier avec 8 blocs distincts. Après TASK-FAC-02 (transformation en page), il faut découper les sous-blocs.

**Découpe proposée :**

| Composant | Lignes estimées | Contenu |
|---|---|---|
| `InvoiceHeader.tsx` | ~50L | Numéro, statut, actions PDF/Envoyer/Annuler |
| `InvoicePaymentSection.tsx` | ~120L | Progress bar + CGV 40/60 + historique paiements |
| `InvoicePaymentForm.tsx` | ~80L | Formulaire enregistrement paiement |
| `InvoiceChargesSection.tsx` | ~150L | Liste charges + formulaire DAMAGE/LABOR |
| `InvoiceCreditNotesSummary.tsx` | ~60L | Résumé avoirs dans fiche (distinct de AvoirsPage) |
| `InvoiceTimeline.tsx` | ~50L | Wrapper `TimelineAudit` avec entrées facture |
| Résidu `index.tsx` | <200L | Assemblage + appels queries |

**Critères done** :
- ☐ Composant résiduel fiche < 200L
- ☐ Chaque composant < 150L
- ☐ `useInvoiceDetail`, `useInvoicePayments` appelés au niveau page, props passées en bas

---

### TASK-FAC-06 — MoneyInput dans formulaires paiement et charges (P2)

**Problème** : Formulaires de paiement et de charges utilisent `input type=number step=0.01` en euros. Standard projet = `MoneyInput` (centimes).

**Champs concernés** :
- `paymentAmount` dans formulaire paiement → `MoneyInput` + `paymentAmountCents` (centimes)
- `chargeAmountEuros` dans formulaire charge DAMAGE → `MoneyInput` + `chargeAmountCents`

```tsx
// Avant
const [paymentAmount, setPaymentAmount] = useState('')
// ...
const cents = Math.round(parseFloat(paymentAmount) * 100)

// Après
const [paymentAmountCents, setPaymentAmountCents] = useState(0)
// ...
// cents = paymentAmountCents (directement)
<MoneyInput value={paymentAmountCents} onChange={setPaymentAmountCents} />
```

**Critères done** :
- ☐ `MoneyInput` utilisé pour tous les montants editables de la fiche facture
- ☐ Conversion euros/centimes supprimée

---

### TASK-FAC-07 — Normaliser design system dans `AvoirsPage` (P2)

**Problème** : `AvoirsPage` utilise des classes non-standard (`bg-dark-9002`, `text-body`, `text-muted`) absentes du design system Tailwind configuré.

**Corrections** :

| Classe actuelle | Remplacement |
|---|---|
| `bg-dark-9002` | `bg-dark-900` |
| `text-body` | *(retirer — default)* |
| `text-muted` | `text-dark-400` |
| `text-accent` | `text-primary-500` |
| `bg-accent` | `bg-primary-600` |
| `focus:ring-accent` | `focus:ring-primary-500` |

**Critères done** :
- ☐ Aucune classe `*-9002`, `text-body`, `text-muted`, `*-accent` dans `AvoirsPage`
- ☐ Rendu visuel identique avec classes standard

---

### TASK-FAC-08 — Migrer TvaReportPage vers TanStack Query (P2)

**Problème** : `TvaReportPage` utilise `useState + async fetch` manuel au lieu de TanStack Query. Inconsistance avec le reste du projet.

```tsx
// Avant (useState + fetch)
const [report, setReport] = useState<TvaReportResponse | null>(null)
const [loading, setLoading] = useState(false)
const fetchReport = async () => { setLoading(true); ... }

// Après (TanStack Query)
const { data: report, isLoading, error, refetch } = useQuery({
  queryKey: ['tva-report', month],
  queryFn: () => invoicesApi.getTvaReport(month),
  enabled: false, // déclenché manuellement via refetch()
  staleTime: 5 * 60_000,
})
```

**Critères done** :
- ☐ `TvaReportPage` utilise `useQuery` de TanStack Query
- ☐ Bouton "Générer" appelle `refetch()`
- ☐ Gestion d'erreur via `error` Query (pas state local)

---

### TASK-FAC-09 — Normaliser design system dans CautionsPage et RapprochementPage (P2)

**Problème** : TASK-FAC-07 couvre `AvoirsPage`, mais `CautionsPage` et `RapprochementPage` contiennent
les mêmes classes non-standard. Elles doivent être normalisées également.

**Classes non-standard identifiées** :

| Fichier | Ligne | Classe actuelle | Remplacement |
|---------|-------|----------------|--------------|
| `CautionsPage.tsx` | L95 | `card2` | `card` (ou supprimer si identique) |
| `CautionsPage.tsx` | L95 | `focus:ring-accent` | `focus:ring-primary-500` |
| `CautionsPage.tsx` | L139, L152 | `bg-dark-9002` | `bg-dark-900` |
| `CautionsPage.tsx` | L31, L98, L109, L114 | `text-muted` | `text-dark-400` |
| `RapprochementPage.tsx` | L69, L199 | `bg-dark-9002` | `bg-dark-900` |
| `RapprochementPage.tsx` | L80, L122 | `text-muted` | `text-dark-400` |
| `RapprochementPage.tsx` | L89, L101, L116, L128 | `focus:ring-accent` | `focus:ring-primary-500` |
| `AvoirsPage.tsx` | L62, L74, L85 | `text-muted` | `text-dark-400` |
| `AvoirsPage.tsx` | L69, L79, L91 | `focus:ring-accent` | `focus:ring-primary-500` |

> Note : `AvoirsPage` est partiellement couverte par TASK-FAC-07 pour `bg-dark-9002` et `text-body`.
> Cette tâche étend la couverture aux occurrences restantes de `text-muted` et `focus:ring-accent`
> dans les 3 pages du module.

**Critères done** :
- ☐ Aucune classe `bg-dark-9002`, `text-muted`, `focus:ring-accent`, `card2` dans `CautionsPage`, `RapprochementPage`, `AvoirsPage`
- ☐ Rendu visuel identique avec classes standard

---

### TASK-FAC-10 — Ajouter `onSuccess` aux mutations InvoicesPage (P2)

**Problème** : Plusieurs mutations dans `InvoicesPage` n'ont que `onError` sans `onSuccess`.
Les données ne sont pas invalidées après mutation → la liste reste périmée jusqu'au prochain refetch.

**Mutations concernées** :
- L92 : mutation envoi facture → après succès, invalider `['invoices']`
- L122 : mutation annulation → après succès, invalider `['invoices']` + fermer menu contextuel
- L133 : mutation autre action → après succès, invalider `['invoices']`

**Implémentation** :

```tsx
// Avant (incomplet) :
useMutation({
  mutationFn: (id: number) => invoicesApi.sendInvoice(id),
  onError: (err) => showError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Erreur envoi'),
})

// Après (complet) :
useMutation({
  mutationFn: (id: number) => invoicesApi.sendInvoice(id),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['invoices'] })
    showSuccess('Facture marquée comme envoyée')
  },
  onError: (err) => showError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Erreur envoi'),
})
```

**Critères done** :
- ☐ Les 3 mutations de `InvoicesPage` ont un `onSuccess` invalidant `['invoices']`
- ☐ Feedback utilisateur sur succès (toast ou état local)
- ☐ `tsc` 0 erreur

---

### TASK-FAC-11 — URL sync filtres L1 (P1)

**Problème** : `InvoicesPage` gère les filtres `status` (via `filterStore` Zustand) mais le
filtre texte de recherche et la pagination ne sont pas persistés dans l'URL. Retour depuis fiche → perd
la position dans la liste.

**Observation** : L'usage de `filterStore` (Zustand) est un pattern de persistance non-URL — il persiste
entre les pages mais ne permet pas les URLs partageables ni la restauration via le bouton Retour.

**Solution** : Ajouter `validateSearch` sur la route `invoices/index.tsx` pour persister `page`, `q`
et `status` dans l'URL.

```tsx
// routes/_app/invoices/index.tsx
export const Route = createFileRoute('/_app/invoices/')({
  validateSearch: (search) => ({
    page:   typeof search.page   === 'number' ? search.page   : 1,
    q:      typeof search.q      === 'string' ? search.q      : '',
    status: typeof search.status === 'string' ? search.status : 'all',
  }),
  component: InvoicesPage,
})
```

```tsx
// InvoicesPage.tsx — remplacer filterStore.status par searchParam
const search   = useSearch({ from: '/_app/invoices/' })
const navigate = useNavigate()
const status   = search.status ?? 'all'
const page     = search.page   ?? 1
const query    = search.q      ?? ''
```

**Critères done** :
- ☐ `validateSearch` sur route `/invoices/`
- ☐ Filtres page/q/status dans l'URL
- ☐ Retour depuis fiche → filtres restaurés
- ☐ URL partageable avec filtres pré-appliqués

---

## Endpoints backend

```
GET    /api/v1/invoices/                  → liste paginée + filtre statut
POST   /api/v1/invoices/                  → créer (reservation_id, dates)
GET    /api/v1/invoices/{id}              → détail
POST   /api/v1/invoices/{id}/cancel       → annuler
POST   /api/v1/invoices/{id}/mark-sent    → marquer envoyée
POST   /api/v1/invoices/{id}/payments     → enregistrer paiement
GET    /api/v1/invoices/{id}/payments     → liste paiements
POST   /api/v1/invoices/{id}/charges      → ajouter frais
GET    /api/v1/invoices/{id}/credit-notes → liste avoirs
POST   /api/v1/invoices/{id}/credit-notes → créer avoir
GET    /api/v1/invoices/{id}/pdf          → PDF blob
GET    /api/v1/invoices/sequence-gaps     → trous séquence (year param)
GET    /api/v1/invoices/tva-report        → rapport TVA (month param)
GET    /api/v1/dashboard/finances         → rapport mensuel (year param)
GET    /api/v1/deposits/                  → liste cautions/dépôts
```

---

## Ordre d'implémentation

### P0 — Bloquants navigation (bloquer toute feature si non fait)
1. **TASK-FAC-01** : SubNav layout `/invoices` → cohérence navigation
2. **TASK-FAC-02** : Modal → Page dédiée `$id/index.tsx` → URL navigable, SubNav fiche

### P1 — Qualité UX obligatoire
3. **TASK-FAC-03** : Skeleton L1 (desktop + mobile)
4. **TASK-FAC-04** : SwipeActions mobile L1
5. **TASK-FAC-05** : Découpe `InvoiceDetailModal` en composants (après TASK-FAC-02)

### P1 — UX et cohérence
6. **TASK-FAC-11** : URL sync filtres L1 (page/q/status)

### P2 — Normalisation et cohérence
7. **TASK-FAC-06** : MoneyInput dans paiements/charges
8. **TASK-FAC-07** : Design system dans AvoirsPage (bg-dark-9002, text-body)
9. **TASK-FAC-08** : TanStack Query dans TvaReportPage
10. **TASK-FAC-09** : Design system dans CautionsPage + RapprochementPage (text-muted, focus:ring-accent, bg-dark-9002, card2)
11. **TASK-FAC-10** : Mutations `onSuccess` manquants dans InvoicesPage

---

## Critères done module complet

- ☐ SubNav visible et fonctionnel dans layout `/invoices`
- ☐ Fiche facture accessible via URL directe `/invoices/{id}`
- ☐ SubNav fiche [Détails | Avoirs | Audit] fonctionnel
- ☐ Skeleton loading sur L1 (liste) et L2 (fiche)
- ☐ SwipeActions mobiles sur liste
- ☐ Tous les montants éditables via `MoneyInput`
- ☐ Design system cohérent (zéro classe hors design system dans tout le module)
- ☐ TvaReportPage sur TanStack Query
- ☐ InvoiceDetailModal retirée ou inactivée
- ☐ URL sync filtres L1 fonctionnel
- ☐ Toutes les mutations ont `onSuccess` invalidant les queries
- ☐ Aucun composant > 300L
