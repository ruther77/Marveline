import { api } from './fetchClient'
import type { WebAuthnCredential, WebAuthnRegisterOptions, WebAuthnAuthenticateOptions } from '@/types/webauthn'

export const webauthnApi = {
  registerOptions: async (deviceName: string): Promise<WebAuthnRegisterOptions> => {
    return api.post<WebAuthnRegisterOptions>('/webauthn/register/options', { device_name: deviceName })
  },

  registerVerify: async (data: {
    credential_id: string
    client_data_json: string
    attestation_object: string
    device_name: string
  }): Promise<{ id: number; device_name: string; status: string }> => {
    return api.post('/webauthn/register/verify', data)
  },

  authenticateOptions: async (): Promise<WebAuthnAuthenticateOptions> => {
    return api.post<WebAuthnAuthenticateOptions>('/webauthn/authenticate/options')
  },

  authenticateVerify: async (data: {
    credential_id: string
    client_data_json: string
    authenticator_data: string
    signature: string
  }): Promise<{ verified: boolean; stepup_valid_seconds: number }> => {
    return api.post('/webauthn/authenticate/verify', data)
  },

  listCredentials: async (): Promise<WebAuthnCredential[]> => {
    return api.get<WebAuthnCredential[]>('/webauthn/credentials')
  },

  deleteCredential: async (credentialId: number): Promise<{ deleted: boolean }> => {
    return api.delete(`/webauthn/credentials/${credentialId}`)
  },
}
