import { useState, useRef } from 'react'
import { Paperclip, Upload, Download, Trash2, FileText, Image, Loader2 } from 'lucide-react'
import { useDevisAttachments, useUploadDevisAttachment, useDeleteDevisAttachment } from '@/api/queries/useDevis'
import { devisApi } from '@/api/devis'
import { normalizeError } from '@shared/errors/normalizer'
import type { DevisAttachment } from '@/types/devis'

interface DevisAttachmentsProps {
  devisId: number
  readOnly?: boolean
  className?: string
}

const MIME_ICONS: Record<string, typeof FileText> = {
  'application/pdf': FileText,
  'image/jpeg': Image,
  'image/png': Image,
  'image/webp': Image,
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}

/**
 * G7 — Panneau de pieces jointes d'un devis.
 * Upload (drag & drop + bouton), liste, download, suppression.
 */
export default function DevisAttachments({ devisId, readOnly = false, className = '' }: DevisAttachmentsProps) {
  const [error, setError] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: attachments, isLoading } = useDevisAttachments(devisId)
  const uploadMutation = useUploadDevisAttachment()
  const deleteMutation = useDeleteDevisAttachment()

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setError('')

    for (const file of Array.from(files)) {
      try {
        await uploadMutation.mutateAsync({ devisId, file })
      } catch (err) {
        setError(normalizeError(err).message || `Erreur upload ${file.name}`)
        break
      }
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    handleUpload(e.dataTransfer.files)
  }

  const handleDelete = async (attachmentId: number) => {
    setError('')
    try {
      await deleteMutation.mutateAsync({ devisId, attachmentId })
    } catch (err) {
      setError(normalizeError(err).message || 'Erreur suppression')
    }
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center gap-2">
        <Paperclip className="w-4 h-4 text-dark-400" />
        <span className="text-sm font-medium text-dark-300">
          Pieces jointes ({attachments?.length ?? 0})
        </span>
      </div>

      {/* Zone upload */}
      {!readOnly && (
        <div
          className={`border-2 border-dashed rounded-xl p-4 text-center transition-colors cursor-pointer ${
            dragOver
              ? 'border-primary-400 bg-primary-500/5'
              : 'border-dark-600 hover:border-dark-500'
          }`}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          {uploadMutation.isPending ? (
            <Loader2 className="w-5 h-5 animate-spin text-primary-400 mx-auto" />
          ) : (
            <>
              <Upload className="w-5 h-5 text-dark-400 mx-auto mb-1" />
              <p className="text-xs text-dark-400">
                Glisser-deposer ou cliquer — PDF, JPEG, PNG, WEBP (max 10 Mo)
              </p>
            </>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,.webp"
            multiple
            className="hidden"
            onChange={(e) => handleUpload(e.target.files)}
          />
        </div>
      )}

      {/* Erreur */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-2">
          <p className="text-red-400 text-xs">{error}</p>
        </div>
      )}

      {/* Liste */}
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="h-12 bg-dark-800 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-1.5">
          {(attachments ?? []).map((att) => {
            const Icon = MIME_ICONS[att.mime_type] || FileText
            return (
              <div key={att.id} className="card flex items-center gap-3 rounded-lg px-3 py-2">
                <Icon className="w-4 h-4 text-dark-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white truncate">{att.filename}</p>
                  <p className="text-xs text-dark-500">{formatSize(att.file_size)}</p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <a
                    href={devisApi.downloadAttachment(devisId, att.id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1.5 hover:bg-dark-700 rounded transition-colors"
                    title="Telecharger"
                  >
                    <Download className="w-3.5 h-3.5 text-dark-400" />
                  </a>
                  {!readOnly && (
                    <button
                      onClick={() => handleDelete(att.id)}
                      disabled={deleteMutation.isPending}
                      className="p-1.5 hover:bg-red-500/10 rounded transition-colors disabled:opacity-50"
                      title="Supprimer"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-dark-400 hover:text-red-400" />
                    </button>
                  )}
                </div>
              </div>
            )
          })}

          {(attachments ?? []).length === 0 && (
            <p className="text-xs text-dark-500 text-center py-2">Aucune piece jointe.</p>
          )}
        </div>
      )}
    </div>
  )
}
