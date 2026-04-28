import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { webauthnApi } from '../webauthn'

export function useWebAuthnCredentials() {
  return useQuery({
    queryKey: queryKeys.webauthn.credentials(),
    queryFn: () => webauthnApi.listCredentials(),
    staleTime: 60_000,
  })
}

export function useRegisterWebAuthn() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ deviceName }: { deviceName: string }) => {
      const options = await webauthnApi.registerOptions(deviceName)

      // WebAuthn ceremony via navigator.credentials.create
      const publicKey: PublicKeyCredentialCreationOptions = {
        challenge: Uint8Array.from(atob(options.challenge.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0)),
        rp: { id: options.rp_id, name: options.rp_name },
        user: {
          id: Uint8Array.from(atob(options.user_id.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0)),
          name: options.user_name,
          displayName: options.user_display_name,
        },
        pubKeyCredParams: [
          { type: 'public-key', alg: -7 },   // ES256
          { type: 'public-key', alg: -257 },  // RS256
        ],
        timeout: options.timeout,
        attestation: options.attestation as AttestationConveyancePreference,
        authenticatorSelection: options.authenticator_selection as AuthenticatorSelectionCriteria,
      }

      const credential = await navigator.credentials.create({ publicKey }) as PublicKeyCredential
      const response = credential.response as AuthenticatorAttestationResponse

      const toBase64Url = (buf: ArrayBuffer) => {
        const bytes = new Uint8Array(buf)
        let binary = ''
        bytes.forEach(b => binary += String.fromCharCode(b))
        return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
      }

      return webauthnApi.registerVerify({
        credential_id: toBase64Url(credential.rawId),
        client_data_json: toBase64Url(response.clientDataJSON),
        attestation_object: toBase64Url(response.attestationObject),
        device_name: deviceName,
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.webauthn.credentials() })
    },
  })
}

export function useDeleteWebAuthnCredential() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (credentialId: number) => webauthnApi.deleteCredential(credentialId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.webauthn.credentials() })
    },
  })
}
