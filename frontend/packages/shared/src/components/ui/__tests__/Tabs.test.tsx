/**
 * Tests unitaires pour components/ui/Tabs.tsx
 * Tabs, TabList, TabTrigger, TabContent
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Tabs, TabList, TabTrigger, TabContent } from '../Tabs'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function SimpleTabs({ onChange }: { onChange?: (v: string) => void }) {
  return (
    <Tabs defaultValue="tab1" onChange={onChange}>
      <TabList>
        <TabTrigger value="tab1">Onglet 1</TabTrigger>
        <TabTrigger value="tab2">Onglet 2</TabTrigger>
        <TabTrigger value="tab3" disabled>Désactivé</TabTrigger>
      </TabList>
      <TabContent value="tab1">Contenu 1</TabContent>
      <TabContent value="tab2">Contenu 2</TabContent>
      <TabContent value="tab3">Contenu 3</TabContent>
    </Tabs>
  )
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────

describe('Tabs - rendu de base', () => {
  it('affiche le contenu de l\'onglet actif par défaut', () => {
    render(<SimpleTabs />)
    expect(screen.getByText('Contenu 1')).toBeInTheDocument()
  })

  it('n\'affiche pas le contenu des onglets inactifs', () => {
    render(<SimpleTabs />)
    expect(screen.queryByText('Contenu 2')).toBeNull()
  })
})

describe('Tabs - navigation', () => {
  it('clic sur onglet 2 affiche contenu 2', () => {
    render(<SimpleTabs />)
    fireEvent.click(screen.getByRole('tab', { name: 'Onglet 2' }))
    expect(screen.getByText('Contenu 2')).toBeInTheDocument()
    expect(screen.queryByText('Contenu 1')).toBeNull()
  })

  it('onglet cliqué devient aria-selected=true', () => {
    render(<SimpleTabs />)
    const tab2 = screen.getByRole('tab', { name: 'Onglet 2' })
    fireEvent.click(tab2)
    expect(tab2).toHaveAttribute('aria-selected', 'true')
  })

  it('onglet inactif a aria-selected=false', () => {
    render(<SimpleTabs />)
    const tab2 = screen.getByRole('tab', { name: 'Onglet 2' })
    expect(tab2).toHaveAttribute('aria-selected', 'false')
  })
})

describe('Tabs - disabled', () => {
  it('onglet désactivé ne change pas l\'onglet actif', () => {
    render(<SimpleTabs />)
    fireEvent.click(screen.getByRole('tab', { name: 'Désactivé' }))
    // Toujours sur onglet 1
    expect(screen.getByText('Contenu 1')).toBeInTheDocument()
  })

  it('onglet désactivé est disabled', () => {
    render(<SimpleTabs />)
    expect(screen.getByRole('tab', { name: 'Désactivé' })).toBeDisabled()
  })
})

describe('Tabs - contrôlé (value + onChange)', () => {
  it('onChange est appelé avec la bonne valeur', () => {
    const onChange = vi.fn()
    render(<SimpleTabs onChange={onChange} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Onglet 2' }))
    expect(onChange).toHaveBeenCalledWith('tab2')
  })

  it('valeur contrôlée : affiche le contenu de l\'onglet forcé', () => {
    render(
      <Tabs value="tab2">
        <TabList>
          <TabTrigger value="tab1">1</TabTrigger>
          <TabTrigger value="tab2">2</TabTrigger>
        </TabList>
        <TabContent value="tab1">C1</TabContent>
        <TabContent value="tab2">C2</TabContent>
      </Tabs>
    )
    expect(screen.getByText('C2')).toBeInTheDocument()
    expect(screen.queryByText('C1')).toBeNull()
  })
})

// ─── TabList ──────────────────────────────────────────────────────────────────

describe('TabList - rendu', () => {
  it('a role="tablist"', () => {
    render(
      <Tabs defaultValue="a">
        <TabList><TabTrigger value="a">A</TabTrigger></TabList>
        <TabContent value="a">-</TabContent>
      </Tabs>
    )
    expect(screen.getByRole('tablist')).toBeInTheDocument()
  })

  const variants = ['default', 'pills', 'underline'] as const

  for (const variant of variants) {
    it(`variant ${variant} se rend`, () => {
      render(
        <Tabs defaultValue="a">
          <TabList variant={variant}><TabTrigger value="a">A</TabTrigger></TabList>
          <TabContent value="a">-</TabContent>
        </Tabs>
      )
      expect(screen.getByRole('tablist')).toBeInTheDocument()
    })
  }
})

// ─── TabContent - forceMount ───────────────────────────────────────────────────

describe('TabContent - forceMount', () => {
  it('forceMount=true : contenu monté même si inactif', () => {
    render(
      <Tabs defaultValue="tab1">
        <TabList>
          <TabTrigger value="tab1">1</TabTrigger>
          <TabTrigger value="tab2">2</TabTrigger>
        </TabList>
        <TabContent value="tab1">C1</TabContent>
        <TabContent value="tab2" forceMount>C2 forcé</TabContent>
      </Tabs>
    )
    // C2 est dans le DOM même si tab1 est actif (mais hidden)
    expect(screen.getByText('C2 forcé')).toBeInTheDocument()
  })
})

// ─── TabTrigger - icon ────────────────────────────────────────────────────────

describe('TabTrigger - icon', () => {
  it('affiche l\'icon si fourni', () => {
    render(
      <Tabs defaultValue="a">
        <TabList>
          <TabTrigger value="a" icon={<span data-testid="ico">★</span>}>Onglet</TabTrigger>
        </TabList>
        <TabContent value="a">-</TabContent>
      </Tabs>
    )
    expect(screen.getByTestId('ico')).toBeInTheDocument()
  })
})

// ─── Erreur hors context ──────────────────────────────────────────────────────

describe('useTabsContext - hors Tabs', () => {
  it('TabTrigger hors Tabs lève une erreur', () => {
    // Supprimer les logs d'erreur React pour ce test
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<TabTrigger value="x">X</TabTrigger>)).toThrow()
    spy.mockRestore()
  })
})
