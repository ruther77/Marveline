import { useState } from 'react'
import { cn } from '@/lib/utils'
import type { ReservationStatus } from '@/types/reservation'

interface Props {
  status: ReservationStatus
  deliveryDate?: string
  eventDate?: string
  returnDate?: string
  createdAt?: string
}

const STEPS = ['Créée', 'Départ', 'Événement', 'Retour', 'Clôture'] as const

function getCompletedIndex(status: ReservationStatus): number {
  switch (status) {
    case 'draft': return 0
    case 'confirmed':
    case 'confirmed_risk':
    case 'pre_check': return 0
    case 'delivered':
    case 'extended': return 1
    case 'returned':
    case 'returned_dispute': return 3
    case 'completed': return 4
    case 'cancelled': return -1
    default: return 0
  }
}

function formatShort(iso?: string): string {
  if (!iso) return ''
  const d = new Date(iso.includes('T') ? iso : `${iso}T12:00:00`)
  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })
}

export function ReservationTimeline({ status, deliveryDate, eventDate, returnDate, createdAt }: Props) {
  const completedIdx = getCompletedIndex(status)
  const isCancelled = status === 'cancelled'
  const [expanded, setExpanded] = useState(false)
  const dates = [
    formatShort(createdAt),
    formatShort(deliveryDate),
    formatShort(eventDate),
    formatShort(returnDate),
    '',
  ]

  const dotClass = (i: number) => {
    const done = !isCancelled && i <= completedIdx
    const active = !isCancelled && i === completedIdx + 1
    return cn(
      'rounded-full border-2 transition-all',
      isCancelled && 'bg-red-500/30 border-red-500',
      done && 'bg-primary-500 border-primary-500',
      active && 'bg-transparent border-primary-400 ring-2 ring-primary-400/30',
      !done && !active && !isCancelled && 'bg-dark-900 border-dark-600',
    )
  }

  const lineClass = (i: number) =>
    cn('flex-1 h-0.5 mx-1', !isCancelled && i < completedIdx ? 'bg-primary-500' : 'bg-dark-900')

  return (
    <>
      {/* Desktop : labels + dates toujours visibles */}
      <div className="hidden sm:flex items-center gap-0 w-full py-2">
        {STEPS.map((label, i) => {
          const done = !isCancelled && i <= completedIdx
          return (
            <div key={label} className="flex items-center flex-1 min-w-0">
              <div className="flex flex-col items-center gap-1 shrink-0">
                <div className={cn(dotClass(i), 'w-3 h-3')} />
                <span className={cn('text-[10px] leading-tight', done ? 'text-dark-200' : 'text-dark-500')}>
                  {label}
                </span>
                {dates[i] && (
                  <span className="text-[9px] text-dark-500 leading-none">{dates[i]}</span>
                )}
              </div>
              {i < STEPS.length - 1 && <div className={lineClass(i)} />}
            </div>
          )
        })}
      </div>

      {/* Mobile : dots seuls, tap pour expand */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="sm:hidden w-full py-2"
      >
        <div className="flex items-center gap-0 w-full">
          {STEPS.map((label, i) => (
            <div key={label} className="flex items-center flex-1 min-w-0">
              <div className="flex flex-col items-center gap-0.5 shrink-0">
                <div className={cn(dotClass(i), 'w-2.5 h-2.5')} />
                {expanded && (
                  <>
                    <span className={cn(
                      'text-[9px] leading-tight',
                      !isCancelled && i <= completedIdx ? 'text-dark-200' : 'text-dark-500',
                    )}>
                      {label}
                    </span>
                    {dates[i] && (
                      <span className="text-[8px] text-dark-500 leading-none">{dates[i]}</span>
                    )}
                  </>
                )}
              </div>
              {i < STEPS.length - 1 && <div className={lineClass(i)} />}
            </div>
          ))}
        </div>
        {!expanded && (
          <p className="text-[9px] text-dark-500 text-center mt-1">Appuyer pour détails</p>
        )}
      </button>
    </>
  )
}
