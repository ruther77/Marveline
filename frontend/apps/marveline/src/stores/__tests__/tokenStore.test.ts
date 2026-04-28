/**
 * Tests unitaires pour stores/tokenStore.ts
 * tokenStore est pur JS (pas de React, pas de Zustand)
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { tokenStore } from '../tokenStore'

describe('tokenStore', () => {
  beforeEach(() => {
    tokenStore.clear()
  })

  it('retourne null par défaut', () => {
    expect(tokenStore.getAccessToken()).toBeNull()
  })

  it('stocke et retourne un token', () => {
    tokenStore.setAccessToken('eyJhbGciOiJIUzI1NiJ9.test')

    expect(tokenStore.getAccessToken()).toBe('eyJhbGciOiJIUzI1NiJ9.test')
  })

  it('écrase l\'ancien token', () => {
    tokenStore.setAccessToken('token-v1')
    tokenStore.setAccessToken('token-v2')

    expect(tokenStore.getAccessToken()).toBe('token-v2')
  })

  it('accepte null pour effacer le token', () => {
    tokenStore.setAccessToken('token')
    tokenStore.setAccessToken(null)

    expect(tokenStore.getAccessToken()).toBeNull()
  })

  it('clear() réinitialise à null', () => {
    tokenStore.setAccessToken('token')
    tokenStore.clear()

    expect(tokenStore.getAccessToken()).toBeNull()
  })

  it('clear() est idempotent (double clear)', () => {
    tokenStore.clear()
    tokenStore.clear()

    expect(tokenStore.getAccessToken()).toBeNull()
  })
})
