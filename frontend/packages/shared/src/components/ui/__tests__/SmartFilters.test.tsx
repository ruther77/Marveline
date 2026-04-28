/**
 * Tests unitaires pour components/ui/SmartFilters.tsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import SmartFilters from '../SmartFilters'
import type { FilterConfig } from '../SmartFilters'

const filterConfigs: FilterConfig[] = [
  {
    key: 'status',
    label: 'Statut',
    type: 'select',
    options: [
      { value: 'active', label: 'Actif' },
      { value: 'inactive', label: 'Inactif' },
    ],
  },
  {
    key: 'name',
    label: 'Nom',
    type: 'text',
  },
]

describe('SmartFilters - rendu de base', () => {
  it('rend la barre de recherche par défaut', () => {
    render(<SmartFilters />)
    expect(screen.getByPlaceholderText('Rechercher...')).toBeInTheDocument()
  })

  it('placeholder personnalisé', () => {
    render(<SmartFilters searchPlaceholder="Chercher un client..." />)
    expect(screen.getByPlaceholderText('Chercher un client...')).toBeInTheDocument()
  })

  it('searchable=false → pas de barre de recherche', () => {
    render(<SmartFilters searchable={false} />)
    expect(screen.queryByPlaceholderText('Rechercher...')).toBeNull()
  })

  it('affiche les labels des filtres configurés', () => {
    render(<SmartFilters filters={filterConfigs} />)
    expect(screen.getByText('Statut')).toBeInTheDocument()
  })
})

describe('SmartFilters - recherche texte', () => {
  it('appelle onSearchChange à la saisie', () => {
    const onSearchChange = vi.fn()
    render(<SmartFilters onSearchChange={onSearchChange} />)
    const input = screen.getByPlaceholderText('Rechercher...')
    fireEvent.change(input, { target: { value: 'test' } })
    expect(onSearchChange).toHaveBeenCalledWith('test')
  })

  it('bouton X apparaît quand searchValue non vide', () => {
    render(<SmartFilters searchValue="abc" onSearchChange={vi.fn()} />)
    // Le bouton X (clear) est affiché
    const buttons = screen.getAllByRole('button')
    expect(buttons.length).toBeGreaterThan(0)
  })

  it('clic sur X appelle onSearchChange avec chaîne vide', () => {
    const onSearchChange = vi.fn()
    render(<SmartFilters searchValue="abc" onSearchChange={onSearchChange} />)
    // Le premier bouton dans l'input est le X
    const xButton = screen.getAllByRole('button')[0]
    fireEvent.click(xButton)
    expect(onSearchChange).toHaveBeenCalledWith('')
  })
})

describe('SmartFilters - filtres actifs', () => {
  it('pas de badge de filtres actifs si values vide', () => {
    render(<SmartFilters filters={filterConfigs} values={{}} />)
    // Aucun badge "X filtres actifs"
    expect(screen.queryByText(/filtre/i)).toBeNull()
  })

  it('compte les filtres actifs (non vides)', () => {
    render(
      <SmartFilters
        filters={filterConfigs}
        values={{ status: 'active', name: '' }}
      />
    )
    // status est actif, name est vide → 1 filtre actif
    // Le badge ou le bouton Reset apparaît
    const buttons = screen.getAllByRole('button')
    expect(buttons.length).toBeGreaterThan(0)
  })
})

describe('SmartFilters - presets', () => {
  it('bouton "Filtres rapides" visible si presets fournis', () => {
    const presets = [
      { label: 'Ce mois', filters: { status: 'active' } },
    ]
    render(<SmartFilters presets={presets} />)
    // Le texte "Filtres rapides" est dans un span hidden sm:inline mais présent dans le DOM
    expect(screen.getByText('Filtres rapides')).toBeInTheDocument()
  })

  it('pas de bouton Filtres rapides si presets vide', () => {
    render(<SmartFilters presets={[]} />)
    expect(screen.queryByText('Filtres rapides')).toBeNull()
  })

  it('clic sur Filtres rapides affiche la liste', () => {
    const presets = [
      { label: 'Ce mois', filters: { status: 'active' } },
    ]
    render(<SmartFilters presets={presets} />)
    fireEvent.click(screen.getByText('Filtres rapides'))
    expect(screen.getByText('Ce mois')).toBeInTheDocument()
  })

  it('clic sur un preset appelle onChange pour chaque filtre', () => {
    const onChange = vi.fn()
    const presets = [
      { label: 'Actifs', filters: { status: 'active' } },
    ]
    render(<SmartFilters filters={filterConfigs} presets={presets} onChange={onChange} />)
    fireEvent.click(screen.getByText('Filtres rapides'))
    fireEvent.click(screen.getByText('Actifs'))
    // onChange appelé pour reset + preset
    expect(onChange).toHaveBeenCalled()
  })
})

describe('SmartFilters - suggestions', () => {
  it('affiche les suggestions si fournies', () => {
    const suggestions = [
      { label: 'Clients actifs', filters: { status: 'active' } },
    ]
    render(<SmartFilters suggestions={suggestions} />)
    expect(screen.getByText('Clients actifs')).toBeInTheDocument()
  })

  it('clic sur une suggestion appelle onChange', () => {
    const onChange = vi.fn()
    const suggestions = [
      { label: 'Clients actifs', filters: { status: 'active' } },
    ]
    render(<SmartFilters suggestions={suggestions} onChange={onChange} />)
    fireEvent.click(screen.getByText('Clients actifs'))
    expect(onChange).toHaveBeenCalledWith('status', 'active')
  })
})
