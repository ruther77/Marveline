import { useState } from 'react'
import { Download } from 'lucide-react'
import { Button } from './Button'

export interface PDFDownloadButtonProps {
  fetchPdf: () => Promise<Blob>
  filename: string
  label?: string
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  onError?: (err: Error) => void
}

export function PDFDownloadButton({
  fetchPdf,
  filename,
  label = 'Télécharger PDF',
  variant = 'secondary',
  size = 'md',
  onError,
}: PDFDownloadButtonProps) {
  const [loading, setLoading] = useState(false)

  async function handleDownload() {
    setLoading(true)
    try {
      const blob = await fetchPdf()
      const objectUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = objectUrl
      a.download = filename
      a.click()
      URL.revokeObjectURL(objectUrl)
    } catch (err) {
      onError?.(err as Error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Button
      variant={variant}
      size={size}
      onClick={handleDownload}
      loading={loading}
      type="button"
    >
      {!loading && <Download className="w-4 h-4 mr-1.5" />}
      {label}
    </Button>
  )
}
