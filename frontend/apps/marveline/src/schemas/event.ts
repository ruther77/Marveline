import { z } from 'zod'
import { dateIsoSchema, idSchema } from './common'

export const createEventSchema = z.object({
  reservation_id: idSchema.optional(),
  name: z.string().min(1, 'Nom requis'),
  event_date: dateIsoSchema,
  event_location: z.string().optional(),
})

export const incidentSchema = z.object({
  event_id: idSchema,
  description: z.string().min(1, 'Description requise'),
  severity: z.enum(['low', 'medium', 'high', 'critical']),
  affected_items: z.array(idSchema).default([]),
})

export const actionPlanSchema = z.object({
  incident_id: idSchema,
  label: z.string().min(1, 'Libellé requis'),
  assignee: z.string().min(1, 'Responsable requis'),
  deadline: dateIsoSchema,
})

export type CreateEventInput = z.input<typeof createEventSchema>
export type IncidentInput = z.input<typeof incidentSchema>
