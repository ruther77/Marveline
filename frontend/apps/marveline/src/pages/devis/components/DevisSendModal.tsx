import { useState } from 'react'
import { Modal } from '@shared/components/ui'
import { useDevisMutations } from '@/api/queries/useDevis'
import { normalizeError } from '@shared/errors/normalizer'

interface Props {
  devisId: number
  reference: string
  open: boolean
  onClose: () => void
}

export function DevisSendModal({ devisId, reference, open, onClose }: Props) {
  const [error, setError] = useState<string | null>(null)
  const { send } = useDevisMutations()

  const handleConfirm = () => {
    setError(null)
    send.mutate(devisId, {
      onSuccess: () => onClose(),
      onError: (err) => {
        setError(
          normalizeError(err).message ||
            'Erreur lors de l\'envoi du devis.'
        )
      },
    })
  }

  return (
    <Modal
      isOpen={open}
      onClose={onClose}
      title="Envoyer le devis"
      footer={
        <div className="flex justify-end gap-4">
          <button onClick={onClose} className="text-sm text-dark-400 hover:text-dark-50 px-4 py-2">
            Annuler
          </button>
          <button
            onClick={handleConfirm}
            disabled={send.isPending}
            className="bg-gold-500 hover:bg-gold-600 text-dark-900 text-sm font-medium px-6 py-2 rounded-lg disabled:opacity-60"
          >
            {send.isPending ? 'Envoi…' : 'Envoyer'}
          </button>
        </div>
      }
    >
      <p className="text-dark-300 text-sm">
        Le devis <span className="font-medium">{reference}</span> sera marqué comme{' '}
        <span className="text-blue-400 font-medium">Envoyé</span>. Le client pourra ensuite
        l'accepter ou le refuser.
      </p>
      {error && <p className="text-red-400 text-sm mt-4">{error}</p>}
    </Modal>
  )
}
