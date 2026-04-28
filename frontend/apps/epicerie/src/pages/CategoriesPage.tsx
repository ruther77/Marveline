// Route : /_app/categories
// Gestion CRUD des catégories de marges épicerie

import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Plus, Trash2, X, AlertTriangle, Loader2, Search } from 'lucide-react'
import { margeCategoriesApi } from '@/api/categories'
import type { MargeCategorie, MargeCategorieCreate } from '@/api/categories'
import { normalizeError } from '@shared/errors/normalizer'

// ── Dialog générique ──────────────────────────────────────────────────────────

function Dialog({ isOpen, onClose, title, children, footer }: {
  isOpen: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  footer?: React.ReactNode
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return
    const prev = document.activeElement as HTMLElement | null
    ref.current?.focus()
    return () => prev?.focus()
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-50" aria-hidden="true" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          ref={ref}
          tabIndex={-1}
          role="dialog"
          aria-modal="true"
          className="pointer-events-auto w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-200 outline-none"
          onClick={e => e.stopPropagation()}
        >
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
            <h2 className="text-base font-semibold text-slate-900">{title}</h2>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              aria-label="Fermer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="px-5 py-4">{children}</div>
          {footer && (
            <div className="px-5 py-4 border-t border-slate-100 flex items-center justify-end gap-2">
              {footer}
            </div>
          )}
        </div>
      </div>
    </>
  )
}

// ── CreateModal ───────────────────────────────────────────────────────────────

function CreateModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const [code, setCode] = useState('')
  const [taux, setTaux] = useState(3000)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setCode('')
    setTaux(3000)
    setError(null)
  }, [isOpen])

  const createMut = useMutation({
    mutationFn: (payload: MargeCategorieCreate) => margeCategoriesApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['epicerie-marge-categories'] })
      qc.invalidateQueries({ queryKey: ['epicerie-marges'] })
      onClose()
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur lors de la création'),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = code.trim().toUpperCase()
    if (!trimmed) { setError('Le code est requis'); return }
    if (!/^[A-Z0-9_]+$/.test(trimmed)) { setError('Code invalide — lettres majuscules, chiffres et _ uniquement'); return }
    createMut.mutate({ categorie: trimmed, taux_marge_centieme: taux })
  }

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Nouvelle catégorie de marge"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors"
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={createMut.isPending}
            className="flex items-center gap-2 px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-xl transition-colors disabled:opacity-50"
          >
            {createMut.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Créer
          </button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-red-600 text-sm">
            {error}
          </div>
        )}
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1.5">
            Code catégorie *
          </label>
          <input
            type="text"
            value={code}
            onChange={e => setCode(e.target.value.toUpperCase())}
            className="w-full px-3 py-2 text-sm font-mono border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
            placeholder="Ex : ALC_CIDRE"
            autoFocus
          />
          <p className="text-[11px] text-slate-400 mt-1">
            Majuscules, chiffres et underscore. Format recommandé : GROUPE_SOUS
          </p>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1.5">
            Taux de marge initial — <span className="font-semibold text-slate-700">{(taux / 100).toFixed(0)} %</span>
          </label>
          <input
            type="range"
            min={0}
            max={10000}
            step={100}
            value={taux}
            onChange={e => setTaux(Number(e.target.value))}
            className="w-full h-2 bg-slate-100 rounded-lg appearance-none cursor-pointer accent-emerald-500"
          />
          <div className="flex justify-between text-[10px] text-slate-300 mt-0.5">
            <span>0 %</span><span>50 %</span><span>100 %</span>
          </div>
        </div>
      </form>
    </Dialog>
  )
}

// ── DeleteDialog ──────────────────────────────────────────────────────────────

