import { FileText, Download, Send, Bell, CreditCard, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  INVOICE_STATUS_LABELS as STATUS_LABELS,
  INVOICE_STATUS_COLORS as STATUS_COLORS,
} from '@/lib/constants'
import type { InvoiceDetail, InvoiceStatus } from '@/types/invoice'

interface InvoiceDetailHeaderProps {
  invoice: Pick<InvoiceDetail, 'invoice_number' | 'status' | 'is_paid'>
  cancelPending: boolean
  remindPending: boolean
  showPaymentForm: boolean
  onDownloadPdf: () => void
  onOpenSendModal: () => void
  onRemind: () => void
  onTogglePaymentForm: () => void
  onCancel: () => void
}

export function InvoiceDetailHeader({
  invoice,
  cancelPending,
  remindPending,
  onDownloadPdf,
  onOpenSendModal,
  onRemind,
  onTogglePaymentForm,
  onCancel,
}: InvoiceDetailHeaderProps) {
  return (
    <div className="space-y-3">
      {/* Ref + badge */}
      <div className="flex items-center gap-3">
        <FileText className="w-5 h-5 text-primary-400 shrink-0" />
        <span className="font-mono text-lg text-primary-400">
          {invoice.invoice_number}
        </span>
        <span
          className={cn(
            'inline-flex items-center px-2 py-0.5 rounded text-xs shrink-0',
            STATUS_COLORS[invoice.status as InvoiceStatus],
          )}
        >
          {STATUS_LABELS[invoice.status as InvoiceStatus]}
        </span>
      </div>

      {/* Actions — wrap on mobile */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={onDownloadPdf}
          className="btn-secondary btn-sm flex items-center gap-1"
        >
          <Download className="w-3 h-3" />
          PDF
        </button>
        {invoice.status === 'draft' && (
          <button
            onClick={onOpenSendModal}
            className="btn-secondary btn-sm flex items-center gap-1 text-blue-400"
          >
            <Send className="w-3 h-3" />
            Envoyer
          </button>
        )}
        {!invoice.is_paid && (invoice.status === 'sent' || invoice.status === 'overdue') && (
          <button
            onClick={onRemind}
            disabled={remindPending}
            className="btn-secondary btn-sm flex items-center gap-1 text-amber-400"
          >
            <Bell className="w-3 h-3" />
            {remindPending ? 'Relance…' : 'Relancer'}
          </button>
        )}
        {!invoice.is_paid && invoice.status !== 'cancelled' && (
          <>
            <button
              onClick={onTogglePaymentForm}
              className="btn-primary btn-sm flex items-center gap-1"
            >
              <CreditCard className="w-3 h-3" />
              Paiement
            </button>
            <button
              onClick={onCancel}
              disabled={cancelPending}
              className="btn-secondary btn-sm flex items-center gap-1 text-red-400"
            >
              <XCircle className="w-3 h-3" />
              Annuler
            </button>
          </>
        )}
      </div>
    </div>
  )
}
