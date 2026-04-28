import { z } from 'zod'
import { amountEurosSchema, dateIsoSchema, idSchema } from './common'

export const reservationCreateSchema = z
  .object({
    customer_id: idSchema,
    event_date: dateIsoSchema,
    delivery_date: dateIsoSchema,
    return_date: dateIsoSchema,
    event_location: z.string().optional(),
    event_type: z.enum(['mariage', 'anniversaire', 'entreprise', 'autre']).optional(),
    event_name: z.string().optional(),
    guest_count: z.number().int().positive().optional(),
    deposit_amount_euros: amountEurosSchema.optional(),
    notes: z.string().optional(),
    lines: z
      .array(z.object({ product_id: idSchema, quantity: z.number().int().positive(), variant_id: idSchema.optional() }))
      .min(1, 'Au moins une ligne requise'),
  })
  .refine(
    (d) => new Date(d.delivery_date) <= new Date(d.event_date),
    { message: 'La livraison doit être avant ou le jour de l\'événement', path: ['delivery_date'] },
  )
  .refine(
    (d) => new Date(d.return_date) >= new Date(d.event_date),
    { message: 'Le retour doit être après ou le jour de l\'événement', path: ['return_date'] },
  )

export const reservationUpdateSchema = z.object({
  event_date: dateIsoSchema.optional(),
  delivery_date: dateIsoSchema.optional(),
  return_date: dateIsoSchema.optional(),
  event_location: z.string().optional(),
  deposit_paid: z.boolean().optional(),
  event_type: z.enum(['mariage', 'anniversaire', 'entreprise', 'autre']).optional(),
  event_name: z.string().optional(),
  guest_count: z.number().int().positive().optional(),
})

export const cautionSchema = z.object({
  amount_euros: amountEurosSchema,
  method: z.enum(['cash', 'card', 'transfer', 'check']),
  notes: z.string().optional(),
})

export const extendSchema = z
  .object({
    new_return_date: dateIsoSchema,
    reason: z.string().min(1, 'Raison requise'),
    extra_charge_euros: amountEurosSchema.optional(),
  })

export const preCheckSchema = z.object({
  item_id: idSchema,
  checked: z.boolean(),
})

export type ReservationCreateInput = z.input<typeof reservationCreateSchema>
