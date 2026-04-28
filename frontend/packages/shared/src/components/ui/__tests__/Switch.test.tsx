/**
 * Tests unitaires pour components/ui/Switch.tsx
 * Switch, LabeledSwitch
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Switch, LabeledSwitch } from '../Switch'

// ─── Switch ───────────────────────────────────────────────────────────────────

describe('Switch - rendu de base', () => {
  it('rend un input de type checkbox avec role="switch"', () => {
    render(<Switch />)
    expect(screen.getByRole('switch')).toBeInTheDocument()
  })

  it('affiche le label si fourni', () => {
    render(<Switch label="Activer les notifications" />)
    expect(screen.getByText('Activer les notifications')).toBeInTheDocument()
  })

  it('affiche la description si fournie', () => {
    render(<Switch label="Option" description="Détail de l'option" />)
    expect(screen.getByText("Détail de l'option")).toBeInTheDocument()
  })

  it('affiche le message d\'erreur si fourni', () => {
    render(<Switch label="Option" error="Champ requis" />)
    expect(screen.getByText('Champ requis')).toBeInTheDocument()
  })

  it('sans label : pas d\'élément label visible', () => {
    render(<Switch />)
    expect(screen.queryByRole('label')).toBeNull()
  })
})

describe('Switch - disabled', () => {
  it('disabled=true : input est désactivé', () => {
    render(<Switch disabled />)
    expect(screen.getByRole('switch')).toBeDisabled()
  })
})

describe('Switch - checked', () => {
  it('checked=true : input est coché', () => {
    const onChange = vi.fn()
    render(<Switch checked onChange={onChange} />)
    expect(screen.getByRole('switch')).toBeChecked()
  })

  it('checked=false : input n\'est pas coché', () => {
    const onChange = vi.fn()
    render(<Switch checked={false} onChange={onChange} />)
    expect(screen.getByRole('switch')).not.toBeChecked()
  })

  it('onChange est appelé quand le switch change', () => {
    const onChange = vi.fn()
    render(<Switch checked={false} onChange={onChange} />)
    fireEvent.click(screen.getByRole('switch'))
    expect(onChange).toHaveBeenCalled()
  })
})

describe('Switch - sizes', () => {
  const sizes = ['sm', 'md', 'lg'] as const

  for (const size of sizes) {
    it(`size ${size} se rend sans erreur`, () => {
      render(<Switch size={size} label={`size ${size}`} />)
      expect(screen.getByRole('switch')).toBeInTheDocument()
    })
  }
})

describe('Switch - forwardRef', () => {
  it('transmet la ref à l\'input', () => {
    const ref = { current: null } as React.RefObject<HTMLInputElement>
    render(<Switch ref={ref} />)
    expect(ref.current).not.toBeNull()
    expect(ref.current?.type).toBe('checkbox')
  })
})

describe('Switch - displayName', () => {
  it('displayName = "Switch"', () => {
    expect(Switch.displayName).toBe('Switch')
  })
})

// ─── LabeledSwitch ────────────────────────────────────────────────────────────

describe('LabeledSwitch', () => {
  it('affiche les labels off et on', () => {
    const onChange = vi.fn()
    render(<LabeledSwitch labelOff="Désactivé" labelOn="Activé" checked={false} onChange={onChange} />)
    expect(screen.getByText('Désactivé')).toBeInTheDocument()
    expect(screen.getByText('Activé')).toBeInTheDocument()
  })

  it('checked=false : labelOff est en text-white', () => {
    const onChange = vi.fn()
    render(<LabeledSwitch labelOff="Non" labelOn="Oui" checked={false} onChange={onChange} />)
    const offLabel = screen.getByText('Non')
    expect(offLabel.className).toContain('text-white')
  })

  it('checked=true : labelOn est en text-white', () => {
    const onChange = vi.fn()
    render(<LabeledSwitch labelOff="Non" labelOn="Oui" checked onChange={onChange} />)
    const onLabel = screen.getByText('Oui')
    expect(onLabel.className).toContain('text-white')
  })

  it('displayName = "LabeledSwitch"', () => {
    expect(LabeledSwitch.displayName).toBe('LabeledSwitch')
  })
})
