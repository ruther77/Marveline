import { BottomSheet as Modal } from '@shared/components/ui/BottomSheet'
import { Link } from '@tanstack/react-router'
import { useInvoicesList } from '@/api/queries/useInvoices'
import { DomainStatusBadge } from '@shared/components/ui'
import { formatCents } from '@/lib/utils'

interface Props {
  isOpen: boolean
  onClose: () => void
  reservationId: number
}

export function FacturesModal({ isOpen, onClose, reservationId }: Props) {
  const { data, isLoading } = useInvoicesList({ reservation_id: reservationId }, isOpen)
  const invoices = data?.items ?? []

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Facturation (${invoices.length})`} size="lg">
      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          {[1, 2].map((i) => <div key={i} className="h-16 bg-dark-900 rounded" />)}
        </div>
      ) : invoices.length === 0 ? (
        <p className="text-sm text-dark-400 py-8 text-center">Aucune facture liée</p>
      ) : (
        <div className="space-y-3">
          {invoices.map((inv) => {
            const paidPct = inv.total_amount_cents > 0
              ? Math.round((inv.paid_amount_cents / inv.total_amount_cents) * 100)
              : 0

            return (
              <div key={inv.id} className="card p-4 space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{inv.invoice_number}</span>
                    <DomainStatusBadge status={inv.status} />
                  </div>
                  <span className="text-sm font-semibold">{formatCents(inv.total_amount_cents)}</span>
                </div>

                <div className="flex items-center gap-2 text-xs text-dark-400">
                  <span>Payé : {formatCents(inv.paid_amount_cents)} / {formatCents(inv.total_amount_cents)}</span>
                  <span className="text-dark-500">({paidPct}%)</span>
                </div>

                <div className="w-full h-1.5 bg-dark-900 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-green-500 rounded-full transition-all"
                    style={{ width: `${paidPct}%` }}
                  />
                </div>

                <div className="flex gap-2 pt-1">
                  <Link
                    to="/finance/invoices"
                    search={{ reservation_id: reservationId, page: 1 }}
                    className="text-xs text-primary-400 hover:text-primary-300"
                  >
                    Voir facture
                  </Link>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </Modal>
  )
}