function DeleteDialog({ isOpen, onClose, categorie }: {
  isOpen: boolean
  onClose: () => void
  categorie: string | null
}) {
  const qc = useQueryClient()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { if (!isOpen) setError(null) }, [isOpen])

  const deleteMut = useMutation({
    mutationFn: (code: string) => margeCategoriesApi.delete(code),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['epicerie-marge-categories'] })
      qc.invalidateQueries({ queryKey: ['epicerie-marges'] })
      onClose()
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur lors de la suppression'),
  })

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Supprimer la catégorie"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors"
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={() => categorie && deleteMut.mutate(categorie)}
            disabled={deleteMut.isPending}
            className="flex items-center gap-2 px-5 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-xl transition-colors disabled:opacity-50"
          >
            {deleteMut.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Supprimer
          </button>
        </>
      }
    >
      <div className="space-y-3">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-red-600 text-sm">
            {error}
          </div>
        )}
        <div className="flex items-start gap-3">
          <div className="p-2 bg-red-50 rounded-xl shrink-0">
            <AlertTriangle className="w-5 h-5 text-red-500" />
          </div>
          <div>
            <p className="text-sm text-slate-700">
              Supprimer la catégorie <span className="font-mono font-semibold">{categorie}</span> ?
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Les produits associés conserveront ce code mais la marge ne sera plus définie.
            </p>
          </div>
        </div>
      </div>
    </Dialog>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CategoriesPage() {
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  const { data: marges = [], isLoading, isError, refetch } = useQuery<MargeCategorie[]>({
    queryKey: ['epicerie-marge-categories'],
    queryFn: () => margeCategoriesApi.getAll(),
  })

  const handleDelete = (code: string) => { setSelected(code); setDeleteOpen(true) }

  const filtered = search.trim()
    ? marges.filter(m => m.categorie.toLowerCase().includes(search.toLowerCase()))
    : marges

  return (
    <div className="w-full px-6 py-6 space-y-5">
      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900">Catégories de marges</h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Codes utilisés pour calculer les prix de vente
          </p>
        </div>
        <Link
          to="/marges"
          className="text-xs text-slate-400 hover:text-emerald-600 transition-colors"
        >
          ← Gérer les taux
        </Link>
        <button
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-xl transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4" />
          Nouvelle catégorie
        </button>
      </div>

      {/* Search */}
      <div className="relative max-w-xs">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-300" />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Filtrer…"
          className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
        />
      </div>

      {/* Table */}
      <div className="rounded-2xl border border-slate-200 overflow-hidden bg-white">
        {isLoading ? (
          <div className="p-6 space-y-2 animate-pulse">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-10 bg-slate-100 rounded-xl" />
            ))}
          </div>
        ) : isError ? (
          <div className="p-6 text-center">
            <p className="text-sm text-slate-400">Erreur de chargement</p>
            <button onClick={() => refetch()} className="text-emerald-600 text-sm mt-2 hover:underline">
              Réessayer
            </button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-sm text-slate-400 mb-4">
              {search ? 'Aucun résultat pour ce filtre' : 'Aucune catégorie définie'}
            </p>
            {!search && (
              <button
                onClick={() => setCreateOpen(true)}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-xl transition-colors"
              >
                Créer la première
              </button>
            )}
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/80">
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                  Code
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide hidden sm:table-cell">
                  Groupe
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wide">
                  Marge
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {filtered.map(m => {
                const group = m.categorie.split('_')[0]
                return (
                  <tr key={m.categorie} className="border-b border-slate-100 hover:bg-slate-50/50 group">
                    <td className="px-4 py-3">
                      <span className="font-mono text-sm font-medium text-slate-800">{m.categorie}</span>
                    </td>
                    <td className="px-4 py-3 hidden sm:table-cell">
                      <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-500 rounded-md font-medium">
                        {group}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-sm font-semibold text-emerald-700">
                        {m.taux_pct.toFixed(0)} %
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-0.5 justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => handleDelete(m.categorie)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                          aria-label="Supprimer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Count */}
      {!isLoading && !isError && marges.length > 0 && (
        <p className="text-xs text-slate-400">
          {filtered.length} catégorie{filtered.length > 1 ? 's' : ''}
          {search && ` sur ${marges.length}`}
        </p>
      )}

      <CreateModal isOpen={createOpen} onClose={() => setCreateOpen(false)} />
      <DeleteDialog isOpen={deleteOpen} onClose={() => setDeleteOpen(false)} categorie={selected} />
    </div>
  )
}
