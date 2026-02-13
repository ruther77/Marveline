import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { categoriesApi } from '@/api/categories'
import { useMultiModal } from '@/hooks/useModal'
import { CategoryFormModal, CategoryDeleteModal } from './components'
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
  allCategories: Category[]
  level: number
  onEdit: (category: Category) => void
  onDelete: (category: Category) => void
  openMenuId: number | null
  setOpenMenuId: (id: number | null) => void
}

function CategoryNode({
  category,
  allCategories,
  level,
  onEdit,
  onDelete,
  openMenuId,
  setOpenMenuId,
}: CategoryNodeProps) {
  const [isExpanded, setIsExpanded] = useState(true)
  const children = allCategories.filter((c) => c.parent_id === category.id)
  const hasChildren = children.length > 0

  return (
    <div>
      <div
        className={cn(
          'flex items-center justify-between py-3 px-4 hover:bg-dark-800/50 rounded-lg',
          level > 0 && 'ml-8'
        )}
      >
        <div className="flex items-center gap-3 flex-1">
          {hasChildren ? (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1 hover:bg-dark-700 rounded"
            >
              {isExpanded ? (
                <ChevronDown className="w-4 h-4" />
              ) : (
                <ChevronRight className="w-4 h-4" />
              )}
            </button>
          ) : (
            <div className="w-6" />
          )}

          <FolderTree className="w-5 h-5 text-primary-500" />

          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium">{category.name}</span>
              {!category.is_active && (
                <span className="px-2 py-0.5 bg-dark-700 text-dark-400 text-xs rounded">
                  Inactif
                </span>
              )}
            </div>
            {category.description && (
              <p className="text-sm text-dark-400 mt-0.5">
                {category.description}
              </p>
            )}
          </div>
        </div>

        <div className="relative">
          <button
            onClick={() =>
              setOpenMenuId(openMenuId === category.id ? null : category.id)
            }
            className="p-1 hover:bg-dark-700 rounded"
          >
            <MoreVertical className="w-4 h-4" />
          </button>

          {openMenuId === category.id && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setOpenMenuId(null)}
              />
              <div className="absolute right-0 mt-2 w-48 bg-dark-800 border border-dark-700 rounded-lg shadow-lg z-20">
                <button
                  onClick={() => onEdit(category)}
                  className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 first:rounded-t-lg"
                >
                  <Edit className="w-4 h-4" />
                  Modifier
                </button>
                <button
                  onClick={() => onDelete(category)}
                  className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 text-red-500 last:rounded-b-lg"
                >
                  <Trash2 className="w-4 h-4" />
                  Supprimer
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {hasChildren && isExpanded && (
        <div>
          {children.map((child) => (
            <CategoryNode
              key={child.id}
              category={child}
              allCategories={allCategories}
              level={level + 1}
              onEdit={onEdit}
              onDelete={onDelete}
              openMenuId={openMenuId}
              setOpenMenuId={setOpenMenuId}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function CategoriesPage() {
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)
  const modal = useMultiModal<Category>()

  const { data: categories, isLoading } = useQuery({
    queryKey: ['categories', false], // Get all including inactive
    queryFn: () => categoriesApi.getCategories(false),
  })

  const handleOpenModal = (type: ModalType, category?: Category) => {
    setOpenMenuId(null)
    modal.open(type, category)
  }

  // Get root categories (no parent)
  const rootCategories = categories?.filter((c) => !c.parent_id) || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Catégories</h1>
          <p className="text-dark-400 mt-1">
            Organisez vos produits par catégories
          </p>
        </div>
        <button
          onClick={() => handleOpenModal('create')}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Nouvelle catégorie
        </button>
      </div>

      {/* Categories Tree */}
      <div className="card">
        {isLoading ? (
          <div className="text-center py-8 text-dark-400">Chargement...</div>
        ) : rootCategories.length === 0 ? (
          <div className="text-center py-8 text-dark-400">
            Aucune catégorie trouvée
          </div>
        ) : (
          <div className="space-y-1">
            {rootCategories.map((category) => (
              <CategoryNode
                key={category.id}
                category={category}
                allCategories={categories || []}
                level={0}
                onEdit={(cat) => handleOpenModal('edit', cat)}
                onDelete={(cat) => handleOpenModal('delete', cat)}
                openMenuId={openMenuId}
                setOpenMenuId={setOpenMenuId}
              />
            ))}
          </div>
        )}
      </div>

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
