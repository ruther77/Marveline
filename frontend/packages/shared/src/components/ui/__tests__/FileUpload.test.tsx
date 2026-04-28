/**
 * Tests unitaires pour components/ui/FileUpload.tsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FileUpload } from '../FileUpload'

describe('FileUpload - rendu de base', () => {
  it('affiche le texte de la zone de dépôt', () => {
    render(<FileUpload onChange={vi.fn()} />)
    expect(screen.getByText('Glissez vos fichiers ici')).toBeInTheDocument()
  })

  it('affiche le lien parcourez', () => {
    render(<FileUpload onChange={vi.fn()} />)
    expect(screen.getByText('parcourez')).toBeInTheDocument()
  })

  it('affiche le label si fourni', () => {
    render(<FileUpload onChange={vi.fn()} label="Pièces jointes" />)
    expect(screen.getByText('Pièces jointes')).toBeInTheDocument()
  })

  it('affiche le hint si fourni', () => {
    render(<FileUpload onChange={vi.fn()} hint="Formats acceptés : PDF, JPG" />)
    expect(screen.getByText('Formats acceptés : PDF, JPG')).toBeInTheDocument()
  })

  it('affiche l\'erreur si fournie', () => {
    render(<FileUpload onChange={vi.fn()} error="Fichier trop volumineux" />)
    expect(screen.getByText('Fichier trop volumineux')).toBeInTheDocument()
  })
})

describe('FileUpload - sélection de fichiers', () => {
  it('input file présent dans le DOM', () => {
    const { container } = render(<FileUpload onChange={vi.fn()} />)
    expect(container.querySelector('input[type="file"]')).not.toBeNull()
  })

  it('accept transmis à l\'input file', () => {
    const { container } = render(<FileUpload onChange={vi.fn()} accept="image/*" />)
    const input = container.querySelector('input[type="file"]')
    expect(input?.getAttribute('accept')).toBe('image/*')
  })

  it('multiple=true → input[multiple]', () => {
    const { container } = render(<FileUpload onChange={vi.fn()} multiple />)
    const input = container.querySelector('input[type="file"]')
    expect(input).toHaveAttribute('multiple')
  })

  it('sélection d\'un fichier via input → onChange appelé', () => {
    const onChange = vi.fn()
    const { container } = render(<FileUpload onChange={onChange} />)
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['content'], 'test.pdf', { type: 'application/pdf' })
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    fireEvent.change(input)
    expect(onChange).toHaveBeenCalled()
  })
})

describe('FileUpload - fichiers affichés', () => {
  it('affiche le nom des fichiers sélectionnés', () => {
    const file = new File(['content'], 'document.pdf', { type: 'application/pdf' }) as any
    render(<FileUpload onChange={vi.fn()} value={[file]} />)
    expect(screen.getByText('document.pdf')).toBeInTheDocument()
  })

  it('clic supprimer → onChange avec liste sans le fichier', () => {
    const onChange = vi.fn()
    const file = new File(['content'], 'doc.pdf', { type: 'application/pdf' }) as any
    render(<FileUpload onChange={onChange} value={[file]} />)
    // Le bouton X est le seul bouton quand un fichier est affiché
    const btns = screen.getAllByRole('button')
    // Clic sur le dernier bouton (bouton supprimer du fichier)
    fireEvent.click(btns[btns.length - 1])
    expect(onChange).toHaveBeenCalledWith([])
  })
})
