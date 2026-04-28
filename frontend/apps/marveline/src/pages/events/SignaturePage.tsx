import { useRef, useState, useEffect } from 'react'
import { useParams, useNavigate } from '@tanstack/react-router'
import { normalizeError } from '@shared/errors/normalizer'
import { Pen, RotateCcw, Check, ArrowLeft } from 'lucide-react'
import { useUploadReservationSignature, useReservationDetail } from '@/api/queries/useReservations'
import { ActionError } from '@shared/components/ui/ActionError'

export default function SignaturePage() {
  const { id: rawId } = useParams({ strict: false }) as { id: string }
  const id = parseInt(rawId, 10)
  const navigate = useNavigate()

  const { data: reservation } = useReservationDetail(id)
  const alreadySigned = !!reservation?.signature_url

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [drawing, setDrawing] = useState(false)
  const [isEmpty, setIsEmpty] = useState(true)
  const [saved, setSaved] = useState(false)

  // Initialiser le canvas blanc
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.fillStyle = '#1a1a2e'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.strokeStyle = '#e8d5a0'
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
  }, [])

  const getPos = (e: React.MouseEvent | React.TouchEvent, canvas: HTMLCanvasElement) => {
    const rect = canvas.getBoundingClientRect()
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    if ('touches' in e) {
      return {
        x: (e.touches[0].clientX - rect.left) * scaleX,
        y: (e.touches[0].clientY - rect.top) * scaleY,
      }
    }
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    }
  }

  const startDraw = (e: React.MouseEvent | React.TouchEvent) => {
    const canvas = canvasRef.current
    if (!canvas) return
    e.preventDefault()
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const pos = getPos(e, canvas)
    ctx.beginPath()
    ctx.moveTo(pos.x, pos.y)
    setDrawing(true)
    setIsEmpty(false)
  }

  const draw = (e: React.MouseEvent | React.TouchEvent) => {
    if (!drawing) return
    const canvas = canvasRef.current
    if (!canvas) return
    e.preventDefault()
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const pos = getPos(e, canvas)
    ctx.lineTo(pos.x, pos.y)
    ctx.stroke()
  }

  const stopDraw = () => setDrawing(false)

  const clearCanvas = () => {
    if (saved) return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.fillStyle = '#1a1a2e'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    setIsEmpty(true)
  }

  const mutation = useUploadReservationSignature()

  const handleSave = () => {
    const canvas = canvasRef.current
    if (!canvas || isEmpty || mutation.isPending) return
    const dataUrl = canvas.toDataURL('image/png')
    mutation.mutate(
      { reservationId: id, signatureData: dataUrl },
      {
        onSuccess: () => {
          setSaved(true)
          setTimeout(() => {
            navigate({ to: '/reservations/$id', params: { id: String(id) } })
          }, 1500)
        },
      }
    )
  }

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-2xl lg:max-w-5xl mx-auto">
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate({ to: '/reservations/$id', params: { id: String(id) } })}
          aria-label="Retour aux réservations"
          className="p-2 hover:bg-dark-600 rounded text-dark-400"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <Pen className="w-5 h-5 text-gold-400" />
        <h1 className="text-xl font-semibold">
          Signature contrat — Réservation #{id}
        </h1>
      </div>

      <div className="card p-4 space-y-4">
        {alreadySigned ? (
          <>
            <div className="flex items-center gap-2 text-green-400 text-sm">
              <Check className="w-4 h-4" />
              Cette reservation a deja ete signee.
            </div>
            <div className="border-2 border-green-700/40 rounded-lg overflow-hidden">
              <img
                src={reservation.signature_url!}
                alt="Signature"
                className="w-full h-auto max-h-[200px] object-contain bg-dark-800"
              />
            </div>
          </>
        ) : (
          <>
            <p className="text-dark-300 text-sm">
              Veuillez signer dans le cadre ci-dessous pour confirmer votre accord avec les conditions du contrat de location.
            </p>

            <div className={`border-2 border-dashed rounded-lg overflow-hidden ${saved ? 'border-green-700/40 opacity-60' : 'border-dark-600'}`}>
              <canvas
                ref={canvasRef}
                width={600}
                height={200}
                className={`w-full touch-none ${saved ? 'cursor-not-allowed' : 'cursor-crosshair'}`}
                onMouseDown={saved ? undefined : startDraw}
                onMouseMove={saved ? undefined : draw}
                onMouseUp={saved ? undefined : stopDraw}
                onMouseLeave={saved ? undefined : stopDraw}
                onTouchStart={saved ? undefined : startDraw}
                onTouchMove={saved ? undefined : draw}
                onTouchEnd={saved ? undefined : stopDraw}
              />
            </div>

            {saved ? (
              <div className="flex items-center gap-2 text-green-400 text-sm">
                <Check className="w-4 h-4" />
                Signature enregistree. Redirection...
              </div>
            ) : (
              <>
                <ActionError
                  message={(mutation.isError ? normalizeError(mutation.error).message || "Erreur lors de l'enregistrement" : null)}
                  onDismiss={() => mutation.reset()}
                />
                <div className="flex items-center justify-between gap-3">
                  <button
                    onClick={clearCanvas}
                    className="flex items-center gap-2 text-sm text-dark-400 hover:text-dark-50 transition-colors"
                  >
                    <RotateCcw className="w-4 h-4" />
                    Effacer
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={isEmpty || mutation.isPending}
                    className="btn-primary flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <Check className="w-4 h-4" />
                    {mutation.isPending ? 'Enregistrement...' : 'Valider la signature'}
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}
