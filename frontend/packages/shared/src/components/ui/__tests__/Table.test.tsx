/**
 * Tests unitaires pour components/ui/Table.tsx
 * Table, Pagination
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Table, Pagination } from '../Table'

// ─── Table ────────────────────────────────────────────────────────────────────

type Item = { id: number; name: string; status: string }

const columns = [
  { key: 'name', header: 'Nom' },
  { key: 'status', header: 'Statut' },
]

const data: Item[] = [
  { id: 1, name: 'Alice', status: 'Actif' },
  { id: 2, name: 'Bob', status: 'Inactif' },
]

describe('Table - rendu de base', () => {
  it('affiche les headers de colonnes', () => {
    render(<Table data={data} columns={columns} keyExtractor={(i) => i.id} />)
    expect(screen.getByText('Nom')).toBeInTheDocument()
    expect(screen.getByText('Statut')).toBeInTheDocument()
  })

  it('affiche les données', () => {
    render(<Table data={data} columns={columns} keyExtractor={(i) => i.id} />)
    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('Bob')).toBeInTheDocument()
    expect(screen.getByText('Actif')).toBeInTheDocument()
  })

  it('affiche le message vide si data=[]', () => {
    render(<Table data={[]} columns={columns} keyExtractor={(i) => i.id} />)
    expect(screen.getByText('Aucune donnée')).toBeInTheDocument()
  })

  it('emptyMessage personnalisé', () => {
    render(
      <Table
        data={[]}
        columns={columns}
        keyExtractor={(i) => i.id}
        emptyMessage="Rien à afficher"
      />
    )
    expect(screen.getByText('Rien à afficher')).toBeInTheDocument()
  })
})

describe('Table - loading', () => {
  it('loading=true : affiche les skeletons', () => {
    const { container } = render(
      <Table data={data} columns={columns} keyExtractor={(i) => i.id} loading />
    )
    const pulses = container.querySelectorAll('.animate-pulse')
    expect(pulses.length).toBeGreaterThan(0)
  })

  it('loading=true : ne rend pas les données', () => {
    render(<Table data={data} columns={columns} keyExtractor={(i) => i.id} loading />)
    expect(screen.queryByText('Alice')).toBeNull()
  })
})

describe('Table - tri', () => {
  it('colonne sortable : clic appelle onSort avec la clé', () => {
    const onSort = vi.fn()
    const sortableColumns = [
      { key: 'name', header: 'Nom', sortable: true },
      { key: 'status', header: 'Statut' },
    ]
    render(
      <Table
        data={data}
        columns={sortableColumns}
        keyExtractor={(i) => i.id}
        onSort={onSort}
      />
    )
    fireEvent.click(screen.getByText('Nom'))
    expect(onSort).toHaveBeenCalledWith('name')
  })

  it('colonne non sortable : clic n\'appelle pas onSort', () => {
    const onSort = vi.fn()
    render(<Table data={data} columns={columns} keyExtractor={(i) => i.id} onSort={onSort} />)
    fireEvent.click(screen.getByText('Statut'))
    expect(onSort).not.toHaveBeenCalled()
  })
})

describe('Table - onRowClick', () => {
  it('clic sur une ligne appelle onRowClick avec l\'item', () => {
    const onRowClick = vi.fn()
    render(
      <Table data={data} columns={columns} keyExtractor={(i) => i.id} onRowClick={onRowClick} />
    )
    fireEvent.click(screen.getByText('Alice'))
    expect(onRowClick).toHaveBeenCalledWith(data[0])
  })
})

describe('Table - render personnalisé', () => {
  it('utilise la fonction render de la colonne', () => {
    const customColumns = [
      {
        key: 'name',
        header: 'Nom',
        render: (item: Item) => <span data-testid="custom">{item.name.toUpperCase()}</span>,
      },
    ]
    render(<Table data={data} columns={customColumns} keyExtractor={(i) => i.id} />)
    expect(screen.getByText('ALICE')).toBeInTheDocument()
  })
})

// ─── Pagination ───────────────────────────────────────────────────────────────

describe('Pagination - rendu de base', () => {
  it('affiche les boutons Précédent et Suivant', () => {
    render(<Pagination page={2} totalPages={5} onPageChange={vi.fn()} />)
    expect(screen.getByText('Précédent')).toBeInTheDocument()
    expect(screen.getByText('Suivant')).toBeInTheDocument()
  })

  it('bouton Précédent désactivé à page=1', () => {
    render(<Pagination page={1} totalPages={5} onPageChange={vi.fn()} />)
    expect(screen.getByText('Précédent')).toBeDisabled()
  })

  it('bouton Suivant désactivé à la dernière page', () => {
    render(<Pagination page={5} totalPages={5} onPageChange={vi.fn()} />)
    expect(screen.getByText('Suivant')).toBeDisabled()
  })

  it('clic Précédent appelle onPageChange(page-1)', () => {
    const onPageChange = vi.fn()
    render(<Pagination page={3} totalPages={5} onPageChange={onPageChange} />)
    fireEvent.click(screen.getByText('Précédent'))
    expect(onPageChange).toHaveBeenCalledWith(2)
  })

  it('clic Suivant appelle onPageChange(page+1)', () => {
    const onPageChange = vi.fn()
    render(<Pagination page={3} totalPages={5} onPageChange={onPageChange} />)
    fireEvent.click(screen.getByText('Suivant'))
    expect(onPageChange).toHaveBeenCalledWith(4)
  })

  it('affiche total et range si total+perPage fournis', () => {
    render(
      <Pagination page={1} totalPages={3} onPageChange={vi.fn()} total={25} perPage={10} />
    )
    expect(screen.getByText('25')).toBeInTheDocument()
  })

  it('affiche "Page X sur Y" sans total', () => {
    render(<Pagination page={2} totalPages={4} onPageChange={vi.fn()} />)
    expect(screen.getByText(/Page 2 sur 4/)).toBeInTheDocument()
  })
})
