import { formatCents } from '@/lib/utils'
import type { DevisDetailFull } from '@/types/devis'

interface DevisLinesTableProps {
  devis: Pick<DevisDetailFull, 'lines' | 'discount_pct' | 'subtotal_cents' | 'total_cents' | 'tva_cents' | 'tva_rate' | 'caution_amount_cents' | 'total_weight_kg' | 'total_volume_liters' | 'delivery_fee_cents'>
}

export function DevisLinesTable({ devis }: DevisLinesTableProps) {
  return (
    <div className="card p-0 overflow-hidden">
      <div className="px-4 py-4 border-b border-dark-600">
        <h2 className="font-medium">Articles</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-dark-600 text-dark-400">
              <th className="text-left px-4 py-4 font-medium">Produit</th>
              <th className="text-center px-4 py-4 font-medium">Qté</th>
              <th className="text-right px-4 py-4 font-medium">PU HT</th>
              <th className="text-right px-4 py-4 font-medium">Sous-total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-dark-600">
            {(devis.lines ?? []).map((l) => (
              <tr key={l.id}>
                <td className="px-4 py-4">{l.label}</td>
                <td className="px-4 py-4 text-center text-dark-300">{l.quantity}</td>
                <td className="px-4 py-4 text-right text-dark-300">{formatCents(l.unit_price_cents)}</td>
                <td className="px-4 py-4 text-right font-medium">{formatCents(l.subtotal_cents)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot className="border-t border-dark-600">
            {devis.discount_pct ? (
              <tr>
                <td colSpan={3} className="px-4 py-2 text-right text-dark-400 text-sm">
                  Remise ({(devis.discount_pct / 100).toFixed(devis.discount_pct % 100 === 0 ? 0 : 1)}%)
                </td>
                <td className="px-4 py-2 text-right text-orange-400">
                  -{formatCents(devis.subtotal_cents - (devis.total_cents - devis.tva_cents - (devis.delivery_fee_cents ?? 0)))}
                </td>
              </tr>
            ) : null}
            <tr>
              <td colSpan={3} className="px-4 py-2 text-right text-dark-400 text-sm">Sous-total HT</td>
              <td className="px-4 py-2 text-right">{formatCents(devis.subtotal_cents)}</td>
            </tr>
            <tr>
              <td colSpan={3} className="px-4 py-2 text-right text-dark-400 text-sm">
                TVA ({(devis.tva_rate / 100).toFixed(0)}%)
              </td>
              <td className="px-4 py-2 text-right">{formatCents(devis.tva_cents)}</td>
            </tr>
            {(devis.delivery_fee_cents ?? 0) > 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-2 text-right text-dark-400 text-sm">Frais livraison</td>
                <td className="px-4 py-2 text-right">{formatCents(devis.delivery_fee_cents!)}</td>
              </tr>
            )}
            <tr className="bg-dark-900/40">
              <td colSpan={3} className="px-4 py-4 text-right font-semibold">Total TTC</td>
              <td className="px-4 py-4 text-right text-gold-400 font-bold text-base">{formatCents(devis.total_cents)}</td>
            </tr>
            {(devis.caution_amount_cents ?? 0) > 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-2 text-right text-dark-400 text-sm">Caution</td>
                <td className="px-4 py-2 text-right text-dark-300">{formatCents(devis.caution_amount_cents!)}</td>
              </tr>
            )}
          </tfoot>
        </table>
      </div>
      {(devis.total_weight_kg || devis.total_volume_liters) ? (
        <div className="px-4 py-3 border-t border-dark-600 flex items-center gap-4 text-sm text-dark-300">
          <span className="font-medium text-dark-200">Logistique</span>
          {devis.total_weight_kg ? (
            <span>{devis.total_weight_kg.toFixed(1).replace('.', ',')} kg</span>
          ) : null}
          {devis.total_volume_liters ? (
            <span>{devis.total_volume_liters.toFixed(1).replace('.', ',')} L</span>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
