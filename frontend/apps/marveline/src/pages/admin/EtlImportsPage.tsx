// Route : /_massacorp/etl-imports (ou /_app/admin/etl-imports)
// Queue factures fournisseur — Upload, Preview, Validation (ADR-25)

import { PageHeader } from '@/components/PageHeader'
import { formatCents } from '@/lib/utils'
import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  uploadFacture,
  listImports,
  validateImport,
  rejectImport,
  updateImportPreview,
} from '@/api/etl_imports'
import type { EtlImportRead, EtlImportUpdateRequest } from '@/types/etl_import'
import { normalizeError } from '@shared/errors/normalizer'

// ─── Constantes ──────────────────────────────────────────────────────────────

const STATUT_LABELS: Record<string, string> = {
  PENDING: 'En attente',
  RUNNING: 'Traitement…',
  PREVIEW: 'À valider',
  VALIDATED: 'Validée',
  REJECTED: 'Rejetée',
  SUCCES: 'Succès',
  PARTIEL: 'Partiel',
  ECHEC: 'Échec',
}

const STATUT_COLORS: Record<string, string> = {
  PENDING: 'bg-dark-600 text-dark-300',
  RUNNING: 'bg-primary-500/20 text-primary-400',
  PREVIEW: 'bg-gold-400/20 text-gold-400',
  VALIDATED: 'bg-green-500/20 text-green-400',
  REJECTED: 'bg-red-500/20 text-red-400',
  SUCCES: 'bg-green-500/20 text-green-400',
  PARTIEL: 'bg-gold-400/20 text-gold-400',
  ECHEC: 'bg-red-500/20 text-red-400',
}

const TABS = [
  { key: 'preview', label: 'À valider' },
  { key: 'all', label: 'Tout' },
  { key: 'validated', label: 'Validées' },
  { key: 'rejected', label: 'Rejetées' },
] as const

type TabKey = typeof TABS[number]['key']

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('fr-FR')
}

// ─── Drop Zone ───────────────────────────────────────────────────────────────

