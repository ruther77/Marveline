import { useState } from 'react'
import { useNavigate, useSearch, Link } from '@tanstack/react-router'
import { useProductsList, useCategoriesList } from '@/api/queries'
import { cn } from '@/lib/utils'
import { PAGE_SIZE_DEFAULT } from '@/lib/constants'
import { useMultiModal } from '@/hooks/useModal'
import { ProductFormModal, ProductDeleteModal } from './components'
import { NoData, ErrorState } from '@shared/components/ui/EmptyState'
import { SwipeActions } from '@shared/components/ui/SwipeActions'
import type { Product } from '@/types/product'
import { Package, Plus, Search, Pencil, Trash2 } from 'lucide-react'

// ── Labels fallback pour les 20 categories enum backend ────────────────────
const CATEGORY_LABELS: Record<string, string> = {
  assiettes: 'Assiettes',
  verres: 'Verres',
  couverts: 'Couverts',
  nappes: 'Nappes',
  serviettes: 'Serviettes',
  nappages: 'Nappages',
  tables: 'Tables',
  chaises: 'Chaises',
  bancs: 'Bancs',
  mobilier: 'Mobilier',
  machines: 'Machines',
  candy_bar: 'Candy Bar',
  mange_debout: 'Mange-debout',
  decorations: 'Décorations',
  housses: 'Housses',
  accessoires_transport: 'Transport',
  vaisselle: 'Vaisselle',
  vaisselle_service: 'Service',
  vaisselle_enfants: 'Enfants',
  porcelaine: 'Porcelaine',
}

/** Resout le nom affichable d'une catégorie produit.
 *  Cherche d'abord par slug dans la table categories, puis fallback sur le map enum. */
function resolveCategoryName(category: string, categories?: { slug: string; name: string }[]): string {
  return categories?.find((c) => c.slug === category)?.name
    ?? CATEGORY_LABELS[category]
    ?? category.replace(/_/g, ' ')
}

// ── Skeleton catalogue card ────────────────────────────────────────────────

function CatalogCardSkeleton() {
  return (
    <div className="card rounded-xl overflow-hidden animate-pulse" style={{ padding: 0 }}>
      <div className="h-36 bg-dark-900" />
      <div className="p-4 space-y-2">
        <div className="h-3 skel rounded w-3/4" />
        <div className="h-2 skel rounded w-1/2" />
        <div className="flex justify-between mt-4">
          <div className="h-4 skel rounded w-20" />
          <div className="h-4 skel rounded w-16" />
        </div>
      </div>
    </div>
  )
}

// ── Catalog card (s-catalogue-produit style) ──────────────────────────────

