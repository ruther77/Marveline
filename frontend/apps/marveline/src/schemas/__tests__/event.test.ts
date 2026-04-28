/**
 * Tests unitaires pour schemas/event.ts
 */
import { describe, it, expect } from 'vitest'
import { createEventSchema, incidentSchema, actionPlanSchema } from '../event'

describe('createEventSchema', () => {
  it('valide un événement minimal', () => {
    const result = createEventSchema.parse({
      name: 'Mariage Dupont',
      event_date: '2026-06-20',
    })
    expect(result.name).toBe('Mariage Dupont')
  })

  it('rejette un nom vide', () => {
    expect(() =>
      createEventSchema.parse({ name: '', event_date: '2026-06-20' })
    ).toThrow()
  })

  it('accepte reservation_id optionnel', () => {
    const result = createEventSchema.parse({
      name: 'Anniversaire',
      event_date: '2026-07-01',
      reservation_id: 42,
    })
    expect(result.reservation_id).toBe(42)
  })
})

describe('incidentSchema', () => {
  it('valide un incident critique', () => {
    const result = incidentSchema.parse({
      event_id: 1,
      description: 'Matériel cassé',
      severity: 'critical',
      affected_items: [10, 11],
    })
    expect(result.severity).toBe('critical')
    expect(result.affected_items).toHaveLength(2)
  })

  it('affected_items par défaut vide', () => {
    const result = incidentSchema.parse({
      event_id: 1,
      description: 'Problème retour',
      severity: 'low',
    })
    expect(result.affected_items).toEqual([])
  })

  it('rejette une sévérité inconnue', () => {
    expect(() =>
      incidentSchema.parse({
        event_id: 1,
        description: 'Test',
        severity: 'extreme',
      })
    ).toThrow()
  })

  it('rejette une description vide', () => {
    expect(() =>
      incidentSchema.parse({ event_id: 1, description: '', severity: 'low' })
    ).toThrow()
  })
})

describe('actionPlanSchema', () => {
  it('valide un plan d\'action', () => {
    const result = actionPlanSchema.parse({
      incident_id: 5,
      label: 'Remplacer la table',
      assignee: 'Jean Dupont',
      deadline: '2026-06-25',
    })
    expect(result.label).toBe('Remplacer la table')
  })

  it('rejette un label vide', () => {
    expect(() =>
      actionPlanSchema.parse({
        incident_id: 5,
        label: '',
        assignee: 'Jean',
        deadline: '2026-06-25',
      })
    ).toThrow()
  })
})
