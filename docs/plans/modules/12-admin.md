# Module 12 — Administration

> Roadmap L1→L5 — Audit réel 2026-02-25 | Source : fichiers lus + grep codebase

---

## État actuel — Synthèse audit

### Ce qui fonctionne bien
- 7 pages admin complètes : `UsersPage`, `SessionsPage`, `ApiKeysPage`, `FeatureFlagsPage`, `AuditLogsPage`, `VpnPage`, `AdminSettingsPage`
- CRUD utilisateurs avec modals (`UserFormModal`, `UserDeleteModal`, `UserInviteModal`)
- Sessions : révocation individuelle + tout révoquer
- API Keys : création, révocation, affichage one-shot du token
- Feature Flags : toggle par environnement (desktop + mobile)
- Audit logs : filtres date/user/action, export
- VPN (WireGuard) : peers, pools, statut temps réel
- Paramètres tenant : formulaire éditable (TVA, SMTP, branding)

### Anti-patterns identifiés

| ID | Fichier | Problème | Priorité |
|----|---------|----------|----------|
| AP-01 | `routes/_app/admin/*.tsx` | Pas de fichier `_app/admin.tsx` — layout parent absent → **pas de SubNav module** | P0 |
| AP-02 | `UsersPage.tsx:178,255` | Loading = texte `"Chargement..."` (desktop ET mobile) | P1 |
| AP-03 | `SessionsPage.tsx:161` | Loading = texte `"Chargement..."` | P1 |
| AP-04 | `AuditLogsPage.tsx:177,247` | Loading = texte `"Chargement..."` (desktop ET mobile) | P1 |
| AP-05 | `ApiKeysPage.tsx:137,224` | Loading = `Loader2` + texte `"Chargement..."` | P1 |
| AP-06 | `FeatureFlagsPage.tsx:140,218` | Loading = `Loader2` + texte `"Chargement..."` | P1 |
| AP-07 | `AdminSettingsPage.tsx:88,208,257` | Loading = `Loader2` + texte `"Chargement..."` | P1 |
| AP-08 | `VpnPage.tsx:505,747,763` | Loading = texte `"Chargement du statut..."` | P1 |
| AP-09 | `AdminSettingsPage.tsx` multiple | Classes `text-body`, `text-accent`, `text-muted`, `text-muted2` | P2 |
| AP-10 | `ApiKeysPage.tsx` multiple | Classes `text-body` | P2 |
| AP-11 | `VpnPage.tsx` multiple | Classes `text-body` | P2 |
| AP-12 | `FeatureFlagsPage.tsx` multiple | Classes `text-body` | P2 |
| AP-13 | `UserFormModal.tsx:200,202` | Classes `text-accent`, `text-body` | P2 |
| AP-14 | `UserDeleteModal.tsx:47` | Classe `text-body` | P2 |

---

## Tâches L1→L5

### TASK-ADM-01 (P0) — Créer layout parent `_app/admin.tsx` avec SubNav

**Problème** : Il n'existe pas de fichier `frontend/src/routes/_app/admin.tsx`. Sans ce fichier layout
parent, les pages admin n'ont pas de SubNav commun.

**Fichier à créer** : `frontend/src/routes/_app/admin.tsx`

```tsx
// routes/_app/admin.tsx
import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

const ADMIN_NAV = [
  { label: 'Utilisateurs', href: '/admin/users' },
  { label: 'Sessions', href: '/admin/sessions' },
  { label: 'Clés API', href: '/admin/api-keys' },
  { label: 'Fonctionnalités', href: '/admin/features' },
  { label: 'Audit', href: '/admin/audit-logs' },
  { label: 'VPN', href: '/admin/vpn' },
  { label: 'Paramètres', href: '/admin/settings' },
]

export const Route = createFileRoute('/_app/admin')({
  component: () => (
    <div className="space-y-0">
      <SubNav items={ADMIN_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  ),
})
```

