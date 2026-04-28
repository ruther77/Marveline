import { useState, ReactNode } from 'react'
import { ZodSchema } from 'zod'
import { Button } from './Button'
import { cn } from '../../lib/utils'

export interface StepDef {
  label: string
  component: ReactNode
  schema?: ZodSchema
  data?: unknown
}

export interface StepperFormProps {
  steps: StepDef[]
  onComplete: () => void
  onStepChange?: (step: number) => void
  isSubmitting?: boolean
  submitLabel?: string
}

export function StepperForm({
  steps,
  onComplete,
  onStepChange,
  isSubmitting = false,
  submitLabel = 'Terminer',
}: StepperFormProps) {
  const [current, setCurrent] = useState(0)
  const [error, setError] = useState<string | null>(null)

  function goNext() {
    const step = steps[current]
    if (step.schema && step.data !== undefined) {
      const result = step.schema.safeParse(step.data)
      if (!result.success) {
        setError(result.error.errors[0]?.message ?? 'Données invalides')
        return
      }
    }
    setError(null)
    if (current < steps.length - 1) {
      const next = current + 1
      setCurrent(next)
      onStepChange?.(next)
    } else {
      onComplete()
    }
  }

  function goPrev() {
    if (current > 0) {
      setError(null)
      const prev = current - 1
      setCurrent(prev)
      onStepChange?.(prev)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Barre de progression */}
      <div className="flex items-center gap-2">
        {steps.map((s, i) => (
          <div key={i} className="flex items-center gap-2 flex-1 last:flex-none">
            <div className={cn(
              'w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0',
              i < current ? 'bg-green-600 text-white' :
              i === current ? 'bg-primary-600 text-white' :
              'bg-dark-900 text-dark-400'
            )}>
              {i < current ? '✓' : i + 1}
            </div>
            <span className={cn('text-sm hidden sm:block', i === current ? 'text-dark-50' : 'text-dark-400')}>
              {s.label}
            </span>
            {i < steps.length - 1 && <div className="flex-1 h-px bg-dark-600 mx-1" />}
          </div>
        ))}
      </div>

      {/* Contenu de l'étape */}
      <div>{steps[current].component}</div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {/* Navigation */}
      <div className="flex justify-between">
        <Button variant="secondary" onClick={goPrev} disabled={current === 0}>
          Précédent
        </Button>
        <Button onClick={goNext} loading={isSubmitting && current === steps.length - 1}>
          {current === steps.length - 1 ? submitLabel : 'Suivant'}
        </Button>
      </div>
    </div>
  )
}
