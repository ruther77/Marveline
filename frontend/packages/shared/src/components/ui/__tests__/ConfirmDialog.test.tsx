/**
 * Tests unitaires pour components/ui/ConfirmDialog.tsx
 * ConfirmDialog, DeleteConfirm, LogoutConfirm, UnsavedChangesConfirm
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import {
  ConfirmDialog,
  DeleteConfirm,
  LogoutConfirm,
  UnsavedChangesConfirm,
} from '../ConfirmDialog'

// ─── ConfirmDialog ────────────────────────────────────────────────────────────

describe('ConfirmDialog - isOpen=false', () => {
  it('ne rend rien si isOpen=false', () => {
    const { container } = render(
      <ConfirmDialog
        isOpen={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Titre"
      />
    )
    expect(container.firstChild).toBeNull()
  })
})

describe('ConfirmDialog - rendu de base', () => {
  it('affiche le titre', () => {
    render(
      <ConfirmDialog
        isOpen
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Confirmer l'action"
      />
    )
    expect(screen.getByText("Confirmer l'action")).toBeInTheDocument()
  })

  it('affiche la description si fournie', () => {
    render(
      <ConfirmDialog
        isOpen
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Titre"
        description="Cette action est irréversible."
      />
    )
    expect(screen.getByText('Cette action est irréversible.')).toBeInTheDocument()
  })

  it('affiche les boutons Annuler et Confirmer par défaut', () => {
    render(
      <ConfirmDialog
        isOpen
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Titre"
      />
    )
    expect(screen.getByText('Annuler')).toBeInTheDocument()
    expect(screen.getByText('Confirmer')).toBeInTheDocument()
  })

  it('utilise confirmText et cancelText personnalisés', () => {
    render(
      <ConfirmDialog
        isOpen
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Titre"
        confirmText="Supprimer"
        cancelText="Retour"
      />
    )
    expect(screen.getByText('Supprimer')).toBeInTheDocument()
    expect(screen.getByText('Retour')).toBeInTheDocument()
  })
})

describe('ConfirmDialog - interactions', () => {
  it('clic Confirmer appelle onConfirm', () => {
    const onConfirm = vi.fn()
    render(
      <ConfirmDialog
        isOpen
        onClose={vi.fn()}
        onConfirm={onConfirm}
        title="Titre"
      />
    )
    fireEvent.click(screen.getByText('Confirmer'))
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('clic Annuler appelle onClose', () => {
    const onClose = vi.fn()
    render(
      <ConfirmDialog
        isOpen
        onClose={onClose}
        onConfirm={vi.fn()}
        title="Titre"
      />
    )
    fireEvent.click(screen.getByText('Annuler'))
    expect(onClose).toHaveBeenCalledOnce()
  })
})

describe('ConfirmDialog - loading', () => {
  it('loading=true : bouton Annuler est désactivé', () => {
    render(
      <ConfirmDialog
        isOpen
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Titre"
        loading
      />
    )
    expect(screen.getByText('Annuler').closest('button')).toBeDisabled()
  })
})

describe('ConfirmDialog - icon personnalisée', () => {
  it('affiche l\'icon fournie', () => {
    render(
      <ConfirmDialog
        isOpen
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Titre"
        icon={<span data-testid="custom-icon">★</span>}
      />
    )
    expect(screen.getByTestId('custom-icon')).toBeInTheDocument()
  })
})

describe('ConfirmDialog - variants', () => {
  const variants = ['danger', 'warning', 'info', 'default'] as const

  for (const variant of variants) {
    it(`variant ${variant} se rend avec titre visible`, () => {
      render(
        <ConfirmDialog
          isOpen
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          title={`Variant ${variant}`}
          variant={variant}
        />
      )
      expect(screen.getByText(`Variant ${variant}`)).toBeInTheDocument()
    })
  }
})

// ─── DeleteConfirm ────────────────────────────────────────────────────────────

describe('DeleteConfirm', () => {
  it('affiche le titre "Supprimer cet élément ?"', () => {
    render(
      <DeleteConfirm isOpen onClose={vi.fn()} onConfirm={vi.fn()} />
    )
    expect(screen.getByText('Supprimer cet élément ?')).toBeInTheDocument()
  })

  it('affiche le bouton "Supprimer"', () => {
    render(
      <DeleteConfirm isOpen onClose={vi.fn()} onConfirm={vi.fn()} />
    )
    expect(screen.getByText('Supprimer')).toBeInTheDocument()
  })

  it('inclut itemName dans la description', () => {
    render(
      <DeleteConfirm
        isOpen
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        itemName="Produit ABC"
      />
    )
    expect(screen.getByText(/Produit ABC/)).toBeInTheDocument()
  })
})

// ─── LogoutConfirm ────────────────────────────────────────────────────────────

describe('LogoutConfirm', () => {
  it('affiche le titre "Se déconnecter ?"', () => {
    render(
      <LogoutConfirm isOpen onClose={vi.fn()} onConfirm={vi.fn()} />
    )
    expect(screen.getByText('Se déconnecter ?')).toBeInTheDocument()
  })

  it('affiche le bouton "Se déconnecter"', () => {
    render(
      <LogoutConfirm isOpen onClose={vi.fn()} onConfirm={vi.fn()} />
    )
    expect(screen.getByText('Se déconnecter')).toBeInTheDocument()
  })
})

// ─── UnsavedChangesConfirm ────────────────────────────────────────────────────

describe('UnsavedChangesConfirm', () => {
  it('affiche le titre "Modifications non enregistrées"', () => {
    render(
      <UnsavedChangesConfirm isOpen onClose={vi.fn()} onConfirm={vi.fn()} />
    )
    expect(screen.getByText('Modifications non enregistrées')).toBeInTheDocument()
  })

  it('affiche "Ne pas enregistrer" et "Annuler"', () => {
    render(
      <UnsavedChangesConfirm isOpen onClose={vi.fn()} onConfirm={vi.fn()} />
    )
    expect(screen.getByText('Ne pas enregistrer')).toBeInTheDocument()
    expect(screen.getByText('Annuler')).toBeInTheDocument()
  })

  it('affiche "Enregistrer" si onSave fourni', () => {
    render(
      <UnsavedChangesConfirm
        isOpen
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        onSave={vi.fn()}
      />
    )
    expect(screen.getByText('Enregistrer')).toBeInTheDocument()
  })

  it('n\'affiche pas "Enregistrer" si onSave absent', () => {
    render(
      <UnsavedChangesConfirm isOpen onClose={vi.fn()} onConfirm={vi.fn()} />
    )
    expect(screen.queryByText('Enregistrer')).toBeNull()
  })

  it('clic "Ne pas enregistrer" appelle onConfirm', () => {
    const onConfirm = vi.fn()
    render(
      <UnsavedChangesConfirm isOpen onClose={vi.fn()} onConfirm={onConfirm} />
    )
    fireEvent.click(screen.getByText('Ne pas enregistrer'))
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('clic "Enregistrer" appelle onSave', () => {
    const onSave = vi.fn()
    render(
      <UnsavedChangesConfirm
        isOpen
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        onSave={onSave}
      />
    )
    fireEvent.click(screen.getByText('Enregistrer'))
    expect(onSave).toHaveBeenCalledOnce()
  })
})
