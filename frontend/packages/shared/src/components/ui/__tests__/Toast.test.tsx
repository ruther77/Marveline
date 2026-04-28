/**
 * Tests unitaires pour components/ui/Toast.tsx
 * ToastProvider, useToast
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { ToastProvider, useToast } from '../Toast'

// Mock registerToastError depuis main
vi.mock('../../../main', () => ({
  registerToastError: vi.fn(),
}))

// Composant helper pour accéder au context useToast
function ToastTrigger({ type, title, message }: {
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message?: string
}) {
  const toast = useToast()
  return (
    <button
      onClick={() => toast[type](title, message)}
      data-testid={`btn-${type}`}
    >
      Trigger {type}
    </button>
  )
}

function RemoveTrigger() {
  const toast = useToast()
  return (
    <button
      onClick={() => toast.addToast({ type: 'info', title: 'Test', duration: -1 })}
      data-testid="btn-add"
    >
      Add
    </button>
  )
}

// ─── ToastProvider ────────────────────────────────────────────────────────────

describe('ToastProvider - rendu de base', () => {
  it('rend les children sans erreur', () => {
    render(
      <ToastProvider>
        <p>Contenu</p>
      </ToastProvider>
    )
    expect(screen.getByText('Contenu')).toBeInTheDocument()
  })
})

describe('ToastProvider - affichage de toasts', () => {
  it('success() affiche un toast avec title', () => {
    render(
      <ToastProvider>
        <ToastTrigger type="success" title="Opération réussie" />
      </ToastProvider>
    )
    fireEvent.click(screen.getByTestId('btn-success'))
    expect(screen.getByText('Opération réussie')).toBeInTheDocument()
  })

  it('error() affiche un toast error', () => {
    render(
      <ToastProvider>
        <ToastTrigger type="error" title="Une erreur est survenue" />
      </ToastProvider>
    )
    fireEvent.click(screen.getByTestId('btn-error'))
    expect(screen.getByText('Une erreur est survenue')).toBeInTheDocument()
  })

  it('warning() affiche un toast warning', () => {
    render(
      <ToastProvider>
        <ToastTrigger type="warning" title="Avertissement" />
      </ToastProvider>
    )
    fireEvent.click(screen.getByTestId('btn-warning'))
    expect(screen.getByText('Avertissement')).toBeInTheDocument()
  })

  it('info() affiche un toast info', () => {
    render(
      <ToastProvider>
        <ToastTrigger type="info" title="Information" />
      </ToastProvider>
    )
    fireEvent.click(screen.getByTestId('btn-info'))
    expect(screen.getByText('Information')).toBeInTheDocument()
  })

  it('toast avec message affiche le message', () => {
    render(
      <ToastProvider>
        <ToastTrigger type="success" title="Titre" message="Détail du message" />
      </ToastProvider>
    )
    fireEvent.click(screen.getByTestId('btn-success'))
    expect(screen.getByText('Détail du message')).toBeInTheDocument()
  })

  it('toast a role="alert"', () => {
    render(
      <ToastProvider>
        <ToastTrigger type="info" title="Alerte" />
      </ToastProvider>
    )
    fireEvent.click(screen.getByTestId('btn-info'))
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})

describe('ToastProvider - fermeture manuelle', () => {
  it('clic sur bouton Fermer supprime le toast', () => {
    render(
      <ToastProvider>
        <ToastTrigger type="success" title="À fermer" />
      </ToastProvider>
    )
    fireEvent.click(screen.getByTestId('btn-success'))
    expect(screen.getByText('À fermer')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Fermer'))
    expect(screen.queryByText('À fermer')).toBeNull()
  })
})

describe('ToastProvider - auto-suppression', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it('toast supprimé après duration (5000ms)', () => {
    render(
      <ToastProvider>
        <ToastTrigger type="success" title="Temporaire" />
      </ToastProvider>
    )
    fireEvent.click(screen.getByTestId('btn-success'))
    expect(screen.getByText('Temporaire')).toBeInTheDocument()
    act(() => { vi.advanceTimersByTime(5001) })
    expect(screen.queryByText('Temporaire')).toBeNull()
  })
})

// ─── useToast - hors context ──────────────────────────────────────────────────

describe('useToast - hors ToastProvider', () => {
  it('lève une erreur si utilisé hors provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    function BrokenComponent() {
      useToast()
      return null
    }
    expect(() => render(<BrokenComponent />)).toThrow()
    spy.mockRestore()
  })
})
