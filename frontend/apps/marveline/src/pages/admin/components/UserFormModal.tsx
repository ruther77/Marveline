import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useCreateUser, useUpdateUser } from '@/api/queries';
import { Modal, ModalFooter } from '@shared/components/ui/Modal';
import { ActionError } from '@shared/components/ui/ActionError';
import { normalizeError } from '@shared/errors/normalizer';
import type { User, UserCreate, UserUpdate } from '@/types';

// Validation schemas
const createUserSchema = z.object({
  email: z.string().email('Email invalide'),
  password: z.string().min(8, 'Minimum 8 caracteres'),
  first_name: z.string().min(1, 'Prénom requis'),
  last_name: z.string().min(1, 'Nom requis'),
  is_active: z.boolean().default(true),
  role: z.string().default('staff'),
}).transform((data) => ({
  ...data,
  // Backward compat: "admin" → "tenant_admin" (IAM v2)
  role: data.role === 'admin' ? 'tenant_admin' : data.role,
}));

const updateUserSchema = z.object({
  email: z.string().email('Email invalide').optional(),
  password: z.string().min(8, 'Minimum 8 caracteres').optional().or(z.literal('')),
  first_name: z.string().min(1, 'Prénom requis').optional(),
  last_name: z.string().min(1, 'Nom requis').optional(),
  is_active: z.boolean().optional(),
  role: z.string().optional(),
});

type CreateFormData = z.infer<typeof createUserSchema>;
type UpdateFormData = z.infer<typeof updateUserSchema>;

interface UserFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  user?: User | null;
}

export function UserFormModal({ isOpen, onClose, user }: UserFormModalProps) {
  const isEdit = !!user;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateFormData | UpdateFormData>({
    resolver: zodResolver(isEdit ? updateUserSchema : createUserSchema),
    defaultValues: {
      email: '',
      password: '',
      first_name: '',
      last_name: '',
      is_active: true,
      role: 'staff',
    },
  });

  // Reset form when user changes or modal opens
  useEffect(() => {
    if (isOpen) {
      if (user) {
        reset({
          email: user.email,
          password: '',
          first_name: user.first_name || '',
          last_name: user.last_name || '',
          is_active: user.is_active,
          role: user.role || 'staff',
        });
      } else {
        reset({
          email: '',
          password: '',
          first_name: '',
          last_name: '',
          is_active: true,
          role: 'staff',
        });
      }
    }
  }, [isOpen, user, reset]);

  const createMutation = useCreateUser()
  const updateMutation = useUpdateUser()

  const onSubmit = (data: CreateFormData | UpdateFormData) => {
    if (isEdit && user) {
      // Remove password field and filter out empty strings
      const { password, ...rest } = data as UpdateFormData;
      // Filter out empty strings and undefined values (but keep false for booleans)
      const updateData = Object.fromEntries(
        Object.entries(rest).filter(([_, value]) => {
          if (typeof value === 'boolean') return true; // Keep all boolean values
          return value !== '' && value !== undefined && value !== null;
        })
      );
      updateMutation.mutate({ id: user.id, data: updateData as UserUpdate }, { onSuccess: onClose });
    } else {
      createMutation.mutate(data as UserCreate, { onSuccess: onClose });
    }
  };

  const isLoading = createMutation.isPending || updateMutation.isPending;
  const error = createMutation.error || updateMutation.error;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier utilisateur' : 'Nouvel utilisateur'}
      size="md"
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
        <ActionError
          message={error ? (normalizeError(error).message || 'Une erreur est survenue') : null}
          onDismiss={() => { createMutation.reset(); updateMutation.reset() }}
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-dark-400 mb-1">Prénom</label>
            <input
              {...register('first_name')}
              type="text"
              className="input"
              placeholder="Jean"
            />
            {errors.first_name && (
              <p className="text-danger text-xs mt-1">{errors.first_name.message}</p>
            )}
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">Nom</label>
            <input
              {...register('last_name')}
              type="text"
              className="input"
              placeholder="Dupont"
            />
            {errors.last_name && (
              <p className="text-danger text-xs mt-1">{errors.last_name.message}</p>
            )}
          </div>
        </div>

        <div>
          <label className="block text-sm text-dark-400 mb-1">Email</label>
          <input
            {...register('email')}
            type="email"
            className="input"
            placeholder="jean.dupont@exemple.com"
          />
          {errors.email && (
            <p className="text-danger text-xs mt-1">{errors.email.message}</p>
          )}
        </div>

        <div>
          <label className="block text-sm text-dark-400 mb-1">
            Mot de passe {isEdit && <span className="normal-case font-normal">(laisser vide pour ne pas modifier)</span>}
          </label>
          <input
            {...register('password')}
            type="password"
            className="input"
            placeholder="••••••••"
          />
          {errors.password && (
            <p className="text-danger text-xs mt-1">{errors.password.message}</p>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
          <div>
            <label className="block text-sm text-dark-400 mb-1">Rôle</label>
            <select
              {...register('role')}
              className="input"
            >
              <option value="staff">Staff</option>
              <option value="manager">Manager</option>
              <option value="tenant_admin">Administrateur</option>
            </select>
          </div>
          <div className="flex items-center min-h-[44px] mt-4">
            <label className="flex items-center gap-4 cursor-pointer">
              <input
                {...register('is_active')}
                type="checkbox"
                className="w-4 h-4 rounded text-primary-400 focus:ring-primary-500"
              />
              <span className="text-sm">Compte actif</span>
            </label>
          </div>
        </div>
      </form>
    </Modal>
  );
}
