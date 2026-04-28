import { formatCents, formatDate, cn } from '@/lib/utils'
import type { InvoiceDetail } from '@/types/invoice'

interface InvoicePaymentProgressProps {
  invoice: Pick<
    InvoiceDetail,
    | 'total_amount_cents'
    | 'paid_amount_cents'
    | 'remaining_amount_cents'
    | 'payment_completion_percentage'
    | 'is_paid'
    | 'is_overdue'
    | 'due_date'
    | 'advance_rate'
    | 'advance_due_date'
  >
}

export function InvoicePaymentProgress({ invoice }: InvoicePaymentProgressProps) {
  const advanceRate = invoice.advance_rate ?? 0.4
  const advancePercent = Math.round(advanceRate * 100)
  const balancePercent = 100 - advancePercent
  const acompte = Math.round(invoice.total_amount_cents * advanceRate)
  const solde = invoice.total_amount_cents - acompte
  const acomptePaid = invoice.paid_amount_cents >= acompte
  const soldePaid = invoice.paid_amount_cents >= invoice.total_amount_cents

  return (
    <div className="space-y-4">
      {/* Barre de progression */}
      <div>
        <div className="flex justify-between text-sm mb-1">
          <span className="text-dark-400">Progression paiement</span>
          <span className="font-medium">
            {invoice.payment_completion_percentage.toFixed(0)}%
          </span>
        </div>
        <div className="w-full bg-dark-900 rounded-full h-2">
          <div
            className={cn(
              'h-2 rounded-full transition-all',
              invoice.is_paid ? 'bg-green-500' :
              invoice.payment_completion_percentage > 0 ? 'bg-primary-500' :
              'bg-dark-600'
            )}
            style={{ width: `${Math.min(100, invoice.payment_completion_percentage)}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-dark-500 mt-1">
          <span>Payé : {formatCents(invoice.paid_amount_cents)}</span>
          <span>Restant : {formatCents(invoice.remaining_amount_cents)}</span>
        </div>
      </div>

      {/* Échéances CGV */}
      <div className="card p-4 space-y-2 text-sm">
        <div className="font-medium text-dark-300 mb-1">Échéances CGV</div>
        <div className="flex justify-between items-center">
          <div>
            <span className="text-dark-400">Acompte {advancePercent}%</span>
            <span className="ml-2 font-medium">{formatCents(acompte)}</span>
          </div>
          <span className={cn(
            'text-xs px-2 py-0.5 rounded',
            acomptePaid ? 'bg-green-500/10 text-green-500' : 'bg-dark-900 text-dark-400'
          )}>
            {acomptePaid ? 'Reçu' : invoice.advance_due_date ? `Dû le ${formatDate(invoice.advance_due_date)}` : 'À la confirmation'}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <div>
            <span className="text-dark-400">Solde {balancePercent}%</span>
            <span className="ml-2 font-medium">{formatCents(solde)}</span>
          </div>
          <span className={cn(
            'text-xs px-2 py-0.5 rounded',
            soldePaid ? 'bg-green-500/10 text-green-500' :
            invoice.is_overdue ? 'bg-red-500/10 text-red-400' :
            'bg-dark-900 text-dark-400'
          )}>
            {soldePaid ? 'Reçu' : `Dû le ${formatDate(invoice.due_date)}`}
          </span>
        </div>
      </div>
    </div>
  )
}