function DropZone({ onUpload, isUploading }: {
  onUpload: (file: File, fournisseur: string) => void
  isUploading: boolean
}) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [fournisseur, setFournisseur] = useState('metro')

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file && file.name.toLowerCase().endsWith('.pdf')) {
      onUpload(file, fournisseur)
    }
  }, [onUpload, fournisseur])

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) onUpload(file, fournisseur)
    e.target.value = ''
  }, [onUpload, fournisseur])

  return (
    <div className="card p-6">
      <div className="flex items-center gap-4 mb-4">
        <h2 className="text-lg font-semibold text-dark-50">Importer une facture</h2>
        <select
          value={fournisseur}
          onChange={e => setFournisseur(e.target.value)}
          className="bg-dark-900 text-dark-200 border border-dark-600 rounded px-3 py-1.5 text-sm"
        >
          <option value="metro">METRO</option>
          <option value="taiyat">TAIYAT</option>
        </select>
      </div>

      <div
        onDragOver={e => { e.preventDefault(); setIsDragOver(true) }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
          ${isDragOver
            ? 'border-primary-400 bg-primary-500/10'
            : 'border-dark-600 hover:border-dark-500 bg-dark-900/50'
          }
          ${isUploading ? 'opacity-50 pointer-events-none' : ''}
        `}
        onClick={() => document.getElementById('etl-file-input')?.click()}
      >
        <input
          id="etl-file-input"
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={handleFileInput}
          disabled={isUploading}
        />
        {isUploading ? (
          <div className="flex items-center justify-center gap-3">
            <div className="w-5 h-5 border-2 border-primary-400 border-t-transparent rounded-full animate-spin" />
            <span className="text-dark-300">Parsing en cours…</span>
          </div>
        ) : (
          <>
            <div className="text-4xl mb-2 text-dark-500">+</div>
            <p className="text-dark-300">
              Glissez un PDF ici ou <span className="text-primary-400 underline">parcourir</span>
            </p>
            <p className="text-dark-500 text-sm mt-1">
              Formats : factures METRO, TAIYAT (PDF)
            </p>
          </>
        )}
      </div>
    </div>
  )
}

// ─── Preview Card ────────────────────────────────────────────────────────────

function PreviewCard({ item, onValidate, onReject, onUpdate, isActing }: {
  item: EtlImportRead
  onValidate: (id: number) => void
  onReject: (id: number) => void
  onUpdate: (id: number, data: EtlImportUpdateRequest) => void
  isActing: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [editData, setEditData] = useState<EtlImportUpdateRequest>({
    numero_facture: item.numero_facture || undefined,
    date_facture: item.date_facture || undefined,
    montant_ht_total: item.montant_ht_total || undefined,
    montant_tva_total: item.montant_tva_total || undefined,
    montant_ttc_total: item.montant_ttc_total || undefined,
  })

  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-3 mb-3">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUT_COLORS[item.statut] || 'bg-dark-600 text-dark-300'}`}>
              {STATUT_LABELS[item.statut] || item.statut}
            </span>
            <span className="text-dark-400 text-sm font-mono">
              {item.vendor_code || '—'}
            </span>
            {item.quality_score !== null && (
              <span className={`text-xs ${item.quality_score >= 70 ? 'text-green-400' : item.quality_score >= 40 ? 'text-gold-400' : 'text-red-400'}`}>
                Q: {item.quality_score}/100
              </span>
            )}
          </div>

          {/* Infos facture */}
          {!editing ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <div>
                <span className="text-dark-500 text-xs block">N° Facture</span>
                <span className="text-dark-200">{item.numero_facture || '—'}</span>
              </div>
              <div>
                <span className="text-dark-500 text-xs block">Date</span>
                <span className="text-dark-200">{formatDate(item.date_facture)}</span>
              </div>
              <div>
                <span className="text-dark-500 text-xs block">HT</span>
                <span className="text-dark-200">{formatCents(item.montant_ht_total)}</span>
              </div>
              <div>
                <span className="text-dark-500 text-xs block">TTC</span>
                <span className="text-dark-100 font-medium">{formatCents(item.montant_ttc_total)}</span>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
              <div>
                <label className="text-dark-500 text-xs block mb-1">N° Facture</label>
                <input
                  type="text"
                  value={editData.numero_facture || ''}
                  onChange={e => setEditData({ ...editData, numero_facture: e.target.value })}
                  className="w-full bg-dark-900 border border-dark-600 rounded px-2 py-1 text-dark-200 text-sm"
                />
              </div>
              <div>
                <label className="text-dark-500 text-xs block mb-1">Date</label>
                <input
                  type="date"
                  value={editData.date_facture || ''}
                  onChange={e => setEditData({ ...editData, date_facture: e.target.value })}
                  className="w-full bg-dark-900 border border-dark-600 rounded px-2 py-1 text-dark-200 text-sm"
                />
              </div>
              <div>
                <label className="text-dark-500 text-xs block mb-1">HT (centimes)</label>
                <input
                  type="number"
                  value={editData.montant_ht_total ?? ''}
                  onChange={e => setEditData({ ...editData, montant_ht_total: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full bg-dark-900 border border-dark-600 rounded px-2 py-1 text-dark-200 text-sm"
                />
              </div>
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center gap-2 mt-3 text-xs text-dark-500">
            <span>{item.nb_lignes_total ?? 0} lignes</span>
            {item.nb_lignes_conflit > 0 && (
              <span className="text-gold-400">{item.nb_lignes_conflit} conflits</span>
            )}
            {item.ecart_reconciliation !== null && Number(item.ecart_reconciliation) !== 0 && (
              <span className="text-gold-400">ecart: {Number(item.ecart_reconciliation).toFixed(2)}</span>
            )}
            <span className="ml-auto">{item.fichier_source}</span>
          </div>
        </div>

        {/* Actions */}
        {item.statut === 'PREVIEW' && (
          <div className="flex flex-col gap-2 shrink-0">
            {!editing ? (
              <>
                <button
                  onClick={() => onValidate(item.id)}
                  disabled={isActing}
                  className="px-3 py-1.5 bg-green-600 hover:bg-green-500 text-white text-sm rounded transition-colors disabled:opacity-50"
                >
                  Valider
                </button>
                <button
                  onClick={() => setEditing(true)}
                  className="px-3 py-1.5 bg-dark-600 hover:bg-dark-500 text-dark-200 text-sm rounded transition-colors"
                >
                  Modifier
                </button>
                <button
                  onClick={() => onReject(item.id)}
                  disabled={isActing}
                  className="px-3 py-1.5 bg-red-600/20 hover:bg-red-600/40 text-red-400 text-sm rounded transition-colors disabled:opacity-50"
                >
                  Rejeter
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => {
                    onUpdate(item.id, editData)
                    setEditing(false)
                  }}
                  className="px-3 py-1.5 bg-primary-500 hover:bg-primary-400 text-white text-sm rounded transition-colors"
                >
                  Sauver
                </button>
                <button
                  onClick={() => setEditing(false)}
                  className="px-3 py-1.5 bg-dark-600 hover:bg-dark-500 text-dark-200 text-sm rounded transition-colors"
                >
                  Annuler
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── History Row ─────────────────────────────────────────────────────────────

function HistoryRow({ item }: { item: EtlImportRead }) {
  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b border-dark-600/50 text-sm">
      <span className={`px-2 py-0.5 rounded text-xs font-medium shrink-0 ${STATUT_COLORS[item.statut] || ''}`}>
        {STATUT_LABELS[item.statut] || item.statut}
      </span>
      <span className="text-dark-400 font-mono w-20 shrink-0">{item.vendor_code || '—'}</span>
      <span className="text-dark-200 truncate flex-1">{item.numero_facture || item.fichier_source || '—'}</span>
      <span className="text-dark-300 w-24 text-right shrink-0">{formatCents(item.montant_ttc_total)}</span>
      <span className="text-dark-500 w-24 text-right shrink-0">{formatDate(item.created_at)}</span>
    </div>
  )
}

// ─── Skeleton ────────────────────────────────────────────────────────────────

function ListSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map(i => (
        <div key={i} className="card p-4 animate-pulse">
          <div className="flex items-center gap-3 mb-3">
            <div className="h-5 w-16 skel rounded" />
            <div className="h-4 w-12 skel rounded" />
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="h-8 skel rounded" />
            <div className="h-8 skel rounded" />
            <div className="h-8 skel rounded" />
            <div className="h-8 skel rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function EtlImportsPage() {
  const qc = useQueryClient()
  const [activeTab, setActiveTab] = useState<TabKey>('preview')
  const [error, setError] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['etl-imports', activeTab],
    queryFn: () => listImports(activeTab, 50, 0),
    refetchInterval: activeTab === 'preview' ? 5000 : undefined,
  })

  const uploadMut = useMutation({
    mutationFn: ({ file, fournisseur }: { file: File; fournisseur: string }) =>
      uploadFacture(file, fournisseur),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['etl-imports'] })
      setError(null)
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur lors de l\'upload'),
  })

  const validateMut = useMutation({
    mutationFn: validateImport,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['etl-imports'] })
      setError(null)
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur de validation'),
  })

  const rejectMut = useMutation({
    mutationFn: rejectImport,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['etl-imports'] })
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur de rejet'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: EtlImportUpdateRequest }) =>
      updateImportPreview(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['etl-imports'] })
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur de mise à jour'),
  })

  const handleUpload = useCallback((file: File, fournisseur: string) => {
    uploadMut.mutate({ file, fournisseur })
  }, [uploadMut])

  const items = data?.items ?? []
  const isActing = validateMut.isPending || rejectMut.isPending
  const showPreviewCards = activeTab === 'preview' || activeTab === 'all'

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      <PageHeader title="Factures Fournisseur" />
      {/* Drop Zone */}
      <DropZone onUpload={handleUpload} isUploading={uploadMut.isPending} />

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-red-400 text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">fermer</button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-dark-900 rounded-lg p-1">
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex-1 px-3 py-2 rounded text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? 'bg-dark-900 text-dark-50'
                : 'text-dark-400 hover:text-dark-200'
            }`}
          >
            {tab.label}
            {tab.key === 'preview' && data && (
              <span className="ml-1.5 text-xs text-gold-400">
                {data.items.filter(i => i.statut === 'PREVIEW').length || ''}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Liste */}
      {isLoading ? (
        <ListSkeleton />
      ) : items.length === 0 ? (
        <div className="card p-8 text-center text-dark-400">
          {activeTab === 'preview'
            ? 'Aucune facture en attente de validation'
            : 'Aucun import trouvé'
          }
        </div>
      ) : showPreviewCards ? (
        <div className="space-y-3">
          {items.map(item => (
            item.statut === 'PREVIEW' ? (
              <PreviewCard
                key={item.id}
                item={item}
                onValidate={id => validateMut.mutate(id)}
                onReject={id => rejectMut.mutate(id)}
                onUpdate={(id, d) => updateMut.mutate({ id, data: d })}
                isActing={isActing}
              />
            ) : (
              <HistoryRow key={item.id} item={item} />
            )
          ))}
        </div>
      ) : (
        <div className="card overflow-hidden">
          {items.map(item => (
            <HistoryRow key={item.id} item={item} />
          ))}
        </div>
      )}

      {/* Total */}
      {data && data.total > items.length && (
        <p className="text-center text-dark-500 text-sm">
          {items.length} / {data.total} affichés
        </p>
      )}
    </div>
  )
}
