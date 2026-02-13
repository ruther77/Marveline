import { ReactNode } from 'react';
import { AlertTriangle, Trash2, LogOut, Info } from 'lucide-react';
import { Modal } from './Modal';
import { Button } from './Button';
import { cn } from '../../lib/utils';

export type ConfirmVariant = 'danger' | 'warning' | 'info' | 'default';

export interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description?: ReactNode;
  confirmText?: string;
  cancelText?: string;
  variant?: ConfirmVariant;
  loading?: boolean;
  icon?: ReactNode;
}

const variantConfig = {
  danger: {
    icon: Trash2,
    iconBg: 'bg-red-900/50',
    iconColor: 'text-red-400',
    buttonVariant: 'danger' as const,
  },
  warning: {
    icon: AlertTriangle,
    iconBg: 'bg-yellow-900/50',
    iconColor: 'text-yellow-400',
    buttonVariant: 'primary' as const,
  },
  info: {
    icon: Info,
    iconBg: 'bg-blue-900/50',
    iconColor: 'text-blue-400',
    buttonVariant: 'primary' as const,
  },
  default: {
    icon: Info,
    iconBg: 'bg-dark-700',
    iconColor: 'text-dark-300',
    buttonVariant: 'primary' as const,
  },
};

export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  confirmText = 'Confirmer',
  cancelText = 'Annuler',
  variant = 'default',
  loading = false,
  icon,
}: ConfirmDialogProps) {
  const config = variantConfig[variant];
  const IconComponent = config.icon;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="sm"
      showCloseButton={false}
      closeOnOverlayClick={!loading}
    >
      <div className="text-center">
        <div
          className={cn(
            'w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4',
            config.iconBg
          )}
        >
          {icon || <IconComponent className={cn('w-6 h-6', config.iconColor)} />}
        </div>
        <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
        {description && (
          <p className="text-dark-400 text-sm mb-6">{description}</p>
        )}
        <div className="flex items-center justify-center gap-3">
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={loading}
          >
            {cancelText}
          </Button>
          <Button
            variant={config.buttonVariant}
            onClick={onConfirm}
            loading={loading}
          >
            {confirmText}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

// Preset Dialogs
export interface DeleteConfirmProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  itemName?: string;
  loading?: boolean;
}

export function DeleteConfirm({
  isOpen,
  onClose,
  onConfirm,
  itemName,
  loading,
}: DeleteConfirmProps) {
  return (
    <ConfirmDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      variant="danger"
      title="Supprimer cet élément ?"
      description={
        itemName
          ? `Êtes-vous sûr de vouloir supprimer "${itemName}" ? Cette action est irréversible.`
          : 'Êtes-vous sûr de vouloir supprimer cet élément ? Cette action est irréversible.'
      }
      confirmText="Supprimer"
      loading={loading}
    />
  );
}

export interface LogoutConfirmProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  loading?: boolean;
}

export function LogoutConfirm({
  isOpen,
  onClose,
  onConfirm,
  loading,
}: LogoutConfirmProps) {
  return (
    <ConfirmDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      variant="warning"
      icon={<LogOut className="w-6 h-6 text-yellow-400" />}
      title="Se déconnecter ?"
      description="Vous serez redirigé vers la page de connexion."
      confirmText="Se déconnecter"
      loading={loading}
    />
  );
}

export interface UnsavedChangesConfirmProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  onSave?: () => void;
}

export function UnsavedChangesConfirm({
  isOpen,
  onClose,
  onConfirm,
  onSave,
}: UnsavedChangesConfirmProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="sm"
      showCloseButton={false}
    >
      <div className="text-center">
        <div className="w-12 h-12 rounded-full bg-yellow-900/50 flex items-center justify-center mx-auto mb-4">
          <AlertTriangle className="w-6 h-6 text-yellow-400" />
        </div>
        <h3 className="text-lg font-semibold text-white mb-2">
          Modifications non enregistrées
        </h3>
        <p className="text-dark-400 text-sm mb-6">
          Vous avez des modifications non enregistrées. Voulez-vous les sauvegarder avant de quitter ?
        </p>
        <div className="flex items-center justify-center gap-3">
          <Button variant="ghost" onClick={onConfirm}>
            Ne pas enregistrer
          </Button>
          {onSave && (
            <Button variant="primary" onClick={onSave}>
              Enregistrer
            </Button>
          )}
          <Button variant="secondary" onClick={onClose}>
            Annuler
          </Button>
        </div>
      </div>
    </Modal>
  );
}
