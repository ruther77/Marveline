import type { CustomerRFM, RFMSegment } from '@/types/customer'

const SEGMENT_CONFIG: Record<RFMSegment, { color: string; bg: string; label: string }> = {
  Champions:  { color: 'text-green-300',  bg: 'bg-green-900/40 border-green-700/40',  label: 'Champions' },
  Loyal:      { color: 'text-blue-300',   bg: 'bg-blue-900/40 border-blue-700/40',   label: 'Fidèles' },
  Potential:  { color: 'text-yellow-300', bg: 'bg-yellow-900/40 border-yellow-700/40', label: 'Potentiels' },
  New:        { color: 'text-cyan-300',   bg: 'bg-cyan-900/40 border-cyan-700/40',   label: 'Nouveaux' },
  'At Risk':  { color: 'text-orange-300', bg: 'bg-orange-900/40 border-orange-700/40', label: 'À risque' },
  Lost:       { color: 'text-red-300',    bg: 'bg-red-900/40 border-red-700/40',    label: 'Perdus' },
}

const ALL_SEGMENTS: RFMSegment[] = ['Champions', 'Loyal', 'Potential', 'New', 'At Risk', 'Lost']

interface RFMMatrixProps {
  items: CustomerRFM[]
  selectedSegment: RFMSegment | null
  onSegmentClick: (segment: RFMSegment | null) => void
}

export function RFMMatrix({ items, selectedSegment, onSegmentClick }: RFMMatrixProps) {
  const countBySegment: Record<string, number> = {}
  for (const item of items) {
    countBySegment[item.segment] = (countBySegment[item.segment] ?? 0) + 1
  }
  const total = items.length || 1

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
      {ALL_SEGMENTS.map((seg) => {
        const count = countBySegment[seg] ?? 0
        const pct = Math.round((count / total) * 100)
        const cfg = SEGMENT_CONFIG[seg]
        const isSelected = selectedSegment === seg
        return (
          <button
            key={seg}
            onClick={() => onSegmentClick(isSelected ? null : seg)}
            className={`rounded-xl border p-4 text-left transition-all ${cfg.bg} ${
              isSelected ? 'ring-2 ring-gold-500/60 scale-[1.02]' : 'hover:opacity-80'
            }`}
          >
            <p className={`text-sm font-semibold ${cfg.color}`}>{cfg.label}</p>
            <p className="text-2xl font-bold mt-1">{count}</p>
            <p className="text-xs text-dark-400 mt-0.5">{pct}% des clients</p>
          </button>
        )
      })}
    </div>
  )
}
