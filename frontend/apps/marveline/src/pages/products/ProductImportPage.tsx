import { PageHeader } from '@/components/PageHeader'
import { useState, useRef, useCallback } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { ArrowLeft, Upload, FileText, CheckCircle, AlertTriangle, X } from 'lucide-react'
import { useImportProductsCsv } from '@/api/queries'
import type { ProductImportReport } from '@/types/product'
import { normalizeError } from '@shared/errors/normalizer'

const CSV_COLUMNS = ['name*', 'sku*', 'category*', 'price_per_day_cents*', 'deposit_amount_cents', 'stock_quantity', 'condition', 'image_url']
const EXAMPLE_ROWS = [
  ['Chaise Thonet', 'CHT-001', 'mobilier', '150', '50', '30', 'bon', ''],
  ['Table ronde 150cm', 'TBL-R150', 'mobilier', '350', '100', '10', 'bon', ''],
  ['Nappage blanc', 'NAP-BL', 'linge', '80', '20', '50', 'bon', ''],
]

// ============================================
// Parsing CSV preview côté client (5 premières lignes)
// ============================================

function parsePreview(text: string): { headers: string[]; rows: string[][] } {
  const lines = text.split(/\r?\n/).filter((l) => l.trim())
  if (lines.length === 0) return { headers: [], rows: [] }
  const headers = lines[0].split(',').map((h) => h.trim())
  const rows = lines
    .slice(1, 6)
    .map((l) => l.split(',').map((c) => c.trim()))
  return { headers, rows }
}

// ============================================
// Page
// ============================================

