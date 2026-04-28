/**
 * Tests unitaires pour components/ui/Radio.tsx
 * Radio, RadioGroup, RadioCards
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Radio, RadioGroup, RadioCards } from '../Radio'

// ─── Radio ────────────────────────────────────────────────────────────────────

describe('Radio - rendu de base', () => {
  it('rend un input de type radio', () => {
    render(<Radio name="test" value="a" />)
    expect(screen.getByRole('radio')).toBeInTheDocument()
  })

  it('affiche le label si fourni', () => {
    render(<Radio name="test" value="a" label="Option A" />)
    expect(screen.getByText('Option A')).toBeInTheDocument()
  })

  it('affiche la description si fournie', () => {
    render(<Radio name="test" value="a" label="Option" description="Détail de l'option" />)
    expect(screen.getByText("Détail de l'option")).toBeInTheDocument()
  })
})

describe('Radio - disabled', () => {
  it('disabled=true : input désactivé', () => {
    render(<Radio name="test" value="a" disabled />)
    expect(screen.getByRole('radio')).toBeDisabled()
  })
})

describe('Radio - checked', () => {
  it('checked=true : input coché', () => {
    render(<Radio name="test" value="a" checked onChange={vi.fn()} />)
    expect(screen.getByRole('radio')).toBeChecked()
  })

  it('checked=false : input non coché', () => {
    render(<Radio name="test" value="a" checked={false} onChange={vi.fn()} />)
    expect(screen.getByRole('radio')).not.toBeChecked()
  })

  it('onChange appelé au clic', () => {
    const onChange = vi.fn()
    render(<Radio name="test" value="a" onChange={onChange} />)
    fireEvent.click(screen.getByRole('radio'))
    expect(onChange).toHaveBeenCalled()
  })
})

describe('Radio - forwardRef', () => {
  it('transmet la ref à l\'input', () => {
    const ref = { current: null } as React.RefObject<HTMLInputElement>
    render(<Radio ref={ref} name="test" value="a" />)
    expect(ref.current).not.toBeNull()
    expect(ref.current?.type).toBe('radio')
  })
})

describe('Radio - displayName', () => {
  it('displayName = "Radio"', () => {
    expect(Radio.displayName).toBe('Radio')
  })
})

// ─── RadioGroup ───────────────────────────────────────────────────────────────

describe('RadioGroup - rendu de base', () => {
  const options = [
    { value: 'a', label: 'Option A' },
    { value: 'b', label: 'Option B' },
    { value: 'c', label: 'Option C', disabled: true },
  ]

  it('a role="radiogroup"', () => {
    render(<RadioGroup options={options} value="a" onChange={vi.fn()} name="grp" />)
    expect(screen.getByRole('radiogroup')).toBeInTheDocument()
  })

  it('affiche toutes les options', () => {
    render(<RadioGroup options={options} value="a" onChange={vi.fn()} name="grp" />)
    expect(screen.getByText('Option A')).toBeInTheDocument()
    expect(screen.getByText('Option B')).toBeInTheDocument()
    expect(screen.getByText('Option C')).toBeInTheDocument()
  })

  it('affiche le label du groupe si fourni', () => {
    render(<RadioGroup options={options} value="a" onChange={vi.fn()} name="grp" label="Groupe" />)
    expect(screen.getByText('Groupe')).toBeInTheDocument()
  })

  it('la valeur sélectionnée est cochée', () => {
    render(<RadioGroup options={options} value="b" onChange={vi.fn()} name="grp" />)
    const radios = screen.getAllByRole('radio')
    expect(radios[0]).not.toBeChecked()
    expect(radios[1]).toBeChecked()
  })

  it('onChange appelé avec la valeur correcte', () => {
    const onChange = vi.fn()
    render(<RadioGroup options={options} value="a" onChange={onChange} name="grp" />)
    fireEvent.click(screen.getAllByRole('radio')[1])
    expect(onChange).toHaveBeenCalledWith('b')
  })

  it('affiche message d\'erreur', () => {
    render(
      <RadioGroup
        options={options}
        value=""
        onChange={vi.fn()}
        name="grp"
        error="Sélection requise"
      />
    )
    expect(screen.getByText('Sélection requise')).toBeInTheDocument()
  })
})

describe('RadioGroup - orientation', () => {
  const options = [{ value: 'a', label: 'A' }, { value: 'b', label: 'B' }]

  it('orientation vertical par défaut', () => {
    render(<RadioGroup options={options} value="a" onChange={vi.fn()} name="grp" />)
    expect(screen.getByRole('radiogroup')).toBeInTheDocument()
  })

  it('orientation horizontal se rend', () => {
    render(
      <RadioGroup
        options={options}
        value="a"
        onChange={vi.fn()}
        name="grp"
        orientation="horizontal"
      />
    )
    expect(screen.getByRole('radiogroup')).toBeInTheDocument()
  })
})

// ─── RadioCards ───────────────────────────────────────────────────────────────

describe('RadioCards - rendu de base', () => {
  const options = [
    { value: 'x', label: 'Carte X', description: 'Desc X' },
    { value: 'y', label: 'Carte Y' },
  ]

  it('affiche tous les labels', () => {
    render(<RadioCards options={options} value="x" onChange={vi.fn()} name="cards" />)
    expect(screen.getByText('Carte X')).toBeInTheDocument()
    expect(screen.getByText('Carte Y')).toBeInTheDocument()
  })

  it('affiche la description si fournie', () => {
    render(<RadioCards options={options} value="x" onChange={vi.fn()} name="cards" />)
    expect(screen.getByText('Desc X')).toBeInTheDocument()
  })

  it('onChange appelé au clic', () => {
    const onChange = vi.fn()
    render(<RadioCards options={options} value="x" onChange={onChange} name="cards" />)
    const radios = screen.getAllByRole('radio')
    fireEvent.click(radios[1])
    expect(onChange).toHaveBeenCalledWith('y')
  })
})
