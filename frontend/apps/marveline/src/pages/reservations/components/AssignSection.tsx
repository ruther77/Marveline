import { useEffect, useState } from 'react'
import { normalizeError } from '@shared/errors/normalizer'
import { ActionError } from '@shared/components/ui/ActionError'
import { useGlobalUsers, useAssignReservationUser } from '@/api/queries'
import { useAuthStore } from '@/stores/authStore'

interface AssignSectionProps {
  reservationId: number
  assignedUserId: number | null
  status: string
}

export function AssignSection({ reservationId, assignedUserId, status }: AssignSectionProps) {
  const { user: currentUser } = useAuthStore()
  const { data: usersData, error: usersError } = useGlobalUsers()
  const assignMutation = useAssignReservationUser()
  const [selectedAssignee, setSelectedAssignee] = useState('')

  const users = usersData?.items ?? []
  const assigneeName = assignedUserId
    ? (users.find((u) => u.id === assignedUserId)?.full_name ?? `#${assignedUserId}`)
    : 'Non affectée'

  useEffect(() => {
    setSelectedAssignee(assignedUserId ? String(assignedUserId) : '')
  }, [assignedUserId])

  if (status === 'cancelled' || status === 'completed') return null

  return (
    <div className="p-4 border border-dark-600 rounded-lg bg-dark-900/40 space-y-2">
      <ActionError
        message={assignMutation.error ? normalizeError(assignMutation.error).message || "Erreur lors de l'affectation" : null}
        onDismiss={() => assignMutation.reset()}
      />

      <div className="flex items-center justify-between gap-4">
        <span className="text-sm text-dark-400">Responsable</span>
        <span className="text-sm font-medium">{assigneeName}</span>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <select
          value={selectedAssignee}
          onChange={(e) => setSelectedAssignee(e.target.value)}
          className="input text-sm min-w-[180px]"
        >
          <option value="">Non affectée</option>
          {users.map((u) => (
            <option key={u.id} value={String(u.id)}>
              {u.full_name || u.email}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => assignMutation.mutate({ reservationId, userId: selectedAssignee ? Number(selectedAssignee) : null })}
          disabled={assignMutation.isPending}
          className="btn-secondary btn-sm"
        >
          {assignMutation.isPending ? 'Affectation…' : 'Affecter'}
        </button>
        {currentUser?.id && (
          <button
            type="button"
            onClick={() => assignMutation.mutate({ reservationId, userId: currentUser.id })}
            disabled={assignMutation.isPending}
            className="btn-secondary btn-sm"
          >
            M&apos;affecter
          </button>
        )}
      </div>

      {usersError && (
        <p className="text-xs text-amber-400">
          Liste utilisateurs indisponible (scope `users:read` requis).
        </p>
      )}
    </div>
  )
}
