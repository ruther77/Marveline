import { useState, useEffect } from 'react'
import { cn } from '../../lib/utils'

interface CountdownChipProps {
  targetDate: string
  className?: string
}

function computeDiff(target: string) {
  const now = Date.now()
  const end = new Date(target + 'T00:00:00').getTime()
  const diff = end - now
  if (diff <= 0) return { days: 0, hours: 0, minutes: 0, overdue: true, totalMs: diff }

  const days = Math.floor(diff / 86400000)
  const hours = Math.floor((diff % 86400000) / 3600000)
  const minutes = Math.floor((diff % 3600000) / 60000)
  return { days, hours, minutes, overdue: false, totalMs: diff }
}

function getVariant(days: number, overdue: boolean): 'ok' | 'warn' | 'danger' {
  if (overdue) return 'danger'
  if (days <= 1) return 'danger'
  if (days <= 3) return 'warn'
  return 'ok'
}

const VARIANT_STYLES = {
  ok: 'bg-green-500/10 border-green-500/30',
  warn: 'bg-amber-500/10 border-amber-500/30',
  danger: 'bg-red-500/10 border-red-500/30',
}

const VALUE_STYLES = {
  ok: 'text-green-400',
  warn: 'text-amber-400',
  danger: 'text-red-400',
}

export function CountdownChip({ targetDate, className }: CountdownChipProps) {
  const [diff, setDiff] = useState(() => computeDiff(targetDate))

  useEffect(() => {
    const id = setInterval(() => setDiff(computeDiff(targetDate)), 60000)
    return () => clearInterval(id)
  }, [targetDate])

  const variant = getVariant(diff.days, diff.overdue)

  if (diff.overdue) {
    const overdueDays = Math.abs(Math.ceil(diff.totalMs / 86400000))
    return (
      <div className={cn('inline-flex items-center gap-2 border rounded-xl px-3 py-2', VARIANT_STYLES[variant], className)}>
        <div className="text-center">
          <div className={cn('font-display text-xl font-extrabold leading-none', VALUE_STYLES[variant])}>
            +{overdueDays}
          </div>
          <div className="text-[9px] font-semibold text-dark-500 mt-0.5">j retard</div>
        </div>
      </div>
    )
  }

  return (
    <div className={cn('inline-flex items-center gap-2 border rounded-xl px-3 py-2', VARIANT_STYLES[variant], className)}>
      <div className="text-center">
        <div className={cn('font-display text-xl font-extrabold leading-none', VALUE_STYLES[variant])}>
          {diff.days}
        </div>
        <div className="text-[9px] font-semibold text-dark-500 mt-0.5">j</div>
      </div>
      <div className={cn('font-display text-lg font-extrabold', 'text-dark-500')}>:</div>
      <div className="text-center">
        <div className={cn('font-display text-xl font-extrabold leading-none', VALUE_STYLES[variant])}>
          {String(diff.hours).padStart(2, '0')}
        </div>
        <div className="text-[9px] font-semibold text-dark-500 mt-0.5">h</div>
      </div>
      <div className={cn('font-display text-lg font-extrabold', 'text-dark-500')}>:</div>
      <div className="text-center">
        <div className={cn('font-display text-xl font-extrabold leading-none', VALUE_STYLES[variant])}>
          {String(diff.minutes).padStart(2, '0')}
        </div>
        <div className="text-[9px] font-semibold text-dark-500 mt-0.5">m</div>
      </div>
    </div>
  )
}
