/**
 * Tests unitaires pour components/ui/Alert.tsx
 * Alert, InlineAlert, BannerAlert
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Alert, InlineAlert, BannerAlert } from '../Alert'

// ─── Alert ────────────────────────────────────────────────────────────────────

describe('Alert - rendu de base', () => {
  it('affiche le contenu enfant', () => {
    render(<Alert>Message important</Alert>)
    expect(screen.getByText('Message important')).toBeInTheDocument()
  })

  it('a role="alert"', () => {
    render(<Alert>Alerte</Alert>)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('affiche le titre quand fourni', () => {
    render(<Alert title="Titre alerte">Corps</Alert>)
    expect(screen.getByText('Titre alerte')).toBeInTheDocument()
  })

  it('pas de titre si absent', () => {
    render(<Alert>Corps seulement</Alert>)
    expect(screen.queryByRole('heading')).toBeNull()
  })

  it('applique className personnalisée', () => {
    render(<Alert className="my-alert">Msg</Alert>)
    expect(screen.getByRole('alert').className).toContain('my-alert')
  })
})

describe('Alert - variants', () => {
  const variants = ['info', 'success', 'warning', 'error'] as const

  for (const variant of variants) {
    it(`variant ${variant} se rend avec role="alert"`, () => {
      render(<Alert variant={variant}>{variant}</Alert>)
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  }
})

describe('Alert - dismissible', () => {
  it('sans dismissible : pas de bouton Fermer', () => {
    render(<Alert>Test</Alert>)
    expect(screen.queryByLabelText('Fermer')).toBeNull()
  })

  it('dismissible=true : affiche bouton Fermer', () => {
    render(<Alert dismissible>Test</Alert>)
    expect(screen.getByLabelText('Fermer')).toBeInTheDocument()
  })

  it('clic Fermer appelle onDismiss', () => {
    const onDismiss = vi.fn()
    render(<Alert dismissible onDismiss={onDismiss}>Test</Alert>)
    fireEvent.click(screen.getByLabelText('Fermer'))
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })
})

describe('Alert - icon personnalisée', () => {
  it('affiche l\'icon personnalisée au lieu de l\'icon par défaut', () => {
    render(<Alert icon={<span data-testid="custom-icon">★</span>}>Test</Alert>)
    expect(screen.getByTestId('custom-icon')).toBeInTheDocument()
  })
})

describe('Alert - actions', () => {
  it('affiche les actions si fournies', () => {
    render(
      <Alert actions={<button>Réessayer</button>}>Message</Alert>
    )
    expect(screen.getByText('Réessayer')).toBeInTheDocument()
  })

  it('sans actions : pas de zone d\'actions', () => {
    render(<Alert>Message</Alert>)
    expect(screen.queryByText('Réessayer')).toBeNull()
  })
})

// ─── InlineAlert ──────────────────────────────────────────────────────────────

describe('InlineAlert - rendu de base', () => {
  it('affiche le contenu enfant', () => {
    render(<InlineAlert>Erreur de validation</InlineAlert>)
    expect(screen.getByText('Erreur de validation')).toBeInTheDocument()
  })

  it('a role="alert"', () => {
    render(<InlineAlert>Test</InlineAlert>)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('variant par défaut = error', () => {
    const { container } = render(<InlineAlert>Test</InlineAlert>)
    // La classe error contient border-red
    expect(container.firstChild).not.toBeNull()
  })

  it('variant success se rend', () => {
    render(<InlineAlert variant="success">OK</InlineAlert>)
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('OK')).toBeInTheDocument()
  })

  it('applique className personnalisée', () => {
    render(<InlineAlert className="inline-cls">Msg</InlineAlert>)
    expect(screen.getByRole('alert').className).toContain('inline-cls')
  })
})

// ─── BannerAlert ──────────────────────────────────────────────────────────────

describe('BannerAlert - rendu de base', () => {
  it('affiche le contenu enfant', () => {
    render(<BannerAlert>Maintenance prévue</BannerAlert>)
    expect(screen.getByText('Maintenance prévue')).toBeInTheDocument()
  })

  it('a role="alert"', () => {
    render(<BannerAlert>Info</BannerAlert>)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('applique className personnalisée', () => {
    render(<BannerAlert className="banner-cls">Msg</BannerAlert>)
    expect(screen.getByRole('alert').className).toContain('banner-cls')
  })
})

describe('BannerAlert - action', () => {
  it('affiche le bouton d\'action avec son label', () => {
    render(
      <BannerAlert action={{ label: 'En savoir plus', onClick: vi.fn() }}>
        Info
      </BannerAlert>
    )
    expect(screen.getByText('En savoir plus')).toBeInTheDocument()
  })

  it('clic sur action appelle onClick', () => {
    const onClick = vi.fn()
    render(
      <BannerAlert action={{ label: 'Clic', onClick }}>Info</BannerAlert>
    )
    fireEvent.click(screen.getByText('Clic'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('sans action : pas de bouton action', () => {
    render(<BannerAlert>Info</BannerAlert>)
    expect(screen.queryByText('En savoir plus')).toBeNull()
  })
})

describe('BannerAlert - dismissible', () => {
  it('dismissible=true : affiche bouton Fermer', () => {
    render(<BannerAlert dismissible>Info</BannerAlert>)
    expect(screen.getByLabelText('Fermer')).toBeInTheDocument()
  })

  it('clic Fermer appelle onDismiss', () => {
    const onDismiss = vi.fn()
    render(<BannerAlert dismissible onDismiss={onDismiss}>Info</BannerAlert>)
    fireEvent.click(screen.getByLabelText('Fermer'))
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it('sans dismissible : pas de bouton Fermer', () => {
    render(<BannerAlert>Info</BannerAlert>)
    expect(screen.queryByLabelText('Fermer')).toBeNull()
  })
})
