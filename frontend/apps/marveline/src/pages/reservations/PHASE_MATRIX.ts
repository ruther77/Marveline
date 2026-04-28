import type { PhaseMatrix } from '@/types/reservation'

/**
 * Source unique de vérité : quelles sections affiche-t-on pour chaque phase,
 * et dans quel ordre.
 *
 * Toute incohérence de contenu entre phases (ex: LitigePage sans ProductLines)
 * se corrige ici — pas en éditant 13 pages.
 *
 * L'ordre des entrées correspond à l'ordre de rendu dans ReservationView.
 */
export const PHASE_SECTIONS: PhaseMatrix = {
  'brouillon': [
    'hero',
    'status-alert',
    'info-grid',
    'product-lines',
    'quick-links',
  ],

  'brouillon-incomplet': [
    'hero',
    'status-alert',
  ],

  'confirmee': [
    'hero',
    'status-alert',
    'info-grid',
    'deposit',
    'product-lines',
    'invoice',
    'assign',
    'quick-links',
  ],

  'prete': [
    'hero',
    'status-alert',
    'info-grid',
    'deposit',
    'pre-check',
    'product-lines',
    'invoice',
    'assign',
    'quick-links',
  ],

  'risque': [
    'hero',
    'status-alert',
    'info-grid',
    'deposit',
    'risks',
    'product-lines',
    'invoice',
    'assign',
  ],

  'precheck': [
    'hero',
    'status-alert',
    'info-grid',
    'deposit',
    'pre-check',
    'product-lines',
    'invoice',
    'assign',
    'quick-links',
  ],

  'legal': [
    'hero',
    'status-alert',
    'legal-docs',
    'deposit',
    'pre-check',
  ],

  'en-cours': [
    'hero',
    'status-alert',
    'countdown',
    'info-grid',
    'field-timeline',
    'extend',
    'product-lines',
    'invoice',
    'assign',
    'quick-links',
  ],

  'prolongee': [
    'hero',
    'status-alert',
    'countdown',
    'info-grid',
    'field-timeline',
    'extend',
    'product-lines',
    'invoice',
    'assign',
    'quick-links',
  ],

  'retournee': [
    'hero',
    'status-alert',
    'field-timeline',
    'deposit',
    'product-lines',
    'invoice',
    'assign',
    'quick-links',
  ],

  'litige': [
    'hero',
    'status-alert',
    'field-timeline',
    'risks',
    'dispute-log',
    'deposit',
    'product-lines',
    'invoice',
    'assign',
  ],

  'terminee': [
    'hero',
    'status-alert',
    'field-timeline',
    'deposit',
    'product-lines',
    'invoice',
  ],

  'annulee': [
    'hero',
    'status-alert',
    'product-lines',
  ],
}
