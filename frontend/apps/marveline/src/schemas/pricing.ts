import { z } from 'zod'
import { dateIsoSchema, idSchema } from './common'

export const pricingTierSchema = z.object({
  min_qty: z.number().int().min(1),
  max_qty: z.number().int().positive().optional(),
  unit_price_cents: z.number().int().min(0, 'Prix invalide'),
})

export const pricingRuleSchema = z
  .object({
    name: z.string().min(1, 'Nom requis'),
    rule_type: z.enum(['flat', 'per_day', 'tiered', 'volume', 'seasonal', 'custom']),
    applies_to: z.enum(['product', 'category', 'all']),
    target_id: idSchema.optional(),
    discount_pct: z.number().min(0).max(100).optional(),
    tiers: z.array(pricingTierSchema).optional(),
    valid_from: dateIsoSchema.optional(),
    valid_to: dateIsoSchema.optional(),
  })
  .refine(
    (d) => {
      if (d.valid_from && d.valid_to) {
        return new Date(d.valid_to) >= new Date(d.valid_from)
      }
      return true
    },
    { message: 'La date de fin doit être après la date de début', path: ['valid_to'] },
  )
  .refine(
    (d) => d.rule_type !== 'tiered' || (d.tiers && d.tiers.length > 0),
    { message: 'Les règles par paliers nécessitent au moins un palier', path: ['tiers'] },
  )

export type PricingRuleInput = z.input<typeof pricingRuleSchema>
