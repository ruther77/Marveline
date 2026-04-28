import { z } from 'zod'

/** Convertit un montant saisi en euros (décimal) vers des centimes (entier). */
export const amountEurosSchema = z
  .number({ invalid_type_error: 'Montant invalide' })
  .min(0, 'Le montant doit être positif')
  .transform((v) => Math.round(v * 100))

/** Valide une date ISO YYYY-MM-DD. */
export const dateIsoSchema = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, 'Format date invalide (YYYY-MM-DD)')

/** Id numérique > 0. */
export const idSchema = z.number().int().positive()

/** Méthode de paiement. */
export const paymentMethodSchema = z.enum(['cash', 'card', 'transfer', 'check'])
