/**
 * Tests unitaires pour components/ui/Textarea.tsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Textarea } from '../Textarea'

describe('Textarea - rendu de base', () => {
  it('rend un textarea', () => {
    render(<Textarea />)
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('affiche le label si fourni', () => {
    render(<Textarea label="Description" />)
    expect(screen.getByText('Description')).toBeInTheDocument()
  })

  it('le label est lié au textarea via htmlFor', () => {
    render(<Textarea label="Notes" id="notes-field" />)
    expect(screen.getByText('Notes')).toHaveAttribute('for', 'notes-field')
  })

  it('affiche le hint si fourni (sans erreur)', () => {
    render(<Textarea hint="Maximum 500 caractères" />)
    expect(screen.getByText('Maximum 500 caractères')).toBeInTheDocument()
  })

  it('affiche l\'erreur si fournie', () => {
    render(<Textarea error="Ce champ est requis" />)
    expect(screen.getByText('Ce champ est requis')).toBeInTheDocument()
  })

  it('hint masqué si erreur présente', () => {
    render(<Textarea hint="Aide" error="Erreur" />)
    expect(screen.queryByText('Aide')).toBeNull()
  })

  it('rows=4 par défaut', () => {
    render(<Textarea />)
    expect(screen.getByRole('textbox')).toHaveAttribute('rows', '4')
  })

  it('rows personnalisé', () => {
    render(<Textarea rows={8} />)
    expect(screen.getByRole('textbox')).toHaveAttribute('rows', '8')
  })
})

describe('Textarea - disabled', () => {
  it('disabled=true : textarea désactivé', () => {
    render(<Textarea disabled />)
    expect(screen.getByRole('textbox')).toBeDisabled()
  })
})

describe('Textarea - onChange', () => {
  it('onChange appelé à la saisie', () => {
    const onChange = vi.fn()
    render(<Textarea onChange={onChange} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Texte test' } })
    expect(onChange).toHaveBeenCalled()
  })
})

describe('Textarea - resize', () => {
  const resizes = ['none', 'vertical', 'horizontal', 'both'] as const

  for (const resize of resizes) {
    it(`resize="${resize}" se rend sans erreur`, () => {
      render(<Textarea resize={resize} />)
      expect(screen.getByRole('textbox')).toBeInTheDocument()
    })
  }
})

describe('Textarea - forwardRef', () => {
  it('transmet la ref au textarea', () => {
    const ref = { current: null } as React.RefObject<HTMLTextAreaElement>
    render(<Textarea ref={ref} />)
    expect(ref.current).not.toBeNull()
    expect(ref.current?.tagName).toBe('TEXTAREA')
  })
})

describe('Textarea - displayName', () => {
  it('displayName = "Textarea"', () => {
    expect(Textarea.displayName).toBe('Textarea')
  })
})
