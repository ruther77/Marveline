import { useEffect, useState } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { ComboboxAsync } from '@shared/components/ui/ComboboxAsync'
import type { ComboboxItem } from '@shared/components/ui/ComboboxAsync'
import { useAddAction } from '@/api/queries/useEvenements'
import { useUsers } from '@/api/queries/admin/useUsers'
import { normalizeError } from '@shared/errors/normalizer'

// Calculé une seule fois au module level — évite une nouvelle Date() à chaque render
const todayStr = new Date().toISOString().slice(0, 10)

const schema = z.object({
  label: z.string().min(2, 'Minimum 2 caractères'),
  assignee_id: z
    .number({ invalid_type_error: 'Responsable requis' })
    .int()
    .positive('Responsable requis'),
  deadline: z
    .string()
    .min(1, 'Échéance obligatoire')
    .refine((v) => v >= todayStr, "La date doit être aujourd'hui ou ultérieure"),
  status: z.enum(['todo', 'in_progress', 'done']).default('todo'),
})

type FormData = z.infer<typeof schema>

const DEFAULT_VALUES: Partial<FormData> = {
  label: '',
  deadline: todayStr,
  status: 'todo',
}

interface Props {
  open: boolean
  onClose: () => void
  evenementId: number
  incidentId: number
}

export function CreateActionPlanModal({ open, onClose, evenementId, incidentId }: Props) {
  const [searchQuery, setSearchQuery] = useState('')

  const { register, handleSubmit, control, reset, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: DEFAULT_VALUES,
  })

  // Charger la liste des users une seule fois (filtrage local)
  const { data: usersData, isLoading: usersLoading } = useUsers({ limit: 50 }, open)

  const userItems: ComboboxItem[] = (usersData?.items ?? [])
    .map((u) => ({ id: u.id, label: u.full_name || u.email }))
    .filter(
      (i) => !searchQuery || i.label.toLowerCase().includes(searchQuery.toLowerCase())
    )

  const addAction = useAddAction(evenementId, incidentId)

  // Reset le formulaire à chaque fermeture
  useEffect(() => {
    if (!open) {
      reset(DEFAULT_VALUES)
      setSearchQuery('')
    }
  }, [open, reset])

  const onSubmit = (data: FormData) => {
    addAction.mutate(
      {
        label: data.label,
        assignee_id: data.assignee_id,
        deadline: data.deadline,
        status: data.status,
      },
      { onSuccess: onClose }
    )
  }

  return (
    <Modal
      isOpen={open}
      onClose={onClose}
      title="Créer un plan d'action"
      size="md"
      footer={
        <ModalFooter
          onCancel={onClose}
          onConfirm={handleSubmit(onSubmit)}
          confirmText="Créer l'action"
          loading={addAction.isPending}
        />
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>

        {/* Erreur mutation */}
        {addAction.error != null && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {normalizeError(addAction.error).message || 'Erreur lors de la création'}
          </div>
        )}

        {/* Action à mener */}
        <div>
          <label className="block text-sm text-dark-400 mb-1">
            Action à mener <span className="text-red-400">*</span>
          </label>
          <input
            {...register('label')}
            type="text"
            className="input"
            placeholder="ex : Contacter le fournisseur, vérifier le stock…"
            autoFocus
          />
          {errors.label && (
            <p className="text-red-400 text-xs mt-1">{errors.label.message}</p>
          )}
        </div>

        {/* Responsable — ComboboxAsync */}
        <div>
          <label className="block text-sm text-dark-400 mb-1">
            Responsable <span className="text-red-400">*</span>
          </label>
          <Controller
            control={control}
            name="assignee_id"
            render={({ field }) => (
              <ComboboxAsync
                value={field.value ?? ''}
                onChange={(id) => field.onChange(id === '' ? undefined : id)}
                items={userItems}
                onSearchChange={setSearchQuery}
                isLoading={usersLoading}
                placeholder="Rechercher un membre de l'équipe…"
              />
            )}
          />
          {errors.assignee_id && (
            <p className="text-red-400 text-xs mt-1">{errors.assignee_id.message}</p>
          )}
        </div>

        {/* Échéance + Statut initial */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-dark-400 mb-1">
              Échéance <span className="text-red-400">*</span>
            </label>
            <input
              {...register('deadline')}
              type="date"
              min={todayStr}
              className="input"
            />
            {errors.deadline && (
              <p className="text-red-400 text-xs mt-1">{errors.deadline.message}</p>
            )}
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">Statut initial</label>
            <select {...register('status')} className="input">
              <option value="todo">À faire</option>
              <option value="in_progress">En cours</option>
              <option value="done">Terminé</option>
            </select>
          </div>
        </div>

      </form>
    </Modal>
  )
}
