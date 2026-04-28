import { useState } from 'react'
import { Modal } from '@shared/components/ui'
import { useRescheduleEvenement } from '@/api/queries/useEvenements'
import { normalizeError } from '@shared/errors/normalizer'
import { Calendar, AlertTriangle } from 'lucide-react'
import type { ConflictItem } from '@/types/event'

interface Props {
  open: boolean
  onClose: () => void
  evenementId: number
  evenementName: string
  currentDate: string
}

export function RescheduleModal({ open, onClose, evenementId, evenementName, currentDate }: Props) {
  const [newDate, setNewDate] = useState(currentDate)
  const [softConflicts, setSoftConflicts] = useState<ConflictItem[]>([])
  const [error, setError] = useState<string | null>(null)

  const reschedule = useRescheduleEvenement(evenementId)

  const resetState = () => {
    setSoftConflicts([])
    setError(null)
    setNewDate(currentDate)
  }

  const handleClose = () => { resetState(); onClose() }

  const handleSubmit = (force: boolean) => {
    if (!newDate) return
    setError(null)
    reschedule.mutate({ new_date: newDate, force }, {
      onSuccess: (data) => {
        if (data.conflicts.length > 0 && !force) {
          setSoftConflicts(data.conflicts)
        } else {
          handleClose()
        }
      },
      onError: (err) => {
        setSoftConflicts([])
        setError(normalizeError(err).message || 'Erreur lors de la reprogrammation.')
      },
    })
  }

  const hasConflicts = softConflicts.length > 0

  return (
    <Modal
      isOpen={open}
      onClose={handleClose}
      title="Reprogrammer l'événement"
      footer={
        <div className="flex justify-end gap-4">
          <button onClick={handleClose} className="text-sm text-dark-400 hover:text-dark-50 px-4 py-2">
            Annuler
          </button>
          {hasConflicts ? (
            <>
              <button
                onClick={() => setSoftConflicts([])}
                className="text-sm text-dark-400 hover:text-dark-50 border border-dark-600 px-4 py-2 rounded-lg"
              >
                Changer la date
              </button>
              <button
                onClick={() => handleSubmit(true)}
                disabled={reschedule.isPending}
                className="flex items-center gap-2 bg-amber-700 hover:bg-amber-800 text-white text-sm font-medium px-6 py-2 rounded-lg disabled:opacity-50"
              >
                {reschedule.isPending ? 'Confirmation…' : 'Confirmer malgré les conflits'}
              </button>
            </>
          ) : (
            <button
              onClick={() => handleSubmit(false)}
              disabled={!newDate || newDate === currentDate || reschedule.isPending}
              className="flex items-center gap-2 bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium px-6 py-2 rounded-lg disabled:opacity-50"
            >
              <Calendar className="w-4 h-4" />
              {reschedule.isPending ? 'Reprogrammation…' : 'Reprogrammer'}
            </button>
          )}
        </div>
      }
    >
      <div className="space-y-4">
        <div className="bg-dark-900/50 rounded-lg px-4 py-4">
          <p className="text-sm font-medium">{evenementName}</p>
          <p className="text-dark-400 text-xs mt-0.5">
            Date actuelle : <span className="text-white">{new Date(currentDate).toLocaleDateString('fr-FR')}</span>
          </p>
        </div>

        {!hasConflicts && (
          <div>
            <label className="block text-sm text-dark-400 mb-1">Nouvelle date <span className="text-red-400">*</span></label>
            <input
              type="date"
              value={newDate}
              onChange={(e) => setNewDate(e.target.value)}
              className="input"
            />
          </div>
        )}

        {hasConflicts && (
          <div className="space-y-2">
            <p className="text-sm font-medium text-amber-400 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              Conflits détectés pour le {new Date(newDate).toLocaleDateString('fr-FR')}
            </p>
            {softConflicts.map((c, i) => (
              <div key={i} className="bg-amber-900/20 border border-amber-700/30 rounded-lg px-4 py-3 text-sm text-amber-300">
                {c.message}
              </div>
            ))}
            <p className="text-xs text-dark-400">Vous pouvez forcer la reprogrammation ou choisir une autre date.</p>
          </div>
        )}

        {error && <p className="text-red-400 text-sm">{error}</p>}
      </div>
    </Modal>
  )
}
