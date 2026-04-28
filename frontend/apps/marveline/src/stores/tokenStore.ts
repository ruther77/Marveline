/**
 * tokenStore — stockage en mémoire du accessToken (jamais en localStorage).
 * Variable module-level, non-persistée, non-observable.
 * Utiliser tokenStore dans fetchClient pour injecter l'Authorization header.
 */

let _accessToken: string | null = null

export const tokenStore = {
  getAccessToken: (): string | null => _accessToken,
  setAccessToken: (token: string | null): void => {
    _accessToken = token
  },
  clear: (): void => {
    _accessToken = null
  },
}
