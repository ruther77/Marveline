import {
  Send,
  CheckCircle,
  XCircle,
  RefreshCw,
  RotateCcw,
  FileText,
  MessageSquare,
  Download,
} from 'lucide-react'

interface DevisActionsProps {
  devisId: number
  reference: string
  status: string
  pdfPending: boolean
  acceptPending: boolean
  negotiationPending: boolean
  versionPendingPending: boolean
  renewPending: boolean
  duplicatePending: boolean
  cancelPending: boolean
  showCancelConfirm: boolean
  onSend: () => void
  onAccept: () => void
  onRefuse: () => void
  onConvert: () => void
  onRenew: () => void
  onNegotiate: () => void
  onVersionPending: () => void
  onPreviewPdf: () => void
  onDuplicate: () => void
  onCancelRequest: () => void
  onCancelConfirm: () => void
  onCancelAbort: () => void
}

export function DevisActions({
  status,
  pdfPending,
  acceptPending,
  negotiationPending,
  versionPendingPending,
  renewPending,
  duplicatePending,
  cancelPending,
  showCancelConfirm,
  onSend,
  onAccept,
  onRefuse,
  onConvert,
  onRenew,
  onNegotiate,
  onVersionPending,
  onPreviewPdf,
  onDuplicate,
  onCancelRequest,
  onCancelConfirm,
  onCancelAbort,
}: DevisActionsProps) {
  const canSend = status === 'draft' || status === 'version_pending'
  const canAccept = status === 'sent' || status === 'negotiation'
  const canRefuse = status === 'sent' || status === 'negotiation'
  const canConvert = status === 'accepted'
  const canRenew = status === 'expired'
  const canCancel = !['cancelled', 'converted', 'refused'].includes(status)
  const canNegotiate = status === 'sent' || status === 'negotiation'
  const canVersionPending = status === 'negotiation'

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {canSend && (
        <button
          onClick={onSend}
          className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-1.5 rounded-lg"
        >
          <Send className="w-4 h-4" /> Envoyer
        </button>
      )}
      {canAccept && (
        <button
          onClick={onAccept}
          disabled={acceptPending}
          className="flex items-center gap-1.5 bg-green-600 hover:bg-green-700 text-white text-sm px-4 py-1.5 rounded-lg disabled:opacity-60"
        >
          <CheckCircle className="w-4 h-4" /> Accepter
        </button>
      )}
      {canRefuse && (
        <button
          onClick={onRefuse}
          className="flex items-center gap-1.5 bg-red-700 hover:bg-red-800 text-white text-sm px-4 py-1.5 rounded-lg"
        >
          <XCircle className="w-4 h-4" /> Refuser
        </button>
      )}
      {canConvert && (
        <button
          onClick={onConvert}
          className="flex items-center gap-1.5 bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium text-sm px-4 py-1.5 rounded-lg"
        >
          <RefreshCw className="w-4 h-4" /> Convertir
        </button>
      )}
      {canRenew && (
        <button
          onClick={onRenew}
          disabled={renewPending}
          className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm px-4 py-1.5 rounded-lg disabled:opacity-60"
        >
          <RotateCcw className="w-4 h-4" /> {renewPending ? 'Renouvellement…' : 'Renouveler'}
        </button>
      )}
      {canNegotiate && (
        <button
          onClick={onNegotiate}
          disabled={negotiationPending}
          className="flex items-center gap-1.5 bg-dark-900 hover:bg-dark-600 text-dark-50 text-sm px-4 py-1.5 rounded-lg disabled:opacity-60"
        >
          <MessageSquare className="w-4 h-4" /> {negotiationPending ? 'Ouverture…' : 'Négociation'}
        </button>
      )}
      {canVersionPending && (
        <button
          onClick={onVersionPending}
          disabled={versionPendingPending}
          className="flex items-center gap-1.5 bg-orange-600 hover:bg-orange-700 text-white text-sm px-4 py-1.5 rounded-lg disabled:opacity-60"
        >
          <RefreshCw className="w-4 h-4" />
          {versionPendingPending ? 'Transition…' : 'Passer en révision'}
        </button>
      )}
      <button
        onClick={onPreviewPdf}
        disabled={pdfPending}
        className="flex items-center gap-1.5 bg-dark-900 hover:bg-dark-600 text-dark-50 text-sm px-4 py-1.5 rounded-lg disabled:opacity-60"
      >
        <Download className="w-4 h-4" />
        {pdfPending ? 'Chargement…' : 'PDF'}
      </button>
      <button
        onClick={onDuplicate}
        disabled={duplicatePending}
        className="flex items-center gap-1.5 bg-dark-900 hover:bg-dark-600 text-dark-50 text-sm px-4 py-1.5 rounded-lg disabled:opacity-60"
      >
        <FileText className="w-4 h-4" /> Dupliquer
      </button>
      {canCancel && (
        showCancelConfirm ? (
          <div className="flex items-center gap-2">
            <span className="text-sm text-dark-300">Annuler ce devis ?</span>
            <button
              onClick={onCancelConfirm}
              disabled={cancelPending}
              className="text-sm text-red-400 hover:text-red-300 px-4 py-1.5 rounded-lg border border-red-700/50 hover:bg-red-900/20 disabled:opacity-50"
            >
              Confirmer
            </button>
            <button
              onClick={onCancelAbort}
              className="text-sm text-dark-400 hover:text-dark-50 px-4 py-1.5 rounded-lg"
            >
              Non
            </button>
          </div>
        ) : (
          <button
            onClick={onCancelRequest}
            className="text-dark-400 hover:text-red-400 text-sm px-4 py-1.5 rounded-lg"
          >
            Annuler
          </button>
        )
      )}
    </div>
  )
}
