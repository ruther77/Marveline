/**
 * Tests unitaires pour components/ui/QRScanner.tsx
 * Mode 'generate' : testé complètement (pas de dépendances matérielles)
 * Mode 'scan' : testé partiellement (mock @zxing/browser)
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QRScanner } from '../QRScanner'

// Mock @zxing/browser (lecture caméra non disponible en JSDOM)
vi.mock('@zxing/browser', () => ({
  BrowserQRCodeReader: vi.fn().mockImplementation(() => ({
    decodeFromConstraints: vi.fn().mockResolvedValue(undefined),
  })),
}))

describe('QRScanner - mode generate', () => {
  it('affiche le QR code si generateValue fournie', () => {
    const { container } = render(
      <QRScanner
        mode="generate"
        generateValue="https://example.com"
        active={false}
        onScan={vi.fn()}
      />
    )
    // QRCodeSVG rend un svg
    expect(container.querySelector('svg')).not.toBeNull()
  })

  it('affiche "Aucune valeur" si generateValue absente', () => {
    render(
      <QRScanner
        mode="generate"
        generateValue=""
        active={false}
        onScan={vi.fn()}
      />
    )
    expect(screen.getByText('Aucune valeur à encoder')).toBeInTheDocument()
  })

  it('affiche "Aucune valeur" si generateValue undefined', () => {
    render(
      <QRScanner
        mode="generate"
        active={false}
        onScan={vi.fn()}
      />
    )
    expect(screen.getByText('Aucune valeur à encoder')).toBeInTheDocument()
  })
})

describe('QRScanner - mode scan', () => {
  it('affiche "Scanner inactif" si active=false', () => {
    render(
      <QRScanner
        mode="scan"
        active={false}
        onScan={vi.fn()}
      />
    )
    expect(screen.getByText('Scanner inactif')).toBeInTheDocument()
  })

  it('rend un élément video en mode scan', () => {
    const { container } = render(
      <QRScanner
        mode="scan"
        active={false}
        onScan={vi.fn()}
      />
    )
    expect(container.querySelector('video')).not.toBeNull()
  })
})
