// Diff visuel entre deux désignations — highlight caractères différents

import { useMemo } from 'react'

interface DesignationDiffProps {
  textA: string
  textB: string
  labelA?: string
  labelB?: string
}

interface DiffSegment {
  text: string
  type: 'same' | 'added' | 'removed'
}

function computeDiff(a: string, b: string): { diffA: DiffSegment[]; diffB: DiffSegment[] } {
  const wordsA = a.split(/(\s+)/)
  const wordsB = b.split(/(\s+)/)

  const diffA: DiffSegment[] = []
  const diffB: DiffSegment[] = []

  const setB = new Set(wordsB.map(w => w.toLowerCase().trim()).filter(Boolean))
  const setA = new Set(wordsA.map(w => w.toLowerCase().trim()).filter(Boolean))

  for (const w of wordsA) {
    if (!w.trim()) { diffA.push({ text: w, type: 'same' }); continue }
    diffA.push({ text: w, type: setB.has(w.toLowerCase().trim()) ? 'same' : 'removed' })
  }

  for (const w of wordsB) {
    if (!w.trim()) { diffB.push({ text: w, type: 'same' }); continue }
    diffB.push({ text: w, type: setA.has(w.toLowerCase().trim()) ? 'same' : 'added' })
  }

  return { diffA, diffB }
}

function DiffLine({ segments }: { segments: DiffSegment[] }) {
  return (
    <span>
      {segments.map((s, i) => (
        <span key={i} className={
          s.type === 'removed' ? 'bg-red-100 text-red-700 px-0.5 rounded' :
          s.type === 'added' ? 'bg-green-100 text-green-700 px-0.5 rounded' :
          'text-slate-700'
        }>
          {s.text}
        </span>
      ))}
    </span>
  )
}

export default function DesignationDiff({ textA, textB, labelA = 'Entrante', labelB = 'Catalogue' }: DesignationDiffProps) {
  const { diffA, diffB } = useMemo(() => computeDiff(textA, textB), [textA, textB])

  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="bg-slate-50 rounded-lg p-3">
        <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">{labelA}</p>
        <p className="text-sm font-medium leading-relaxed"><DiffLine segments={diffA} /></p>
      </div>
      <div className="bg-slate-50 rounded-lg p-3">
        <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">{labelB}</p>
        <p className="text-sm font-medium leading-relaxed"><DiffLine segments={diffB} /></p>
      </div>
    </div>
  )
}
