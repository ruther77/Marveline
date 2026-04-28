// Route : /_app/etl-imports
// Queue factures fournisseur — Upload multi, Preview, Validation rapide (ADR-25)

import { useState, useCallback } from 'react'
import { useNavigate, Link } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { uploadFacture, listImports } from '@/api/etl_imports'
import type { EtlImportRead } from '@/types/etl_import'
import { normalizeError } from '@shared/errors/normalizer'
import { formatCents, formatDate, STATUT_LABELS, STATUT_COLORS } from '@/utils/etl-helpers'
import MonthlyStats from '@/components/etl/MonthlyStats'
import QuickValidateButton from '@/components/etl/QuickValidateButton'
import { Pagination } from '@/components/Pagination'

const IMPORTS_PER_PAGE = 25

// ─── Tabs ───────────────────────────────────────────────────────────────────

const TABS = [
  { key: 'preview', label: 'À valider' },
  { key: 'all', label: 'Tout' },
  { key: 'validated', label: 'Validées' },
  { key: 'rejected', label: 'Rejetées' },
] as const

type TabKey = typeof TABS[number]['key']

// ─── Helpers ────────────────────────────────────────────────────────────────

function isQuickValidatable(item: EtlImportRead): boolean {
  return item.statut === 'PREVIEW' && item.quality_score === 100
    && item.nb_lignes_conflit === 0 && item.nb_lignes_erreur === 0
}

function TenantBadge({
  tenantId, clientName,
}: { tenantId: number | null; clientName: string | null }) {
  if (tenantId == null) return null
  const label = tenantId === 3 ? 'Resto' : tenantId === 2 ? 'Épicerie' : `#${tenantId}`
  const color = tenantId === 3
    ? 'bg-amber-100 text-amber-700 border-amber-200'
    : 'bg-emerald-100 text-emerald-700 border-emerald-200'
  const tooltip = clientName ? `${clientName} → tenant ${tenantId}` : `tenant ${tenantId}`
  return (
    <span
      title={tooltip}
      className={`text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded border ${color} shrink-0`}
    >
      {label}
    </span>
  )
}

// ─── Drop Zone (multi-fichier) ──────────────────────────────────────────────

