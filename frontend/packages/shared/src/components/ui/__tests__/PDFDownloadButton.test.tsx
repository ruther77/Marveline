/**
 * Tests unitaires pour components/ui/PDFDownloadButton.tsx
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { PDFDownloadButton } from '../PDFDownloadButton'

// Mock URL.createObjectURL / revokeObjectURL
const createObjectURLMock = vi.fn(() => 'blob:mock')
const revokeObjectURLMock = vi.fn()

beforeEach(() => {
  global.URL.createObjectURL = createObjectURLMock
  global.URL.revokeObjectURL = revokeObjectURLMock
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('PDFDownloadButton - rendu de base', () => {
  it('affiche le label par défaut', () => {
    render(<PDFDownloadButton fetchPdf={vi.fn()} filename="doc.pdf" />)
    expect(screen.getByText('Télécharger PDF')).toBeInTheDocument()
  })

  it('affiche un label personnalisé', () => {
    render(<PDFDownloadButton fetchPdf={vi.fn()} filename="doc.pdf" label="Exporter PDF" />)
    expect(screen.getByText('Exporter PDF')).toBeInTheDocument()
  })

  it('rend un bouton cliquable', () => {
    render(<PDFDownloadButton fetchPdf={vi.fn()} filename="doc.pdf" />)
    expect(screen.getByRole('button')).toBeInTheDocument()
  })
})

describe('PDFDownloadButton - téléchargement', () => {
  it('appelle fetchPdf au clic', async () => {
    const fetchPdf = vi.fn().mockResolvedValue(new Blob(['pdf content'], { type: 'application/pdf' }))
    render(<PDFDownloadButton fetchPdf={fetchPdf} filename="test.pdf" />)
    fireEvent.click(screen.getByRole('button'))
    await waitFor(() => expect(fetchPdf).toHaveBeenCalledOnce())
  })

  it('crée un objectURL et le révoque après téléchargement', async () => {
    const blob = new Blob(['pdf'], { type: 'application/pdf' })
    const fetchPdf = vi.fn().mockResolvedValue(blob)
    render(<PDFDownloadButton fetchPdf={fetchPdf} filename="doc.pdf" />)
    fireEvent.click(screen.getByRole('button'))
    await waitFor(() => expect(revokeObjectURLMock).toHaveBeenCalled())
    expect(createObjectURLMock).toHaveBeenCalledWith(blob)
  })

  it('appelle onError en cas d\'échec', async () => {
    const error = new Error('Erreur réseau')
    const fetchPdf = vi.fn().mockRejectedValue(error)
    const onError = vi.fn()
    render(<PDFDownloadButton fetchPdf={fetchPdf} filename="doc.pdf" onError={onError} />)
    fireEvent.click(screen.getByRole('button'))
    await waitFor(() => expect(onError).toHaveBeenCalledWith(error))
  })
})
