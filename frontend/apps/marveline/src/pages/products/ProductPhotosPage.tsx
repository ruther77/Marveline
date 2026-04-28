import { PageHeader } from '@/components/PageHeader'
import { useRef } from 'react'
import { useParams } from '@tanstack/react-router'
import { ImageIcon, Upload, Trash2, Star } from 'lucide-react'
import { BackButton } from '@/layout/EntityBreadcrumb'
import { useProductDetail } from '@/api/queries/useProducts'
import { useProductImages, useAddProductImage, useDeleteProductImage, useSetPrimaryImage } from '@/api/queries/useProducts'
import { ErrorState } from '@shared/components/ui/EmptyState'

export default function ProductPhotosPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const productId = parseInt(id, 10)
  const inputRef = useRef<HTMLInputElement>(null)

  const { data: product } = useProductDetail(productId)
  const { data: images = [], isLoading, error, refetch } = useProductImages(productId)
  const addImage = useAddProductImage(productId)
  const deleteImage = useDeleteProductImage(productId)
  const setPrimary = useSetPrimaryImage(productId)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    addImage.mutate(file)
    e.target.value = ''
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <BackButton />
        <div>
          <div className="flex items-center gap-2">
            <ImageIcon className="w-5 h-5 text-gold-400" />
            <PageHeader title="Galerie photos" subtitle={product?.name ?? `Produit #${productId}`} />
          </div>

        </div>
        <button
          onClick={() => inputRef.current?.click()}
          disabled={addImage.isPending}
          className="ml-auto flex items-center gap-2 bg-gold-600 hover:bg-gold-700 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50"
        >
          <Upload className="w-4 h-4" />
          {addImage.isPending ? 'Envoi…' : 'Ajouter'}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>

      {/* Grille */}
      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 animate-pulse">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="aspect-square bg-dark-800 rounded-xl flex items-center justify-center">
              <svg className="w-8 h-8 text-dark-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
              </svg>
            </div>
          ))}
        </div>
      ) : error ? (
        <ErrorState onRetry={() => refetch()} />
      ) : images.length === 0 && product?.image_url ? (
        <div className="space-y-4">
          <p className="text-xs text-dark-400">Image principale (définie dans l'éditeur produit)</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <div className="relative rounded-xl overflow-hidden aspect-square">
              <img src={product.image_url} alt="" className="w-full h-full object-cover" />
              <div className="absolute top-2 left-2 bg-gold-600 text-white text-xs px-2 py-0.5 rounded-full flex items-center gap-1">
                <Star className="w-3 h-3" /> Principale
              </div>
            </div>
            <button
              onClick={() => inputRef.current?.click()}
              className="aspect-square border-2 border-dashed border-dark-600 rounded-xl flex flex-col items-center justify-center gap-2 text-dark-500 hover:border-gold-600 hover:text-gold-400 transition-colors"
            >
              <Upload className="w-6 h-6" />
              <span className="text-xs">Ajouter</span>
            </button>
          </div>
        </div>
      ) : images.length === 0 ? (
        <div
          className="border-2 border-dashed border-dark-600 rounded-xl p-12 text-center cursor-pointer hover:border-gold-600 transition-colors"
          onClick={() => inputRef.current?.click()}
        >
          <ImageIcon className="w-10 h-10 text-dark-500 mx-auto mb-4" />
          <p className="text-dark-400 text-sm">Aucune photo — cliquez pour ajouter</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {images.map((img) => (
            <div key={img.id} className="relative group rounded-xl overflow-hidden bg-dark-900 aspect-square">
              <img
                src={img.url}
                alt=""
                loading="lazy"
                className="w-full h-full object-cover"
              />
              {/* Badge primaire */}
              {img.is_primary && (
                <div className="absolute top-2 left-2 bg-gold-600 text-white text-xs px-2 py-0.5 rounded-full flex items-center gap-1">
                  <Star className="w-3 h-3" /> Principale
                </div>
              )}
              {/* Actions hover */}
              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-4">
                {!img.is_primary && (
                  <button
                    onClick={() => setPrimary.mutate(img.id)}
                    disabled={setPrimary.isPending}
                    title="Définir comme principale"
                    className="p-2 bg-gold-600 hover:bg-gold-700 rounded-lg text-white disabled:opacity-50"
                  >
                    <Star className="w-4 h-4" />
                  </button>
                )}
                <button
                  onClick={() => deleteImage.mutate(img.id)}
                  disabled={deleteImage.isPending}
                  title="Supprimer"
                  className="p-2 bg-red-600 hover:bg-red-700 rounded-lg text-white disabled:opacity-50"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
          {/* Tuile ajout */}
          <button
            onClick={() => inputRef.current?.click()}
            className="aspect-square border-2 border-dashed border-dark-600 rounded-xl flex flex-col items-center justify-center gap-2 text-dark-500 hover:border-gold-600 hover:text-gold-400 transition-colors"
          >
            <Upload className="w-6 h-6" />
            <span className="text-xs">Ajouter</span>
          </button>
        </div>
      )}

      {/* Compteur */}
      {images.length > 0 && (
        <p className="text-xs text-dark-500 text-right">
          {images.length} photo{images.length > 1 ? 's' : ''}
        </p>
      )}
    </div>
  )
}
