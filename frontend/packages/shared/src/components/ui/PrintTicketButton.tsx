/**
 * PrintTicketButton — bouton d'impression ticket ESC/POS.
 *
 * Envoie une requête POST /print/ticket vers le backend.
 * L'impression est asynchrone (Celery) — feedback immédiat.
 *
 * Usage :
 *   <PrintTicketButton
 *     api={api}
 *     ticketType="vente_epicerie"
 *     lignes={[{ designation: 'Pain', quantite: 2, total_cts: 350 }]}
 *     totalTtcCts={350}
 *   />
 */
import { useState } from 'react'
import { Printer, Loader2, Check, AlertCircle } from 'lucide-react'

interface TicketLine {
  designation: string
  quantite?: number
  prix_unitaire_cts?: number
  total_cts?: number
}

interface TvaBreakdown {
  taux_label: string
  base_ht_cts?: number
  montant_tva_cts?: number
}

interface PrintTicketButtonProps {
  api: {
    post: <T>(path: string, body?: unknown) => Promise<T>
  }
  ticketType: 'vente_epicerie' | 'commande_cuisine' | 'recu_restaurant'
  lignes: TicketLine[]
  sousTotal_ht_cts?: number
  tvaBreakdown?: TvaBreakdown[]
  totalTtcCts: number
  numeroTicket?: string
  mentionLegale?: string
  qrUrl?: string
  ouvrirTiroir?: boolean
  className?: string
  label?: string
}

type PrintState = 'idle' | 'printing' | 'done' | 'error'

export default function PrintTicketButton({
  api,
  ticketType,
  lignes,
  sousTotal_ht_cts = 0,
  tvaBreakdown = [],
  totalTtcCts,
  numeroTicket = '',
  mentionLegale = 'Merci de votre visite',
  qrUrl,
  ouvrirTiroir = false,
  className = '',
  label = 'Imprimer ticket',
}: PrintTicketButtonProps) {
  const [state, setState] = useState<PrintState>('idle')

  const handlePrint = async () => {
    setState('printing')
    try {
      await api.post('/print/ticket', {
        ticket_type: ticketType,
        lignes: lignes.map(l => ({
          designation: l.designation,
          quantite: l.quantite ?? 1,
          prix_unitaire_cts: l.prix_unitaire_cts ?? 0,
          total_cts: l.total_cts ?? 0,
        })),
        sous_total_ht_cts: sousTotal_ht_cts,
        tva_breakdown: tvaBreakdown.map(t => ({
          taux_label: t.taux_label,
          base_ht_cts: t.base_ht_cts ?? 0,
          montant_tva_cts: t.montant_tva_cts ?? 0,
        })),
        total_ttc_cts: totalTtcCts,
        numero_ticket: numeroTicket,
        mention_legale: mentionLegale,
        qr_url: qrUrl,
        ouvrir_tiroir: ouvrirTiroir,
      })
      setState('done')
      setTimeout(() => setState('idle'), 2000)
    } catch {
      setState('error')
      setTimeout(() => setState('idle'), 3000)
    }
  }

  const Icon = {
    idle: Printer,
    printing: Loader2,
    done: Check,
    error: AlertCircle,
  }[state]

  const stateStyles = {
    idle: 'bg-stone-100 text-stone-700 hover:bg-stone-200 border-stone-200',
    printing: 'bg-stone-100 text-stone-400 border-stone-200',
    done: 'bg-green-50 text-green-700 border-green-200',
    error: 'bg-red-50 text-red-700 border-red-200',
  }[state]

  const stateLabel = {
    idle: label,
    printing: 'Impression...',
    done: 'Imprimé',
    error: 'Erreur impression',
  }[state]

  return (
    <button
      onClick={handlePrint}
      disabled={state === 'printing'}
      className={`flex items-center gap-2 px-4 py-2 text-[13px] font-medium rounded-lg border transition-colors min-h-[44px] ${stateStyles} ${className}`}
    >
      <Icon className={`w-4 h-4 ${state === 'printing' ? 'animate-spin' : ''}`} />
      {stateLabel}
    </button>
  )
}
