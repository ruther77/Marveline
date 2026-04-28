/**
 * Tests unitaires pour components/ui/Button.tsx
 * Button forwardRef — variants, sizes, loading, icons, disabled
 */
import { describe, it, expect, vi, createRef } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Button } from '../Button'

// ─── Rendu de base ────────────────────────────────────────────────────────────

describe('Button - rendu de base', () => {
  it('affiche le texte enfant', () => {
    render(<Button>Enregistrer</Button>)
    expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeInTheDocument()
  })

  it('est un élément button', () => {
    render(<Button>Test</Button>)
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('appelle onClick quand cliqué', () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Clic</Button>)
    fireEvent.click(screen.getByRole('button'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('applique une className personnalisée', () => {
    render(<Button className="my-custom">Test</Button>)
    expect(screen.getByRole('button').className).toContain('my-custom')
  })
})

// ─── Variants ─────────────────────────────────────────────────────────────────

describe('Button - variants', () => {
  const variants = ['primary', 'secondary', 'danger', 'ghost', 'outline', 'link'] as const

  for (const variant of variants) {
    it(`variant ${variant} se rend sans erreur`, () => {
      render(<Button variant={variant}>{variant}</Button>)
      expect(screen.getByRole('button')).toBeInTheDocument()
    })
  }
})

// ─── Sizes ────────────────────────────────────────────────────────────────────

describe('Button - sizes', () => {
  const sizes = ['xs', 'sm', 'md', 'lg'] as const

  for (const size of sizes) {
    it(`size ${size} se rend sans erreur`, () => {
      render(<Button size={size}>{size}</Button>)
      expect(screen.getByRole('button')).toBeInTheDocument()
    })
  }
})

// ─── Loading ──────────────────────────────────────────────────────────────────

describe('Button - loading', () => {
  it('loading=true : bouton est disabled', () => {
    render(<Button loading>Chargement</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('loading=true : onClick ne se déclenche pas', () => {
    const onClick = vi.fn()
    render(<Button loading onClick={onClick}>Chargement</Button>)
    fireEvent.click(screen.getByRole('button'))
    expect(onClick).not.toHaveBeenCalled()
  })

  it('loading=true : rend le spinner (Loader2)', () => {
    const { container } = render(<Button loading>Chargement</Button>)
    // Loader2 de lucide-react rend un svg
    const svg = container.querySelector('svg')
    expect(svg).not.toBeNull()
  })

  it('loading=false : rightIcon est visible', () => {
    render(<Button rightIcon={<span data-testid="ricon">→</span>}>Texte</Button>)
    expect(screen.getByTestId('ricon')).toBeInTheDocument()
  })

  it('loading=true : rightIcon est caché', () => {
    render(<Button loading rightIcon={<span data-testid="ricon">→</span>}>Texte</Button>)
    expect(screen.queryByTestId('ricon')).toBeNull()
  })
})

// ─── Disabled ─────────────────────────────────────────────────────────────────

describe('Button - disabled', () => {
  it('disabled=true : bouton est disabled', () => {
    render(<Button disabled>Désactivé</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('disabled=true : onClick ne se déclenche pas', () => {
    const onClick = vi.fn()
    render(<Button disabled onClick={onClick}>Désactivé</Button>)
    fireEvent.click(screen.getByRole('button'))
    expect(onClick).not.toHaveBeenCalled()
  })
})

// ─── Icons ────────────────────────────────────────────────────────────────────

describe('Button - leftIcon / rightIcon', () => {
  it('leftIcon est affiché', () => {
    render(<Button leftIcon={<span data-testid="licon">←</span>}>Texte</Button>)
    expect(screen.getByTestId('licon')).toBeInTheDocument()
  })

  it('rightIcon est affiché', () => {
    render(<Button rightIcon={<span data-testid="ricon">→</span>}>Texte</Button>)
    expect(screen.getByTestId('ricon')).toBeInTheDocument()
  })

  it('loading=true masque leftIcon et affiche le spinner', () => {
    render(<Button loading leftIcon={<span data-testid="licon">←</span>}>Texte</Button>)
    expect(screen.queryByTestId('licon')).toBeNull()
    const { container } = render(<Button loading>X</Button>)
    expect(container.querySelector('svg')).not.toBeNull()
  })
})

// ─── forwardRef ───────────────────────────────────────────────────────────────

describe('Button - forwardRef', () => {
  it('transmet la ref au bouton DOM', () => {
    const ref = { current: null } as React.RefObject<HTMLButtonElement>
    render(<Button ref={ref}>Ref</Button>)
    expect(ref.current).not.toBeNull()
    expect(ref.current?.tagName.toLowerCase()).toBe('button')
  })
})

// ─── displayName ─────────────────────────────────────────────────────────────

describe('Button - displayName', () => {
  it('displayName = "Button"', () => {
    expect(Button.displayName).toBe('Button')
  })
})
