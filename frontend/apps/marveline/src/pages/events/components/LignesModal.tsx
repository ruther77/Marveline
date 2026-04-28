import { BottomSheet as Modal } from '@shared/components/ui/BottomSheet'
import { formatCents } from '@/lib/utils'
import type { ReservationDetail } from '@/types/reservation'
import { Link } from '@tanstack/react-router'
import { Package } from 'lucide-react'

interface Props {
  isOpen: boolean
  onClose: () => void
  reservation: ReservationDetail
}

export function LignesModal({ isOpen, onClose, reservation }: Props) {
  const lines = reservation.lines ?? []
  const rentalDays = reservation.rental_days ?? 1

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Articles (${lines.length})`} size="lg">
      {lines.length === 0 ? (
        <p className="text-sm text-[var(--muted)] py-8 text-center">Aucun article</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[var(--muted)] border-b border-[var(--border)]">
                <th className="py-2 pr-4">Produit</th>
                <th className="py-2 pr-4 text-right">Qté</th>
                <th className="py-2 pr-4 text-right">Prix/j</th>
                <th className="py-2 pr-4 text-right">Jours</th>
                <th className="py-2 text-right">Sous-total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {lines.map((line) => {
                const name = line.variant?.label || line.product?.name || line.bundle?.name || '—'
                return (
                  <tr key={line.id}>
                    <td className="py-2 pr-4">
                      <div className="flex gap-3 items-center">
                        <div className="w-12 h-12 rounded-lg overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center">
                          {line.product?.image_url ? (
                            <img src={line.product.image_url} alt={name} className="w-full h-full object-cover" loading="lazy" />
                          ) : (
                            <Package className="w-5 h-5 text-dark-600" />
                          )}
                        </div>
                        <span>{name}</span>
                      </div>
                    </td>
                    <td className="py-2 pr-4 text-right">{line.quantity}</td>
                    <td className="py-2 pr-4 text-right">{formatCents(line.unit_price_cents)}</td>
                    <td className="py-2 pr-4 text-right">{rentalDays}</td>
                    <td className="py-2 text-right font-medium">{formatCents(line.subtotal_cents)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between pt-4 border-t border-[var(--border)] mt-4">
        <span className="text-sm text-[var(--muted)]">Total estimé</span>
        <span className="font-semibold">{formatCents(reservation.total_amount_cents)}</span>
      </div>

      {reservation.status === 'draft' && (
        <div className="mt-4">
          <Link
            to="/reservations/$id/lines"
            params={{ id: String(reservation.id) }}
            className="btn-secondary btn-sm w-full text-center"
          >
            Modifier les lignes
          </Link>
        </div>
      )}
    </Modal>
  )
}
