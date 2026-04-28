export interface WebAuthnCredential {
  id: number
  device_name: string
  created_at: string
  last_used_at: string | null
  aaguid: string | null
}

export interface WebAuthnRegisterOptions {
  challenge: string
  rp_id: string
  rp_name: string
  user_id: string
  user_name: string
  user_display_name: string
  timeout: number
  attestation: string
  authenticator_selection: {
    authenticatorAttachment?: string
    residentKey?: string
    userVerification?: string
  }
}

export interface WebAuthnAuthenticateOptions {
  challenge: string
  rp_id: string
  timeout: number
  user_verification: string
  allow_credentials: { id: string; type: string }[]
}
