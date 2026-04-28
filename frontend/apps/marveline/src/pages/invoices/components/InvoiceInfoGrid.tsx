import { Calendar, CreditCard } from 'lucide-react'
import { formatDate, formatCents, cn } from '@/lib/utils'
import { PAYMENT_METHOD_LABELS } from '@/lib/constants'
import type { InvoiceDetail } from '@/types/invoice'

interface InvoiceInfoGridProps {
  invoice: Pick<
    InvoiceDetail,
    | 'issue_date'
    | 'due_date'
    | 'is_overdue'
    | 'total_amount_cents'
    | 'tva_breakdown'
    | 'tva_rate'
    | 'tva_amount_cents'
    | 'paid_amount_cents'
    | 'remaining_amount_cents'
    | 'payment_method'
    | 'payment_date'
  >
  effectiveVatRate: number
}

export function InvoiceInfoGrid({ invoice, effectiveVatRate }: InvoiceInfoGridProps) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <label className="text-sm text-dark-400">Date d'émission</label>
        <div className="flex items-center gap-2 mt-1">
          <Calendar className="w-4 h-4 text-dark-400" />
          <span>{formatDate(invoice.issue_date)}</span>
        </div>
      </div>

      <div>
        <label className="text-sm text-dark-400">Date d'échéance</label>
        <div className="flex items-center gap-2 mt-1">
          <Calendar className={cn('w-4 h-4', invoice.is_overdue ? 'text-red-400' : 'text-dark-400')} />
          <span className={invoice.is_overdue ? 'text-red-400 font-medium' : ''}>
            {formatDate(invoice.due_date)}
          </span>
        </div>
      </div>

      <div>
        <label className="text-sm text-dark-400">Montant total TTC</label>
        <p className="font-medium mt-1 text-lg">
          {formatCents(invoice.total_amount_cents)}
        </p>
        {invoice.tva_breakdown && invoice.tva_breakdown.length > 1 ? (
          <div className="text-xs text-dark-500 mt-1 space-y-0.5">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1 font-medium text-dark-400 border-b border-dark-600 pb-1 mb-1">
              <span>Taux</span>
              <span className="text-right">Base HT</span>
              <span className="text-right">TVA</span>
              <span className="text-right">TTC</span>
            </div>
            {invoice.tva_breakdown.map((row) => (
              <div key={row.rate} className="grid grid-cols-2 sm:grid-cols-4 gap-1">
                <span>{Math.round(row.rate * 1000) / 10} %</span>
                <span className="text-right">{formatCents(row.base_ht_cents)}</span>
                <span className="text-right">{formatCents(row.tva_cents)}</span>
                <span className="text-right">{formatCents(row.ttc_cents)}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-dark-500 space-y-0.5 mt-1">
            <div className="flex justify-between">
              <span>HT</span>
              <span>{formatCents(invoice.tva_amount_cents != null
                ? invoice.total_amount_cents
                : Math.round(invoice.total_amount_cents / (1 + effectiveVatRate)))}</span>
            </div>
            <div className="flex justify-between">
              <span>TVA {invoice.tva_rate != null ? Math.round(invoice.tva_rate * 100) : Math.round(effectiveVatRate * 100)}%</span>
              <span>{formatCents(invoice.tva_amount_cents != null
                ? invoice.tva_amount_cents
                : invoice.total_amount_cents - Math.round(invoice.total_amount_cents / (1 + effectiveVatRate)))}</span>
            </div>
          </div>
        )}
      </div>

      <div>
        <label className="text-sm text-dark-400">Déjà payé</label>
        <p className="font-medium mt-1 text-lg text-green-400">
          {formatCents(invoice.paid_amount_cents)}
        </p>
      </div>

      <div>
        <label className="text-sm text-dark-400">Reste dû</label>
        <p className={cn(
          'font-medium mt-1 text-lg',
          invoice.remaining_amount_cents === 0 ? 'text-green-400' : 'text-red-400'
        )}>
          {formatCents(invoice.remaining_amount_cents)}
        </p>
      </div>

      {invoice.payment_method && (
        <div>
          <label className="text-sm text-dark-400">Méthode de paiement</label>
          <div className="flex items-center gap-2 mt-1">
            <CreditCard className="w-4 h-4 text-dark-400" />
            <span>{PAYMENT_METHOD_LABELS[invoice.payment_method]}</span>
          </div>
        </div>
      )}

      {invoice.payment_date && (
        <div>
          <label className="text-sm text-dark-400">Date de paiement</label>
          <div className="flex items-center gap-2 mt-1">
            <Calendar className="w-4 h-4 text-green-400" />
            <span>{formatDate(invoice.payment_date)}</span>
          </div>
        </div>
      )}
    </div>
  )
}