> En TanStack Router v1, la création de `_app/admin.tsx` avec `createFileRoute('/_app/admin')`
> déclenche automatiquement la reconnaissance des routes filles `/_app/admin/*` comme enfants.
> Vérifier que `routeTree.gen.ts` est regénéré (`npm run build` ou relancer le serveur Vite).

> Après ajout du wrapper, supprimer le padding `p-4 md:p-6` redondant dans chaque page admin
> (UsersPage, SessionsPage, etc.) pour éviter le double padding.

**Critères done** :
- ☐ `routes/_app/admin.tsx` créé et exporté
- ☐ SubNav visible avec 7 onglets
- ☐ `routeTree.gen.ts` regénéré (aucune erreur)
- ☐ `tsc --noEmit` 0 erreur
- ☐ 1582 Vitest pass

---

### TASK-ADM-02 (P1) — Skeleton loading UsersPage

**Problème** : `UsersPage.tsx:178` (desktop) et `:255` (mobile) affichent `"Chargement..."` texte.

**Fichier à modifier** : `frontend/src/pages/admin/UsersPage.tsx`

```tsx
function UserRowSkeleton() {
  return (
    <tr className="animate-pulse border-b border-dark-700/50">
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-dark-700 rounded-full shrink-0" />
          <div className="space-y-1">
            <div className="h-3.5 bg-dark-700 rounded w-32" />
            <div className="h-3 bg-dark-700 rounded w-44" />
          </div>
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="h-5 bg-dark-700 rounded-full w-16" />
      </td>
      <td className="px-4 py-3">
        <div className="h-5 bg-dark-700 rounded-full w-14" />
      </td>
      <td className="px-4 py-3">
        <div className="h-3 bg-dark-700 rounded w-20" />
      </td>
      <td className="px-4 py-3" />
    </tr>
  )
}

function UserCardSkeleton() {
  return (
    <div className="card animate-pulse">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-dark-700 rounded-full shrink-0" />
        <div className="flex-1 space-y-1.5">
          <div className="h-3.5 bg-dark-700 rounded w-36" />
          <div className="h-3 bg-dark-700 rounded w-48" />
        </div>
        <div className="h-5 bg-dark-700 rounded-full w-14" />
      </div>
    </div>
  )
}

// Desktop : remplacer texte par 8 squelettes dans tbody
// Mobile : remplacer texte par 6 cards squelettes
```

**Critères done** :
- ☐ Desktop : skeleton 8 lignes tableau (avatar + nom/email + rôle + statut)
- ☐ Mobile : skeleton 6 cards
- ☐ Aucun texte `"Chargement..."` dans `UsersPage`

---

### TASK-ADM-03 (P1) — Skeleton loading SessionsPage

**Problème** : `SessionsPage.tsx:161` affiche `"Chargement..."` texte.

**Fichier à modifier** : `frontend/src/pages/admin/SessionsPage.tsx`

```tsx
function SessionRowSkeleton() {
  return (
    <tr className="animate-pulse border-b border-dark-700/50">
      <td className="px-4 py-3">
        <div className="h-3.5 bg-dark-700 rounded w-36" />
      </td>
      <td className="px-4 py-3">
        <div className="h-3.5 bg-dark-700 rounded w-24" />
      </td>
      <td className="px-4 py-3">
        <div className="h-3 bg-dark-700 rounded w-20" />
      </td>
      <td className="px-4 py-3">
        <div className="h-5 bg-dark-700 rounded-full w-12" />
      </td>
      <td className="px-4 py-3" />
    </tr>
  )
}

// Remplacer le texte "Chargement..." par :
{Array.from({ length: 5 }).map((_, i) => <SessionRowSkeleton key={i} />)}
```

**Critères done** :
- ☐ Skeleton 5 lignes (user + IP + date + statut actuelle)
- ☐ Aucun texte `"Chargement..."` dans `SessionsPage`

---

