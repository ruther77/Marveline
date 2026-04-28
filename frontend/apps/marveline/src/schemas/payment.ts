import { z } from 'zod'
import { amountEurosSchema, dateIsoSchema, paymentMethodSchema } from './common'

export const paymentCreateSchema = z.object({
  amount_euros: amountEurosSchema,
  payment_method: paymentMethodSchema,
  payment_date: dateIsoSchema,
  is_deposit: z.boolean().default(false),
  notes: z.string().optional(),
})

export type PaymentCreateInput = z.input<typeof paymentCreateSchema>
