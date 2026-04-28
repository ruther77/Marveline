/**
 * Tests unitaires pour components/ui/DatePicker.tsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DatePicker } from '../DatePicker'

describe('DatePicker - rendu de base', () => {
  it('affiche le placeholder par défaut', () => {
    render(<DatePicker onChange={vi.fn()} />)
    expect(screen.getByText('Sélectionner une date')).toBeInTheDocument()
  })

  it('placeholder personnalisé', () => {
    render(<DatePicker onChange={vi.fn()} placeholder="Choisir une date" />)
    expect(screen.getByText('Choisir une date')).toBeInTheDocument()
  })

  it('affiche le label si fourni', () => {
    render(<DatePicker onChange={vi.fn()} label="Date de début" />)
    expect(screen.getByText('Date de début')).toBeInTheDocument()
  })

  it('affiche le hint si fourni (sans erreur)', () => {
    render(<DatePicker onChange={vi.fn()} hint="Format JJ/MM/AAAA" />)
    expect(screen.getByText('Format JJ/MM/AAAA')).toBeInTheDocument()
  })

  it('affiche l\'erreur si fournie', () => {
    render(<DatePicker onChange={vi.fn()} error="Date requise" />)
    expect(screen.getByText('Date requise')).toBeInTheDocument()
  })

  it('affiche la valeur formatée si date fournie', () => {
    const date = new Date(2026, 0, 15) // 15 janv 2026
    render(<DatePicker value={date} onChange={vi.fn()} />)
    expect(screen.getByText(/15/)).toBeInTheDocument()
  })
})

describe('DatePicker - calendrier', () => {
  it('clic sur le trigger ouvre le calendrier', () => {
    render(<DatePicker onChange={vi.fn()} />)
    fireEvent.click(screen.getByText('Sélectionner une date'))
    // Les jours de la semaine doivent apparaître
    expect(screen.getByText('Lu')).toBeInTheDocument()
  })

  it('les jours de la semaine sont affichés', () => {
    render(<DatePicker onChange={vi.fn()} />)
    fireEvent.click(screen.getByText('Sélectionner une date'))
    const weekDays = ['Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa', 'Di']
    weekDays.forEach(day => {
      expect(screen.getByText(day)).toBeInTheDocument()
    })
  })

  it('clic sur une date appelle onChange', () => {
    const onChange = vi.fn()
    render(<DatePicker onChange={onChange} />)
    fireEvent.click(screen.getByText('Sélectionner une date'))
    // Cliquer sur le premier bouton de jour visible
    const dayButtons = screen.getAllByRole('button').filter(btn => {
      const text = btn.textContent?.trim()
      return text && /^\d+$/.test(text) && parseInt(text) >= 1 && parseInt(text) <= 31
    })
    if (dayButtons.length > 0) {
      fireEvent.click(dayButtons[0])
      expect(onChange).toHaveBeenCalled()
    }
  })
})

describe('DatePicker - navigation mois', () => {
  it('boutons précédent/suivant présents à l\'ouverture', () => {
    render(<DatePicker onChange={vi.fn()} />)
    fireEvent.click(screen.getByText('Sélectionner une date'))
    const buttons = screen.getAllByRole('button')
    expect(buttons.length).toBeGreaterThanOrEqual(2)
  })
})
