import { useRef, useState } from 'react'
import { ImagePlus, Loader2, Star, Trash2 } from 'lucide-react'
import {
  useAddProductImage,
  useDeleteProductImage,
  useProductImages,
  useSetPrimaryImage,
} from '@/api/queries/useProducts'
import { normalizeError } from '@shared/errors/normalizer'

interface ProductImageGalleryProps {
  productId: number
}

export function ProductImageGallery({ productId }: ProductImageGalleryProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const { data: images = [], isLoading } = useProductImages(productId)
  const addMutation = useAddProductImage(productId)
  const deleteMutation = useDeleteProductImage(productId)
  const setPrimaryMutation = useSetPrimaryImage(productId)

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadError(null)
    try {
      await addMutation.mutateAsync(file)
    } catch (err) {
      setUploadError(normalizeError(err).message || 'Erreur lors de l\'upload')
    }
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 animate-pulse">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="aspect-square bg-dark-800 rounded-lg" />
        ))}
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="block text-sm text-dark-400 mb-1">
          Galerie d'images ({images.length})
        </label>
        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={handleFileChange}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={addMutation.isPending}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs bg-dark-900 hover:bg-dark-600 rounded-lg transition-colors disabled:opacity-50"
          >
            {addMutation.isPending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <ImagePlus className="w-3.5 h-3.5" />
            )}
            Ajouter
          </button>
        </div>
      </div>

      {uploadError && (
        <p className="text-xs text-red-400 mb-2">{uploadError}</p>
      )}

      {images.length === 0 ? (
        <p className="text-xs text-dark-500 italic">Aucune image dans la galerie.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {images.map((img) => (
            <div key={img.id} className="relative group rounded-lg overflow-hidden bg-dark-900 aspect-square">
              <img
                src={img.url}
                alt={`Image ${img.sort_order + 1}`}
                loading="lazy"
                className="w-full h-full object-cover"
              />
              {img.is_primary && (
                <div className="absolute top-1 left-1 bg-amber-500 rounded-full p-0.5">
                  <Star className="w-2.5 h-2.5 text-white fill-white" />
                </div>
              )}
              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-1.5">
                {!img.is_primary && (
                  <button
                    type="button"
                    title="Définir comme principale"
                    onClick={() => setPrimaryMutation.mutate(img.id)}
                    disabled={setPrimaryMutation.isPending}
                    className="p-1 bg-amber-500 hover:bg-amber-400 rounded-full transition-colors disabled:opacity-50"
                  >
                    <Star className="w-3 h-3 text-white" />
                  </button>
                )}
                <button
                  type="button"
                  title="Supprimer"
                  onClick={() => deleteMutation.mutate(img.id)}
                  disabled={deleteMutation.isPending}
                  className="p-1 bg-red-600 hover:bg-red-500 rounded-full transition-colors disabled:opacity-50"
                >
                  <Trash2 className="w-3 h-3 text-white" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
