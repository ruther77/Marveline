import { configureApiClient, refreshAccessToken } from '../fetchClient'

interface AuthStoreApiBridgeOptions {
  onTokenRefreshed: (token: string) => void
  onUnauthorized: () => void
  getCSRF: () => string | null
  fetchCSRF: () => Promise<void>
}

export function configureAuthStoreApiBridge(opts: AuthStoreApiBridgeOptions): void {
  configureApiClient(opts)
}

export function refreshAccessTokenFromBridge(): Promise<string> {
  return refreshAccessToken()
}
