import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { useCategoriesList } from '@/api/queries'
import { useMultiModal } from '@/hooks/useModal'
import { useResponsive } from '@/hooks/useMediaQuery'
import { CategoryFormModal, CategoryDeleteModal } from './components'
import { NoData, ErrorState } from '@shared/components/ui/EmptyState'
import type { Category } from '@/types/product'
import {
  FolderTree,
  Plus,
  Edit,
  Trash2,
  MoreVertical,
  ChevronRight,
  ChevronDown,
} from 'lucide-react'
import { cn } from '@/lib/utils'

type ModalType = 'create' | 'edit' | 'delete'

interface CategoryNodeProps {
  category: Category
  allCatégories: Category[]
  level: number
  onEdit: (category: Category) => void
  onDelete: (category: Category) => void
  openMenuId: number | null
  setOpenMenuId: (id: number | null) => void
  isMobile: boolean
}

function CategoryNode({
  category,
  allCatégories,
  level,
  onEdit,
  onDelete,
  openMenuId,
  setOpenMenuId,
  isMobile,
}: CategoryNodeProps) {
  const [isExpanded, setIsExpanded] = useState(true)
  const children = allCatégories.filter((c) => c.parent_id === category.id)
  const hasChildren = children.length > 0

  return (
    <div className={cn(level > 0 && (isMobile ? 'ml-4' : 'ml-8'))}>
      <div
        className="card flex items-center justify-between transition-colors hover:border-[var(--border2)] !py-3 !px-4"
      >
        <div className="flex items-center gap-4 flex-1 min-w-0">
          {hasChildren ? (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1 hover:bg-dark-600 rounded shrink-0 min-h-[44px] min-w-[44px] flex items-center justify-center"
            >
              {isExpanded ? (
                <ChevronDown className="w-4 h-4" />
              ) : (
                <ChevronRight className="w-4 h-4" />
              )}
            </button>
          ) : (
            <div className="w-6 shrink-0" />
          )}

          <FolderTree className="w-5 h-5 text-primary-500 shrink-0" />

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium truncate">{category.name}</span>
              {hasChildren && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-primary-500/10 text-primary-400 shrink-0">
                  {children.length}
                </span>
              )}
              {!category.is_active && (
                <span className="px-2 py-0.5 bg-dark-800 text-dark-400 text-xs rounded shrink-0">
                  Inactif
                </span>
              )}
            </div>
            {category.description && (
              <p className="text-sm text-dark-400 mt-0.5 truncate">
                {category.description}
              </p>
            )}
          </div>
        </div>

        <div className="relative shrink-0 ml-2">
          <button
            onClick={() =>
              setOpenMenuId(openMenuId === category.id ? null : category.id)
            }
            className="p-1 hover:bg-dark-600 rounded min-h-[44px] min-w-[44px] flex items-center justify-center"
          >
            <MoreVertical className="w-4 h-4" />
          </button>

          {openMenuId === category.id && (
            <>
              <div
                className="fixed inset-0 z-10"
                aria-hidden="true"
                onClick={() => setOpenMenuId(null)}
              />
              <div className="absolute right-0 mt-2 w-48 dropdown-menu">
                <button
                  onClick={() => onEdit(category)}
                  className="w-full px-4 py-2 text-left hover:bg-dark-600 flex items-center gap-2 first:rounded-t-lg"
                >
                  <Edit className="w-4 h-4" />
                  Modifier
                </button>
                <button
                  onClick={() => onDelete(category)}
                  className="w-full px-4 py-2 text-left hover:bg-dark-600 flex items-center gap-2 text-red-500 last:rounded-b-lg"
                >
                  <Trash2 className="w-4 h-4" />
                  Supprimer
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {hasChildren && (
        <div
          className={cn(
            'space-y-2 mt-2 accordion-enter',
            isExpanded && 'accordion-open'
          )}
        >
          {children.map((child) => (
            <CategoryNode
              key={child.id}
              category={child}
              allCatégories={allCatégories}
              level={level + 1}
              onEdit={onEdit}
              onDelete={onDelete}
              openMenuId={openMenuId}
              setOpenMenuId={setOpenMenuId}
              isMobile={isMobile}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function CatégoriesPage() {
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)
  const modal = useMultiModal<Category>()
  const { isMobile } = useResponsive()

  const { data: categories, isLoading, error, refetch } = useCategoriesList(false)

  const handleOpenModal = (type: ModalType, category?: Category) => {
    setOpenMenuId(null)
    modal.open(type, category)
  }

  const rootCatégories = categories?.filter((c) => !c.parent_id) || []

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <PageHeader title="Categories" subtitle="Organisez vos produits par categories" />
        <button
          onClick={() => handleOpenModal('create')}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">Nouvelle categorie</span>
        </button>
      </div>

      {/* Categories Tree */}
      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card flex items-center gap-4 !py-3 !px-4">
              <div className="w-4 h-4 skel rounded shrink-0" />
              <div className="h-3 skel rounded w-40" />
              <div className="ml-auto h-5 skel rounded w-8" />
            </div>
          ))}
        </div>
      ) : error ? (
        <ErrorState onRetry={() => refetch()} />
      ) : rootCatégories.length === 0 ? (
        <NoData
          onAction={() => handleOpenModal('create')}
          actionLabel="Nouvelle catégorie"
        />
      ) : (
        <div className="space-y-3">
          {rootCatégories.map((category) => (
            <CategoryNode
              key={category.id}
              category={category}
              allCatégories={categories || []}
              level={0}
              onEdit={(cat) => handleOpenModal('edit', cat)}
              onDelete={(cat) => handleOpenModal('delete', cat)}
              openMenuId={openMenuId}
              setOpenMenuId={setOpenMenuId}
              isMobile={isMobile}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      <CategoryFormModal
        isOpen={modal.isOpen('create') || modal.isOpen('edit')}
        onClose={modal.close}
        category={modal.data}
        mode={modal.isOpen('edit') ? 'edit' : 'create'}
      />

      <CategoryDeleteModal
        isOpen={modal.isOpen('delete')}
        onClose={modal.close}
        category={modal.data}
      />
    </div>
  )
}
