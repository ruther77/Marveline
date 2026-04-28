/**
 * Tests unitaires pour components/ui/Input.tsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Input } from '../Input'

describe('Input - rendu de base', () => {
  it('rend un input de type text par défaut', () => {
    render(<Input />)
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('affiche le label si fourni', () => {
    render(<Input label="Nom" />)
    expect(screen.getByText('Nom')).toBeInTheDocument()
  })

  it('le label est lié à l\'input via htmlFor', () => {
    render(<Input label="Email" id="email-input" />)
    const label = screen.getByText('Email')
    expect(label).toHaveAttribute('for', 'email-input')
  })

  it('affiche le hint si fourni (sans erreur)', () => {
    render(<Input hint="Format: prenom.nom@exemple.fr" />)
    expect(screen.getByText('Format: prenom.nom@exemple.fr')).toBeInTheDocument()
  })

  it('affiche l\'erreur si fournie', () => {
    render(<Input error="Ce champ est requis" />)
    expect(screen.getByText('Ce champ est requis')).toBeInTheDocument()
  })

  it('hint masqué si erreur présente', () => {
    render(<Input hint="Aide" error="Erreur" />)
    expect(screen.queryByText('Aide')).toBeNull()
    expect(screen.getByText('Erreur')).toBeInTheDocument()
  })
})

describe('Input - disabled', () => {
  it('disabled=true : input désactivé', () => {
    render(<Input disabled />)
    expect(screen.getByRole('textbox')).toBeDisabled()
  })
})

describe('Input - valeur et onChange', () => {
  it('onChange appelé à la saisie', () => {
    const onChange = vi.fn()
    render(<Input onChange={onChange} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'test' } })
    expect(onChange).toHaveBeenCalled()
  })
})

describe('Input - icônes', () => {
  it('affiche leftIcon si fourni', () => {
    render(<Input leftIcon={<span data-testid="left-icon">L</span>} />)
    expect(screen.getByTestId('left-icon')).toBeInTheDocument()
  })

  it('affiche rightIcon si fourni', () => {
    render(<Input rightIcon={<span data-testid="right-icon">R</span>} />)
    expect(screen.getByTestId('right-icon')).toBeInTheDocument()
  })

  it('affiche rightElement si fourni (prioritaire sur rightIcon)', () => {
    render(
      <Input
        rightElement={<button data-testid="right-elem">X</button>}
        rightIcon={<span data-testid="right-icon">R</span>}
      />
    )
    expect(screen.getByTestId('right-elem')).toBeInTheDocument()
    expect(screen.queryByTestId('right-icon')).toBeNull()
  })
})

describe('Input - forwardRef', () => {
  it('transmet la ref à l\'input', () => {
    const ref = { current: null } as React.RefObject<HTMLInputElement>
    render(<Input ref={ref} />)
    expect(ref.current).not.toBeNull()
    expect(ref.current?.tagName).toBe('INPUT')
  })
})

describe('Input - displayName', () => {
  it('displayName = "Input"', () => {
    expect(Input.displayName).toBe('Input')
  })
})
