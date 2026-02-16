import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '@/api/admin';
import { Modal, ModalFooter } from '@/components/ui/Modal';
import type { User, UserCreate, UserUpdate } from '@/types';

// Validation schemas
const createUserSchema = z.object({
  email: z.string().email('Email invalide'),
  password: z.string().min(8, 'Minimum 8 caracteres'),
  first_name: z.string().min(1, 'Prenom requis'),
  last_name: z.string().min(1, 'Nom requis'),
  is_active: z.boolean().default(true),
  role: z.string().default('staff'),
});

const updateUserSchema = z.object({
  email: z.string().email('Email invalide').optional(),
  password: z.string().min(8, 'Minimum 8 caracteres').optional().or(z.literal('')),
  first_name: z.string().min(1, 'Prenom requis').optional(),
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
  const queryClient = useQueryClient();
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

  const createMutation = useMutation({
    mutationFn: (data: UserCreate) => adminApi.createUser(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      onClose();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: UserUpdate }) =>
      adminApi.updateUser(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      onClose();
    },
  });

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
      updateMutation.mutate({ id: user.id, data: updateData as UserUpdate });
    } else {
      createMutation.mutate(data as UserCreate);
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
          confirmText={isEdit ? 'Enregistrer' : 'Creer'}
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
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Prenom
            </label>
            <input
              {...register('first_name')}
              type="text"
              className="input w-full"
              placeholder="Jean"
            />
            {errors.first_name && (
              <p className="text-red-400 text-xs mt-1">{errors.first_name.message}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Nom
            </label>
            <input
              {...register('last_name')}
              type="text"
              className="input w-full"
              placeholder="Dupont"
            />
            {errors.last_name && (
              <p className="text-red-400 text-xs mt-1">{errors.last_name.message}</p>
            )}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Email
          </label>
          <input
            {...register('email')}
            type="email"
            className="input w-full"
            placeholder="jean.dupont@exemple.com"
          />
          {errors.email && (
            <p className="text-red-400 text-xs mt-1">{errors.email.message}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Mot de passe {isEdit && '(laisser vide pour ne pas modifier)'}
          </label>
          <input
            {...register('password')}
            type="password"
            className="input w-full"
            placeholder="********"
          />
          {errors.password && (
            <p className="text-red-400 text-xs mt-1">{errors.password.message}</p>
          )}
        </div>

        <div className="flex items-center gap-6 pt-2">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              {...register('is_active')}
              type="checkbox"
              className="w-4 h-4 rounded border-dark-500 bg-dark-700 text-primary-600 focus:ring-primary-500"
            />
            <span className="text-sm text-dark-300">Compte actif</span>
          </label>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Rôle
            </label>
            <select
              {...register('role')}
              className="input w-full"
            >
              <option value="staff">Staff</option>
              <option value="manager">Manager</option>
              <option value="admin">Administrateur</option>
            </select>
          </div>
        </div>
      </form>
    </Modal>
  );
}
