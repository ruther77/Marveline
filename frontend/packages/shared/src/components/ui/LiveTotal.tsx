interface TotalLine {
  quantity: number
  unit_price_cents: number
  discount_pct?: number
}

interface LiveTotalProps {
  lines: TotalLine[]
  tva_rate?: number // ex: 0.20
  className?: string
}

function formatCents(cents: number): string {
  return (cents / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
}

export function LiveTotal({ lines, tva_rate = 0.2, className }: LiveTotalProps) {
  const subtotal = lines.reduce((acc, l) => {
    const lineTotal = l.quantity * l.unit_price_cents
    const discount = l.discount_pct ? Math.round(lineTotal * l.discount_pct) : 0
    return acc + lineTotal - discount
  }, 0)

  const tva = Math.round(subtotal * tva_rate)
  const total = subtotal + tva

  return (
    <div className={`rounded-lg border border-dark-600 bg-dark-900 p-4 space-y-2 ${className ?? ''}`}>
      <div className="flex justify-between text-sm text-dark-300">
        <span>Sous-total HT</span>
        <span>{formatCents(subtotal)}</span>
      </div>
      <div className="flex justify-between text-sm text-dark-300">
        <span>TVA ({(tva_rate * 100).toFixed(0)} %)</span>
        <span>{formatCents(tva)}</span>
      </div>
      <div className="border-t border-dark-600 pt-2 flex justify-between text-base font-semibold">
        <span>Total TTC</span>
        <span className="text-primary-400">{formatCents(total)}</span>
      </div>
    </div>
  )
}
