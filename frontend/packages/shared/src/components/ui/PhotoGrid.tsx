import { useState, useRef } from 'react'
import { cn } from '../../lib/utils'
import { Camera, X, ZoomIn } from 'lucide-react'

interface PhotoGridProps {
  photos: string[]
  onAdd?: (file: File) => void
  onRemove?: (index: number) => void
  maxPhotos?: number
  readOnly?: boolean
  className?: string
}

export function PhotoGrid({
  photos,
  onAdd,
  onRemove,
  maxPhotos = 6,
  readOnly = false,
  className,
}: PhotoGridProps) {
  const [preview, setPreview] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file && onAdd) {
      onAdd(file)
    }
    if (inputRef.current) inputRef.current.value = ''
  }

  const canAdd = !readOnly && onAdd && photos.length < maxPhotos

  return (
    <>
      <div className={cn('grid grid-cols-3 gap-1.5', className)}>
        {photos.map((url, i) => (
          <div
            key={i}
            className="relative aspect-square rounded-xl overflow-hidden bg-dark-900 cursor-pointer group"
            onClick={() => setPreview(url)}
          >
            <img
              src={url}
              alt={`Photo ${i + 1}`}
              className="w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 group-active:opacity-100 transition-opacity flex items-center justify-center rounded-xl">
              <ZoomIn className="w-5 h-5 text-white" />
            </div>
            {!readOnly && onRemove && (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); onRemove(i) }}
                className="absolute top-1.5 right-1.5 w-6 h-6 bg-black/60 rounded-full flex items-center justify-center text-white opacity-0 group-hover:opacity-100 transition-opacity"
                aria-label="Supprimer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
            {photos.length > 3 && i === 2 && photos.length > 3 && (
              <div className="absolute bottom-1.5 right-1.5 bg-black/60 rounded-md px-1.5 py-0.5 text-[10px] font-bold text-white">
                +{photos.length - 3}
              </div>
            )}
          </div>
        ))}

        {canAdd && (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="aspect-square rounded-xl border-2 border-dashed border-dark-600 flex flex-col items-center justify-center gap-1 text-dark-500 hover:border-dark-400 hover:text-dark-300 transition-colors"
          >
            <Camera className="w-5 h-5" />
            <span className="text-[10px] font-medium">Photo</span>
          </button>
        )}
      </div>

      {canAdd && (
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleFileChange}
          className="hidden"
        />
      )}

      {preview && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setPreview(null)}
        >
          <button
            className="absolute top-4 right-4 w-10 h-10 bg-white/10 rounded-full flex items-center justify-center text-white"
            onClick={() => setPreview(null)}
            aria-label="Fermer"
          >
            <X className="w-5 h-5" />
          </button>
          <img
            src={preview}
            alt="Aperçu"
            className="max-w-full max-h-[85vh] rounded-xl object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  )
}
