/**
 * Tests unitaires pour components/ui/SignaturePad.tsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { forwardRef, useImperativeHandle } from 'react'
import { SignaturePad } from '../SignaturePad'

// Mock react-signature-canvas (canvas non disponible en JSDOM)
vi.mock('react-signature-canvas', () => {
  return {
    default: forwardRef((_props: Record<string, unknown>, ref: unknown) => {
      useImperativeHandle(ref, () => ({
        clear: vi.fn(),
        isEmpty: vi.fn(() => false),
        toDataURL: vi.fn(() => 'data:image/png;base64,mock'),
      }))
      return <canvas data-testid="signature-canvas" />
    }),
  }
})

describe('SignaturePad - rendu de base', () => {
  it('rend le canvas de signature', () => {
    render(<SignaturePad onSign={vi.fn()} />)
    expect(screen.getByTestId('signature-canvas')).toBeInTheDocument()
  })

  it('affiche le label si fourni', () => {
    render(<SignaturePad onSign={vi.fn()} label="Signature client" />)
    expect(screen.getByText('Signature client')).toBeInTheDocument()
  })

  it('pas de label si non fourni', () => {
    const { container } = render(<SignaturePad onSign={vi.fn()} />)
    expect(container.querySelector('label')).toBeNull()
  })

  it('affiche le bouton "Effacer la signature" par défaut', () => {
    render(<SignaturePad onSign={vi.fn()} />)
    expect(screen.getByText('Effacer la signature')).toBeInTheDocument()
  })

  it('bouton Effacer absent en mode readOnly', () => {
    render(<SignaturePad onSign={vi.fn()} readOnly />)
    expect(screen.queryByText('Effacer la signature')).toBeNull()
  })
})

describe('SignaturePad - interactions', () => {
  it('clic sur Effacer appelle onClear', () => {
    const onClear = vi.fn()
    render(<SignaturePad onSign={vi.fn()} onClear={onClear} />)
    fireEvent.click(screen.getByText('Effacer la signature'))
    expect(onClear).toHaveBeenCalledOnce()
  })

  it('pas d\'erreur si onClear absent au clic Effacer', () => {
    render(<SignaturePad onSign={vi.fn()} />)
    expect(() => fireEvent.click(screen.getByText('Effacer la signature'))).not.toThrow()
  })
})