export default function ProductImportPage() {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<{ headers: string[]; rows: string[][] } | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [report, setReport] = useState<ProductImportReport | null>(null)

  const importMutation = useImportProductsCsv()

  function handleFile(f: File) {
    if (!f.name.endsWith('.csv') && f.type !== 'text/csv') return
    setFile(f)
    setReport(null)
    const reader = new FileReader()
    reader.onload = (e) => {
      const text = e.target?.result as string
      setPreview(parsePreview(text))
    }
    reader.readAsText(f, 'utf-8')
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) handleFile(dropped)
  }, [])

  function handleSubmit() {
    if (!file) return
    importMutation.mutate(file, {
      onSuccess: (data) => setReport(data),
    })
  }

  const errorMsg = importMutation.error ? normalizeError(importMutation.error).message : null

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      {/* En-tête */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate({ to: '/catalogue/products' })}
          className="p-2 hover:bg-dark-600 rounded text-dark-400"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <PageHeader title="Importer des produits (CSV)" subtitle="Créez plusieurs produits en une seule opération" />
      </div>

      {/* Format attendu */}
      <div className="card p-4 space-y-4">
        <h2 className="text-sm font-semibold text-dark-200 flex items-center gap-2">
          <FileText className="w-4 h-4 text-dark-400" />
          Format CSV attendu
        </h2>
        <p className="text-xs text-dark-400">
          Colonnes (* = obligatoire) — séparateur virgule, encodage UTF-8 :
        </p>
        <div className="flex flex-wrap gap-2">
          {CSV_COLUMNS.map((col) => (
            <span
              key={col}
              className={`text-xs px-2 py-1 rounded font-mono ${
                col.endsWith('*')
                  ? 'bg-gold-900/30 text-gold-300 border border-gold-800/40'
                  : 'bg-dark-900 text-dark-300'
              }`}
            >
              {col.replace('*', '')}
            </span>
          ))}
        </div>
        <p className="text-xs text-dark-500">
          <strong className="text-dark-400">price_per_day_cents</strong> : montant en centimes (ex: 150 = 1,50 €) —{' '}
          <strong className="text-dark-400">category</strong> : slug (mobilier, linge, vaisselle…)
        </p>
        {/* Exemple */}
        <div className="overflow-x-auto">
          <table className="text-xs w-full border-collapse">
            <thead>
              <tr>
                {['name', 'sku', 'category', 'price_per_day_cents', 'deposit_amount_cents', 'stock_quantity'].map((h) => (
                  <th key={h} className="text-left text-dark-500 font-medium py-1 pr-4 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {EXAMPLE_ROWS.map((row, i) => (
                <tr key={i}>
                  {row.slice(0, 6).map((cell, j) => (
                    <td key={j} className="text-dark-300 py-0.5 pr-4 whitespace-nowrap">
                      {cell || '—'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Zone drop */}
      {!report && (
        <div
          onDrop={onDrop}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-10 flex flex-col items-center justify-center gap-4 cursor-pointer transition-colors ${
            dragOver
              ? 'border-primary-500 bg-primary-900/10'
              : 'border-border hover:border-border2 bg-s2/50'
          }`}
        >
          <Upload className={`w-10 h-10 ${dragOver ? 'text-primary-400' : 'text-dark-500'}`} />
          {file ? (
            <div className="text-center">
              <p className="text-sm font-medium text-dark-200">{file.name}</p>
              <p className="text-xs text-dark-500 mt-0.5">
                {(file.size / 1024).toFixed(1)} Ko — cliquer pour changer
              </p>
            </div>
          ) : (
            <div className="text-center">
              <p className="text-sm text-dark-300">
                Glissez un fichier CSV ici ou <span className="text-primary-400">parcourir</span>
              </p>
              <p className="text-xs text-dark-500 mt-1">Format .csv, UTF-8</p>
            </div>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) handleFile(f)
            }}
          />
        </div>
      )}

      {/* Preview */}
      {preview && !report && preview.headers.length > 0 && (
        <div className="card p-4 space-y-2">
          <p className="text-sm font-medium text-dark-300">
            Aperçu — 5 premières lignes
          </p>
          <div className="overflow-x-auto">
            <table className="text-xs w-full border-collapse">
              <thead>
                <tr>
                  {preview.headers.map((h) => (
                    <th key={h} className="text-left text-dark-400 font-medium py-1 pr-4 whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, i) => (
                  <tr key={i} className="border-t border-dark-600">
                    {row.map((cell, j) => (
                      <td key={j} className="text-dark-300 py-1.5 pr-4 whitespace-nowrap">
                        {cell || <span className="text-dark-600">—</span>}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Erreur API */}
      {errorMsg && (
        <div className="flex items-start gap-4 bg-red-900/20 border border-red-800/40 rounded-xl p-4">
          <X className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-300">{errorMsg}</p>
        </div>
      )}

      {/* Rapport résultat */}
      {report && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <div className="bg-green-900/20 border border-green-800/40 rounded-xl p-4 text-center">
              <CheckCircle className="w-6 h-6 text-green-400 mx-auto mb-1" />
              <p className="text-2xl font-bold text-green-300">{report.created}</p>
              <p className="text-xs text-green-500">créé{report.created > 1 ? 's' : ''}</p>
            </div>
            <div className="card p-4 text-center">
              <p className="text-2xl font-bold text-dark-300">{report.skipped}</p>
              <p className="text-xs text-dark-500">ignoré{report.skipped > 1 ? 's' : ''}</p>
              <p className="text-xs text-dark-600">(doublons/vides)</p>
            </div>
            <div className={`rounded-xl p-4 text-center border ${report.errors.length > 0 ? 'bg-red-900/20 border-red-800/40' : 'card'}`}>
              <AlertTriangle className={`w-6 h-6 mx-auto mb-1 ${report.errors.length > 0 ? 'text-red-400' : 'text-dark-600'}`} />
              <p className={`text-2xl font-bold ${report.errors.length > 0 ? 'text-red-300' : 'text-dark-600'}`}>
                {report.errors.length}
              </p>
              <p className={`text-xs ${report.errors.length > 0 ? 'text-red-500' : 'text-dark-600'}`}>
                erreur{report.errors.length > 1 ? 's' : ''}
              </p>
            </div>
          </div>

          {report.errors.length > 0 && (
            <div className="card p-4 space-y-2">
              <p className="text-sm font-medium text-dark-300">Détail des erreurs</p>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {report.errors.map((err, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs py-1">
                    <span className="text-dark-500 flex-shrink-0 w-14">Ligne {err.row}</span>
                    {err.field && (
                      <span className="font-mono text-dark-400 flex-shrink-0">{err.field}</span>
                    )}
                    <span className="text-red-300">{err.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-4">
            <button
              onClick={() => {
                setFile(null)
                setPreview(null)
                setReport(null)
              }}
              className="btn-secondary flex-1"
            >
              Importer un autre fichier
            </button>
            <button
              onClick={() => navigate({ to: '/catalogue/products' })}
              className="btn-primary flex-1"
            >
              Voir les produits
            </button>
          </div>
        </div>
      )}

      {/* Bouton importer */}
      {file && !report && (
        <button
          onClick={handleSubmit}
          disabled={importMutation.isPending}
          className="btn-primary w-full flex items-center justify-center gap-2"
        >
          <Upload className="w-4 h-4" />
          {importMutation.isPending ? 'Import en cours…' : 'Importer'}
        </button>
      )}
    </div>
  )
}
