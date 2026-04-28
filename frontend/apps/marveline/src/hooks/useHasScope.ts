import { useAuthStore } from '@/stores/authStore'

/**
 * Retourne true si l'utilisateur connecté possède le scope demandé.
 * Source de vérité : user.permissions[] du backend (GET /auth/me).
 * Non-authentifié → false.
 */
export function useHasScope(scope: string): boolean {
  const permissions = useAuthStore((s) => s.user?.permissions)
  return permissions?.includes(scope) ?? false
}

/**
 * Retourne true si l'utilisateur possède AU MOINS UN des scopes listés.
 */
export function useHasAnyScope(...scopes: string[]): boolean {
  const permissions = useAuthStore((s) => s.user?.permissions)
  if (!permissions) return false
  return scopes.some((s) => permissions.includes(s))
}

/**
 * Retourne true si l'utilisateur possède TOUS les scopes listés.
 */
export function useHasAllScopes(...scopes: string[]): boolean {
  const permissions = useAuthStore((s) => s.user?.permissions)
  if (!permissions) return false
  return scopes.every((s) => permissions.includes(s))
}
