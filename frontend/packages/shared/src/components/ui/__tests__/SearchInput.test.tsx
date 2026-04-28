/**
 * Tests unitaires pour components/ui/SearchInput.tsx
 * SearchInput, SearchWithSuggestions
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { SearchInput, SearchWithSuggestions } from '../SearchInput'

// ─── SearchInput ──────────────────────────────────────────────────────────────

describe('SearchInput - rendu de base', () => {
  it('rend un input de type search', () => {
    render(<SearchInput value="" onChange={vi.fn()} />)
    expect(screen.getByRole('searchbox')).toBeInTheDocument()
  })

  it('placeholder par défaut "Rechercher..."', () => {
    render(<SearchInput value="" onChange={vi.fn()} />)
    expect(screen.getByPlaceholderText('Rechercher...')).toBeInTheDocument()
  })

  it('placeholder personnalisé', () => {
    render(<SearchInput value="" onChange={vi.fn()} placeholder="Chercher un client" />)
    expect(screen.getByPlaceholderText('Chercher un client')).toBeInTheDocument()
  })

  it('valeur initiale affichée', () => {
    render(<SearchInput value="test" onChange={vi.fn()} />)
    expect(screen.getByRole('searchbox')).toHaveValue('test')
  })
})

describe('SearchInput - onChange', () => {
  it('onChange appelé lors de la saisie', () => {
    const onChange = vi.fn()
    render(<SearchInput value="" onChange={onChange} />)
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'hello' } })
    expect(onChange).toHaveBeenCalledWith('hello')
  })
})

describe('SearchInput - bouton Effacer', () => {
  it('bouton Effacer visible si valeur non vide', () => {
    render(<SearchInput value="texte" onChange={vi.fn()} />)
    expect(screen.getByLabelText('Effacer la recherche')).toBeInTheDocument()
  })

  it('bouton Effacer absent si valeur vide', () => {
    render(<SearchInput value="" onChange={vi.fn()} />)
    expect(screen.queryByLabelText('Effacer la recherche')).toBeNull()
  })

  it('clic sur Effacer appelle onChange("")', () => {
    const onChange = vi.fn()
    render(<SearchInput value="texte" onChange={onChange} />)
    fireEvent.click(screen.getByLabelText('Effacer la recherche'))
    expect(onChange).toHaveBeenCalledWith('')
  })

  it('showClear=false : bouton Effacer absent même avec valeur', () => {
    render(<SearchInput value="texte" onChange={vi.fn()} showClear={false} />)
    expect(screen.queryByLabelText('Effacer la recherche')).toBeNull()
  })
})

describe('SearchInput - touche Escape', () => {
  it('Escape efface la valeur via onChange("")', () => {
    const onChange = vi.fn()
    render(<SearchInput value="texte" onChange={onChange} />)
    fireEvent.keyDown(screen.getByRole('searchbox'), { key: 'Escape' })
    expect(onChange).toHaveBeenCalledWith('')
  })
})

describe('SearchInput - sizes', () => {
  const sizes = ['sm', 'md', 'lg'] as const

  for (const size of sizes) {
    it(`size ${size} se rend`, () => {
      render(<SearchInput value="" onChange={vi.fn()} size={size} />)
      expect(screen.getByRole('searchbox')).toBeInTheDocument()
    })
  }
})

describe('SearchInput - loading', () => {
  it('loading=true : affiche spinner au lieu de l\'icône recherche', () => {
    const { container } = render(<SearchInput value="" onChange={vi.fn()} loading />)
    // Loader2 avec animate-spin
    expect(container.querySelector('.animate-spin')).not.toBeNull()
  })
})

describe('SearchInput - forwardRef', () => {
  it('transmet la ref à l\'input', () => {
    const ref = { current: null } as React.RefObject<HTMLInputElement>
    render(<SearchInput value="" onChange={vi.fn()} ref={ref} />)
    expect(ref.current).not.toBeNull()
    expect(ref.current?.type).toBe('search')
  })
})

describe('SearchInput - displayName', () => {
  it('displayName = "SearchInput"', () => {
    expect(SearchInput.displayName).toBe('SearchInput')
  })
})

// ─── SearchWithSuggestions ────────────────────────────────────────────────────

describe('SearchWithSuggestions - rendu de base', () => {
  const suggestions = [
    { id: '1', label: 'Alice Dupont', description: 'Client' },
    { id: '2', label: 'Bob Martin' },
  ]

  it('rend un SearchInput', () => {
    render(
      <SearchWithSuggestions
        value=""
        onChange={vi.fn()}
        suggestions={suggestions}
        onSelect={vi.fn()}
      />
    )
    expect(screen.getByRole('searchbox')).toBeInTheDocument()
  })

  it('liste de suggestions apparaît au focus avec valeur non vide', () => {
    render(
      <SearchWithSuggestions
        value="ali"
        onChange={vi.fn()}
        suggestions={suggestions}
        onSelect={vi.fn()}
      />
    )
    fireEvent.focus(screen.getByRole('searchbox'))
    expect(screen.getByText('Alice Dupont')).toBeInTheDocument()
  })

  it('clic sur suggestion appelle onSelect avec la suggestion', () => {
    const onSelect = vi.fn()
    render(
      <SearchWithSuggestions
        value="ali"
        onChange={vi.fn()}
        suggestions={suggestions}
        onSelect={onSelect}
      />
    )
    fireEvent.focus(screen.getByRole('searchbox'))
    fireEvent.click(screen.getByText('Alice Dupont'))
    expect(onSelect).toHaveBeenCalledWith(suggestions[0])
  })

  it('emptyMessage affiché si suggestions vides', () => {
    render(
      <SearchWithSuggestions
        value="xyz"
        onChange={vi.fn()}
        suggestions={[]}
        onSelect={vi.fn()}
        emptyMessage="Pas de résultat"
      />
    )
    fireEvent.focus(screen.getByRole('searchbox'))
    expect(screen.getByText('Pas de résultat')).toBeInTheDocument()
  })
})
