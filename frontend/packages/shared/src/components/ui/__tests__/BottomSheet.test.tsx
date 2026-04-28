/**
 * Tests unitaires pour components/ui/BottomSheet.tsx
 * Sur desktop, BottomSheet délègue à Modal (isMobile=false).
 * Sur mobile, rend MobileSheet avec role="dialog".
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { BottomSheet } from '../BottomSheet'

// Mock useResponsive
vi.mock('@/hooks/useMediaQuery', () => ({
  useResponsive: vi.fn(() => ({ isMobile: false })),
}))

import { useResponsive } from '@/hooks/useMediaQuery'

describe('BottomSheet - desktop (isMobile=false → délègue à Modal)', () => {
  it('isOpen=false → ne rend rien', () => {
    const { container } = render(
      <BottomSheet isOpen={false} onClose={vi.fn()}>
        <p>Contenu</p>
      </BottomSheet>
    )
    expect(container.firstChild).toBeNull()
  })

  it('isOpen=true → affiche le contenu via Modal', () => {
    render(
      <BottomSheet isOpen onClose={vi.fn()}>
        <p>Contenu modal</p>
      </BottomSheet>
    )
    expect(screen.getByText('Contenu modal')).toBeInTheDocument()
  })

  it('affiche le titre via Modal', () => {
    render(
      <BottomSheet isOpen onClose={vi.fn()} title="Titre sheet">
        <p>-</p>
      </BottomSheet>
    )
    expect(screen.getByText('Titre sheet')).toBeInTheDocument()
  })
})

describe('BottomSheet - mobile (isMobile=true → MobileSheet)', () => {
  beforeEach(() => {
    vi.mocked(useResponsive).mockReturnValue({ isMobile: true } as ReturnType<typeof useResponsive>)
  })

  afterEach(() => {
    vi.mocked(useResponsive).mockReturnValue({ isMobile: false } as ReturnType<typeof useResponsive>)
  })

  it('isOpen=false → ne rend rien', () => {
    const { container } = render(
      <BottomSheet isOpen={false} onClose={vi.fn()}>
        <p>Contenu</p>
      </BottomSheet>
    )
    // MobileSheet retourne null si !isOpen
    expect(screen.queryByText('Contenu')).toBeNull()
  })

  it('isOpen=true → role="dialog"', () => {
    render(
      <BottomSheet isOpen onClose={vi.fn()}>
        <p>Contenu sheet</p>
      </BottomSheet>
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('affiche le titre', () => {
    render(
      <BottomSheet isOpen onClose={vi.fn()} title="Mobile Sheet Titre">
        <p>-</p>
      </BottomSheet>
    )
    expect(screen.getByText('Mobile Sheet Titre')).toBeInTheDocument()
  })

  it('bouton Fermer appelle onClose', () => {
    const onClose = vi.fn()
    render(
      <BottomSheet isOpen onClose={onClose} title="Titre">
        <p>-</p>
      </BottomSheet>
    )
    fireEvent.click(screen.getByLabelText('Fermer'))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('clic overlay appelle onClose si closeOnOverlayClick=true', () => {
    const onClose = vi.fn()
    const { container } = render(
      <BottomSheet isOpen onClose={onClose} closeOnOverlayClick>
        <p>-</p>
      </BottomSheet>
    )
    const overlay = container.querySelector('.fixed.inset-0.bg-black\\/60')
    if (overlay) fireEvent.click(overlay)
    expect(onClose).toHaveBeenCalled()
  })
})