function DropZone({ onUpload, uploadProgress }: {
  onUpload: (files: File[], fournisseur: string) => void
  uploadProgress: { current: number; total: number } | null
}) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [fournisseur, setFournisseur] = useState('metro')
  const isUploading = uploadProgress !== null

  const handleFiles = useCallback((files: FileList | File[]) => {
    const accepted = Array.from(files).filter(f => {
      const n = f.name.toLowerCase()
      return n.endsWith('.pdf') || n.endsWith('.xlsx') || n.endsWith('.heic')
    })
    if (accepted.length > 0) onUpload(accepted, fournisseur)
  }, [onUpload, fournisseur])

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6">
      <div className="flex items-center gap-4 mb-4">
        <h2 className="text-lg font-semibold text-slate-900 flex-1">Importer des factures</h2>
        <Link to="/etl-dashboard" className="text-[12px] font-medium text-violet-600 hover:text-violet-800 bg-violet-50 px-3 py-1.5 rounded-lg hover:bg-violet-100 transition-colors">
          Tableau de bord
        </Link>
        <select value={fournisseur} onChange={e => setFournisseur(e.target.value)}
          className="bg-white text-slate-700 border border-slate-300 rounded-lg px-3 py-1.5 text-sm">
          <option value="metro">METRO</option>
          <option value="taiyat">TAIYAT</option>
          <option value="eurociel">EUROCIEL</option>
          <option value="ethan">ETHAN</option>
          <option value="gnanam">GNANAM</option>
        </select>
      </div>

      <div
        onDragOver={e => { e.preventDefault(); setIsDragOver(true) }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={e => { e.preventDefault(); setIsDragOver(false); handleFiles(e.dataTransfer.files) }}
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer min-h-[120px] flex items-center justify-center ${
          isDragOver ? 'border-emerald-400 bg-emerald-50' : 'border-slate-300 hover:border-slate-400 bg-slate-50'
        } ${isUploading ? 'opacity-50 pointer-events-none' : ''}`}
        onClick={() => !isUploading && document.getElementById('etl-file-input')?.click()}
      >
        <input id="etl-file-input" type="file" accept=".pdf,.xlsx,.heic" multiple className="hidden"
          onChange={e => { if (e.target.files) handleFiles(e.target.files); e.target.value = '' }}
          disabled={isUploading} />

        {isUploading ? (
          <div className="flex flex-col items-center gap-2">
            <div className="w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-slate-500 text-sm">
              Import {uploadProgress.current}/{uploadProgress.total}…
            </span>
            <div className="w-48 h-1.5 bg-slate-200 rounded-full overflow-hidden">
              <div className="h-full bg-emerald-500 transition-all duration-300 rounded-full"
                style={{ width: `${(uploadProgress.current / uploadProgress.total) * 100}%` }} />
            </div>
          </div>
        ) : (
          <div>
            <div className="text-4xl mb-2 text-slate-300">📄</div>
            <p className="text-slate-500">
              Glissez vos factures ici ou <span className="text-emerald-600 underline">parcourir</span>
            </p>
            <p className="text-slate-400 text-sm mt-1">
              Multi-fichier · PDF (METRO, TAIYAT, EUROCIEL), XLSX (ETHAN), HEIC (GNANAM)
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Preview Card ───────────────────────────────────────────────────────────

function PreviewCard({ item, navigate, onError }: {
  item: EtlImportRead
  navigate: (opts: { to: string; params: { id: string } }) => void
  onError: (msg: string) => void
}) {
  const canQuickValidate = isQuickValidatable(item)
  const hasProblems = !canQuickValidate
  const hasEcart = item.ecart_reconciliation !== null && Math.abs(Number(item.ecart_reconciliation)) > 1

  // UNE couleur, UN signal
  const borderColor = canQuickValidate ? 'border-emerald-200 bg-emerald-50/30' : hasEcart ? 'border-amber-200 bg-amber-50/20' : 'border-slate-200'
  const accentDot = canQuickValidate ? 'bg-emerald-500' : hasEcart ? 'bg-amber-500' : 'bg-slate-300'

  return (
    <div
      onClick={() => navigate({ to: '/etl-imports/$id', params: { id: String(item.id) } })}
      className={`rounded-xl border p-4 cursor-pointer hover:shadow-md transition-all ${borderColor}`}
    >
      <div className="flex items-center gap-4">
        {/* Signal visuel unique */}
        <div className={`w-3 h-3 rounded-full shrink-0 ${accentDot}`} />

        {/* Infos principales */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-semibold text-slate-800">{item.numero_facture || '—'}</span>
            <span className="text-xs text-slate-400 font-mono">{item.vendor_code}</span>
            <TenantBadge tenantId={item.target_tenant_id} clientName={item.client_name} />
            <span className="text-xs text-slate-400">{formatDate(item.date_facture)}</span>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span>{item.nb_lignes_total ?? 0} lignes</span>
            <span className="font-mono">{formatCents(item.montant_ttc_total)} TTC</span>
            {hasEcart && (
              <span className="text-amber-600 font-medium">
                écart {Number(item.ecart_reconciliation).toFixed(0)}€
              </span>
            )}
          </div>
        </div>

        {/* Action unique */}
        {canQuickValidate ? (
          <QuickValidateButton importId={item.id} onError={onError} />
        ) : (
          <span className="text-xs font-medium text-slate-500 bg-slate-100 px-3 py-1.5 rounded-lg">
            Réviser →
          </span>
        )}
      </div>
    </div>
  )
}

// ─── History Row ────────────────────────────────────────────────────────────

function HistoryRow({ item, navigate }: {
  item: EtlImportRead
  navigate: (opts: { to: string; params: { id: string } }) => void
}) {
  return (
    <div onClick={() => navigate({ to: '/etl-imports/$id', params: { id: String(item.id) } })}
      className="flex items-center gap-4 px-4 py-3 border-b border-slate-100 text-sm cursor-pointer hover:bg-slate-50 transition-colors">
      <span className={`px-2 py-0.5 rounded text-xs font-medium shrink-0 ${STATUT_COLORS[item.statut] || ''}`}>
        {STATUT_LABELS[item.statut] || item.statut}
      </span>
      <span className="text-slate-400 font-mono w-20 shrink-0">{item.vendor_code || '—'}</span>
      <TenantBadge tenantId={item.target_tenant_id} clientName={item.client_name} />
      <span className="text-slate-700 truncate flex-1">{item.numero_facture || item.fichier_source || '—'}</span>
      <span className="text-slate-600 w-24 text-right shrink-0">{formatCents(item.montant_ttc_total)}</span>
      <span className="text-slate-400 w-24 text-right shrink-0">{formatDate(item.created_at)}</span>
      <span className="text-slate-300 shrink-0">→</span>
    </div>
  )
}

// ─── Skeleton ───────────────────────────────────────────────────────────────

function ListSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map(i => (
        <div key={i} className="bg-white rounded-xl border border-slate-200 p-4 animate-pulse">
          <div className="flex items-center gap-3 mb-3">
            <div className="h-5 w-16 bg-slate-100 rounded" />
            <div className="h-4 w-12 bg-slate-100 rounded" />
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[1, 2, 3, 4].map(j => <div key={j} className="h-8 bg-slate-100 rounded" />)}
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Page ───────────────────────────────────────────────────────────────────

export default function EtlImportsPage() {
  const qc = useQueryClient()
  const nav = useNavigate()
  const [activeTab, setActiveTab] = useState<TabKey>('preview')
  const [page, setPage] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const [uploadProgress, setUploadProgress] = useState<{ current: number; total: number } | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['etl-imports', activeTab, page],
    queryFn: () => listImports(activeTab, IMPORTS_PER_PAGE, (page - 1) * IMPORTS_PER_PAGE),
    refetchInterval: activeTab === 'preview' ? 5000 : undefined,
    placeholderData: prev => prev,
  })

  function handleTabChange(next: TabKey) {
    setActiveTab(next)
    setPage(1)
  }

  // All imports pour les stats mensuelles
  const { data: allData } = useQuery({
    queryKey: ['etl-imports', 'all'],
    queryFn: () => listImports('all', 200, 0),
    staleTime: 60_000,
  })

  const handleMultiUpload = useCallback(async (files: File[], fournisseur: string) => {
    setError(null)
    setUploadProgress({ current: 0, total: files.length })
    let lastId: number | null = null

    for (let i = 0; i < files.length; i++) {
      try {
        const resp = await uploadFacture(files[i], fournisseur)
        lastId = resp.etl_import_id
        setUploadProgress({ current: i + 1, total: files.length })
      } catch (err) {
        setError(normalizeError(err).message || `Erreur upload ${files[i].name}`)
      }
    }

    setUploadProgress(null)
    qc.invalidateQueries({ queryKey: ['etl-imports'] })
    setActiveTab('preview')
    setPage(1)

    // Navigate to last import if single file, stay on list if multi
    if (files.length === 1 && lastId) {
      nav({ to: '/etl-imports/$id', params: { id: String(lastId) } })
    }
  }, [qc, nav])

  const items = data?.items ?? []
  const showPreviewCards = activeTab === 'preview' || activeTab === 'all'

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900">Factures Fournisseur</h1>
        <MonthlyStats imports={allData?.items ?? []} />
      </div>

      {/* Drop Zone */}
      <DropZone onUpload={handleMultiUpload} uploadProgress={uploadProgress} />

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-600 text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">fermer</button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-100 rounded-lg p-1">
        {TABS.map(tab => (
          <button key={tab.key} onClick={() => handleTabChange(tab.key)}
            className={`flex-1 px-3 py-2 rounded text-sm font-medium transition-colors ${
              activeTab === tab.key ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}>
            {tab.label}
            {tab.key === 'preview' && data && (
              <span className="ml-1.5 text-xs text-amber-600">
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
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <div className="text-5xl mb-4">📋</div>
          <h3 className="text-lg font-semibold text-slate-700 mb-2">
            {activeTab === 'preview' ? 'Aucune facture en attente' : 'Aucun import trouvé'}
          </h3>
          <p className="text-sm text-slate-500">
            {activeTab === 'preview'
              ? 'Glissez vos factures PDF dans la zone ci-dessus pour commencer.'
              : 'Les imports apparaîtront ici une fois créés.'
            }
          </p>
        </div>
      ) : showPreviewCards ? (
        <div className="space-y-3">
          {items.map(item =>
            item.statut === 'PREVIEW'
              ? <PreviewCard key={item.id} item={item} navigate={nav} onError={setError} />
              : <HistoryRow key={item.id} item={item} navigate={nav} />
          )}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          {items.map(item => <HistoryRow key={item.id} item={item} navigate={nav} />)}
        </div>
      )}

      {/* Pagination */}
      {data && (
        <Pagination
          page={page}
          total={data.total}
          perPage={IMPORTS_PER_PAGE}
          onPageChange={setPage}
          itemLabel="import"
        />
      )}
    </div>
  )
}
