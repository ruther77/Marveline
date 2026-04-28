/**
 * Tests unitaires pour components/ui/Dropdown.tsx
 * Dropdown, DropdownItem, DropdownSeparator, DropdownLabel, SelectDropdown
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import {
  Dropdown,
  DropdownItem,
  DropdownSeparator,
  DropdownLabel,
  SelectDropdown,
} from '../Dropdown'

// ─── Dropdown ─────────────────────────────────────────────────────────────────

describe('Dropdown - rendu de base', () => {
  it('affiche le trigger', () => {
    render(
      <Dropdown trigger={<button>Menu</button>}>
        <DropdownItem>Item 1</DropdownItem>
      </Dropdown>
    )
    expect(screen.getByText('Menu')).toBeInTheDocument()
  })

  it('contenu masqué par défaut', () => {
    render(
      <Dropdown trigger={<button>Menu</button>}>
        <DropdownItem>Item 1</DropdownItem>
      </Dropdown>
    )
    expect(screen.queryByText('Item 1')).toBeNull()
  })

  it('clic sur trigger ouvre le dropdown', () => {
    render(
      <Dropdown trigger={<button>Menu</button>}>
        <DropdownItem>Item 1</DropdownItem>
      </Dropdown>
    )
    fireEvent.click(screen.getByText('Menu'))
    expect(screen.getByText('Item 1')).toBeInTheDocument()
  })

  it('second clic sur trigger ferme le dropdown', () => {
    render(
      <Dropdown trigger={<button>Menu</button>}>
        <DropdownItem>Item 1</DropdownItem>
      </Dropdown>
    )
    fireEvent.click(screen.getByText('Menu'))
    fireEvent.click(screen.getByText('Menu'))
    expect(screen.queryByText('Item 1')).toBeNull()
  })
})

describe('Dropdown - closeOnSelect', () => {
  it('clic sur un item ferme le dropdown (closeOnSelect=true par défaut)', () => {
    render(
      <Dropdown trigger={<button>Menu</button>}>
        <DropdownItem onClick={vi.fn()}>Item 1</DropdownItem>
      </Dropdown>
    )
    fireEvent.click(screen.getByText('Menu'))
    fireEvent.click(screen.getByText('Item 1'))
    expect(screen.queryByText('Item 1')).toBeNull()
  })

  it('closeOnSelect=false : clic sur item ne ferme pas', () => {
    render(
      <Dropdown trigger={<button>Menu</button>} closeOnSelect={false}>
        <DropdownItem onClick={vi.fn()}>Item 1</DropdownItem>
      </Dropdown>
    )
    fireEvent.click(screen.getByText('Menu'))
    fireEvent.click(screen.getByText('Item 1'))
    expect(screen.getByText('Item 1')).toBeInTheDocument()
  })
})

// ─── DropdownItem ─────────────────────────────────────────────────────────────

describe('DropdownItem', () => {
  it('affiche le contenu', () => {
    render(
      <Dropdown trigger={<button>T</button>}>
        <DropdownItem>Action</DropdownItem>
      </Dropdown>
    )
    fireEvent.click(screen.getByText('T'))
    expect(screen.getByText('Action')).toBeInTheDocument()
  })

  it('onClick appelé au clic', () => {
    const onClick = vi.fn()
    render(
      <Dropdown trigger={<button>T</button>}>
        <DropdownItem onClick={onClick}>Cliquer</DropdownItem>
      </Dropdown>
    )
    fireEvent.click(screen.getByText('T'))
    fireEvent.click(screen.getByText('Cliquer'))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('disabled=true : bouton désactivé', () => {
    render(
      <Dropdown trigger={<button>T</button>}>
        <DropdownItem disabled>Désactivé</DropdownItem>
      </Dropdown>
    )
    fireEvent.click(screen.getByText('T'))
    expect(screen.getByText('Désactivé').closest('button')).toBeDisabled()
  })

  it('affiche shortcut si fourni', () => {
    render(
      <Dropdown trigger={<button>T</button>}>
        <DropdownItem shortcut="⌘K">Raccourci</DropdownItem>
      </Dropdown>
    )
    fireEvent.click(screen.getByText('T'))
    expect(screen.getByText('⌘K')).toBeInTheDocument()
  })

  it('affiche icon si fourni', () => {
    render(
      <Dropdown trigger={<button>T</button>}>
        <DropdownItem icon={<span data-testid="ico">★</span>}>Avec icône</DropdownItem>
      </Dropdown>
    )
    fireEvent.click(screen.getByText('T'))
    expect(screen.getByTestId('ico')).toBeInTheDocument()
  })
})

// ─── DropdownSeparator / DropdownLabel ────────────────────────────────────────

describe('DropdownSeparator', () => {
  it('rend un séparateur', () => {
    const { container } = render(
      <Dropdown trigger={<button>T</button>}>
        <DropdownItem>A</DropdownItem>
        <DropdownSeparator />
        <DropdownItem>B</DropdownItem>
      </Dropdown>
    )
    fireEvent.click(screen.getByText('T'))
    expect(container.querySelector('.border-t')).not.toBeNull()
  })
})

describe('DropdownLabel', () => {
  it('affiche le label de section', () => {
    render(
      <Dropdown trigger={<button>T</button>}>
        <DropdownLabel>Section</DropdownLabel>
        <DropdownItem>A</DropdownItem>
      </Dropdown>
    )
    fireEvent.click(screen.getByText('T'))
    expect(screen.getByText('Section')).toBeInTheDocument()
  })
})

// ─── SelectDropdown ───────────────────────────────────────────────────────────

describe('SelectDropdown - rendu de base', () => {
  const options = [
    { value: 'a', label: 'Option A' },
    { value: 'b', label: 'Option B' },
  ]

  it('affiche le placeholder si aucune valeur', () => {
    render(<SelectDropdown options={options} value="" onChange={vi.fn()} />)
    expect(screen.getByText('Sélectionner...')).toBeInTheDocument()
  })

  it('affiche la valeur sélectionnée', () => {
    render(<SelectDropdown options={options} value="a" onChange={vi.fn()} />)
    expect(screen.getByText('Option A')).toBeInTheDocument()
  })

  it('affiche le label si fourni', () => {
    render(<SelectDropdown options={options} value="" onChange={vi.fn()} label="Choisir" />)
    expect(screen.getByText('Choisir')).toBeInTheDocument()
  })

  it('affiche l\'erreur si fournie', () => {
    render(<SelectDropdown options={options} value="" onChange={vi.fn()} error="Requis" />)
    expect(screen.getByText('Requis')).toBeInTheDocument()
  })

  it('onChange appelé lors de la sélection', () => {
    const onChange = vi.fn()
    render(<SelectDropdown options={options} value="" onChange={onChange} />)
    // Ouvrir le dropdown en cliquant sur le trigger
    fireEvent.click(screen.getByText('Sélectionner...'))
    fireEvent.click(screen.getByText('Option A'))
    expect(onChange).toHaveBeenCalledWith('a')
  })
})
