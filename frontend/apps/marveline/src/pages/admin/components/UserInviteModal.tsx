import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Mail, CheckCircle } from 'lucide-react'
import { useInviteUser } from '@/api/queries'
import { Modal } from '@shared/components/ui/Modal'
import { ActionError } from '@shared/components/ui/ActionError'
import { normalizeError } from '@shared/errors/normalizer'

const schema = z.object({
  email: z.string().email('Email invalide'),
  role: z.string().default('staff'),
  first_name: z.string().optional(),
  last_name: z.string().optional(),
})

type FormData = z.infer<typeof schema>

interface UserInviteModalProps {
  isOpen: boolean
  onClose: () => void
}

export function UserInviteModal({ isOpen, onClose }: UserInviteModalProps) {
  const inviteUser = useInviteUser()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { role: 'staff' },
  })

  const handleClose = () => {
    reset()
    inviteUser.reset()
    onClose()
  }

  const onSubmit = (data: FormData) => {
    inviteUser.mutate(
      {
        email: data.email,
        role: data.role,
        first_name: data.first_name || undefined,
        last_name: data.last_name || undefined,
      },
      {
        onSuccess: () => {
          // Garder le modal ouvert pour afficher la confirmation
        },
      }
    )
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Inviter un utilisateur"
    >
      {inviteUser.isSuccess ? (
        <div className="py-6 text-center space-y-4">
          <CheckCircle className="w-12 h-12 text-green-500 mx-auto" />
          <p className="font-medium">Invitation envoyée</p>
          <p className="text-sm text-dark-400">
            {inviteUser.data?.invite_sent
              ? `Un email d'invitation a été envoyé à ${inviteUser.data.email}.`
              : `Le compte a été créé pour ${inviteUser.data?.email}. L'email d'invitation n'a pas pu être envoyé.`}
          </p>
          <div className="flex justify-end mt-4">
            <button className="btn-primary" onClick={handleClose}>
              Fermer
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              Email <span className="text-red-400">*</span>
            </label>
            <input
              {...register('email')}
              type="email"
              className="input"
              placeholder="utilisateur@exemple.com"
              autoFocus
            />
            {errors.email && (
              <p className="text-red-400 text-xs mt-1">{errors.email.message}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Prénom</label>
              <input
                {...register('first_name')}
                type="text"
                className="input"
                placeholder="Optionnel"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Nom</label>
              <input
                {...register('last_name')}
                type="text"
                className="input"
                placeholder="Optionnel"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Rôle</label>
            <select {...register('role')} className="input">
              <option value="staff">Staff</option>
              <option value="manager">Manager</option>
              <option value="admin">Administrateur</option>
            </select>
          </div>

          <ActionError
            message={inviteUser.isError ? (normalizeError(inviteUser.error).message || "Erreur lors de l'invitation") : null}
            onDismiss={() => inviteUser.reset()}
          />

          <div className="flex justify-end gap-4 mt-2">
            <button
              type="button"
              className="btn-secondary"
              onClick={handleClose}
              disabled={inviteUser.isPending}
            >
              Annuler
            </button>
            <button
              type="submit"
              className="btn-primary flex items-center gap-2"
              disabled={inviteUser.isPending}
            >
              <Mail className="w-4 h-4" />
              {inviteUser.isPending ? 'Envoi...' : "Envoyer l'invitation"}
            </button>
          </div>
        </form>
      )}
    </Modal>
  )
}
