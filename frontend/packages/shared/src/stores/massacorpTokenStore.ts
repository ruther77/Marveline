/**
 * massacorpTokenStore — stockage en mémoire du accessToken MassaCorp.
 * Séparé du tokenStore Marveline pour éviter collision dans le même onglet.
 * Non-persisté, non-observable — variable module-level.
 */

let _accessToken: string | null = null

export const massacorpTokenStore = {
  getAccessToken: (): string | null => _accessToken,
  setAccessToken: (token: string | null): void => {
    _accessToken = token
  },
  clear: (): void => {
    _accessToken = null
  },
}
