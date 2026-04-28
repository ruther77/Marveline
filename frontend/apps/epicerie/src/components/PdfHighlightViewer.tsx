/**
 * Viewer PDF avec highlight de ligne synchronisé.
 *
 * Utilise pdf.js pour le rendu canvas + overlay highlight.
 * Lazy-loaded pour ne pas impacter le bundle initial.
 *
 * Props:
 *   pdfUrl: URL du PDF à afficher
 *   highlightLine: {page, y} pour highlight (page 0-indexed, y en points PDF origin top)
 */
import { useEffect, useRef, useState, useCallback } from 'react'

interface HighlightLine {
  page: number   // 0-indexed
  y: number      // Y en points PDF (origin top-left)
}

interface PdfHighlightViewerProps {
  pdfUrl: string | null
  highlightLine: HighlightLine | null
}

const SCALE = 1.5
const HIGHLIGHT_HEIGHT = 16  // px

export default function PdfHighlightViewer({ pdfUrl, highlightLine }: PdfHighlightViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRefs = useRef<Map<number, HTMLCanvasElement>>(new Map())
  const [numPages, setNumPages] = useState(0)
  const [pageHeights, setPageHeights] = useState<Map<number, number>>(new Map())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pdfDocRef = useRef<unknown>(null)

  // Charger le PDF
  useEffect(() => {
    if (!pdfUrl) return
    let cancelled = false

    async function loadPdf() {
      try {
        const pdfjs = await import('pdfjs-dist')
        pdfjs.GlobalWorkerOptions.workerSrc = new URL(
          'pdfjs-dist/build/pdf.worker.min.mjs',
          import.meta.url,
        ).toString()

        const doc = await pdfjs.getDocument(pdfUrl!).promise
        if (cancelled) return
        pdfDocRef.current = doc
        setNumPages(doc.numPages)
        setLoading(false)
      } catch (err) {
        if (!cancelled) {
          setError('Erreur chargement PDF')
          setLoading(false)
        }
      }
    }
    loadPdf()
    return () => { cancelled = true }
  }, [pdfUrl])

  // Rendre une page
  const renderPage = useCallback(async (pageNum: number) => {
    const doc = pdfDocRef.current as { getPage: (n: number) => Promise<unknown> } | null
    if (!doc) return

    const page = await doc.getPage(pageNum) as {
      getViewport: (opts: { scale: number }) => { width: number; height: number }
      render: (opts: { canvasContext: CanvasRenderingContext2D; viewport: unknown }) => { promise: Promise<void> }
    }
    const viewport = page.getViewport({ scale: SCALE })

    const canvas = canvasRefs.current.get(pageNum)
    if (!canvas) return

    canvas.width = viewport.width
    canvas.height = viewport.height
    canvas.style.width = `${viewport.width}px`
    canvas.style.height = `${viewport.height}px`

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    await page.render({ canvasContext: ctx, viewport }).promise

    setPageHeights(prev => {
      const next = new Map(prev)
      next.set(pageNum, viewport.height)
      return next
    })
  }, [])

  // Rendre toutes les pages au chargement
  useEffect(() => {
    if (numPages === 0) return
    for (let i = 1; i <= numPages; i++) {
      renderPage(i)
    }
  }, [numPages, renderPage])

  // Auto-scroll vers la ligne sélectionnée
  useEffect(() => {
    if (!highlightLine || !containerRef.current) return
    const targetPage = highlightLine.page + 1 // pdf.js = 1-indexed
    const canvas = canvasRefs.current.get(targetPage)
    if (!canvas) return

    // Calculer le Y dans le canvas : origin top en points → pixels
    const yPx = highlightLine.y * SCALE
    const canvasTop = canvas.offsetTop

    containerRef.current.scrollTo({
      top: canvasTop + yPx - 100, // 100px de marge en haut
      behavior: 'smooth',
    })
  }, [highlightLine])

  if (!pdfUrl) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400 text-sm">
        Aucun PDF disponible
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse space-y-4 w-full px-4">
          <div className="bg-slate-200 rounded h-[600px]" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-red-500 text-sm">
        {error}
      </div>
    )
  }

  return (
    <div ref={containerRef} className="relative overflow-y-auto h-full bg-slate-100 rounded-xl">
      {Array.from({ length: numPages }, (_, i) => i + 1).map(pageNum => (
        <div key={pageNum} className="relative mb-2">
          {/* Numéro de page */}
          <div className="absolute top-2 right-2 z-10 bg-slate-800/70 text-white text-[10px] px-2 py-0.5 rounded">
            {pageNum}/{numPages}
          </div>

          {/* Canvas PDF */}
          <canvas
            ref={el => {
              if (el) canvasRefs.current.set(pageNum, el)
            }}
            className="w-full"
          />

          {/* Highlight overlay */}
          {highlightLine && highlightLine.page === pageNum - 1 && (
            <div
              className="absolute left-0 right-0 bg-violet-500/20 border-y border-violet-500/40 pointer-events-none transition-all duration-200"
              style={{
                top: `${highlightLine.y * SCALE}px`,
                height: `${HIGHLIGHT_HEIGHT}px`,
              }}
            />
          )}
        </div>
      ))}
    </div>
  )
}
