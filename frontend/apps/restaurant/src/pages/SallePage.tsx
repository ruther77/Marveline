import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Plus, Settings, ShoppingBag, X } from 'lucide-react'
import { restaurantApi } from '@/api/restaurant'
import { normalizeError } from '@shared/errors/normalizer'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import { GrilleTables, PanelCommande } from '@/components'
import { useRestaurantScopes } from '@/hooks/useRestaurantScopes'
import type { TableRead } from '@/types/restaurant-v2'

// ─── ModalOuvertureCommande ──────────────────────────────────────────────────

function ModalOuvertureCommande({
  table,
  onClose,
  onSuccess,
}: {
  table: TableRead | null  // null = emporter
  onClose: () => void
  onSuccess: (commandeId: number, tableId: number | null) => void
}) {
  const trapRef = useFocusTrap<HTMLDivElement>(onClose)
  const [nbCouverts, setNbCouverts] = useState('2')
  const [nomClient, setNomClient] = useState('')
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: () => restaurantApi.ouvrirCommande({
      table_id: table?.id ?? null,
      nb_couverts: Math.max(1, Math.floor(Number(nbCouverts) || 1)),
      nom_client: nomClient.trim() || null,
    }),
    onSuccess: (data) => {
      onSuccess(data.id, table?.id ?? null)
      onClose()
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  const titre = table ? `Ouvrir — Table ${table.numero}` : 'Commande à emporter'

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 sm:p-4" onClick={onClose}>
      <div
        ref={trapRef}
        role="dialog"
        aria-modal="true"
        className="bg-white border border-stone-200 w-full sm:max-w-md shadow-xl rounded-t-2xl sm:rounded-2xl pb-[env(safe-area-inset-bottom)] sm:pb-0"
        onClick={e => e.stopPropagation()}
        onKeyDown={e => { if (e.key === 'Enter' && !mutation.isPending && nbCouverts) mutation.mutate() }}
      >
        {/* Drag handle mobile */}
        <div className="sm:hidden flex justify-center pt-2 pb-1">
          <div className="w-10 h-1 rounded-full bg-stone-300" />
        </div>
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-100">
          <h2 className="text-[16px] font-bold text-stone-900">{titre}</h2>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-900 min-w-[44px] min-h-[44px] flex items-center justify-center -mr-2" aria-label="Fermer">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="px-5 py-4 flex flex-col gap-4">
          {error && <p className="text-[13px] text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
          <div>
            <label className="text-[12px] font-semibold text-stone-600 mb-2 block">Nombre de couverts</label>
            <div className="flex items-center gap-3 flex-wrap">
              {[1, 2, 3, 4, 5, 6].map(n => (
                <button key={n} onClick={() => setNbCouverts(String(n))}
                  className={`w-12 h-12 rounded-xl text-[15px] font-semibold transition-colors ${
                    nbCouverts === String(n) ? 'bg-stone-900 text-white' : 'bg-stone-100 text-stone-700 hover:bg-stone-200'
                  }`}>
                  {n}
                </button>
              ))}
              <input
                type="number"
                min={1}
                max={50}
                value={nbCouverts}
                onChange={e => setNbCouverts(e.target.value)}
                className="w-16 h-12 border border-stone-200 rounded-xl px-2 text-[15px] text-center focus:outline-none focus:border-amber-400"
                aria-label="Nombre de couverts personnalisé"
              />
            </div>
          </div>
          <div>
            <label className="text-[12px] font-semibold text-stone-600 mb-1 block">Nom du client (optionnel)</label>
            <input type="text" value={nomClient} onChange={e => setNomClient(e.target.value)}
              placeholder="Ex: M. Dupont, Anniversaire Julie..."
              className="w-full border border-stone-200 rounded-xl px-3 h-12 text-[14px] focus:outline-none focus:border-amber-400" />
          </div>
        </div>
        <div className="flex gap-3 px-5 py-4 border-t border-stone-100">
          <button onClick={onClose} className="flex-1 h-12 text-[14px] text-stone-700 font-medium bg-stone-100 rounded-xl hover:bg-stone-200">
            Annuler
          </button>
          <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !nbCouverts}
            className="flex-1 h-12 text-[14px] font-semibold text-white bg-amber-600 rounded-xl hover:bg-amber-700 disabled:opacity-50">
            {mutation.isPending ? 'Ouverture…' : 'Ouvrir la commande'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── ModalGestionTables ──────────────────────────────────────────────────────

function ModalGestionTables({ tables, onClose }: { tables: TableRead[]; onClose: () => void }) {
  const qc = useQueryClient()
  const trapRef = useFocusTrap<HTMLDivElement>(onClose)
  const [newNumero, setNewNumero] = useState('')
  const [newCapacite, setNewCapacite] = useState('4')
  const [error, setError] = useState('')

  const createMut = useMutation({
    mutationFn: () => restaurantApi.createTable({ numero: newNumero, capacite: Number(newCapacite) || 4 }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-tables'] })
      setNewNumero('')
      setNewCapacite('4')
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  const deleteMut = useMutation({
    mutationFn: (id: number) => restaurantApi.deleteTable(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-tables'] })
      qc.invalidateQueries({ queryKey: ['restaurant-tickets-cuisine'] })
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur suppression'),
  })

  const occupees = tables.filter(t => t.statut !== 'LIBRE')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div ref={trapRef} role="dialog" aria-modal="true" className="bg-white rounded-2xl border border-stone-200 w-full max-w-md max-h-[80vh] flex flex-col shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-100">
          <h2 className="text-[15px] font-bold text-stone-900">Gérer les tables</h2>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-900" aria-label="Fermer"><X className="h-4 w-4" /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4">
          {error && <p className="text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}

          {/* Ajouter */}
          <div>
            <label className="text-[11px] font-semibold text-stone-600 mb-2 block">Ajouter une table</label>
            <div className="flex gap-2">
              <input type="text" value={newNumero} onChange={e => setNewNumero(e.target.value)}
                placeholder="Numéro / nom" className="flex-1 border border-stone-200 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-amber-400" />
              <input type="number" min={1} value={newCapacite} onChange={e => setNewCapacite(e.target.value)}
                className="w-16 border border-stone-200 rounded-lg px-2 py-2 text-[13px] text-center focus:outline-none focus:border-amber-400" />
              <button onClick={() => createMut.mutate()} disabled={!newNumero.trim() || createMut.isPending}
                className="px-3 py-2 bg-amber-600 text-white text-[12px] font-semibold rounded-lg hover:bg-amber-700 disabled:opacity-50"
                aria-label="Ajouter une table">
                <Plus className="h-4 w-4" />
              </button>
            </div>
            <p className="text-[10px] text-stone-400 mt-1">Nom + places (ex: "Terrasse 1", 6 places)</p>
          </div>

          {/* Tables existantes */}
          <div>
            <label className="text-[11px] font-semibold text-stone-600 mb-2 block">Tables existantes ({tables.length})</label>
            <div className="flex flex-col gap-1.5">
              {tables.map(t => (
                <div key={t.id} className="flex items-center gap-2 px-3 py-2 bg-stone-50 rounded-lg">
                  <span className="text-[13px] font-medium text-stone-900 flex-1">{t.numero}</span>
                  <span className="text-[11px] text-stone-500">{t.capacite} pl.</span>
                  <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
                    t.statut === 'LIBRE' ? 'bg-stone-100 text-stone-500' : 'bg-amber-50 text-amber-600'
                  }`}>
                    {t.statut === 'LIBRE' ? 'Libre' : 'Occupée'}
                  </span>
                  {t.statut === 'LIBRE' && (
                    <button onClick={() => deleteMut.mutate(t.id)} disabled={deleteMut.isPending}
                      className="text-stone-400 hover:text-red-600 p-1"
                      aria-label="Supprimer la table">
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
            {occupees.length > 0 && (
              <p className="text-[10px] text-stone-400 mt-2">{occupees.length} table{occupees.length > 1 ? 's' : ''} occupée{occupees.length > 1 ? 's' : ''} — suppression impossible</p>
            )}
          </div>
        </div>

        <div className="px-5 py-4 border-t border-stone-100">
          <button onClick={onClose} className="w-full py-2.5 text-[13px] font-medium text-stone-500 bg-stone-100 rounded-xl hover:bg-stone-200 min-h-[44px]">
            Fermer
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── SallePage ───────────────────────────────────────────────────────────────

export default function SallePage() {
  const qc = useQueryClient()
  const { canEdit } = useRestaurantScopes()
  const [selectedTableId, setSelectedTableId] = useState<number | null>(null)
  const [selectedCommandeId, setSelectedCommandeId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [showOuverture, setShowOuverture] = useState<TableRead | null | 'emporter'>(null)
  const [showGestion, setShowGestion] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['restaurant-tables'],
    queryFn: restaurantApi.listTables,
    staleTime: 10_000,
    refetchInterval: 15_000,
  })

  const tables = data?.items ?? []

  function handleSelectTable(t: TableRead) {
    setError('')
    if (t.statut === 'LIBRE') {
      setShowOuverture(t)
    } else if (t.commande_active) {
      setSelectedTableId(t.id)
      setSelectedCommandeId(t.commande_active.commande_id)
    }
  }

  function handleCommandeOuverte(commandeId: number, tableId: number | null) {
    qc.invalidateQueries({ queryKey: ['restaurant-tables'] })
    if (tableId) {
      setSelectedTableId(tableId)
    }
    setSelectedCommandeId(commandeId)
  }

  function handleClosePanel() {
    setSelectedTableId(null)
    setSelectedCommandeId(null)
    qc.invalidateQueries({ queryKey: ['restaurant-tables'] })
  }

  const nbActives = tables.filter(t => t.statut === 'OUVERTE' || t.statut === 'SERVIE').length
  const nbLibres = tables.filter(t => t.statut === 'LIBRE').length

  return (
    <div className="flex flex-col min-h-0 h-full bg-stone-50">
      {/* Modal ouverture commande */}
      {showOuverture !== null && (
        <ModalOuvertureCommande
          table={showOuverture === 'emporter' ? null : showOuverture}
          onClose={() => setShowOuverture(null)}
          onSuccess={handleCommandeOuverte}
        />
      )}

      {/* Modal gestion tables */}
      {showGestion && (
        <ModalGestionTables tables={tables} onClose={() => setShowGestion(false)} />
      )}

      {/* Header */}
      <div className="px-4 sm:px-6 py-3 border-b border-stone-200 bg-white flex items-center gap-3 flex-wrap">
        <h1 className="text-[16px] font-semibold text-stone-900 shrink-0">Plan de salle</h1>

        <div className="flex items-center gap-1.5">
          {nbLibres > 0 && (
            <div className="text-[12px] font-semibold px-2.5 py-1 rounded-lg bg-stone-100 text-stone-600">
              {nbLibres} libre{nbLibres > 1 ? 's' : ''}
            </div>
          )}
          {nbActives > 0 && (
            <div className="flex items-center gap-1.5 text-[12px] font-semibold px-2.5 py-1 rounded-lg bg-amber-50 text-amber-700">
              <div className="h-1.5 w-1.5 rounded-full bg-amber-500" />
              {nbActives} active{nbActives > 1 ? 's' : ''}
            </div>
          )}
        </div>

        <div className="flex-1" />

        <button onClick={() => setShowOuverture('emporter')}
          className="flex items-center gap-1.5 px-4 h-11 bg-stone-900 text-white text-[13px] font-semibold rounded-xl hover:opacity-90">
          <ShoppingBag className="h-4 w-4" /> Emporter
        </button>

        {canEdit && (
          <button onClick={() => setShowGestion(true)}
            className="flex items-center gap-1.5 px-4 h-11 border border-stone-200 text-stone-700 text-[13px] font-medium rounded-xl hover:bg-stone-50">
            <Settings className="h-4 w-4" /> Tables
          </button>
        )}

        {error && (
          <div className="flex items-center gap-2 text-[13px] text-red-600 bg-red-50 rounded-lg px-3 py-2 border border-red-200 w-full sm:w-auto">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}
      </div>

      {/* Layout — mobile : grille pleine largeur, panel en overlay. Tablette+ : 2 colonnes. */}
      <div className="flex-1 overflow-hidden flex">
        <div className="w-full md:w-[55%] min-w-0 md:border-r border-stone-200 px-4 sm:px-6 py-5 overflow-y-auto">
          <GrilleTables
            tables={tables}
            selectedTableId={selectedTableId}
            onSelect={handleSelectTable}
            loading={isLoading}
          />
        </div>

        {/* Panneau commande */}
        <div
          className={
            selectedCommandeId !== null
              ? 'fixed inset-0 z-50 bg-white md:static md:flex-1 md:min-w-0 md:relative md:z-auto'
              : 'hidden md:flex md:flex-1 md:min-w-0 md:relative'
          }
        >
          {selectedCommandeId !== null ? (
            <PanelCommande
              commandeId={selectedCommandeId}
              onClose={handleClosePanel}
            />
          ) : (
            <div className="h-full w-full flex flex-col items-center justify-center gap-3 px-8 text-center">
              {tables.length === 0 ? (
                <>
                  <div className="w-12 h-12 rounded-2xl bg-stone-100 flex items-center justify-center mb-1">
                    <Settings className="h-5 w-5 text-stone-400" />
                  </div>
                  <p className="text-[14px] font-semibold text-stone-700">Aucune table configurée</p>
                  <p className="text-[12px] text-stone-400 leading-relaxed">Ajoutez des tables pour commencer à gérer la salle.</p>
                  {canEdit && (
                    <button onClick={() => setShowGestion(true)}
                      className="mt-1 px-4 py-2 text-[12px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-lg hover:bg-amber-100 transition-colors">
                      Gérer les tables
                    </button>
                  )}
                </>
              ) : (
                <>
                  <div className="w-14 h-14 rounded-2xl bg-stone-100 flex items-center justify-center mb-1">
                    <div className="grid grid-cols-2 gap-1">
                      {[0,1,2,3].map(i => (
                        <div key={i} className="w-4 h-3 rounded-sm bg-stone-300" />
                      ))}
                    </div>
                  </div>
                  <p className="text-[14px] font-semibold text-stone-700">Sélectionnez une table</p>
                  <p className="text-[12px] text-stone-400 leading-relaxed max-w-[220px]">
                    Cliquez sur une table occupée pour gérer la commande, ou ouvrez-en une nouvelle sur une table libre.
                  </p>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
