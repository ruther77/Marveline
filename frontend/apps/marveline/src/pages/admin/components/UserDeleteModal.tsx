import { useDeleteUser } from '@/api/queries';
import { AlertTriangle } from 'lucide-react';
import { Modal, ModalFooter } from '@shared/components/ui/Modal';
import { ActionError } from '@shared/components/ui/ActionError';
import { normalizeError } from '@shared/errors/normalizer';
import type { User } from '@/types';

interface UserDeleteModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: User | null;
}

export function UserDeleteModal({ isOpen, onClose, user }: UserDeleteModalProps) {
  const deleteMutation = useDeleteUser();

  const handleDelete = () => {
    if (user) {
      deleteMutation.mutate(user.id, { onSuccess: onClose });
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
        <p className="font-medium">
          {user.first_name} {user.last_name}
        </p>
        <p className="text-dark-400 text-sm mt-1">{user.email}</p>

        <ActionError
          message={deleteMutation.isError ? (normalizeError(deleteMutation.error).message || 'Erreur lors de la suppression') : null}
          onDismiss={() => deleteMutation.reset()}
        />

        <p className="text-dark-500 text-xs mt-4">
          Le compte sera désactivé (soft delete).
        </p>
      </div>
    </Modal>
  );
}
