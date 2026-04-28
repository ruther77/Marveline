import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useSearch } from '@tanstack/react-router'
import { ArrowLeft, ArrowRight, Camera, Check, AlertTriangle, AlertCircle } from 'lucide-react'
import { useDepartureInventory, useUploadDamagePhoto } from '@/api/queries/useOperations'
import { useOperationsStore } from '@/stores/operationsStore'
import { normalizeError } from '@shared/errors/normalizer'

type PhysicalState = 'bon' | 'raye' | 'casse' | 'perdu'

const STATE_OPTIONS: { value: PhysicalState; label: string; emoji: string; color: string }[] = [
  { value: 'bon', label: 'Bon état', emoji: '✅', color: 'border-green-500/40 bg-green-500/10 text-green-400' },
  { value: 'raye', label: 'Rayé / usé', emoji: '🔸', color: 'border-orange-500/40 bg-orange-500/10 text-orange-400' },
  { value: 'casse', label: 'Cassé', emoji: '💥', color: 'border-red-500/40 bg-red-500/10 text-red-400' },
  { value: 'perdu', label: 'Perdu', emoji: '❓', color: 'border-dark-500 bg-dark-900 text-dark-300' },
]

export default function ArticleCheckPage() {
  const { reservationId } = useParams({ strict: false }) as { reservationId: string }
  const search = useSearch({ strict: false }) as { index?: number }
  const navigate = useNavigate()
  const parsedReservationId = Number.parseInt(reservationId ?? '', 10)
  const resId = Number.isInteger(parsedReservationId) && parsedReservationId > 0 ? parsedReservationId : null
  const index = typeof search.index === 'number' ? search.index : 0

  const { data: departure, isLoading } = useDepartureInventory(resId)
  const { updateDepartureItem } = useOperationsStore()

  const items = departure?.items ?? []
  const item = items[index] ?? null
  const total = items.length

  const [quantity, setQuantity] = useState<number>(0)
  const [physicalState, setPhysicalState] = useState<PhysicalState>('bon')
  const [note, setNote] = useState('')
  const [photoUrls, setPhotoUrls] = useState<string[]>([])
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const uploadPhoto = useUploadDamagePhoto()

  useEffect(() => {
    if (item) {
      setQuantity(item.quantity_loaded ?? item.quantity_expected)
      setNote(item.note ?? '')
      setPhysicalState('bon')
      setPhotoUrls(item.photo_urls ?? [])
      setUploadError(null)
    }
  }, [item])

  const handlePhotoCapture = async (file: File) => {
    setUploadError(null)
    try {
      const result = await uploadPhoto.mutateAsync(file)
      setPhotoUrls((prev) => [...prev, result.url])
    } catch (err) {
      setUploadError(normalizeError(err).message || 'Erreur lors de l\'envoi de la photo.')
    }
  }

  const handleSave = () => {
    if (!item) return
    updateDepartureItem(item.line_id, {
      quantity_loaded: quantity,
      condition: physicalState === 'bon' ? 'good'
        : physicalState === 'raye' ? 'fair'
        : physicalState === 'casse' ? 'damaged'
        : 'missing',
      note: note.trim() || undefined,
      photo_urls: photoUrls.length > 0 ? photoUrls : undefined,
    })
  }

  const goTo = (newIndex: number) => {
    handleSave()
    navigate({
      to: '/operations/departure/$reservationId/check',
      params: { reservationId },
      search: { index: newIndex },
    })
  }

  const expected = item?.quantity_expected ?? 0
  const diff = quantity - expected
  const isDamaged = physicalState === 'casse' || physicalState === 'perdu'
  const progress = total > 0 ? Math.round(((index + 1) / total) * 100) : 0

  if (resId == null) {
    return (
      <div className="text-center py-12 text-red-400">
        <p>Identifiant de réservation invalide.</p>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-6 skel rounded w-48" />
        <div className="card p-6 h-24 skel/40 rounded" />
        <div className="card p-4 h-32 skel/40 rounded" />
        <div className="card p-4 h-28 skel/40 rounded" />
      </div>
    )
  }

  if (!item) {
    return (
      <div className="text-center py-12 text-dark-400">
        <p>Article introuvable.</p>
        <button
          onClick={() => navigate({ to: '/operations/departure/$reservationId', params: { reservationId } })}
          className="mt-4 text-primary-400 text-sm"
        >
          Retour au départ
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header + progression */}
      <div className="flex items-center justify-between gap-4">
        <button
          onClick={() => navigate({ to: '/operations/departure/$reservationId', params: { reservationId } })}
          className="p-2 hover:bg-dark-600 rounded text-dark-400"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 text-center">
          <p className="text-sm font-medium">{index + 1} / {total}</p>
        </div>
        <span className="text-xs text-dark-400">{progress}%</span>
      </div>

      {/* Barre progression */}
      <div className="space-y-1">
        <div className="h-1 bg-dark-900 rounded-full overflow-hidden">
          <div
            className="h-full bg-green-500 rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex gap-1">
          {items.map((_, i) => (
            <div
              key={i}
              className={`flex-1 h-1 rounded-full ${
                i < index ? 'bg-green-500' : i === index ? 'bg-primary-500' : 'bg-dark-900'
              }`}
            />
          ))}
        </div>
      </div>

      {/* Article info */}
      <div className="card p-4">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-dark-950 flex items-center justify-center text-xl shrink-0">
            📦
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-medium truncate">{item.product_name}</p>
            <p className="text-xs text-dark-400 mt-0.5">Article {index + 1} sur {total}</p>
          </div>
          <span className="px-2.5 py-1 text-xs font-medium rounded-full border bg-blue-500/15 text-blue-400 border-blue-500/30 shrink-0">
            À vérifier
          </span>
        </div>
      </div>

      {/* Compteur quantité */}
      <div className="card p-4 space-y-4">
        <p className="text-xs uppercase tracking-wide text-dark-400">Quantité constatée</p>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setQuantity((q) => Math.max(0, q - 1))}
            className="w-14 h-14 card border border-dark-600 flex items-center justify-center text-2xl font-bold hover:bg-dark-600 active:scale-95"
          >
            −
          </button>
          <div className="flex-1 text-center">
            <p className="text-4xl font-bold">{quantity}</p>
            <p className="text-xs text-dark-400 mt-1">prévu : {expected}</p>
          </div>
          <button
            onClick={() => setQuantity((q) => q + 1)}
            className="w-14 h-14 card border border-dark-600 flex items-center justify-center text-2xl font-bold hover:bg-dark-600 active:scale-95"
          >
            +
          </button>
        </div>
        {diff !== 0 && (
          <div className={`flex items-center gap-2 p-2.5 rounded-lg ${diff < 0 ? 'bg-yellow-500/10 border border-yellow-500/20' : 'bg-green-500/10 border border-green-500/20'}`}>
            <AlertTriangle className={`w-4 h-4 shrink-0 ${diff < 0 ? 'text-yellow-400' : 'text-green-400'}`} />
            <p className={`text-xs font-medium ${diff < 0 ? 'text-yellow-400' : 'text-green-400'}`}>
              Écart de {diff > 0 ? '+' : ''}{diff} par rapport au prévu
            </p>
          </div>
        )}
      </div>

      {/* État physique */}
      <div className="card p-4 space-y-4">
        <p className="text-xs uppercase tracking-wide text-dark-400">État physique</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {STATE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setPhysicalState(opt.value)}
              className={`flex items-center gap-2 p-4 rounded-xl border font-medium text-sm transition-all ${
                physicalState === opt.value ? opt.color : 'border-dark-600 bg-dark-900 text-dark-400 hover:bg-dark-600'
              }`}
            >
              {physicalState === opt.value ? <Check className="w-3.5 h-3.5 shrink-0" /> : <span className="text-base">{opt.emoji}</span>}
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Photo (optionnelle) */}
      <div className="card p-4 space-y-2">
        <p className="text-xs uppercase tracking-wide text-dark-400">Photo (optionnelle)</p>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) void handlePhotoCapture(file)
            e.target.value = ''
          }}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploadPhoto.isPending}
          className="w-full h-14 border-2 border-dashed border-dark-600 rounded-xl flex items-center justify-center gap-2 text-dark-400 text-sm hover:border-dark-500 hover:text-dark-300 disabled:opacity-50"
        >
          <Camera className="w-4 h-4" />
          {uploadPhoto.isPending ? 'Envoi...' : 'Prendre une photo'}
        </button>
        {photoUrls.length > 0 && (
          <div className="flex gap-2 flex-wrap">
            {photoUrls.map((url, i) => (
              <img key={i} src={url} alt={`Photo ${i + 1}`} className="w-16 h-16 rounded-lg object-cover border border-dark-600" />
            ))}
          </div>
        )}
        {uploadError && <p className="text-red-400 text-xs">{uploadError}</p>}
      </div>

      {/* Notes */}
      <div className="card p-4 space-y-2">
        <p className="text-xs uppercase tracking-wide text-dark-400">Notes</p>
        <textarea
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Observation, commentaire terrain…"
          className="w-full card px-4 py-2 text-sm focus:outline-none focus:border-primary-500 resize-none"
        />
      </div>

      {/* Alerte dommage conditionnel */}
      {isDamaged && (
        <div className="flex items-start gap-4 p-4 rounded-xl border border-red-500/30 bg-red-500/5">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
          <p className="text-xs text-red-300">
            Dommage detecte. Cet article partira avec l'etat enregistre. Une declaration pourra etre creee au retour.
          </p>
        </div>
      )}

      {/* Navigation */}
      <div className="flex gap-2">
        {index > 0 && (
          <button
            onClick={() => goTo(index - 1)}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-4.5 border border-dark-600 text-dark-300 rounded-xl font-medium text-sm hover:bg-dark-600"
          >
            <ArrowLeft className="w-4 h-4" />
            Précédent
          </button>
        )}
        {index < total - 1 ? (
          <button
            onClick={() => goTo(index + 1)}
            className="flex-[2] flex items-center justify-center gap-2 px-4 py-4.5 bg-primary-500 text-white rounded-xl font-medium text-sm hover:bg-primary-600"
          >
            Suivant
            <ArrowRight className="w-4 h-4" />
          </button>
        ) : (
          <button
            onClick={() => {
              handleSave()
              navigate({ to: '/operations/departure/$reservationId', params: { reservationId } })
            }}
            className="flex-[2] flex items-center justify-center gap-2 px-4 py-4.5 bg-green-600 text-white rounded-xl font-medium text-sm hover:bg-green-700"
          >
            <Check className="w-4 h-4" />
            Terminer vérification
          </button>
        )}
      </div>
    </div>
  )
}
