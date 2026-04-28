import { z } from 'zod'
import { amountEurosSchema, dateIsoSchema, idSchema, paymentMethodSchema } from './common'

const venteLineSchema = z.object({
  product_id: idSchema,
  quantity: z.number().int().positive('Quantité invalide'),
  unit_price_euros: amountEurosSchema,
})

export const venteCreateSchema = z.object({
  customer_id: idSchema,
  lines: z.array(venteLineSchema).min(1, 'Au moins une ligne requise'),
  deposit_pct: z.number().min(0).max(100).optional(),
  payment_due_date: dateIsoSchema.optional(),
  notes: z.string().optional(),
})

export const ventePaymentSchema = z.object({
  amount_euros: amountEurosSchema,
  payment_method: paymentMethodSchema,
  payment_date: dateIsoSchema,
  is_deposit: z.boolean().default(false),
  notes: z.string().optional(),
})

export const venteRefundSchema = z.object({
  amount_euros: amountEurosSchema,
  reason: z.string().min(1, 'Raison requise'),
  method: paymentMethodSchema,
})

export type VenteCreateInput = z.input<typeof venteCreateSchema>
export type VentePaymentInput = z.input<typeof ventePaymentSchema>
export type VenteRefundInput = z.input<typeof venteRefundSchema>
