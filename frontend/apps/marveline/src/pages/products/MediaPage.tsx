import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { ImageIcon, ChevronRight, Search } from 'lucide-react'
import { useProductsList } from '@/api/queries/useProducts'
import { ErrorState } from '@shared/components/ui/EmptyState'

export default function MediaPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')

  const { data, isLoading, error, refetch } = useProductsList({ limit: 200 })
  const products = (data?.items ?? data ?? []) as { id: number; name: string; reference?: string; image_url?: string }[]

  const filtered = products.filter((p) =>
    !search || p.name.toLowerCase().includes(search.toLowerCase()) ||
    (p.reference ?? '').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ImageIcon className="w-5 h-5 text-gold-400" />
          <PageHeader title="Médiathèque" />
          <span className="text-sm text-dark-400">({filtered.length} produits)</span>
        </div>
      </div>

      {/* Recherche */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400 pointer-events-none" />
        <input
          type="text"
          placeholder="Rechercher un produit…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input pl-9"
        />
      </div>

      {/* Grille produits */}
      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 animate-pulse">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="card p-4 space-y-2">
              <div className="aspect-square skel rounded-lg" />
              <div className="h-3 skel rounded w-24" />
              <div className="h-2 skel rounded w-16" />
            </div>
          ))}
        </div>
      ) : error ? (
        <ErrorState onRetry={() => refetch()} />
      ) : filtered.length === 0 ? (
        <div className="text-center text-dark-400 text-sm py-8">Aucun produit trouvé</div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {filtered.map((p) => (
            <button
              key={p.id}
              onClick={() => navigate({ to: '/catalogue/products/$id/photos', params: { id: String(p.id) } })}
              className="group flex flex-col card p-0 overflow-hidden hover:border-gold-600 transition-colors text-left"
            >
              <div className="aspect-square bg-dark-900 relative overflow-hidden">
                {p.image_url ? (
                  <img src={p.image_url} alt={p.name} loading="lazy" className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <ImageIcon className="w-8 h-8 text-dark-600" />
                  </div>
                )}
                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  <ChevronRight className="w-6 h-6 text-white" />
                </div>
              </div>
              <div className="p-2">
                <p className="text-xs font-medium truncate">{p.name}</p>
                {p.reference && <p className="text-dark-500 text-xs truncate">{p.reference}</p>}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
