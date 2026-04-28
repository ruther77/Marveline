import { useState } from 'react'
import { formatDate, formatCents } from '@/lib/utils'
import type { DevisDetailFull, DevisVersion } from '@/types/devis'

interface DevisVersionsTabProps {
  devis: DevisDetailFull
  versions: DevisVersion[]
}

type SnapLine = { product_id?: number; bundle_id?: number; label: string; quantity: number; unit_price_cents: number }
type Snap = { total_cents?: number; notes?: string; lines?: SnapLine[]; event_date?: string; valid_until?: string }
type DiffStatus = 'added' | 'removed' | 'changed' | 'same'
type DiffLine = { lineKey: string; label: string; status: DiffStatus; snap?: SnapLine; current?: SnapLine }

function toLineKey(l: { product_id?: number; bundle_id?: number; label?: string }, index: number): string {
  if (l.bundle_id) return `b:${l.bundle_id}`
  if (l.product_id) return `p:${l.product_id}`
  return `free:${l.label ?? ''}:${index}`
}

function buildDiff(snapLines: SnapLine[], currentLines: DevisDetailFull['lines']): DiffLine[] {
  const snapByKey = Object.fromEntries(snapLines.map((l, i) => [toLineKey(l, i), l]))
  const currByKey = Object.fromEntries(currentLines.map((l, i) => [toLineKey(l, i), l]))
  const allKeys = new Set([...snapLines.map((l, i) => toLineKey(l, i)), ...currentLines.map((l, i) => toLineKey(l, i))])

  const diff: DiffLine[] = []
  allKeys.forEach((key) => {
    const s = snapByKey[key]
    const c = currByKey[key]
    if (s && !c) diff.push({ lineKey: key, label: s.label, status: 'removed', snap: s })
    else if (!s && c) diff.push({ lineKey: key, label: c.label, status: 'added', current: c })
    else if (s && c) {
      const changed = s.quantity !== c.quantity || s.unit_price_cents !== c.unit_price_cents
      diff.push({ lineKey: key, label: s.label, status: changed ? 'changed' : 'same', snap: s, current: c })
    }
  })
  return diff.sort((a, b) => a.label.localeCompare(b.label))
}

