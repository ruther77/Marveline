import { z } from 'zod'
import { amountEurosSchema, idSchema } from './common'

const itemConditionSchema = z.enum(['new', 'good', 'fair', 'damaged', 'missing'])

export const damageDeclarationSchema = z.object({
  product_id: idSchema,
  product_name: z.string(),
  category: z.enum(['scratch', 'break', 'missing', 'malfunction', 'other']),
  severity: z.enum(['minor', 'moderate', 'major', 'total_loss']),
  description: z.string().min(1, 'Description requise'),
  photo_urls: z.array(z.string().url()).default([]),
  estimated_cost_euros: amountEurosSchema.optional(),
})

export const departureCheckItemSchema = z.object({
  line_id: idSchema,
  product_id: idSchema,
  quantity_loaded: z.number().int().min(0),
  condition: itemConditionSchema,
  qr_scanned: z.boolean().default(false),
  scanned_codes: z.array(z.string()).default([]),
})

export const departureCheckSchema = z.object({
  reservation_id: idSchema,
  items: z.array(departureCheckItemSchema).min(1, 'Au moins un article requis'),
})

export const returnCheckItemSchema = z.object({
  line_id: idSchema,
  product_id: idSchema,
  quantity_returned: z.number().int().min(0),
  condition: itemConditionSchema,
  damages: z.array(damageDeclarationSchema).default([]),
})

export const returnCheckSchema = z.object({
  reservation_id: idSchema,
  items: z.array(returnCheckItemSchema).min(1, 'Au moins un article requis'),
})

export const casseDeclarationSchema = z.object({
  reservation_id: idSchema,
  product_id: idSchema,
  description: z.string().min(1, 'Description requise'),
  severity: z.enum(['minor', 'moderate', 'major', 'total_loss']),
  estimated_cost_euros: amountEurosSchema,
  photo_urls: z.array(z.string().url()).default([]),
})

export type DamageDeclarationInput = z.input<typeof damageDeclarationSchema>
export type DepartureCheckInput = z.input<typeof departureCheckSchema>
export type ReturnCheckInput = z.input<typeof returnCheckSchema>
