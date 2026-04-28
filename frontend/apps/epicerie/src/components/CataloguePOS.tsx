import { useState, useRef, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Search, ScanLine, AlertTriangle, RefreshCw, Camera, Loader2 } from 'lucide-react'
import { epicerieApi } from '@/api/epicerie'
import { cn } from '@shared/lib/utils'
import { normalizeError } from '@shared/errors/normalizer'
import type { EpicerieProduitRead, ProduitCatalogueRead } from '@/types/epicerie-v2'

const ACCEPTED_IMAGE_TYPES = 'image/jpeg,image/png,image/webp'

function formatEur(centimes: number): string {
  return (centimes / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
}

function useDebounce(delay = 300) {
  const [debounced, setDebounced] = useState('')
  const timer = useRef<ReturnType<typeof setTimeout>>()
  const update = useCallback((v: string) => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setDebounced(v), delay)
  }, [delay])
  return { debounced, update }
}

const BADGE_COLORS = {
  ok:      'bg-green-100 text-green-700 border-green-200',
  bas:     'bg-orange-100 text-orange-700 border-orange-200',
  rupture: 'bg-red-100 text-red-700 border-red-200',
} as const

function ProductThumb({ src, alt }: { src: string | null; alt: string }) {
  const apiUrl = (import.meta.env.VITE_API_URL || '/api/v1').replace('/api/v1', '')
  if (!src) {
    return (
      <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center shrink-0">
        <span className="text-gray-300 text-lg">📦</span>
      </div>
    )
  }
  return (
    <img
      src={`${apiUrl}/uploads/${src}`}
      alt={alt}
      className="w-10 h-10 rounded-lg object-cover shrink-0 bg-gray-100"
      loading="lazy"
      onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
    />
  )
}

