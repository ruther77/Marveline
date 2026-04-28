import { Download, XCircle } from 'lucide-react'

interface DevisPdfPreviewProps {
  url: string
  reference: string
  onDownload: () => void
  onClose: () => void
}

export function DevisPdfPreview({ url, reference, onDownload, onClose }: DevisPdfPreviewProps) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/80">
      <div className="flex items-center justify-between px-4 py-4 bg-dark-900 border-b border-dark-600">
        <span className="font-medium text-sm">
          Aperçu PDF — {reference}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={onDownload}
            className="flex items-center gap-1.5 bg-dark-900 hover:bg-dark-600 text-dark-50 text-sm px-4 py-1.5 rounded-lg"
          >
            <Download className="w-4 h-4" /> Télécharger
          </button>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-dark-600 rounded text-dark-400 hover:text-dark-50"
          >
            <XCircle className="w-5 h-5" />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        <iframe
          src={url}
          className="w-full h-full border-0"
          title="Aperçu du devis PDF"
        />
      </div>
    </div>
  )
}
