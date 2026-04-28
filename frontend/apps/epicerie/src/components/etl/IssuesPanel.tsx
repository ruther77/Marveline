// Panel issues groupées par type — correction guidée

import { useMemo, useState } from 'react'
import type { LigneFactureRead, LigneFieldAlerts } from '@/types/etl_import'
import { validateLigne, FIELD_ACTION_LABELS } from '@/types/etl_import'

interface IssueGroup {
  field: keyof LigneFieldAlerts
  label: string
  severity: 'error' | 'warning'
  lignes: LigneFactureRead[]
}

interface IssuesPanelProps {
  lignes: LigneFactureRead[]
  onFocusLine: (idx: number, field: string) => void
}

const FIELD_ICONS: Record<keyof LigneFieldAlerts, string> = {
  quantite: '🔢',
  prix_unitaire_cts: '💰',
  ean: '📦',
  categorie_code: '🏷️',
  marque: '🏭',
}

export default function IssuesPanel({ lignes, onFocusLine }: IssuesPanelProps) {
  const groups = useMemo(() => {
    const map = new Map<string, IssueGroup>()

    for (const l of lignes) {
      const v = validateLigne(l)
      for (const [field, alert] of Object.entries(v.fields)) {
        if (!alert) continue
        const key = `${field}-${alert}`
        if (!map.has(key)) {
          map.set(key, {
            field: field as keyof LigneFieldAlerts,
            label: FIELD_ACTION_LABELS[field as keyof LigneFieldAlerts],
            severity: alert,
            lignes: [],
          })
        }
        map.get(key)!.lignes.push(l)
      }
    }

    return Array.from(map.values()).sort((a, b) => {
      if (a.severity !== b.severity) return a.severity === 'error' ? -1 : 1
      return b.lignes.length - a.lignes.length
    })
  }, [lignes])

  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  const toggle = (key: string) => {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  if (groups.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="text-5xl mb-4">✅</div>
        <h3 className="text-lg font-semibold text-slate-800 mb-1">Toutes les lignes sont complètes</h3>
        <p className="text-sm text-slate-500">Vous pouvez valider cet import en toute confiance.</p>
      </div>
    )
  }

  const totalIssues = groups.reduce((s, g) => s + g.lignes.length, 0)

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm text-slate-600">
        <span className="font-medium">{totalIssues} correction{totalIssues > 1 ? 's' : ''} nécessaire{totalIssues > 1 ? 's' : ''}</span>
        <span className="text-slate-400">·</span>
        <span className="text-slate-400">{groups.length} type{groups.length > 1 ? 's' : ''} de problème</span>
      </div>

      {groups.map(g => {
        const key = `${g.field}-${g.severity}`
        const isCollapsed = collapsed.has(key)
        const borderColor = g.severity === 'error' ? 'border-red-200' : 'border-amber-200'
        const bgColor = g.severity === 'error' ? 'bg-red-50' : 'bg-amber-50'
        const textColor = g.severity === 'error' ? 'text-red-700' : 'text-amber-700'
        const badgeColor = g.severity === 'error' ? 'bg-red-100 text-red-600' : 'bg-amber-100 text-amber-600'

        return (
          <div key={key} className={`border ${borderColor} rounded-xl overflow-hidden`}>
            <button
              onClick={() => toggle(key)}
              className={`w-full flex items-center gap-3 px-4 py-3 ${bgColor} hover:opacity-90 transition-opacity`}
            >
              <span className="text-lg">{FIELD_ICONS[g.field]}</span>
              <span className={`text-sm font-semibold ${textColor} flex-1 text-left`}>
                {g.label}
              </span>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${badgeColor}`}>
                {g.lignes.length}
              </span>
              <span className="text-slate-400 text-xs">{isCollapsed ? '▸' : '▾'}</span>
            </button>

            {!isCollapsed && (
              <div className="divide-y divide-slate-100">
                {g.lignes.map(l => (
                  <button
                    key={l.idx}
                    onClick={() => onFocusLine(l.idx, g.field)}
                    className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 transition-colors text-left"
                  >
                    <span className="text-xs text-slate-400 font-mono w-6">#{l.idx}</span>
                    <span className="text-sm text-slate-700 flex-1 truncate">{l.designation}</span>
                    <span className="text-xs text-emerald-600 font-medium shrink-0">Corriger →</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
