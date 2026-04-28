import { useState } from 'react'
import TableCard from './TableCard'
import type { TableRead, TableStatut } from '../types/restaurant-v2'

type FiltreTables = 'TOUTES' | 'LIBRES' | 'ACTIVES'

const FILTRES: { key: FiltreTables; label: string }[] = [
  { key: 'TOUTES',  label: 'Toutes' },
  { key: 'LIBRES',  label: 'Libres' },
  { key: 'ACTIVES', label: 'Actives' },
]

function SkeletonGrille() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="animate-pulse bg-stone-100 border border-stone-200 rounded-xl p-3 h-[120px]" />
      ))}
    </div>
  )
}

interface GrilleTablesProps {
  tables: TableRead[]
  selectedTableId: number | null
  onSelect: (t: TableRead) => void
  loading: boolean
}

export default function GrilleTables({ tables, selectedTableId, onSelect, loading }: GrilleTablesProps) {
  const [filtre, setFiltre] = useState<FiltreTables>('TOUTES')

  const filtered = tables.filter(t => {
    if (filtre === 'LIBRES') return t.statut === 'LIBRE'
    if (filtre === 'ACTIVES') return t.statut === 'OUVERTE' || t.statut === 'SERVIE'
    return true
  })

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <p className="text-[12px] font-medium text-stone-500">
          {tables.length} table{tables.length > 1 ? 's' : ''}
        </p>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-[11px] text-stone-500">
            <div className="h-2 w-2 rounded-full border border-stone-400" /> Libre
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-stone-500">
            <div className="h-2 w-2 rounded-full bg-amber-500" /> Occupée
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-stone-500">
            <div className="h-2 w-2 rounded-full bg-green-500" /> À débarrasser
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 mb-3">
        {FILTRES.map(f => (
          <button key={f.key} onClick={() => setFiltre(f.key)}
            className={`text-[13px] font-medium px-4 h-10 rounded-full transition-colors min-w-[44px] ${
              filtre === f.key
                ? 'bg-stone-900 text-white'
                : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
            }`}>
            {f.label}
          </button>
        ))}
      </div>

      {loading ? <SkeletonGrille /> : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 overflow-y-auto">
          {filtered.map(t => (
            <TableCard key={t.id} table={t} selected={selectedTableId === t.id} onSelect={() => onSelect(t)} />
          ))}
          {filtered.length === 0 && (
            <div className="col-span-full text-center py-8 text-stone-500 text-[13px]">Aucune table</div>
          )}
        </div>
      )}
    </div>
  )
}
