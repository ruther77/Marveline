import { useState } from 'react'
import { ClipboardList, Check } from 'lucide-react'
import { usePreCheckItems, useUpdatePreCheckItem, useCompletePreCheck, useCreatePreCheckItem } from '@/api/queries'
import { ActionError } from '@shared/components/ui/ActionError'
import { normalizeError } from '@shared/errors/normalizer'
import { cn } from '@/lib/utils'
import type { ReservationDetail } from '@/types/reservation'

interface Props {
  reservation: ReservationDetail
  hideValidateButton?: boolean
}

export function PreCheckSection({ reservation, hideValidateButton = false }: Props) {
  const { data: preCheckItems = [] } = usePreCheckItems(reservation.id)
  const updatePreCheckMutation = useUpdatePreCheckItem()
  const completePreCheckMutation = useCompletePreCheck()
  const createPreCheckMutation = useCreatePreCheckItem()

  const [newPreCheckLabel, setNewPreCheckLabel] = useState('')

  if (preCheckItems.length === 0 && !['pre_check', 'confirmed'].includes(reservation.status)) return null

  return (
    <div className="border-t border-dark-600 pt-4 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-medium flex items-center gap-2">
          <ClipboardList className="w-4 h-4" />
          Pre-check ({preCheckItems.filter((i) => i.checked).length}/{preCheckItems.length})
        </h3>
        {!hideValidateButton && ['pre_check', 'confirmed'].includes(reservation.status) && preCheckItems.every((i) => i.checked) && preCheckItems.length > 0 && (
          <>
            <button
              onClick={() => completePreCheckMutation.mutate(reservation.id)}
              disabled={completePreCheckMutation.isPending}
              className="btn-primary btn-sm flex items-center gap-1"
            >
              <Check className="w-3 h-3" />
              {completePreCheckMutation.isPending ? 'Validation...' : 'Valider pre-check'}
            </button>
            <ActionError
              message={completePreCheckMutation.error ? normalizeError(completePreCheckMutation.error).message || 'Erreur validation pre-check' : null}
              onDismiss={() => completePreCheckMutation.reset()}
            />
          </>
        )}
      </div>

      {preCheckItems.length === 0 ? (
        <p className="text-sm text-dark-400">Aucun item de pre-check.</p>
      ) : (
        <div className="space-y-1">
          {preCheckItems.map((item) => (
            <label key={item.id} className="flex items-center gap-4 p-2 rounded-lg hover:bg-dark-900 cursor-pointer">
              <input
                type="checkbox"
                checked={item.checked}
                onChange={(e) => updatePreCheckMutation.mutate({
                  reservationId: reservation.id,
                  itemId: item.id,
                  checked: e.target.checked,
                })}
                className="rounded border-dark-600"
              />
              <span className={cn('text-sm', item.checked ? 'line-through text-dark-500' : 'text-dark-200')}>
                {item.label}
              </span>
              <span className="ml-auto text-xs text-dark-500">{item.type}</span>
            </label>
          ))}
        </div>
      )}

      {['pre_check', 'confirmed'].includes(reservation.status) && (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            const label = newPreCheckLabel.trim()
            if (!label) return
            createPreCheckMutation.mutate(
              { reservationId: reservation.id, data: { label, type: 'custom' } },
              { onSuccess: () => setNewPreCheckLabel('') },
            )
          }}
          className="flex items-center gap-2 pt-1"
        >
          <input
            type="text"
            value={newPreCheckLabel}
            onChange={(e) => setNewPreCheckLabel(e.target.value)}
            placeholder="Nouvel item..."
            className="input text-sm py-1"
          />
          <button
            type="submit"
            disabled={!newPreCheckLabel.trim() || createPreCheckMutation.isPending}
            className="btn-secondary btn-sm"
          >
            {createPreCheckMutation.isPending ? '...' : 'Ajouter'}
          </button>
        </form>
      )}
    </div>
  )
}
