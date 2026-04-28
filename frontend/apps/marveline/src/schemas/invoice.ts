import { z } from 'zod'
import { amountEurosSchema, dateIsoSchema, paymentMethodSchema } from './common'

export const invoiceCreateSchema = z
  .object({
    reservation_id: z.number().int().positive(),
    issue_date: dateIsoSchema,
    due_date: dateIsoSchema,
  })
  .refine(
    (d) => new Date(d.due_date) >= new Date(d.issue_date),
    { message: 'La date d\'échéance doit être après la date d\'émission', path: ['due_date'] },
  )

export const addPaymentSchema = z.object({
  amount_euros: amountEurosSchema,
  payment_method: paymentMethodSchema,
  payment_date: dateIsoSchema,
})

export const chargeCreateSchema = z.discriminatedUnion('charge_type', [
  z.object({
    charge_type: z.literal('DAMAGE'),
    amount_euros: amountEurosSchema,
    description: z.string().min(1, 'Description requise'),
    damage_type_id: z.number().int().positive().optional(),
  }),
  z.object({
    charge_type: z.literal('LABOR'),
    hours: z.number().positive('Nombre d\'heures invalide'),
    day_type: z.enum(['weekday', 'weekend', 'night']),
    description: z.string().min(1, 'Description requise'),
  }),
])

export type InvoiceCreateInput = z.input<typeof invoiceCreateSchema>
export type AddPaymentInput = z.input<typeof addPaymentSchema>
