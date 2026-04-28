/**
 * Tests unitaires pour components/ui/Checkbox.tsx
 * Checkbox, CheckboxGroup
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Checkbox, CheckboxGroup } from '../Checkbox'

// ─── Checkbox ─────────────────────────────────────────────────────────────────

describe('Checkbox - rendu de base', () => {
  it('rend un input de type checkbox', () => {
    render(<Checkbox />)
    expect(screen.getByRole('checkbox')).toBeInTheDocument()
  })

  it('affiche le label si fourni', () => {
    render(<Checkbox label="Accepter les CGU" />)
    expect(screen.getByText('Accepter les CGU')).toBeInTheDocument()
  })

  it('affiche la description si fournie', () => {
    render(<Checkbox label="Option" description="Description ici" />)
    expect(screen.getByText('Description ici')).toBeInTheDocument()
  })

  it('affiche le message d\'erreur si fourni', () => {
    render(<Checkbox label="Option" error="Ce champ est requis" />)
    expect(screen.getByText('Ce champ est requis')).toBeInTheDocument()
  })
})

describe('Checkbox - disabled', () => {
  it('disabled=true : input est désactivé', () => {
    render(<Checkbox disabled />)
    expect(screen.getByRole('checkbox')).toBeDisabled()
  })
})

describe('Checkbox - checked', () => {
  it('checked=true : input est coché', () => {
    const onChange = vi.fn()
    render(<Checkbox checked onChange={onChange} />)
    expect(screen.getByRole('checkbox')).toBeChecked()
  })

  it('checked=false : input n\'est pas coché', () => {
    const onChange = vi.fn()
    render(<Checkbox checked={false} onChange={onChange} />)
    expect(screen.getByRole('checkbox')).not.toBeChecked()
  })

  it('onChange est appelé au clic', () => {
    const onChange = vi.fn()
    render(<Checkbox onChange={onChange} />)
    fireEvent.click(screen.getByRole('checkbox'))
    expect(onChange).toHaveBeenCalled()
  })
})

describe('Checkbox - indeterminate', () => {
  it('indeterminate=true sans checked : rend l\'état intermédiaire', () => {
    const { container } = render(<Checkbox indeterminate />)
    // Le svg Minus est rendu quand indeterminate=true et checked=false
    const svg = container.querySelector('svg')
    expect(svg).not.toBeNull()
  })
})

describe('Checkbox - forwardRef', () => {
  it('transmet la ref à l\'input', () => {
    const ref = { current: null } as React.RefObject<HTMLInputElement>
    render(<Checkbox ref={ref} />)
    expect(ref.current).not.toBeNull()
    expect(ref.current?.type).toBe('checkbox')
  })
})

describe('Checkbox - displayName', () => {
  it('displayName = "Checkbox"', () => {
    expect(Checkbox.displayName).toBe('Checkbox')
  })
})

// ─── CheckboxGroup ────────────────────────────────────────────────────────────

describe('CheckboxGroup - rendu de base', () => {
  const options = [
    { value: 'a', label: 'Option A' },
    { value: 'b', label: 'Option B' },
    { value: 'c', label: 'Option C' },
  ]

  it('affiche toutes les options', () => {
    const onChange = vi.fn()
    render(<CheckboxGroup options={options} value={[]} onChange={onChange} />)
    expect(screen.getByText('Option A')).toBeInTheDocument()
    expect(screen.getByText('Option B')).toBeInTheDocument()
    expect(screen.getByText('Option C')).toBeInTheDocument()
  })

  it('affiche le label du groupe si fourni', () => {
    const onChange = vi.fn()
    render(<CheckboxGroup label="Choisir" options={options} value={[]} onChange={onChange} />)
    expect(screen.getByText('Choisir')).toBeInTheDocument()
  })

  it('options sélectionnées sont cochées', () => {
    const onChange = vi.fn()
    render(<CheckboxGroup options={options} value={['a', 'c']} onChange={onChange} />)
    const checkboxes = screen.getAllByRole('checkbox')
    expect(checkboxes[0]).toBeChecked()
    expect(checkboxes[1]).not.toBeChecked()
    expect(checkboxes[2]).toBeChecked()
  })
})

describe('CheckboxGroup - onChange', () => {
  const options = [
    { value: 'a', label: 'A' },
    { value: 'b', label: 'B' },
  ]

  it('cocher une option ajoute sa valeur', () => {
    const onChange = vi.fn()
    render(<CheckboxGroup options={options} value={[]} onChange={onChange} />)
    fireEvent.click(screen.getAllByRole('checkbox')[0])
    expect(onChange).toHaveBeenCalledWith(['a'])
  })

  it('décocher une option la retire', () => {
    const onChange = vi.fn()
    render(<CheckboxGroup options={options} value={['a', 'b']} onChange={onChange} />)
    fireEvent.click(screen.getAllByRole('checkbox')[0])
    expect(onChange).toHaveBeenCalledWith(['b'])
  })
})

describe('CheckboxGroup - erreur', () => {
  it('affiche le message d\'erreur', () => {
    const onChange = vi.fn()
    render(
      <CheckboxGroup
        options={[{ value: 'x', label: 'X' }]}
        value={[]}
        onChange={onChange}
        error="Sélectionnez au moins un élément"
      />
    )
    expect(screen.getByText('Sélectionnez au moins un élément')).toBeInTheDocument()
  })
})