function PhotoUploadCard({
  article,
  onUploaded,
}: {
  article: ProduitCatalogueRead
  onUploaded: () => void
}) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement | null>(null)
  const apiUrl = (import.meta.env.VITE_API_URL || '/api/v1').replace('/api/v1', '')
  const hasImage = Boolean(article.image_url)

  async function handleFile(ev: React.ChangeEvent<HTMLInputElement>) {
    const file = ev.target.files?.[0]
    if (!file) return
    setError('')
    setUploading(true)
    try {
      await epicerieApi.uploadProduitImage(article.id, file)
      onUploaded()
    } catch (err) {
      setError(normalizeError(err).message || 'Upload échoué')
      setTimeout(() => setError(''), 3000)
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <button
      onClick={() => inputRef.current?.click()}
      disabled={uploading}
      className={cn(
        'group w-full text-left p-3 rounded-xl border bg-white transition-all',
        hasImage ? 'border-gray-200' : 'border-amber-300 bg-amber-50',
        'hover:border-blue-400 hover:shadow-sm',
        'disabled:opacity-50 disabled:cursor-wait',
      )}
      aria-label={`Uploader photo pour ${article.designation_clean}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_IMAGE_TYPES}
        className="hidden"
        onChange={handleFile}
      />
      <div className="flex items-start gap-2.5 mb-2">
        <div className="relative w-10 h-10 shrink-0">
          {article.image_url ? (
            <img
              src={`${apiUrl}/uploads/${article.image_url}`}
              alt={article.designation_clean}
              className="w-10 h-10 rounded-lg object-cover bg-gray-100"
            />
          ) : (
            <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center">
              <span className="text-gray-300 text-lg">📦</span>
            </div>
          )}
          <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center shadow">
            {uploading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Camera className="w-3 h-3" />}
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-gray-800 leading-tight line-clamp-2" title={article.designation_clean}>
            {article.designation_clean}
          </div>
          {error ? (
            <div className="text-xs text-red-600 mt-1">{error}</div>
          ) : (
            <div className="text-xs text-gray-500 mt-1">
              {hasImage ? 'Remplacer' : 'Ajouter photo'}
            </div>
          )}
        </div>
      </div>
    </button>
  )
}

function CarteProduitPOS({ article, onAdd }: { article: ProduitCatalogueRead; onAdd: () => void }) {
  const badge = article.statut_badge
  return (
    <button
      onClick={onAdd}
      disabled={badge === 'rupture'}
      className={cn(
        'group w-full text-left p-3 rounded-xl border bg-white',
        'hover:border-blue-300 hover:shadow-sm transition-all',
        'disabled:opacity-50 disabled:cursor-not-allowed',
      )}
    >
      <div className="flex items-start gap-2.5 mb-2">
        <ProductThumb src={article.image_url} alt={article.designation_clean} />
        <div className="flex-1 min-w-0">
          <div className="flex justify-between items-start gap-1">
            <span className="text-sm font-medium text-gray-800 leading-tight line-clamp-2" title={article.designation_clean}>
              {article.designation_clean}
            </span>
            <span className={cn('flex-shrink-0 text-xs px-1.5 py-0.5 rounded border', BADGE_COLORS[badge])}>
              {badge === 'rupture' ? '0' : article.quantite}
            </span>
          </div>
        </div>
      </div>
      <div className="flex justify-between items-center">
        <span className="text-xs text-gray-400">{article.categorie ?? '\u2014'}</span>
        <span className="text-base font-bold text-blue-600">{formatEur(article.prix_unitaire_cts)}</span>
      </div>
    </button>
  )
}

function ScannerEAN({ onFound }: { onFound: (produit: EpicerieProduitRead) => void }) {
  const [ean, setEan] = useState('')
  const [error, setError] = useState('')

  async function scan() {
    if (!ean.trim()) return
    setError('')
    try {
      const produit = await epicerieApi.getProduitByEan(ean.trim())
      onFound(produit)
      setEan('')
    } catch {
      setError('EAN introuvable')
      setTimeout(() => setError(''), 2000)
    }
  }

  return (
    <div className="flex gap-1">
      <input
        type="text"
        value={ean}
        onChange={e => setEan(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && scan()}
        placeholder="Code EAN..."
        className={cn(
          'w-28 px-2 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-blue-300 focus:outline-none',
          error ? 'border-red-300 bg-red-50' : 'border-gray-200',
        )}
      />
      <button onClick={scan} title="Scanner EAN"
        className="p-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center">
        <ScanLine className="h-4 w-4 text-gray-600" />
      </button>
    </div>
  )
}

interface CataloguePOSProps {
  onAdd: (produit: EpicerieProduitRead) => void
}

export default function CataloguePOS({ onAdd }: CataloguePOSProps) {
  const { debounced: search, update: setSearch } = useDebounce()
  const [categorie, setCategorie] = useState('')
  const [photoMode, setPhotoMode] = useState(false)
  const [missingOnly, setMissingOnly] = useState(false)
  const queryClient = useQueryClient()

  const { data: catalogueData, isLoading, error, refetch } = useQuery({
    queryKey: ['epicerie-catalogue-pos', search, categorie],
    queryFn: () => epicerieApi.getCatalogue({ search, categorie, per_page: 200 }),
    staleTime: 15_000,
  })

  const errorMessage = error ? normalizeError(error).message : null
  const allArticles = catalogueData?.items ?? []
  const articles = photoMode && missingOnly
    ? allArticles.filter(a => !a.image_url)
    : allArticles
  const categories = ['', ...new Set(allArticles.map(a => a.categorie).filter((c): c is string => c !== null))]
  const missingCount = allArticles.filter(a => !a.image_url).length

  const invalidateCatalogue = () => {
    queryClient.invalidateQueries({ queryKey: ['epicerie-catalogue-pos'] })
  }

  return (
    <div className="flex flex-col h-full gap-3">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Rechercher un article..."
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-300 focus:outline-none"
          />
        </div>
        <ScannerEAN onFound={onAdd} />
        <button
          type="button"
          onClick={() => setPhotoMode(v => !v)}
          title={photoMode ? 'Revenir au mode vente' : 'Mode édition photos'}
          aria-pressed={photoMode}
          className={cn(
            'px-3 rounded-lg transition-colors min-h-[44px] flex items-center gap-1.5 text-sm font-medium border',
            photoMode
              ? 'bg-blue-600 text-white border-blue-600'
              : 'bg-gray-100 text-gray-700 border-gray-200 hover:bg-gray-200',
          )}
        >
          <Camera className="h-4 w-4" />
          <span className="hidden sm:inline">{photoMode ? 'Fin' : 'Photos'}</span>
          {!photoMode && missingCount > 0 && (
            <span className="text-[10px] px-1.5 rounded-full bg-amber-500 text-white">
              {missingCount}
            </span>
          )}
        </button>
      </div>

      {photoMode && (
        <div className="flex items-center justify-between p-2 rounded-lg bg-blue-50 border border-blue-200 text-xs text-blue-900">
          <span>
            Mode édition : un clic remplace la photo ({missingCount} produit{missingCount > 1 ? 's' : ''} sans image)
          </span>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={missingOnly}
              onChange={e => setMissingOnly(e.target.checked)}
              className="accent-blue-600"
            />
            Sans photo uniquement
          </label>
        </div>
      )}

      <div className="flex gap-2 overflow-x-auto pb-1 flex-shrink-0">
        {categories.map(cat => (
          <button key={cat || '__all__'} onClick={() => setCategorie(cat)}
            className={cn(
              'flex-shrink-0 px-3 py-1 text-xs rounded-full border transition-colors',
              categorie === cat
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300',
            )}>
            {cat || 'Tous'}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 animate-pulse">
            {[1, 2, 3, 4, 5, 6].map(i => (
              <div key={i} className="aspect-square bg-gray-100 rounded-xl" />
            ))}
          </div>
        )}
        {errorMessage && (
          <div className="flex flex-col items-center gap-3 py-12">
            <AlertTriangle className="w-8 h-8 text-red-400" />
            <p className="text-sm text-red-500 text-center max-w-xs">{errorMessage}</p>
            <button
              onClick={() => refetch()}
              className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Réessayer
            </button>
          </div>
        )}
        {!isLoading && !errorMessage && (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {articles.map(a => photoMode ? (
              <PhotoUploadCard key={a.id} article={a} onUploaded={invalidateCatalogue} />
            ) : (
              <CarteProduitPOS key={a.id} article={a}
                onAdd={() => onAdd({ ...a, description: null, vendor_id: null })} />
            ))}
            {articles.length === 0 && (
              <p className="col-span-3 text-center py-12 text-sm text-gray-400">Aucun article trouvé</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
