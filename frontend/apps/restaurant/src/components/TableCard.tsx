import { Check, Users, Clock } from 'lucide-react'
import type { TableRead, TableStatut, StatutPlat } from '../types/restaurant-v2'

function fmtEur(cts: number): string {
  return (cts / 100).toFixed(2) + ' €'
}

function fmtDuree(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime()
  const min = Math.floor(diff / 60_000)
  if (min < 60) return `${min}min`
  return `${Math.floor(min / 60)}h${String(min % 60).padStart(2, '0')}`
}

export function statutPlatBadge(s: StatutPlat): { label: string; cls: string; dot: string } {
  const map: Record<StatutPlat, { label: string; cls: string; dot: string }> = {
    ENVOYEE: { label: 'Envoyé',   cls: 'bg-blue-50 text-blue-600',    dot: 'bg-blue-500' },
    LANCEE:  { label: 'En cours', cls: 'bg-amber-50 text-amber-700',   dot: 'bg-amber-500' },
    PRETE:   { label: 'Prêt',     cls: 'bg-green-50 text-green-700',   dot: 'bg-green-600' },
    SERVIE:  { label: 'Servi',    cls: 'bg-stone-100 text-stone-400',  dot: 'bg-stone-400' },
  }
  return map[s] ?? { label: s, cls: 'bg-stone-100 text-stone-500', dot: 'bg-stone-400' }
}

interface TableCardProps {
  table: TableRead
  selected: boolean
  onSelect: () => void
}

export default function TableCard({ table, selected, onSelect }: TableCardProps) {
  const cmd = table.commande_active
  const preview3 = (cmd?.lignes_preview ?? []).slice(0, 3)
  const reste = (cmd?.lignes_preview?.length ?? 0) - 3

  const cardCls = {
    LIBRE:   `bg-white border-stone-200 ${selected ? 'ring-2 ring-stone-400 ring-offset-1' : 'hover:border-stone-400'}`,
    OUVERTE: `bg-white border-amber-300 shadow-sm ${selected ? 'ring-2 ring-amber-500 ring-offset-1' : 'hover:border-amber-500'}`,
    SERVIE:  `bg-green-50 border-green-200 ${selected ? 'ring-2 ring-green-500 ring-offset-1' : 'hover:border-green-400'}`,
  }[table.statut as TableStatut]

  const nameCls = {
    LIBRE:   'text-stone-500',
    OUVERTE: 'text-amber-700',
    SERVIE:  'text-green-700',
  }[table.statut as TableStatut]

  const statutLabel: Record<TableStatut, string> = {
    LIBRE: 'Libre',
    OUVERTE: 'Occupée',
    SERVIE: 'À débarrasser',
  }

  return (
    <button
      onClick={onSelect}
      aria-label={`Table ${table.numero} — ${statutLabel[table.statut as TableStatut]}`}
      className={`w-full text-left p-3 sm:p-4 rounded-xl border transition-all min-h-[120px] ${cardCls}`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className={`text-[16px] sm:text-[18px] font-bold ${nameCls}`}>
          {table.numero}
        </span>
        <div className="flex items-center gap-1.5">
          {/* Dot + label texte (jamais couleur seule) */}
          {table.statut === 'LIBRE' && (
            <>
              <div className="h-2.5 w-2.5 rounded-full border-2 border-stone-400" />
              <span className="text-[10px] font-semibold uppercase tracking-wide text-stone-500">Libre</span>
            </>
          )}
          {table.statut === 'OUVERTE' && (
            <>
              <div className="h-2.5 w-2.5 rounded-full bg-amber-500" />
              <span className="text-[10px] font-semibold uppercase tracking-wide text-amber-700">Occupée</span>
            </>
          )}
          {table.statut === 'SERVIE' && (
            <>
              <Check className="h-3.5 w-3.5 text-green-600" />
              <span className="text-[10px] font-semibold uppercase tracking-wide text-green-700">À débarrasser</span>
            </>
          )}
        </div>
      </div>

      {table.statut === 'LIBRE' && (
        <div className="flex items-center justify-center min-h-[60px]">
          <span className="text-[13px] text-stone-500">{table.capacite} pers. · disponible</span>
        </div>
      )}

      {table.statut === 'OUVERTE' && cmd && (
        <>
          {cmd.nom_client && (
            <div className="text-[12px] font-medium text-stone-700 truncate mb-1">{cmd.nom_client}</div>
          )}
          <div className="flex items-center gap-3 text-[12px] text-stone-600 mb-2">
            <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" />{cmd.nb_couverts} couv.</span>
            <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{fmtDuree(cmd.date_ouverture)}</span>
          </div>
          {preview3.length > 0 && (
            <div className="border-t border-stone-200/60 pt-2 flex flex-col gap-0.5">
              {preview3.map(l => {
                const b = statutPlatBadge(l.statut_plat)
                return (
                  <div key={l.ligne_id} className="flex items-center gap-1.5 text-[11px]">
                    <div className={`h-1.5 w-1.5 rounded-full shrink-0 ${b.dot}`} />
                    <span className="truncate flex-1 text-stone-600">{l.variante_nom}</span>
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${b.cls}`}>{b.label}</span>
                  </div>
                )
              })}
              {reste > 0 && <div className="text-[10px] text-stone-400 pl-3">+{reste} autre{reste > 1 ? 's' : ''}…</div>}
            </div>
          )}
          <div className="text-right text-[12px] font-semibold text-stone-900 mt-1.5">
            Total : {fmtEur(cmd.total_provisoire_cts)}
          </div>
        </>
      )}

      {table.statut === 'SERVIE' && (
        <div className="flex items-center gap-1.5 text-[12px] text-green-700 mt-1">
          <Check className="h-3.5 w-3.5 shrink-0" />
          <span>Payée · En attente débarrassage</span>
        </div>
      )}
    </button>
  )
}
