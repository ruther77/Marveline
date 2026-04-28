# Module 13 — Authentification & Profil

> Roadmap L1→L5 — Audit réel 2026-02-25 | Source : fichiers lus + grep codebase

---

## État actuel — Synthèse audit

### Ce qui fonctionne bien
- Pages auth complètes : `LoginPage`, `ForgotPasswordPage`, `ResetPasswordPage`, `MFAVerifyPage`, `OAuthCallbackPage` — formulaires avec validation, `Loader2` sur boutons submit (isPending mutation = correct) ✅
- `ProfilePage` : formulaire édition nom/email/téléphone + `PATCH /users/me` ✅
- `SecurityPage` : changement mot de passe (zod + react-hook-form), sessions actives avec révocation, lien MFA ✅
- `MFASetupPage` : flow TOTP complet (QR code → saisie code → backup codes → désactiver) ✅
- Backend auth/sessions/MFA 100% fonctionnel ✅

### Anti-patterns identifiés

| ID | Fichier | Problème | Priorité |
|----|---------|----------|----------|
| AP-01 | `routes/_app/profile/*.tsx` | Pas de fichier `_app/profile.tsx` — layout parent absent → **pas de SubNav Profil** | P0 |
| AP-02 | `MFASetupPage.tsx:72-77` | Loading initial `isLoading` → `<Loader2>` spinner (à remplacer par skeleton) | P1 |

**Note importante sur les `Loader2`** : dans les pages auth et profil, tous les autres `Loader2`
sont dans des boutons submit pendant des mutations (`isPending`) — pattern correct et conforme.
Aucun spinner de chargement de données dans `LoginPage`, `ForgotPasswordPage`, `ResetPasswordPage`,
`MFAVerifyPage`, `ProfilePage`, `SecurityPage`.

---

## Tâches L1→L5

### TASK-AUTH-01 (P0) — Créer layout parent `_app/profile.tsx` avec SubNav

**Problème** : Il n'existe pas de fichier `frontend/src/routes/_app/profile.tsx`. Les routes
`/_app/profile/index.tsx`, `/_app/profile/security.tsx` et `/_app/profile/mfa.tsx` sont sans
layout parent commun → pas de SubNav sur le module profil.

**Fichier à créer** : `frontend/src/routes/_app/profile.tsx`

```tsx
// routes/_app/profile.tsx
import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/components/layout/SubNav'

const PROFILE_NAV = [
  { label: 'Informations', href: '/profile' },
  { label: 'Sécurité', href: '/profile/security' },
  { label: 'Authentification 2FA', href: '/profile/mfa' },
]

export const Route = createFileRoute('/_app/profile')({
  component: () => (
    <div className="space-y-0">
      <SubNav items={PROFILE_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  ),
})
```

> En TanStack Router v1, créer `_app/profile.tsx` avec `createFileRoute('/_app/profile')` fait
> que les routes `/_app/profile/*` héritent automatiquement de ce layout.
> Vérifier que `routeTree.gen.ts` est regénéré après création du fichier.

> Retirer le padding `p-4 md:p-6` redondant dans `ProfilePage`, `SecurityPage`, `MFASetupPage`
> si présent (sinon double padding).

**Critères done** :
- ☐ `routes/_app/profile.tsx` créé
- ☐ SubNav visible avec 3 onglets (Informations / Sécurité / 2FA)
- ☐ `routeTree.gen.ts` regénéré sans erreur
- ☐ `tsc --noEmit` 0 erreur
- ☐ 1582 Vitest pass

---

### TASK-AUTH-02 (P1) — Skeleton loading MFASetupPage

**Problème** : `MFASetupPage.tsx:72-77` affiche un `<Loader2>` spinner pendant le chargement
du statut MFA initial (`isLoading` de `useMfaStatus()`).

**Fichier à modifier** : `frontend/src/pages/profile/MFASetupPage.tsx`

```tsx
function MFAStatusSkeleton() {
  return (
    <div className="max-w-md mx-auto space-y-6 animate-pulse">
      {/* Header */}
      <div className="text-center space-y-3">
        <div className="w-16 h-16 bg-dark-700 rounded-full mx-auto" />
        <div className="h-6 bg-dark-700 rounded w-48 mx-auto" />
        <div className="h-4 bg-dark-700 rounded w-64 mx-auto" />
      </div>
      {/* Statut actuel */}
      <div className="card p-5 space-y-3">
        <div className="h-3 bg-dark-700 rounded w-32" />
        <div className="flex items-center justify-between">
          <div className="h-4 bg-dark-700 rounded w-24" />
          <div className="h-6 bg-dark-700 rounded-full w-16" />
        </div>
      </div>
      {/* Bouton action */}
      <div className="h-10 bg-dark-700 rounded-lg" />
    </div>
  )
}

// Remplacer :
// if (isLoading) return (
//   <div className="flex items-center justify-center py-12">
//     <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
//   </div>
// )
if (isLoading) return <MFAStatusSkeleton />
```

**Critères done** :
- ☐ Skeleton structuré (icône + titre + card statut + bouton)
- ☐ Aucun `Loader2` `isLoading` dans `MFASetupPage` (les `isPending` boutons restent)

---

## Couverture LAYER.html — Mapping final

| Écran LAYER | Route | Composant | Backend | Statut cible |
|------------|-------|-----------|---------|--------------|
| `s-login` | `/login` | `LoginPage` | `POST /auth/login` | ✅ complet |
| `s-mfa-verify` | `/mfa/verify` | `MFAVerifyPage` | `POST /mfa/verify` | ✅ complet |
| `s-forgot-password` | `/forgot-password` | `ForgotPasswordPage` | `POST /auth/forgot-password` | ✅ complet |
| `s-reset-password` | `/reset-password` | `ResetPasswordPage` | `POST /auth/reset-password` | ✅ complet |
| `s-oauth-callback` | `/oauth/callback` | `OAuthCallbackPage` | OAuth routes | ✅ complet |
| `s-profile` | `/profile` | `ProfilePage` | `GET+PATCH /users/me` | ✅ → SubNav |
| `s-securite` | `/profile/security` | `SecurityPage` | `POST /auth/change-password` + sessions | ✅ → SubNav |
| `s-mfa-setup` | `/profile/mfa` | `MFASetupPage` | `/mfa/*` | ✅ → SubNav + skeleton |

---

## Ordre d'exécution recommandé

```
TASK-AUTH-01  ← P0 Layout parent profil + SubNav
TASK-AUTH-02  ← P1 Skeleton MFASetupPage (indépendant)
```

---

## Référence — Fichiers impactés

| Fichier | Action |
|---------|--------|
| `routes/_app/profile.tsx` | **Créer** — layout parent + SubNav |
| `pages/profile/MFASetupPage.tsx` | Modifier — skeleton |

---

## Particularités importantes (pour implémentation)

- Login : `OAuth2PasswordRequestForm` (**form data**, pas JSON) → `GOTCHA:BACKEND:LOGIN-FORM`
- MFA flow : `login` → `mfa_session_token` dans réponse → `POST /mfa/verify` → `access_token`
- Sessions : `family_id` identifie une session, `is_current` marqué backend
- CSRF : `GET /auth/csrf` → header `X-CSRF-Token` injecté automatiquement par `fetchClient`
