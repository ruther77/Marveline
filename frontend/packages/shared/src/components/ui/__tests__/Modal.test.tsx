/**
 * Tests unitaires pour components/ui/Modal.tsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Modal } from '../Modal'

describe('Modal - isOpen=false', () => {
  it('ne rend rien si isOpen=false', () => {
    const { container } = render(
      <Modal isOpen={false} onClose={vi.fn()}>
        <p>Contenu</p>
      </Modal>
    )
    expect(container.firstChild).toBeNull()
  })
})

describe('Modal - rendu de base', () => {
  it('affiche le contenu si isOpen=true', () => {
    render(
      <Modal isOpen onClose={vi.fn()}>
        <p>Contenu de la modal</p>
      </Modal>
    )
    expect(screen.getByText('Contenu de la modal')).toBeInTheDocument()
  })

  it('affiche le titre si fourni', () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="Titre Modal">
        <p>-</p>
      </Modal>
    )
    expect(screen.getByText('Titre Modal')).toBeInTheDocument()
  })

  it('affiche la description si fournie', () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="T" description="Description détaillée">
        <p>-</p>
      </Modal>
    )
    expect(screen.getByText('Description détaillée')).toBeInTheDocument()
  })

  it('affiche le bouton de fermeture par défaut', () => {
    render(
      <Modal isOpen onClose={vi.fn()}>
        <p>-</p>
      </Modal>
    )
    // Le bouton X est présent (aria-label ou svg)
    const buttons = screen.getAllByRole('button')
    expect(buttons.length).toBeGreaterThan(0)
  })

  it('showCloseButton=false : pas de bouton X', () => {
    render(
      <Modal isOpen onClose={vi.fn()} showCloseButton={false}>
        <p>Contenu</p>
      </Modal>
    )
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('affiche le footer si fourni', () => {
    render(
      <Modal isOpen onClose={vi.fn()} footer={<button>Valider</button>}>
        <p>-</p>
      </Modal>
    )
    expect(screen.getByText('Valider')).toBeInTheDocument()
  })
})

describe('Modal - sizes', () => {
  const sizes = ['sm', 'md', 'lg', 'xl', 'full'] as const

  for (const size of sizes) {
    it(`size ${size} se rend`, () => {
      render(
        <Modal isOpen onClose={vi.fn()} size={size}>
          <p>Contenu</p>
        </Modal>
      )
      expect(screen.getByText('Contenu')).toBeInTheDocument()
    })
  }
})

describe('Modal - fermeture', () => {
  it('clic overlay appelle onClose si closeOnOverlayClick=true', () => {
    const onClose = vi.fn()
    const { container } = render(
      <Modal isOpen onClose={onClose} closeOnOverlayClick>
        <p>-</p>
      </Modal>
    )
    // Le premier div fixed est l'overlay
    const overlay = container.querySelector('.fixed.inset-0.bg-black\\/75')
    if (overlay) fireEvent.click(overlay)
    expect(onClose).toHaveBeenCalled()
  })

  it('clic overlay ne ferme pas si closeOnOverlayClick=false', () => {
    const onClose = vi.fn()
    const { container } = render(
      <Modal isOpen onClose={onClose} closeOnOverlayClick={false}>
        <p>-</p>
      </Modal>
    )
    const overlay = container.querySelector('.fixed.inset-0.bg-black\\/75')
    if (overlay) fireEvent.click(overlay)
    expect(onClose).not.toHaveBeenCalled()
  })
})
