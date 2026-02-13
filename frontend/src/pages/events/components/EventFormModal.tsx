import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { eventsApi } from '@/api/events'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import type { Event, CreateEventRequest, UpdateEventRequest, EventType, EventStatus } from '@/types/event'

const eventSchema = z.object({
  customer_name: z.string().min(1, 'Nom requis'),
  customer_email: z.string().email('Email invalide').optional().or(z.literal('')),
  customer_phone: z.string().optional(),
  customer_address: z.string().optional(),
  event_type: z.enum(['wedding', 'baptism', 'birthday', 'seminar', 'other']),
  event_name: z.string().optional(),
  event_date: z.string().min(1, 'Date requise'),
  event_location: z.string().optional(),
  guest_count: z.number().min(0).optional().nullable(),
  rental_start_date: z.string().min(1, 'Date de début requise'),
  rental_end_date: z.string().min(1, 'Date de fin requise'),
  notes: z.string().optional(),
  internal_notes: z.string().optional(),
})

type FormData = z.infer<typeof eventSchema>

interface EventFormModalProps {
  isOpen: boolean
  onClose: () => void
  event?: Partial<Event> | null
  mode: 'create' | 'edit'
}

export function EventFormModal({ isOpen, onClose, event, mode }: EventFormModalProps) {
  const queryClient = useQueryClient()
  const isEdit = mode === 'edit'

  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(eventSchema),
  })

  useEffect(() => {
    if (isOpen && event) {
      reset({
        customer_name: event.customer_name || '',
        customer_email: event.customer_email || '',
        customer_phone: event.customer_phone || '',
        customer_address: event.customer_address || '',
        event_type: event.event_type || 'other',
        event_name: event.event_name || '',
        event_date: event.event_date?.split('T')[0] || '',
        event_location: event.event_location || '',
        guest_count: event.guest_count || null,
        rental_start_date: event.rental_start_date?.split('T')[0] || '',
        rental_end_date: event.rental_end_date?.split('T')[0] || '',
        notes: event.notes || '',
        internal_notes: event.internal_notes || '',
      })
    } else if (isOpen) {
      reset({
        customer_name: '',
        customer_email: '',
        customer_phone: '',
        event_type: 'wedding',
        event_date: '',
        rental_start_date: '',
        rental_end_date: '',
      })
    }
  }, [isOpen, event, reset])

  const createMutation = useMutation({
    mutationFn: (data: CreateEventRequest) => eventsApi.createEvent(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] })
      queryClient.invalidateQueries({ queryKey: ['events-stats'] })
      onClose()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateEventRequest }) =>
      eventsApi.updateEvent(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] })
      onClose()
    },
  })

  const onSubmit = (data: FormData) => {
    const cleanData = {
      ...data,
      items: [], // Empty items initially
    }

    if (isEdit && event?.id) {
      updateMutation.mutate({ id: event.id, data: cleanData as UpdateEventRequest })
    } else {
      createMutation.mutate(cleanData as CreateEventRequest)
    }
  }

  const isLoading = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? "Modifier l'événement" : 'Nouvel événement'}
      size="lg"
      footer={
        <ModalFooter
          onCancel={onClose}
          onConfirm={handleSubmit(onSubmit)}
          cancelText="Annuler"
          confirmText={isEdit ? 'Enregistrer' : 'Créer'}
          loading={isLoading}
        />
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
        {error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {(error as Error).message || 'Une erreur est survenue'}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Nom du client *
            </label>
            <input {...register('customer_name')} type="text" className="input w-full" />
            {errors.customer_name && <p className="text-red-500 text-sm mt-1">{errors.customer_name.message}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">Email</label>
            <input {...register('customer_email')} type="email" className="input w-full" />
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">Téléphone</label>
            <input {...register('customer_phone')} type="tel" className="input w-full" />
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">Type d'événement *</label>
            <select {...register('event_type')} className="input w-full">
              <option value="wedding">Mariage</option>
              <option value="baptism">Baptême</option>
              <option value="birthday">Anniversaire</option>
              <option value="seminar">Séminaire</option>
              <option value="other">Autre</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">Date de l'événement *</label>
            <input {...register('event_date')} type="date" className="input w-full" />
            {errors.event_date && <p className="text-red-500 text-sm mt-1">{errors.event_date.message}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">Début location *</label>
            <input {...register('rental_start_date')} type="date" className="input w-full" />
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">Fin location *</label>
            <input {...register('rental_end_date')} type="date" className="input w-full" />
          </div>
        </div>
      </form>
    </Modal>
  )
}