export function DevisVersionsTab({ devis, versions }: DevisVersionsTabProps) {
  const [diffVersionId, setDiffVersionId] = useState<number | null>(null)

  if (versions.length === 0) {
    return (
      <div className="card p-0 overflow-hidden">
        <div className="px-4 py-4 border-b border-dark-600">
          <h2 className="font-medium">Historique des versions</h2>
        </div>
        <p className="px-4 py-6 text-center text-dark-400 text-sm">
          Aucune version antérieure.
        </p>
      </div>
    )
  }

  return (
    <div className="card p-0 overflow-hidden">
      <div className="px-4 py-4 border-b border-dark-600">
        <h2 className="font-medium">Historique des versions</h2>
      </div>
      <div className="divide-y divide-dark-600">
        {versions.map((v) => {
          const snap = v.snapshot_json as Snap
          const snapLines = snap.lines ?? []
          const isOpen = diffVersionId === v.id
          const diffLines = buildDiff(snapLines, devis.lines ?? [])
          const changedCount = diffLines.filter((d) => d.status !== 'same').length

          return (
            <div key={v.id} className="divide-y divide-dark-900">
              <div className="px-4 py-4 flex items-start justify-between gap-4 text-sm">
                <div className="space-y-0.5 flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">Version {v.version_number}</p>
                    {changedCount > 0 && (
                      <span className="text-xs bg-dark-900 text-dark-300 rounded-full px-1.5 py-0.5">
                        {changedCount} modif.
                      </span>
                    )}
                  </div>
                  <p className="text-dark-400">{formatDate(v.created_at)} · par {v.created_by_name ?? `utilisateur #${v.created_by}`}</p>
                  {snap.notes && <p className="text-dark-300 italic truncate max-w-xs">{snap.notes}</p>}
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  {snap.total_cents !== undefined && (
                    <p className="text-gold-400 font-medium">{formatCents(snap.total_cents)}</p>
                  )}
                  <button
                    onClick={() => setDiffVersionId(isOpen ? null : v.id)}
                    className={`text-xs px-2 py-1 rounded-lg border transition-colors ${
                      isOpen
                        ? 'bg-gold-500/20 border-gold-500/40 text-gold-400'
                        : 'border-dark-600 text-dark-400 hover:text-dark-50 hover:border-dark-400'
                    }`}
                  >
                    {isOpen ? '▲ Fermer' : '▼ Diff'}
                  </button>
                </div>
              </div>

              {isOpen && (
                <div className="bg-dark-900 px-4 py-4 space-y-4 text-xs">
                  {snap.total_cents !== undefined && (
                    <div className="flex items-center gap-2">
                      <span className="text-dark-400">Montant :</span>
                      <span className={snap.total_cents !== devis.total_cents ? 'text-amber-400' : 'text-dark-300'}>
                        {formatCents(snap.total_cents)}
                      </span>
                      {snap.total_cents !== devis.total_cents && (
                        <>
                          <span className="text-dark-600">→</span>
                          <span className="font-medium">{formatCents(devis.total_cents)}</span>
                          <span className={devis.total_cents > snap.total_cents ? 'text-green-400' : 'text-red-400'}>
                            ({devis.total_cents > snap.total_cents ? '+' : ''}{formatCents(devis.total_cents - snap.total_cents)})
                          </span>
                        </>
                      )}
                    </div>
                  )}

                  {snap.notes !== devis.notes && (
                    <div>
                      <p className="text-dark-400 mb-1">Notes :</p>
                      {snap.notes && <p className="text-red-400 line-through opacity-70">{snap.notes}</p>}
                      {devis.notes && <p className="text-green-400">{devis.notes}</p>}
                      {!devis.notes && snap.notes && <p className="text-dark-500 italic">(supprimé)</p>}
                    </div>
                  )}

                  {snapLines.length > 0 && (
                    <div>
                      <p className="text-dark-400 mb-1.5">Articles :</p>
                      <div className="space-y-1">
                        {diffLines.map((d) => (
                          <div
                            key={d.lineKey}
                            className={`flex items-center gap-2 px-2 py-1.5 rounded-lg ${
                              d.status === 'added'   ? 'bg-green-900/30 text-green-400' :
                              d.status === 'removed' ? 'bg-red-900/30 text-red-400' :
                              d.status === 'changed' ? 'bg-amber-900/30 text-amber-400' :
                              'text-dark-400'
                            }`}
                          >
                            <span className="w-3 shrink-0">
                              {d.status === 'added' ? '+' : d.status === 'removed' ? '−' : d.status === 'changed' ? '~' : ' '}
                            </span>
                            <span className="flex-1 truncate">{d.label}</span>
                            {d.status === 'same' && d.current && (
                              <span>{d.current.quantity}× {formatCents(d.current.unit_price_cents)}</span>
                            )}
                            {d.status === 'added' && d.current && (
                              <span>{d.current.quantity}× {formatCents(d.current.unit_price_cents)}</span>
                            )}
                            {d.status === 'removed' && d.snap && (
                              <span>{d.snap.quantity}× {formatCents(d.snap.unit_price_cents)}</span>
                            )}
                            {d.status === 'changed' && d.snap && d.current && (
                              <span>
                                {d.snap.quantity !== d.current.quantity && (
                                  <>{d.snap.quantity}→{d.current.quantity}× </>
                                )}
                                {d.snap.unit_price_cents !== d.current.unit_price_cents && (
                                  <>{formatCents(d.snap.unit_price_cents)}→{formatCents(d.current.unit_price_cents)}</>
                                )}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {changedCount === 0 && snapLines.length === 0 && (
                    <p className="text-dark-500 italic">Snapshot partiel — pas de détail lignes disponible.</p>
                  )}
                  {changedCount === 0 && snapLines.length > 0 && (
                    <p className="text-dark-500 italic">Aucune modification des articles entre cette version et l'actuelle.</p>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
