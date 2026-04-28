import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Modal, Button } from '@shared/components/ui'
import { FileUpload } from '@shared/components/ui'
import { useDeclareCasse, useUploadDamagePhoto } from '@/api/queries/useOperations'
import type { DamageSeverity, DamageCategory } from '@/types/operations'
import { normalizeError } from '@shared/errors/normalizer'

interface DeclaredDamage {
  productId: number
  description: string
  severity: DamageSeverity
  estimatedCostCents: number
}

interface Props {
  open: boolean
  onClose: () => void
  reservationId: number
  products: { id: number; name: string }[]
  onDeclared?: (damage: DeclaredDamage) => void
}

const SEVERITY_OPTIONS: { value: DamageSeverity; label: string; color: string }[] = [
  { value: 'minor', label: 'Mineur', color: 'text-yellow-400' },
  { value: 'moderate', label: 'Modéré', color: 'text-orange-400' },
  { value: 'major', label: 'Majeur', color: 'text-red-400' },
  { value: 'total_loss', label: 'Perte totale', color: 'text-red-600' },
]

const CATEGORY_OPTIONS: { value: DamageCategory; label: string }[] = [
  { value: 'scratch', label: 'Rayure / éraflure' },
  { value: 'break', label: 'Casse' },
  { value: 'missing', label: 'Manquant' },
  { value: 'malfunction', label: 'Dysfonctionnement' },
  { value: 'other', label: 'Autre' },
]

export function DamageDeclarationModal({ open, onClose, reservationId, products, onDeclared }: Props) {
  const [productId, setProductId] = useState<number | ''>('')
  const [description, setDescription] = useState('')
  const [severity, setSeverity] = useState<DamageSeverity>('minor')
  const [category, setCategory] = useState<DamageCategory>('scratch')
  const [costEuros, setCostEuros] = useState('')
  const [photos, setPhotos] = useState<File[]>([])
  const [error, setError] = useState<string | null>(null)

  const declareCasse = useDeclareCasse()
  const uploadDamagePhoto = useUploadDamagePhoto()

  const handleSubmit = async () => {
    if (!productId || !description.trim()) return
    setError(null)

    const estimated_cost_cents = costEuros
      ? Math.round(parseFloat(costEuros) * 100)
      : 0

    let photo_urls: string[] = []
    if (photos.length > 0) {
      try {
        const uploads = await Promise.all(photos.map((f) => uploadDamagePhoto.mutateAsync(f)))
        photo_urls = uploads.map((r) => r.url)
      } catch {
        setError('Erreur lors de l\'envoi des photos. Réessayez.')
        return
      }
    }

    declareCasse.mutate(
      {
        reservationId,
        payload: {
          damage_type_name: category,
          description: description.trim(),
          fee_cents: estimated_cost_cents,
          product_id: productId as number,
          severity,
          photo_urls,
        },
      },
      {
        onSuccess: () => {
          onDeclared?.({
            productId: productId as number,
            description: description.trim(),
            severity,
            estimatedCostCents: estimated_cost_cents,
          })
          onClose()
          setProductId('')
          setDescription('')
          setSeverity('minor')
          setCategory('scratch')
          setCostEuros('')
          setPhotos([])
        },
        onError: (err) => {
          setError(
            normalizeError(err).message || 'Erreur lors de la déclaration.',
          )
        },
      },
    )
  }

  return (
    <Modal
      isOpen={open}
      onClose={onClose}
      title="Déclarer un dommage"
      size="lg"
      footer={
        <div className="flex justify-end gap-4">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Annuler
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => { void handleSubmit() }}
            disabled={!productId || !description.trim()}
            loading={declareCasse.isPending || uploadDamagePhoto.isPending}
            leftIcon={<AlertTriangle className="w-4 h-4" />}
          >
            Déclarer
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-sm text-dark-400 mb-1">Article *</label>
          <select
            value={productId}
            onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : '')}
            className="input w-full"
          >
            <option value="">Sélectionner un article…</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-dark-400 mb-1">Catégorie</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as DamageCategory)}
              className="input w-full"
            >
              {CATEGORY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">Gravité</label>
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value as DamageSeverity)}
              className="input w-full"
            >
              {SEVERITY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm text-dark-400 mb-1">Description *</label>
          <textarea
            rows={3}
            placeholder="Décrivez le dommage constaté…"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="input w-full"
          />
        </div>

        <div>
          <label className="block text-sm text-dark-400 mb-1">Coût estimé (€)</label>
          <input
            type="number"
            step="0.01"
            min={0}
            placeholder="0.00"
            value={costEuros}
            onChange={(e) => setCostEuros(e.target.value)}
            className="input w-full"
          />
        </div>

        <div>
          <FileUpload
            label="Photos (optionnel)"
            accept="image/*"
            multiple
            maxFiles={5}
            value={photos as never}
            onChange={(files) => setPhotos(files)}
          />
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}
      </div>
    </Modal>
  )
}
