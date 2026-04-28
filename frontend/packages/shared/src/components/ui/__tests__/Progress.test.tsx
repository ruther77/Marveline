/**
 * Tests unitaires pour components/ui/Progress.tsx
 * Progress, CircularProgress, StepsProgress
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Progress, CircularProgress, StepsProgress } from '../Progress'

// ─── Progress ─────────────────────────────────────────────────────────────────

describe('Progress - rendu de base', () => {
  it('rend avec role="progressbar"', () => {
    render(<Progress value={50} />)
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('aria-valuenow = valeur courante', () => {
    render(<Progress value={60} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '60')
  })

  it('aria-valuemax = max (défaut 100)', () => {
    render(<Progress value={50} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuemax', '100')
  })

  it('aria-valuemax = max personnalisé', () => {
    render(<Progress value={50} max={200} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuemax', '200')
  })
})

describe('Progress - showLabel', () => {
  it('showLabel=false : pas de pourcentage visible', () => {
    render(<Progress value={75} />)
    expect(screen.queryByText(/75%/)).toBeNull()
  })

  it('showLabel=true : affiche le pourcentage', () => {
    render(<Progress value={75} showLabel />)
    expect(screen.getByText('75%')).toBeInTheDocument()
  })

  it('showLabel arrondit les décimales', () => {
    render(<Progress value={33} max={100} showLabel />)
    expect(screen.getByText('33%')).toBeInTheDocument()
  })

  it('affiche le label texte si fourni', () => {
    render(<Progress value={50} label="Progression" />)
    expect(screen.getByText('Progression')).toBeInTheDocument()
  })
})

describe('Progress - calcul pourcentage', () => {
  it('value=0 → largeur 0%', () => {
    const { container } = render(<Progress value={0} />)
    const bar = container.querySelector('[style]') as HTMLElement
    expect(bar.style.width).toBe('0%')
  })

  it('value=100 → largeur 100%', () => {
    const { container } = render(<Progress value={100} />)
    const bar = container.querySelector('[style]') as HTMLElement
    expect(bar.style.width).toBe('100%')
  })

  it('value > max est plafonné à 100%', () => {
    const { container } = render(<Progress value={150} max={100} />)
    const bar = container.querySelector('[style]') as HTMLElement
    expect(bar.style.width).toBe('100%')
  })

  it('value < 0 est planché à 0%', () => {
    const { container } = render(<Progress value={-10} />)
    const bar = container.querySelector('[style]') as HTMLElement
    expect(bar.style.width).toBe('0%')
  })
})

describe('Progress - variants', () => {
  const variants = ['default', 'success', 'warning', 'danger', 'info'] as const

  for (const variant of variants) {
    it(`variant ${variant} se rend`, () => {
      render(<Progress value={50} variant={variant} />)
      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })
  }
})

describe('Progress - sizes', () => {
  const sizes = ['xs', 'sm', 'md', 'lg'] as const

  for (const size of sizes) {
    it(`size ${size} se rend`, () => {
      render(<Progress value={50} size={size} />)
      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })
  }
})

// ─── CircularProgress ─────────────────────────────────────────────────────────

describe('CircularProgress - rendu de base', () => {
  it('affiche le pourcentage par défaut', () => {
    render(<CircularProgress value={75} />)
    expect(screen.getByText('75%')).toBeInTheDocument()
  })

  it('showLabel=false : pas de pourcentage', () => {
    render(<CircularProgress value={75} showLabel={false} />)
    expect(screen.queryByText('75%')).toBeNull()
  })

  it('affiche le label si fourni', () => {
    render(<CircularProgress value={50} label="Complet" />)
    expect(screen.getByText('Complet')).toBeInTheDocument()
  })

  it('rend un SVG', () => {
    const { container } = render(<CircularProgress value={50} />)
    expect(container.querySelector('svg')).not.toBeNull()
  })
})

describe('CircularProgress - clamping', () => {
  it('value=0 affiche 0%', () => {
    render(<CircularProgress value={0} />)
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('value=100 affiche 100%', () => {
    render(<CircularProgress value={100} />)
    expect(screen.getByText('100%')).toBeInTheDocument()
  })
})

// ─── StepsProgress ────────────────────────────────────────────────────────────

describe('StepsProgress - rendu de base', () => {
  const steps = [
    { label: 'Étape 1' },
    { label: 'Étape 2' },
    { label: 'Étape 3' },
  ]

  it('affiche tous les labels d\'étapes', () => {
    render(<StepsProgress steps={steps} />)
    expect(screen.getByText('Étape 1')).toBeInTheDocument()
    expect(screen.getByText('Étape 2')).toBeInTheDocument()
    expect(screen.getByText('Étape 3')).toBeInTheDocument()
  })

  it('affiche les numéros pour les étapes pending/current', () => {
    render(<StepsProgress steps={steps} currentStep={0} />)
    // L'étape 2 (index 1) est pending → affiche "2"
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('affiche la description si fournie', () => {
    const stepsDesc = [{ label: 'Étape', description: 'Desc ici' }]
    render(<StepsProgress steps={stepsDesc} />)
    expect(screen.getByText('Desc ici')).toBeInTheDocument()
  })
})

describe('StepsProgress - orientation', () => {
  const steps = [{ label: 'A' }, { label: 'B' }]

  it('orientation horizontal par défaut', () => {
    render(<StepsProgress steps={steps} currentStep={0} />)
    expect(screen.getByText('A')).toBeInTheDocument()
  })

  it('orientation vertical se rend', () => {
    render(<StepsProgress steps={steps} currentStep={0} orientation="vertical" />)
    expect(screen.getByText('A')).toBeInTheDocument()
  })
})
