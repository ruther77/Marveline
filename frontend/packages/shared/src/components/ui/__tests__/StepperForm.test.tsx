/**
 * Tests unitaires pour components/ui/StepperForm.tsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { StepperForm } from '../StepperForm'
import { z } from 'zod'

const steps = [
  { label: 'Étape 1', component: <div>Contenu étape 1</div> },
  { label: 'Étape 2', component: <div>Contenu étape 2</div> },
  { label: 'Étape 3', component: <div>Contenu étape 3</div> },
]

describe('StepperForm - rendu de base', () => {
  it('affiche les labels des étapes', () => {
    render(<StepperForm steps={steps} onComplete={vi.fn()} />)
    expect(screen.getByText('Étape 1')).toBeInTheDocument()
    expect(screen.getByText('Étape 2')).toBeInTheDocument()
    expect(screen.getByText('Étape 3')).toBeInTheDocument()
  })

  it('affiche le contenu de la première étape', () => {
    render(<StepperForm steps={steps} onComplete={vi.fn()} />)
    expect(screen.getByText('Contenu étape 1')).toBeInTheDocument()
    expect(screen.queryByText('Contenu étape 2')).toBeNull()
  })

  it('bouton "Suivant" présent', () => {
    render(<StepperForm steps={steps} onComplete={vi.fn()} />)
    expect(screen.getByText('Suivant')).toBeInTheDocument()
  })

  it('bouton "Précédent" désactivé à la première étape', () => {
    render(<StepperForm steps={steps} onComplete={vi.fn()} />)
    expect(screen.getByText('Précédent').closest('button')).toBeDisabled()
  })
})

describe('StepperForm - navigation', () => {
  it('Suivant → passe à l\'étape 2', () => {
    render(<StepperForm steps={steps} onComplete={vi.fn()} />)
    fireEvent.click(screen.getByText('Suivant'))
    expect(screen.getByText('Contenu étape 2')).toBeInTheDocument()
  })

  it('Suivant → "Précédent" activé', () => {
    render(<StepperForm steps={steps} onComplete={vi.fn()} />)
    fireEvent.click(screen.getByText('Suivant'))
    expect(screen.getByText('Précédent').closest('button')).not.toBeDisabled()
  })

  it('Précédent → retourne à l\'étape 1', () => {
    render(<StepperForm steps={steps} onComplete={vi.fn()} />)
    fireEvent.click(screen.getByText('Suivant'))
    fireEvent.click(screen.getByText('Précédent'))
    expect(screen.getByText('Contenu étape 1')).toBeInTheDocument()
  })

  it('onStepChange appelé lors du passage à l\'étape suivante', () => {
    const onStepChange = vi.fn()
    render(<StepperForm steps={steps} onComplete={vi.fn()} onStepChange={onStepChange} />)
    fireEvent.click(screen.getByText('Suivant'))
    expect(onStepChange).toHaveBeenCalledWith(1)
  })

  it('dernier étape → bouton "Terminer"', () => {
    render(<StepperForm steps={steps} onComplete={vi.fn()} />)
    fireEvent.click(screen.getByText('Suivant'))
    fireEvent.click(screen.getByText('Suivant'))
    expect(screen.getByText('Terminer')).toBeInTheDocument()
  })

  it('clic "Terminer" appelle onComplete', () => {
    const onComplete = vi.fn()
    render(<StepperForm steps={steps} onComplete={onComplete} />)
    fireEvent.click(screen.getByText('Suivant'))
    fireEvent.click(screen.getByText('Suivant'))
    fireEvent.click(screen.getByText('Terminer'))
    expect(onComplete).toHaveBeenCalledOnce()
  })

  it('submitLabel personnalisé', () => {
    render(<StepperForm steps={[steps[0]]} onComplete={vi.fn()} submitLabel="Valider" />)
    expect(screen.getByText('Valider')).toBeInTheDocument()
  })
})

describe('StepperForm - validation Zod', () => {
  it('erreur de validation empêche avancer', () => {
    const schema = z.object({ name: z.string().min(1) })
    const stepsWithSchema = [
      { label: 'Étape 1', component: <div>Contenu step 1</div>, schema, data: { name: '' } },
      { label: 'Étape 2', component: <div>Contenu step 2 uniquement</div> },
    ]
    render(<StepperForm steps={stepsWithSchema} onComplete={vi.fn()} />)
    fireEvent.click(screen.getByText('Suivant'))
    // L'erreur est affichée et on reste sur l'étape 1
    expect(screen.queryByText('Contenu step 2 uniquement')).toBeNull()
    expect(screen.getByText(/invalide|required|trop court|character|Données/i)).toBeInTheDocument()
  })

  it('validation OK → passe à l\'étape suivante', () => {
    const schema = z.object({ name: z.string().min(1) })
    const stepsWithSchema = [
      { label: 'Étape 1', component: <div>Contenu step 1</div>, schema, data: { name: 'Alice' } },
      { label: 'Étape 2', component: <div>Contenu step 2 uniquement</div> },
    ]
    render(<StepperForm steps={stepsWithSchema} onComplete={vi.fn()} />)
    fireEvent.click(screen.getByText('Suivant'))
    expect(screen.getByText('Contenu step 2 uniquement')).toBeInTheDocument()
  })
})

describe('StepperForm - isSubmitting', () => {
  it('isSubmitting=true → bouton Terminer désactivé', () => {
    render(<StepperForm steps={[steps[0]]} onComplete={vi.fn()} isSubmitting />)
    expect(screen.getByText('Terminer').closest('button')).toBeDisabled()
  })
})
