import { useMutation, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle } from 'lucide-react';
import { adminApi } from '@/api/admin';
import { Modal, ModalFooter } from '@/components/ui/Modal';
import type { User } from '@/types';

interface UserDeleteModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: User | null;
}

export function UserDeleteModal({ isOpen, onClose, user }: UserDeleteModalProps) {
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: (id: number) => adminApi.deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      onClose();
    },
  });

  const handleDelete = () => {
    if (user) {
      deleteMutation.mutate(user.id);
    }
  };

  if (!user) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Supprimer l'utilisateur"
      size="sm"
      footer={
        <ModalFooter
          onCancel={onClose}
          onConfirm={handleDelete}
          cancelText="Annuler"
          confirmText="Supprimer"
          confirmVariant="danger"
          loading={deleteMutation.isPending}
        />
      }
    >
      <div className="text-center">
        <div className="mx-auto w-12 h-12 bg-red-500/10 rounded-full flex items-center justify-center mb-4">
          <AlertTriangle className="w-6 h-6 text-red-500" />
        </div>
        <p className="text-dark-300 mb-2">
          Etes-vous sur de vouloir supprimer l'utilisateur
        </p>
        <p className="font-medium text-white">
          {user.first_name} {user.last_name}
        </p>
        <p className="text-dark-400 text-sm mt-1">{user.email}</p>

        {deleteMutation.error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {(deleteMutation.error as Error).message || 'Erreur lors de la suppression'}
          </div>
        )}

        <p className="text-dark-500 text-xs mt-4">
          Cette action est irreversible.
        </p>
      </div>
    </Modal>
  );
}
