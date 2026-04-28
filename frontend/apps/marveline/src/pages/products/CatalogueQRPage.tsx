import { useState, useRef } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { useProductsList } from '@/api/queries'
import { useDebounce } from '@/hooks/useDebounce'
import { Search, Printer, Download, QrCode, CheckSquare, Square, ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ErrorState } from '@shared/components/ui/EmptyState'

const PAGE_SIZE = 48

export default function CatalogueQRPage() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const printRef = useRef<HTMLDivElement>(null)
  const debouncedSearch = useDebounce(search, 300)

  const { data, isLoading, error, refetch } = useProductsList({
    skip: (page - 1) * PAGE_SIZE,
    limit: PAGE_SIZE,
    active_only: true,
    search: debouncedSearch || undefined,
  })
  const products = data?.items || []
  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1

  const handleSearchChange = (q: string) => {
    setSearch(q)
    setPage(1)
    setSelected(new Set())
  }

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    const pageIds = products.map((p) => p.id)
    const allSelected = pageIds.every((id) => selected.has(id))
    setSelected((prev) => {
      const next = new Set(prev)
      if (allSelected) { pageIds.forEach((id) => next.delete(id)) }
      else { pageIds.forEach((id) => next.add(id)) }
      return next
    })
  }

  const pageIds = products.map((p) => p.id)
  const allPageSelected = pageIds.length > 0 && pageIds.every((id) => selected.has(id))
  const selectedProducts = products.filter((p) => selected.has(p.id))
  const printProducts = selectedProducts.length > 0 ? selectedProducts : products

  // QR value = URL vers la page stock de l'article (ou juste le SKU)
  const getQRValue = (sku: string) =>
    `${window.location.origin}/stock/items?sku=${encodeURIComponent(sku)}`

  const handlePrint = () => {
    window.print()
  }

  const handleDownloadSVG = (sku: string, name: string) => {
    const svgEl = document.getElementById(`qr-${sku}`)
    if (!svgEl) return
    const blob = new Blob([svgEl.outerHTML], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `qr-${sku}.svg`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2 min-w-0">
            <QrCode className="w-6 h-6 text-primary-400" />
            QR codes catalogue
          </h1>
          <p className="text-dark-400 mt-1">Générez et imprimez les QR codes de vos produits</p>
        </div>
        <button
          onClick={handlePrint}
          className="btn-primary flex items-center gap-2 print:hidden"
        >
          <Printer className="w-4 h-4" />
          <span className="hidden sm:inline">
            Imprimer {selectedProducts.length > 0 ? `(${selectedProducts.length})` : 'tout'}
          </span>
        </button>
      </div>

      {/* Filters — not printed */}
      <div className="card print:hidden space-y-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-400" />
          <input
            type="text"
            placeholder="Rechercher un produit..."
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="input pl-10"
          />
        </div>
        <div className="flex items-center justify-between text-sm text-dark-400">
          <button
            onClick={toggleAll}
            className="flex items-center gap-1.5 hover:text-dark-50 transition-colors"
          >
            {allPageSelected ? (
              <CheckSquare className="w-4 h-4 text-primary-400" />
            ) : (
              <Square className="w-4 h-4" />
            )}
            {selected.size === 0
              ? 'Tout sélectionner'
              : `${selected.size} sélectionné${selected.size !== 1 ? 's' : ''}`}
          </button>
          <span>{data?.total ?? 0} produit{(data?.total ?? 0) !== 1 ? 's' : ''}</span>
        </div>
      </div>

      {/* Grid QR codes */}
      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 animate-pulse">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="card p-4 space-y-4 flex flex-col items-center">
              <div className="w-24 h-24 skel rounded-lg" />
              <div className="h-3 skel rounded w-20" />
              <div className="h-2 skel rounded w-14" />
            </div>
          ))}
        </div>
      ) : error ? (
        <ErrorState onRetry={() => refetch()} />
      ) : products.length === 0 ? (
        <div className="text-center py-12 text-dark-400">Aucun produit trouvé</div>
      ) : (
        <>
          {/* Screen view */}
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 print:hidden">
            {products.map((product) => (
              <div
                key={product.id}
                onClick={() => toggleSelect(product.id)}
                className={cn(
                  'card p-4 flex flex-col items-center gap-4 cursor-pointer transition-all',
                  selected.has(product.id)
                    ? 'border-primary-500 ring-1 ring-primary-500/50'
                    : 'hover:border-dark-600'
                )}
              >
                {selected.has(product.id) && (
                  <div className="self-end -mt-1 -mr-1">
                    <CheckSquare className="w-4 h-4 text-primary-400" />
                  </div>
                )}
                <QRCodeSVG
                  id={`qr-${product.sku}`}
                  value={getQRValue(product.sku)}
                  size={100}
                  bgColor="transparent"
                  fgColor="#ffffff"
                  level="M"
                />
                <div className="text-center w-full">
                  <p className="text-xs font-medium truncate">{product.name}</p>
                  <p className="text-xs text-dark-400 font-mono">{product.sku}</p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDownloadSVG(product.sku, product.name)
                  }}
                  className="text-dark-500 hover:text-primary-400 flex items-center gap-1 text-xs"
                >
                  <Download className="w-3 h-3" />
                  SVG
                </button>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-4 print:hidden">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded hover:bg-dark-600 disabled:opacity-30 text-dark-300"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              <span className="text-sm text-dark-300">
                Page {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-1.5 rounded hover:bg-dark-600 disabled:opacity-30 text-dark-300"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          )}

          {/* Print layout */}
          <div
            ref={printRef}
            className="hidden print:grid print:grid-cols-4 print:gap-4 print:p-4"
          >
            {printProducts.map((product) => (
              <div
                key={product.id}
                className="border border-gray-300 p-4 flex flex-col items-center gap-2 break-inside-avoid"
              >
                <QRCodeSVG
                  value={getQRValue(product.sku)}
                  size={120}
                  bgColor="#ffffff"
                  fgColor="#000000"
                  level="M"
                />
                <div className="text-center">
                  <p className="text-xs font-semibold text-black leading-tight">{product.name}</p>
                  <p className="text-xs text-gray-500 font-mono">{product.sku}</p>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Print styles */}
      <style>{`
        @media print {
          body * { visibility: hidden; }
          .print\\:grid, .print\\:grid * { visibility: visible; }
        }
      `}</style>
    </div>
  )
}