### TASK-ADM-04 (P1) — Skeleton loading AuditLogsPage

**Problème** : `AuditLogsPage.tsx:177` (desktop) et `:247` (mobile) affichent `"Chargement..."`.

**Fichier à modifier** : `frontend/src/pages/admin/AuditLogsPage.tsx`

```tsx
function AuditRowSkeleton() {
  return (
    <tr className="animate-pulse border-b border-dark-700/50">
      <td className="px-4 py-3">
        <div className="h-3 bg-dark-700 rounded w-32" />
      </td>
      <td className="px-4 py-3">
        <div className="h-3.5 bg-dark-700 rounded w-28" />
      </td>
      <td className="px-4 py-3">
        <div className="h-5 bg-dark-700 rounded-full w-20" />
      </td>
      <td className="px-4 py-3">
        <div className="h-3 bg-dark-700 rounded w-40" />
      </td>
    </tr>
  )
}

function AuditCardSkeleton() {
  return (
    <div className="card animate-pulse space-y-2">
      <div className="flex items-center justify-between">
        <div className="h-3.5 bg-dark-700 rounded w-28" />
        <div className="h-5 bg-dark-700 rounded-full w-16" />
      </div>
      <div className="h-3 bg-dark-700 rounded w-48" />
      <div className="h-3 bg-dark-700 rounded w-24" />
    </div>
  )
}

// Desktop : 10 lignes tableau; Mobile : 6 cards
```

**Critères done** :
- ☐ Desktop : skeleton 10 lignes (date + user + action + ressource)
- ☐ Mobile : skeleton 6 cards
- ☐ Aucun texte `"Chargement..."` dans `AuditLogsPage`

---

### TASK-ADM-05 (P1) — Skeleton loading ApiKeysPage

**Problème** : `ApiKeysPage.tsx` lignes 137–138 et 224–225 : `Loader2` + texte `"Chargement..."`.

**Fichier à modifier** : `frontend/src/pages/admin/ApiKeysPage.tsx`

```tsx
function ApiKeyRowSkeleton() {
  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b border-dark-700 animate-pulse">
      <div className="flex-1 space-y-1.5">
        <div className="h-3.5 bg-dark-700 rounded w-40" />
        <div className="h-3 bg-dark-700 rounded w-24 font-mono" />
      </div>
      <div className="h-5 bg-dark-700 rounded-full w-14" />
      <div className="h-3 bg-dark-700 rounded w-20" />
      <div className="w-8 h-8 bg-dark-700 rounded" />
    </div>
  )
}

// Remplacer les 2 occurrences (desktop + mobile) :
{Array.from({ length: 4 }).map((_, i) => <ApiKeyRowSkeleton key={i} />)}
```

**Critères done** :
- ☐ Skeleton 4 lignes (nom + préfixe + statut + date)
- ☐ Aucun `Loader2` ni texte `"Chargement..."` au chargement initial

---

### TASK-ADM-06 (P1) — Skeleton loading FeatureFlagsPage

**Problème** : `FeatureFlagsPage.tsx` lignes 140–141 et 218–219 : `Loader2` + texte `"Chargement..."`.

**Fichier à modifier** : `frontend/src/pages/admin/FeatureFlagsPage.tsx`

```tsx
function FlagRowSkeleton() {
  return (
    <div className="flex items-center justify-between px-4 py-3 border-b border-dark-700 animate-pulse">
      <div className="space-y-1.5">
        <div className="h-3.5 bg-dark-700 rounded w-36 font-mono" />
        <div className="h-3 bg-dark-700 rounded w-56" />
      </div>
      <div className="w-8 h-8 bg-dark-700 rounded-full" />
    </div>
  )
}

// Remplacer les 2 occurrences (desktop + mobile) :
{Array.from({ length: 5 }).map((_, i) => <FlagRowSkeleton key={i} />)}
```

