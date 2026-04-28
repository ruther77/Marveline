import { z } from 'zod'
import { amountEurosSchema, dateIsoSchema, idSchema } from './common'

export const devisLineSchema = z.object({
  product_id: idSchema,
  quantity: z.number().int().positive('Quantité invalide'),
  unit_price_euros: amountEurosSchema,
})

/** Étape 1 du stepper DevisCreate — infos client + événement. */
export const devisStepClientSchema = z.object({
  customer_id: idSchema,
  event_date: dateIsoSchema,
  delivery_date: dateIsoSchema,
  return_date: dateIsoSchema,
  event_location: z.string().optional(),
  event_type: z.enum(['mariage', 'anniversaire', 'entreprise', 'autre']).optional(),
  event_name: z.string().optional(),
  guest_count: z.number().int().positive().optional(),
  valid_until: dateIsoSchema,
})

/** Création complète d'un devis avec refinements dates. */
export const devisCreateSchema = z
  .object({
    customer_id: idSchema,
    event_date: dateIsoSchema,
    valid_until: dateIsoSchema,
    event_location: z.string().optional(),
    notes: z.string().optional(),
    lines: z.array(devisLineSchema).min(1, 'Au moins une ligne requise'),
  })
  .refine(
    (data) => new Date(data.valid_until) > new Date(),
    { message: 'La date de validité doit être dans le futur', path: ['valid_until'] },
  )

export const devisNegotiationSchema = z.object({
  message: z.string().min(1, 'Message requis'),
  proposed_amount_euros: amountEurosSchema.optional(),
})

export type DevisLineInput = z.input<typeof devisLineSchema>
export type DevisCreateInput = z.input<typeof devisCreateSchema>
