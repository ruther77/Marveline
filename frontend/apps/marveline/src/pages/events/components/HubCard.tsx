import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface HubCardProps {
  icon: ReactNode
  title: string
  summary: string
  statusColor?: 'green' | 'amber' | 'red' | 'blue' | 'default'
  onClick: () => void
  hidden?: boolean
}

const STATUS_RING: Record<string, string> = {
  green: 'border-green-500/30 hover:border-green-400/60',
  amber: 'border-amber-500/30 hover:border-amber-400/60',
  red: 'border-red-500/30 hover:border-red-400/60',
  blue: 'border-blue-500/30 hover:border-blue-400/60',
  default: 'border-dark-600 hover:border-dark-500',
}

export function HubCard({ icon, title, summary, statusColor = 'default', onClick, hidden }: HubCardProps) {
  if (hidden) return null

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full text-left rounded-xl bg-dark-900 p-4 border transition-colors',
        STATUS_RING[statusColor],
      )}
    >
      <div className="flex items-center gap-3">
        <span className="text-dark-400 shrink-0">{icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{title}</p>
          <p className="text-xs text-dark-400 truncate">{summary}</p>
        </div>
      </div>
    </button>
  )
}