**Critères done** :
- ☐ Skeleton 5 lignes (nom flag + description + toggle)
- ☐ Aucun `Loader2` ni texte `"Chargement..."` au chargement initial

---

### TASK-ADM-07 (P1) — Skeleton loading AdminSettingsPage

**Problème** : `AdminSettingsPage.tsx` : 3 zones de chargement avec `Loader2` + `"Chargement..."` :
- Ligne 88 : chargement du formulaire principal
- Ligne 208 : pendant la sauvegarde (ce cas est un `isPending` sur mutation — différent du loading)
- Ligne 257 : chargement des feature flags dans la section Fonctionnalités

**Stratégie** : seules les zones ligne 88 et 257 sont des `isLoading` initiaux → skeleton.
La ligne 208 est un `isPending` de mutation → `Loader2` dans le bouton = acceptable, laisser.

**Fichier à modifier** : `frontend/src/pages/admin/AdminSettingsPage.tsx`

```tsx
function SettingsSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Card Informations */}
      <div className="card p-5 space-y-4">
        <div className="h-3 bg-dark-700 rounded w-48" />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="space-y-1.5">
              <div className="h-3 bg-dark-700 rounded w-24" />
              <div className="h-9 bg-dark-700 rounded" />
            </div>
          ))}
        </div>
      </div>
      {/* Card SMTP */}
      <div className="card p-5 space-y-3">
        <div className="h-3 bg-dark-700 rounded w-32" />
        <div className="h-3 bg-dark-700 rounded w-64" />
      </div>
    </div>
  )
}

// Section Feature Flags (ligne 257) :
function FlagsSectionSkeleton() {
  return (
    <div className="space-y-2 animate-pulse">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="flex items-center justify-between py-2">
          <div className="h-3.5 bg-dark-700 rounded w-36" />
          <div className="w-8 h-8 bg-dark-700 rounded-full" />
        </div>
      ))}
    </div>
  )
}
```

**Critères done** :
- ☐ Skeleton structuré pour le formulaire principal
- ☐ Skeleton inline pour la section Feature Flags
- ☐ `Loader2` bouton sauvegarde (ligne 208) conservé (mutation isPending = correct)

---

### TASK-ADM-08 (P1) — Skeleton loading VpnPage

**Problème** : `VpnPage.tsx` lignes 505 (`"Chargement du statut..."`), 747 et 763 (`"Chargement..."`).

**Fichier à modifier** : `frontend/src/pages/admin/VpnPage.tsx`

```tsx
function VpnStatusSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 animate-pulse">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="card p-5 space-y-2">
          <div className="h-3 bg-dark-700 rounded w-20" />
          <div className="h-7 bg-dark-700 rounded w-12" />
        </div>
      ))}
    </div>
  )
}

function VpnPeerRowSkeleton() {
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-dark-700 animate-pulse">
      <div className="w-2 h-2 rounded-full bg-dark-700 shrink-0" />
      <div className="flex-1 space-y-1">
        <div className="h-3.5 bg-dark-700 rounded w-32" />
        <div className="h-3 bg-dark-700 rounded w-24 font-mono" />
      </div>
      <div className="h-5 bg-dark-700 rounded-full w-14" />
    </div>
  )
}

// Ligne 505 : remplacer par <VpnStatusSkeleton />
// Ligne 747/763 : remplacer par 4 <VpnPeerRowSkeleton />
```

**Critères done** :
- ☐ Skeleton statut (3 KPI cards)
- ☐ Skeleton liste peers (4 lignes)
- ☐ Aucun texte `"Chargement..."` dans `VpnPage`

---

### TASK-ADM-09 (P2) — Normaliser classes design system module Admin

**Problème** : Nombreuses classes non-standard dans le module admin.

**Correspondances** :

| Classe actuelle | Remplacement |
|----------------|--------------|
| `text-body` | *(supprimer)* — héritage |
| `text-accent` | `text-primary-400` |
| `text-muted` | `text-dark-400` |
| `text-muted2` | `text-dark-400` |
| `focus:ring-accent` | `focus:ring-primary-500` |

