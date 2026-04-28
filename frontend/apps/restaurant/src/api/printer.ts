import { getMassaCorpApi } from '@shared/stores/massacorpAuthStore'

export interface TicketLine {
  designation: string
  quantite: number
  prix_unitaire_cts: number
  total_cts: number
}

export interface TvaBreakdown {
  taux_label: string
  base_ht_cts: number
  montant_tva_cts: number
}

export interface PrintTicketRequest {
  ticket_type: 'vente_epicerie' | 'commande_cuisine' | 'recu_restaurant'
  lignes: TicketLine[]
  sous_total_ht_cts: number
  tva_breakdown?: TvaBreakdown[]
  total_ttc_cts: number
  numero_ticket?: string
  mention_legale?: string
  qr_url?: string
  ouvrir_tiroir?: boolean
}

export interface PrintTicketResponse {
  status: 'queued'
  message: string
}

export const printerApi = {
  printTicket: (data: PrintTicketRequest) =>
    getMassaCorpApi().post<PrintTicketResponse>('/print/ticket', data),
}