function CatalogCard({ product, categories, onEdit, onDelete }: {
  product: Product
  categories?: { slug: string; name: string }[]
  onEdit: (p: Product) => void
  onDelete: (p: Product) => void
}) {
  const navigate = useNavigate()
  const categoryName = resolveCategoryName(product.category, categories)
  const isLowStock = product.available_quantity > 0 && product.available_quantity <= Math.ceil(product.stock_quantity * 0.2)
  const isOutOfStock = product.available_quantity === 0

  const cardContent = (
    <article
      className="card rounded-xl overflow-hidden hover:border-dark-500 transition-colors cursor-pointer"
      style={{ padding: 0 }}
      onClick={() => navigate({ to: '/catalogue/products/$id' as never, params: { id: String(product.id) } as never })}
    >
      {/* Thumb */}
      <div className="relative h-36 bg-dark-900">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name}
            loading="lazy"
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-[#f5f0ff] to-[#ede9fe]">
            <Package className="w-10 h-10 text-[#a78bfa]" />
          </div>
        )}
        <span className="absolute top-2 left-2 text-xs px-2 py-0.5 rounded-full badge-muted font-medium backdrop-blur-sm">
          {categoryName}
        </span>
      </div>

      {/* Body */}
      <div className="p-4">
        <div className="font-semibold text-sm truncate">{product.name}</div>
        <div className="text-xs text-dark-400 mt-0.5">Réf {product.sku}</div>
        <div className="flex items-center justify-between mt-2">
          <div>
            <span className="text-sm font-bold">{product.price_per_day_euros.toFixed(2)} EUR</span>
            <span className="text-xs text-dark-500 ml-1">/jour</span>
          </div>
          <span className={cn(
            'text-xs font-medium',
            isOutOfStock ? 'text-red-400' : isLowStock ? 'text-orange-400' : 'text-dark-400'
          )}>
            {product.available_quantity} dispo
          </span>
        </div>
      </div>

      {/* Actions desktop (stop propagation) */}
      <div
        className="hidden md:flex gap-1 px-4 pb-4"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={() => onEdit(product)}
          className="flex-1 text-xs py-1.5 rounded-lg border border-dark-600 text-dark-400 hover:text-dark-50 hover:bg-dark-600 transition-colors"
        >
          Modifier
        </button>
        <button
          onClick={() => onDelete(product)}
          className="px-4 py-1.5 rounded-lg border border-dark-600 text-red-400 hover:bg-red-500/10 transition-colors text-xs"
        >
          ✕
        </button>
      </div>
    </article>
  )

  return (
    <SwipeActions
      leftActions={[{
        icon: <Trash2 className="w-5 h-5" />,
        label: 'Supprimer',
        color: 'bg-red-600',
        onClick: () => onDelete(product),
      }]}
      rightActions={[{
        icon: <Pencil className="w-5 h-5" />,
        label: 'Modifier',
        color: 'bg-primary-600',
        onClick: () => onEdit(product),
      }]}
      className="rounded-2xl"
    >
      {cardContent}
    </SwipeActions>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────

type ModalType = 'create' | 'edit' | 'delete'

export default function ProductsPage() {
  const navigate = useNavigate({ from: '/catalogue/products/' })
  const { page, category } = useSearch({ strict: false }) as { page: number; category: string }

  const modal = useMultiModal<Product>()
  const activeFilter = category || 'all'
  const [showExtraFilters, setShowExtraFilters] = useState(false)

  const { data, isLoading, error, refetch } = useProductsList({
    skip: ((page || 1) - 1) * PAGE_SIZE_DEFAULT,
    limit: PAGE_SIZE_DEFAULT,
    active_only: true,
    category: activeFilter !== 'all' ? activeFilter : undefined,
  })

  const { data: categories } = useCategoriesList()

  const products = data?.items || []

  const handleFilterChange = (slug: string) => {
    navigate({ search: (prev) => ({ ...prev, category: slug !== 'all' ? slug : undefined, page: 1 }) })
  }

  // Build category pills : only leaf categories (those with a parent)
  const allCats = (categories || []).filter((c) => c.parent_id != null)
  const primaryCats = allCats.slice(0, 4)
  const extraCats = allCats.slice(4)
  const visibleCats = showExtraFilters ? allCats : primaryCats

  return (
    <div className="space-y-6">
      {/* ── Barre recherche clickable ─────────────────────────────────── */}
      <div
        className="flex items-center gap-4 card px-4 py-4 cursor-pointer hover:border-dark-500 transition-colors"
        onClick={() => navigate({ to: '/catalogue/search' as never })}
      >
        <Search className="w-4 h-4 text-dark-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium">Recherche produit</p>
          <p className="text-xs text-dark-400">Nom, collection, état, disponibilité, prix, QR</p>
        </div>
        <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-medium shrink-0">
          Avancée
        </span>
      </div>

      {/* ── Workflow strip ───────────────────────────────────────────── */}
      <div className="space-y-2">
        <WorkflowStep num={1} title="Découvrir les collections" sub="Accéder rapidement aux categories, statuts et émojis produits." chip="Découverte" chipColor="green" />
        <WorkflowStep num={2} title="Qualifier l'inventaire" sub="Filtres compacts et scénarios permettent de prioriser les items critiqués." chip="Qualification" chipColor="orange" />
        <WorkflowStep num={3} title="Orchestrer la sélection" sub="Composer propositions, packs ou kits avec les outils du catalogue." chip="Proposition" chipColor="blue" onClick={() => navigate({ to: '/catalogue/bundles' })} />
      </div>

      {/* ── Filtres catégorie pills ──────────────────────────────────── */}
      <div className="flex gap-2 flex-wrap">
        <FilterPill active={activeFilter === 'all'} onClick={() => handleFilterChange('all')}>Tout</FilterPill>
        {visibleCats.map((c) => (
          <FilterPill key={c.slug} active={activeFilter === c.slug} onClick={() => handleFilterChange(c.slug)}>
            {c.name}
          </FilterPill>
        ))}
        {extraCats.length > 0 && (
          <FilterPill active={false} onClick={() => setShowExtraFilters((v) => !v)}>
            {showExtraFilters ? 'Moins' : 'Plus'}
          </FilterPill>
        )}
        <button
          onClick={() => modal.open('create')}
          className="ml-auto flex items-center gap-1.5 px-4 py-1 text-xs font-medium rounded-full bg-primary-500 text-white hover:bg-primary-500/90 transition-colors"
        >
          <Plus className="w-3 h-3" />
          Nouveau
        </button>
      </div>

      {/* ── Grid catalogue ──────────────────────────────────────────── */}
      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <CatalogCardSkeleton key={i} />)}
        </div>
      ) : error ? (
        <ErrorState onRetry={() => refetch()} />
      ) : products.length === 0 ? (
        <NoData onAction={() => modal.open('create')} actionLabel="Nouveau produit" />
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {products.map((product) => (
            <CatalogCard
              key={product.id}
              product={product}
              categories={categories}
              onEdit={(p) => modal.open('edit', p)}
              onDelete={(p) => modal.open('delete', p)}
            />
          ))}
        </div>
      )}

      {/* ── Parcours opérationnels ───────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-semibold">Parcours opérationnels</p>
          <Link to="/catalogue/tools" className="text-xs text-primary-400 hover:text-primary-300">
            Options avancées
          </Link>
        </div>
        <div className="space-y-1">
          <ScenarioRow
            icon="🔍"
            name="Parcours 1 · Repérage produit"
            meta="Recherche par référence, prix, état, disponibilité ou QR"
            chip="Exécuter"
            chipColor="blue"
            onClick={() => navigate({ to: '/catalogue/search' as never })}
          />
          <ScenarioRow
            icon="📋"
            name="Parcours 2 · Qualification"
            meta="Comparer les options et retenir la référence la plus adaptée"
            chip="Qualifier"
            chipColor="green"
            onClick={() => navigate({ search: (prev) => ({ ...prev }) })}
          />
          <ScenarioRow
            icon="🧩"
            name="Parcours 3 · Structuration offre"
            meta="Construire l'offre via packs et collections"
            chip="Structurer"
            chipColor="purple"
            onClick={() => navigate({ to: '/catalogue/bundles' })}
          />
        </div>
        <Link to="/catalogue/tools" className="block text-xs text-dark-400 hover:text-primary-400 mt-4 text-center transition-colors">
          Accéder aux options avancées →
        </Link>
      </div>

      {/* ── Modals CRUD ─────────────────────────────────────────────── */}
      <ProductFormModal
        isOpen={modal.isOpen('create') || modal.isOpen('edit')}
        onClose={modal.close}
        product={modal.data}
        mode={modal.isOpen('edit') ? 'edit' : 'create'}
      />
      <ProductDeleteModal
        isOpen={modal.isOpen('delete')}
        onClose={modal.close}
        product={modal.data}
      />
    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────

