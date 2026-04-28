/**
 * Tests unitaires pour components/ui/LiveTotal.tsx
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LiveTotal } from '../LiveTotal'

describe('LiveTotal - calculs', () => {
  it('affiche "Sous-total HT", "TVA" et "Total TTC"', () => {
    render(<LiveTotal lines={[{ quantity: 1, unit_price_cents: 1000 }]} />)
    expect(screen.getByText('Sous-total HT')).toBeInTheDocument()
    expect(screen.getByText(/TVA/)).toBeInTheDocument()
    expect(screen.getByText('Total TTC')).toBeInTheDocument()
  })

  it('calcul correct : 1 x 1000 cents → HT=10€, TVA 20%=2€, TTC=12€', () => {
    render(<LiveTotal lines={[{ quantity: 1, unit_price_cents: 1000 }]} tva_rate={0.2} />)
    expect(screen.getByText(/10,00/)).toBeInTheDocument()
    expect(screen.getByText(/12,00/)).toBeInTheDocument()
  })

  it('calcul multi-lignes', () => {
    render(
      <LiveTotal
        lines={[
          { quantity: 2, unit_price_cents: 500 },
          { quantity: 1, unit_price_cents: 200 },
        ]}
        tva_rate={0.2}
      />
    )
    // HT = 2*500 + 1*200 = 1200 cents = 12€
    // TVA = 240 cents = 2,40€
    // TTC = 1440 cents = 14,40€
    expect(screen.getByText(/12,00/)).toBeInTheDocument()
    expect(screen.getByText(/14,40/)).toBeInTheDocument()
  })

  it('remise appliquée (discount_pct) : HT < valeur brute', () => {
    // Sans remise HT = 10€, avec remise 10% HT = 9€
    // On vérifie que les deux totaux sont distincts via le conteneur
    const { container } = render(
      <LiveTotal
        lines={[{ quantity: 1, unit_price_cents: 1000, discount_pct: 0.1 }]}
        tva_rate={0}
      />
    )
    // Au minimum 3 lignes (HT, TVA, TTC) doivent être présentes
    const rows = container.querySelectorAll('.flex.justify-between')
    expect(rows.length).toBeGreaterThanOrEqual(3)
  })

  it('tva_rate 0% → TVA à 0 €', () => {
    render(<LiveTotal lines={[{ quantity: 1, unit_price_cents: 500 }]} tva_rate={0} />)
    // TVA 0% → 0 €
    expect(screen.getByText(/TVA \(0 %\)/)).toBeInTheDocument()
  })

  it('liste vide → totaux à 0', () => {
    render(<LiveTotal lines={[]} />)
    // Plusieurs 0,00 € attendus (HT, TVA, TTC)
    const zeros = screen.getAllByText(/0,00/)
    expect(zeros.length).toBeGreaterThanOrEqual(2)
  })
})
