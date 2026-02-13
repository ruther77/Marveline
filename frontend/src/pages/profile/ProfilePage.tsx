import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuthStore } from '@/stores/authStore'
import { Loader2, Check } from 'lucide-react'
import { cn } from '@/lib/utils'

const profileSchema = z.object({
  first_name: z.string().min(2, 'Prénom trop court'),
  last_name: z.string().min(2, 'Nom trop court'),
  email: z.string().email('Email invalide'),
})

type ProfileForm = z.infer<typeof profileSchema>

export default function ProfilePage() {
  const { user } = useAuthStore()
  const [success, setSuccess] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      first_name: user?.first_name || '',
      last_name: user?.last_name || '',
      email: user?.email || '',
    },
  })

  const onSubmit = async (data: ProfileForm) => {
    // TODO: Implement profile update API
    console.log('Update profile:', data)
    setSuccess(true)
    setTimeout(() => setSuccess(false), 3000)
  }

  return (
    <div className="max-w-2xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Mon profil</h1>
        <p className="text-dark-400 mt-1">
          Gérez vos informations personnelles
        </p>
      </div>

      {/* Profile Card */}
      <div className="card">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-20 h-20 rounded-full bg-primary-600 flex items-center justify-center text-2xl font-bold">
            {user?.first_name?.[0]}
            {user?.last_name?.[0]}
          </div>
          <div>
            <h2 className="text-xl font-semibold">
              {user?.first_name} {user?.last_name}
            </h2>
            <p className="text-dark-400">{user?.email}</p>
            <div className="flex items-center gap-2 mt-2">
              {user?.is_superuser && (
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-500/10 text-purple-500">
                  Administrateur
                </span>
              )}
              {user?.mfa_enabled && (
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-500">
                  2FA activé
                </span>
              )}
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {success && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm">
              <Check className="w-4 h-4" />
              Profil mis à jour avec succès
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="first_name" className="label">
                Prénom
              </label>
              <input
                id="first_name"
                type="text"
                className={cn('input', errors.first_name && 'input-error')}
                {...register('first_name')}
              />
              {errors.first_name && (
                <p className="mt-1 text-sm text-red-400">
                  {errors.first_name.message}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="last_name" className="label">
                Nom
              </label>
              <input
                id="last_name"
                type="text"
                className={cn('input', errors.last_name && 'input-error')}
                {...register('last_name')}
              />
              {errors.last_name && (
                <p className="mt-1 text-sm text-red-400">
                  {errors.last_name.message}
                </p>
              )}
            </div>
          </div>

          <div>
            <label htmlFor="email" className="label">
              Email
            </label>
            <input
              id="email"
              type="email"
              className={cn('input', errors.email && 'input-error')}
              {...register('email')}
            />
            {errors.email && (
              <p className="mt-1 text-sm text-red-400">{errors.email.message}</p>
            )}
          </div>

          <div className="flex justify-end pt-4">
            <button
              type="submit"
              disabled={isSubmitting || !isDirty}
              className="btn-primary"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  Enregistrement...
                </>
              ) : (
                'Enregistrer les modifications'
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Account Info */}
      <div className="card">
        <h3 className="font-semibold mb-4">Informations du compte</h3>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-dark-400">ID utilisateur</span>
            <span className="font-mono">{user?.id}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-dark-400">Tenant ID</span>
            <span className="font-mono">{user?.tenant_id}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-dark-400">Compte vérifié</span>
            <span className={user?.is_verified ? 'text-green-500' : 'text-yellow-500'}>
              {user?.is_verified ? 'Oui' : 'Non'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