function FilterPill({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'px-4 py-1 text-xs font-medium rounded-full border transition-colors',
        active
          ? 'bg-primary-500 border-primary-500 text-white'
          : 'bg-dark-900 border-dark-600 text-dark-400 hover:bg-dark-600'
      )}
    >
      {children}
    </button>
  )
}

const CHIP_COLORS: Record<string, string> = {
  green:  'bg-green-500/10 text-green-400 border-green-500/20',
  orange: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  blue:   'bg-blue-500/10 text-blue-400 border-blue-500/20',
  purple: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
}

function WorkflowStep({ num, title, sub, chip, chipColor, onClick }: {
  num: number; title: string; sub: string; chip: string; chipColor: string; onClick?: () => void
}) {
  return (
    <div
      className={cn('flex items-center gap-4 p-4 card border border-dark-600', onClick && 'cursor-pointer hover:border-dark-500')}
      onClick={onClick}
    >
      <div className="w-7 h-7 rounded-full bg-dark-800 border border-dark-600 text-xs font-bold flex items-center justify-center shrink-0 text-dark-300">
        {num}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold">{title}</p>
        <p className="text-xs text-dark-400 mt-0.5 line-clamp-1">{sub}</p>
      </div>
      <span className={cn('text-xs px-2 py-0.5 rounded-full border font-medium shrink-0', CHIP_COLORS[chipColor])}>
        {chip}
      </span>
    </div>
  )
}

function ScenarioRow({ icon, name, meta, chip, chipColor, onClick }: {
  icon: string; name: string; meta: string; chip: string; chipColor: string; onClick?: () => void
}) {
  return (
    <div
      className="flex items-center gap-4 px-4 py-2.5 card border border-dark-600 hover:border-dark-500 cursor-pointer transition-colors"
      onClick={onClick}
    >
      <span className="text-lg shrink-0">{icon}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{name}</p>
        <p className="text-xs text-dark-400 truncate">{meta}</p>
      </div>
      <span className={cn('text-xs px-2 py-0.5 rounded-full border font-medium shrink-0', CHIP_COLORS[chipColor])}>
        {chip}
      </span>
    </div>
  )
}
