/**
 * Tests unitaires pour errors/constants.ts
 * ERROR_TITLES, ERROR_MESSAGES, ERROR_ACTIONS, STATUS_CATEGORY_MAP
 */
import { describe, it, expect } from 'vitest'
import {
  ERROR_TITLES,
  ERROR_MESSAGES,
  ERROR_ACTIONS,
  STATUS_CATEGORY_MAP,
} from '../constants'
import type { ErrorCategory } from '../types'

const ALL_CATEGORIES: ErrorCategory[] = [
  'network', 'auth', 'validation', 'not_found',
  'forbidden', 'server', 'chunk_load', 'unknown',
]

describe('ERROR_TITLES', () => {
  it('chaque catégorie a un titre', () => {
    for (const cat of ALL_CATEGORIES) {
      expect(ERROR_TITLES[cat]).toBeTruthy()
    }
  })

  it('les titres sont des chaînes non vides', () => {
    for (const cat of ALL_CATEGORIES) {
      expect(typeof ERROR_TITLES[cat]).toBe('string')
      expect(ERROR_TITLES[cat].length).toBeGreaterThan(0)
    }
  })
})

describe('ERROR_MESSAGES', () => {
  it('chaque catégorie a un message', () => {
    for (const cat of ALL_CATEGORIES) {
      expect(ERROR_MESSAGES[cat]).toBeTruthy()
    }
  })

  it('le message network mentionne le serveur ou connexion', () => {
    expect(ERROR_MESSAGES['network'].toLowerCase()).toMatch(/connexion|serveur/)
  })

  it('le message auth mentionne session ou reconnecter', () => {
    expect(ERROR_MESSAGES['auth'].toLowerCase()).toMatch(/session|reconnecter/)
  })
})

describe('ERROR_ACTIONS', () => {
  it('chaque catégorie a une action', () => {
    for (const cat of ALL_CATEGORIES) {
      expect(ERROR_ACTIONS[cat]).toBeTruthy()
    }
  })

  it('auth → "Se reconnecter"', () => {
    expect(ERROR_ACTIONS['auth']).toBe('Se reconnecter')
  })

  it('validation → "Corriger"', () => {
    expect(ERROR_ACTIONS['validation']).toBe('Corriger')
  })
})

describe('STATUS_CATEGORY_MAP', () => {
  it('401 → auth', () => {
    expect(STATUS_CATEGORY_MAP[401]).toBe('auth')
  })

  it('403 → forbidden', () => {
    expect(STATUS_CATEGORY_MAP[403]).toBe('forbidden')
  })

  it('404 → not_found', () => {
    expect(STATUS_CATEGORY_MAP[404]).toBe('not_found')
  })

  it('422 → validation', () => {
    expect(STATUS_CATEGORY_MAP[422]).toBe('validation')
  })

  it('500 → server', () => {
    expect(STATUS_CATEGORY_MAP[500]).toBe('server')
  })

  it('504 → network (gateway timeout)', () => {
    expect(STATUS_CATEGORY_MAP[504]).toBe('network')
  })

  it('400, 409, 429 → categories correctes', () => {
    expect(STATUS_CATEGORY_MAP[400]).toBe('validation')
    expect(STATUS_CATEGORY_MAP[409]).toBe('validation')
    expect(STATUS_CATEGORY_MAP[429]).toBe('network')
  })
})
