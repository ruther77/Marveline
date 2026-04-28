import { useState } from 'react'
import { Modal } from '@shared/components/ui'
import { useDeclareIncident } from '@/api/queries/useEvenements'
import { normalizeError } from '@shared/errors/normalizer'
import { useUsers } from '@/api/queries/useAdmin'

interface Props {
  open: boolean
  onClose: () => void
  evenementId: number
  onSuccess?: () => void
}

const SEVERITY_OPTIONS = [
  { value: 'low', label: 'Faible', color: 'text-yellow-400', sla: '72h' },
  { value: 'medium', label: 'Modéré', color: 'text-orange-400', sla: '24h' },
  { value: 'high', label: 'Élevé', color: 'text-red-400', sla: '4h' },
  { value: 'critical', label: 'Critique', color: 'text-red-600', sla: '1h' },
] as const

type Severity = (typeof SEVERITY_OPTIONS)[number]['value']

export function DeclareIncidentModal({ open, onClose, evenementId, onSuccess }: Props) {
  const [description, setDescription] = useState('')
  const [severity, setSeverity] = useState<Severity>('medium')
  const [ownerId, setOwnerId] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  const declare = useDeclareIncident(evenementId)
  const { data: usersData } = useUsers({ limit: 100 })
  const users = usersData?.items ?? []

  const handleSubmit = () => {
    if (!description.trim()) { setError('La description est obligatoire'); return }
    setError(null)

    declare.mutate(
      { description: description.trim(), severity, owner_id: ownerId ? Number(ownerId) : undefined },
      {
        onSuccess: () => {
          onClose()
          setDescription('')
          setSeverity('medium')
          setOwnerId('')
          onSuccess?.()
        },
        onError: (err) => {
          setError(
            normalizeError(err).message || 'Erreur lors de la déclaration.'
          )
        },
      }
    )
  }

  const handleClose = () => { setError(null); setOwnerId(''); onClose() }

  const currentSla = SEVERITY_OPTIONS.find((s) => s.value === severity)?.sla ?? '24h'

  return (
    <Modal
      isOpen={open}
      onClose={handleClose}
      title="Déclarer un incident"
      footer={
        <div className="flex justify-end gap-4">
          <button onClick={handleClose} className="text-sm text-dark-400 hover:text-dark-50 px-4 py-2">
            Annuler
          </button>
          <button
            onClick={handleSubmit}
            disabled={!description.trim() || declare.isPending}
            className="bg-red-700 hover:bg-red-800 text-white text-sm font-medium px-6 py-2 rounded-lg disabled:opacity-50"
          >
            {declare.isPending ? 'Déclaration…' : 'Déclarer'}
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-sm text-dark-400 mb-2">Gravité</label>
          <div className="grid grid-cols-2 gap-2">
            {SEVERITY_OPTIONS.map((s) => (
              <button
                key={s.value}
                onClick={() => setSeverity(s.value)}
                className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                  severity === s.value
                    ? 'bg-dark-600 border-gold-500 text-white'
                    : 'bg-dark-900 border-dark-600 text-dark-400 hover:border-dark-500'
                }`}
              >
                <span className={s.color}>{s.label}</span>
              </button>
            ))}
          </div>
          <p className="text-xs text-dark-400 mt-1">SLA : résolution attendue sous <span className="text-gold-400 font-medium">{currentSla}</span></p>
        </div>

        <div>
          <label className="block text-sm text-dark-400 mb-1">Description *</label>
          <textarea
            rows={4}
            placeholder="Décrivez l'incident constaté…"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm text-dark-400 mb-1">Responsable <span className="text-dark-500">(optionnel)</span></label>
          <select
            value={ownerId}
            onChange={(e) => setOwnerId(e.target.value)}
            className="input"
          >
            <option value="">— Non assigné —</option>
            {users.map((u) => (
              <option key={u.id} value={String(u.id)}>
                {u.first_name || u.last_name ? `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim() : u.email}
              </option>
            ))}
          </select>
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}
      </div>
    </Modal>
  )
}
