import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useScheduleRelance } from '@/api/queries'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { normalizeError } from '@shared/errors/normalizer'
import type { CustomerHistoryInvoice } from '@/types/customer'

const MIN_SCHEDULE_MS = 60 * 60 * 1000 // 1h dans le futur minimum

const scheduleSchema = z.object({
  invoice_id: z.number({ invalid_type_error: 'Sélectionnez une facture' }).min(1, 'Sélectionnez une facture'),
  scheduled_at: z.string().min(1, 'Date et heure requises').refine((v) => {
    return new Date(v).getTime() > Date.now() + MIN_SCHEDULE_MS
  }, 'La date doit être dans au moins 1 heure'),
  channel: z.enum(['email', 'sms', 'push']).default('email'),
  message: z.string().max(500, 'Maximum 500 caractères').optional().default(''),
})

type ScheduleFormData = z.infer<typeof scheduleSchema>

interface ScheduleRelanceModalProps {
  isOpen: boolean
  onClose: () => void
  invoices: CustomerHistoryInvoice[]
}

const CHANNEL_LABELS: Record<string, string> = {
  email: 'Email',
  sms:   'SMS',
  push:  'Notification push',
}

function getDefaultScheduledAt(): string {
  const d = new Date(Date.now() + 24 * 60 * 60 * 1000) // demain
  d.setMinutes(0, 0, 0)
  // format datetime-local : YYYY-MM-DDTHH:mm
  return d.toISOString().slice(0, 16)
}

export function ScheduleRelanceModal({ isOpen, onClose, invoices }: ScheduleRelanceModalProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ScheduleFormData>({
    resolver: zodResolver(scheduleSchema),
    defaultValues: {
      invoice_id:   0,
      scheduled_at: getDefaultScheduledAt(),
      channel:      'email',
      message:      '',
    },
  })

  useEffect(() => {
    if (isOpen) {
      reset({
        invoice_id:   invoices.length === 1 ? invoices[0].id : 0,
        scheduled_at: getDefaultScheduledAt(),
        channel:      'email',
        message:      '',
      })
    }
  }, [isOpen, invoices, reset])

  const scheduleMutation = useScheduleRelance()

  const onSubmit = (data: ScheduleFormData) => {
    scheduleMutation.mutate(
      {
        invoice_id:   data.invoice_id,
        scheduled_at: new Date(data.scheduled_at).toISOString(),
        channel:      data.channel,
        message:      data.message || undefined,
      },
      { onSuccess: onClose },
    )
  }

  const error = scheduleMutation.error

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Planifier une relance"
      size="md"
      footer={
        <ModalFooter
          onCancel={onClose}
          onConfirm={handleSubmit(onSubmit)}
          cancelText="Annuler"
          confirmText="Planifier"
          loading={scheduleMutation.isPending}
        />
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
        {error != null && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {normalizeError(error).message || 'Une erreur est survenue'}
          </div>
        )}

        {/* Facture */}
        <div>
          <label htmlFor="invoice_id" className="block text-sm text-dark-400 mb-1">
            Facture <span className="text-red-400">*</span>
          </label>
          {invoices.length === 0 ? (
            <p className="text-sm text-dark-500 italic">Aucune facture disponible pour ce client.</p>
          ) : (
            <select
              id="invoice_id"
              {...register('invoice_id', { valueAsNumber: true })}
              className="input"
            >
              <option value={0}>Sélectionnez une facture</option>
              {invoices.map((inv) => (
                <option key={inv.id} value={inv.id}>
                  {inv.invoice_number} — {inv.status}
                </option>
              ))}
            </select>
          )}
          {errors.invoice_id && (
            <p className="text-red-400 text-xs mt-1">{errors.invoice_id.message}</p>
          )}
        </div>

        {/* Date planifiée */}
        <div>
          <label htmlFor="scheduled_at" className="block text-sm text-dark-400 mb-1">
            Date et heure d'envoi <span className="text-red-400">*</span>
          </label>
          <input
            id="scheduled_at"
            type="datetime-local"
            {...register('scheduled_at')}
            className="input"
          />
          {errors.scheduled_at && (
            <p className="text-red-400 text-xs mt-1">{errors.scheduled_at.message}</p>
          )}
        </div>

        {/* Canal */}
        <div>
          <label htmlFor="channel" className="block text-sm text-dark-400 mb-1">Canal</label>
          <select id="channel" {...register('channel')} className="input">
            {Object.entries(CHANNEL_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        {/* Message optionnel */}
        <div>
          <label htmlFor="message" className="block text-sm text-dark-400 mb-1">
            Message personnalisé
            <span className="ml-1 text-xs text-dark-500">(optionnel)</span>
          </label>
          <textarea
            id="message"
            {...register('message')}
            rows={3}
            className="input resize-none"
            placeholder="Bonjour, nous vous relançons concernant votre facture…"
          />
          {errors.message && (
            <p className="text-red-400 text-xs mt-1">{errors.message.message}</p>
          )}
        </div>
      </form>
    </Modal>
  )
}
