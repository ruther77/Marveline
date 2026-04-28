import { CreditCard } from 'lucide-react'
import { formatDate, formatCents } from '@/lib/utils'
import { PAYMENT_METHOD_LABELS } from '@/lib/constants'
import type { Payment } from '@/types/payment'

interface InvoicePaymentHistoryProps {
  payments: Payment[]
}

export function InvoicePaymentHistory({ payments }: InvoicePaymentHistoryProps) {
  if (payments.length === 0) return null

  return (
    <div className="border-t border-dark-600 pt-4">
      <h4 className="text-sm font-medium text-dark-300 mb-2 flex items-center gap-2">
        <CreditCard className="w-4 h-4" />
        Historique paiements ({payments.length})
      </h4>
      <div className="space-y-0.5">
        {payments.map((p) => (
          <div
            key={p.id}
            className="flex items-center justify-between text-sm py-1.5 border-b border-dark-600 last:border-0"
          >
            <div className="flex items-center gap-2">
              <span className="text-dark-400">{formatDate(p.payment_date)}</span>
              <span className="text-xs bg-dark-900 text-dark-300 px-1.5 py-0.5 rounded">
                {PAYMENT_METHOD_LABELS[p.payment_method]}
              </span>
              {p.notes && (
                <span className="text-xs text-dark-500 italic truncate max-w-[120px]">{p.notes}</span>
              )}
            </div>
            <span className="font-medium text-green-400">{formatCents(p.amount_cents)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