**Fichiers et volumes** :
- `AdminSettingsPage.tsx` : ~15 occurrences (`text-body` ×8, `text-accent` ×3, `text-muted` ×3, `text-muted2` ×4)
- `ApiKeysPage.tsx` : ~8 occurrences `text-body`
- `VpnPage.tsx` : ~8 occurrences `text-body`
- `FeatureFlagsPage.tsx` : ~4 occurrences `text-body`
- `UserFormModal.tsx` : 2 occurrences (`text-accent`, `text-body`)
- `UserDeleteModal.tsx` : 1 occurrence `text-body`

**Méthode** : traiter fichier par fichier avec grep + replace, vérifier rendu après chaque.

**Critères done** :
- ☐ Aucune occurrence de `text-body`, `text-accent`, `text-muted`, `text-muted2` dans le module
- ☐ `tsc --noEmit` 0 erreur

---

## Couverture LAYER.html — Mapping final

| Écran LAYER | Route | Composant | Backend | Statut cible |
|------------|-------|-----------|---------|--------------|
| `s-admin-users` | `/admin/users` | `UsersPage` | `GET /admin/users` | ✅ → skeleton |
| `s-admin-sessions` | `/admin/sessions` | `SessionsPage` | `GET /auth/sessions` | ✅ → skeleton |
| `s-admin-api-keys` | `/admin/api-keys` | `ApiKeysPage` | `GET /admin/api-keys` | ✅ → skeleton |
| `s-admin-features` | `/admin/features` | `FeatureFlagsPage` | `GET /admin/feature-flags` | ✅ → skeleton |
| `s-admin-audit` | `/admin/audit-logs` | `AuditLogsPage` | `GET /admin/audit` | ✅ → skeleton |
| `s-admin-vpn` | `/admin/vpn` | `VpnPage` | `GET /vpn/*` | ✅ → skeleton |
| `s-parametres` | `/admin/settings` | `AdminSettingsPage` | `GET/PATCH /admin/settings` | ✅ → skeleton |
| `s-admin-invite` | — | `UserInviteModal` ✅ | `POST /admin/users/invite` | ✅ implémenté |

---

## Ordre d'exécution recommandé

```
TASK-ADM-01  ← P0 Layout parent + SubNav (bloquant pour toutes les pages)
TASK-ADM-02  ← P1 Skeleton UsersPage
TASK-ADM-03  ← P1 Skeleton SessionsPage
TASK-ADM-04  ← P1 Skeleton AuditLogsPage
TASK-ADM-05  ← P1 Skeleton ApiKeysPage
TASK-ADM-06  ← P1 Skeleton FeatureFlagsPage
TASK-ADM-07  ← P1 Skeleton AdminSettingsPage
TASK-ADM-08  ← P1 Skeleton VpnPage
TASK-ADM-09  ← P2 Design system (toutes pages)
```

---

## Référence — Fichiers impactés

| Fichier | Action |
|---------|--------|
| `routes/_app/admin.tsx` | **Créer** — layout parent + SubNav |
| `pages/admin/UsersPage.tsx` | Modifier — skeleton |
| `pages/admin/SessionsPage.tsx` | Modifier — skeleton |
| `pages/admin/AuditLogsPage.tsx` | Modifier — skeleton |
| `pages/admin/ApiKeysPage.tsx` | Modifier — skeleton, design system |
| `pages/admin/FeatureFlagsPage.tsx` | Modifier — skeleton, design system |
| `pages/admin/AdminSettingsPage.tsx` | Modifier — skeleton, design system |
| `pages/admin/VpnPage.tsx` | Modifier — skeleton, design system |
| `pages/admin/components/UserFormModal.tsx` | Modifier — design system |
| `pages/admin/components/UserDeleteModal.tsx` | Modifier — design system |
