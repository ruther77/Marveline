import { Fragment, ReactNode, useEffect } from 'react';
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useFocusTrap } from '../../hooks/useFocusTrap';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
  showCloseButton?: boolean;
  closeOnOverlayClick?: boolean;
  footer?: ReactNode;
}

const sizes = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-2xl',
  full: 'max-w-5xl',
};

export function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  size = 'md',
  showCloseButton = true,
  closeOnOverlayClick = true,
  footer,
}: ModalProps) {
  const trapRef = useFocusTrap<HTMLDivElement>(onClose)

  if (!isOpen) return null;

  return (
    <Fragment>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/75 backdrop-blur-[6px] z-50"
        aria-hidden="true"
        onClick={closeOnOverlayClick ? onClose : undefined}
      />

      {/* Modal */}
      <div
        className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-8 overflow-y-auto"
        onMouseDown={(e) => {
          if (closeOnOverlayClick && e.target === e.currentTarget) onClose()
        }}
      >
        <div
          ref={trapRef}
          className={cn(
            'relative w-full modal-panel flex flex-col max-h-[calc(100vh-4rem)]',
            sizes[size]
          )}
          role="dialog"
          aria-modal="true"
          aria-labelledby={title ? 'modal-title' : undefined}
          aria-describedby={description ? 'modal-description' : undefined}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          {(title || showCloseButton) && (
            <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-dark-600 shrink-0">
              <div>
                {title && (
                  <h2
                    id="modal-title"
                    className="text-lg font-semibold"
                  >
                    {title}
                  </h2>
                )}
                {description && (
                  <p
                    id="modal-description"
                    className="mt-1 text-sm text-dark-400"
                  >
                    {description}
                  </p>
                )}
              </div>
              {showCloseButton && (
                <button
                  type="button"
                  onClick={onClose}
                  onPointerDown={(e) => { e.stopPropagation(); onClose(); }}
                  className="p-4 -mr-2 min-h-[48px] min-w-[48px] flex items-center justify-center text-dark-400 hover:text-dark-50 hover:bg-dark-600 rounded-lg transition-colors touch-manipulation"
                  aria-label="Fermer"
                >
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>
          )}

          {/* Content */}
          <div className="px-4 sm:px-6 py-4 flex-1 min-h-0 overflow-y-auto">
            {children}
          </div>

          {/* Footer */}
          {footer && (
            <div className="px-4 sm:px-6 py-4 border-t border-dark-600 flex items-center justify-end gap-4 shrink-0">
              {footer}
            </div>
          )}
        </div>
      </div>
    </Fragment>
  );
}

// Composant pour le contenu du footer standard
export interface ModalFooterProps {
  onCancel?: () => void;
  onConfirm?: () => void;
  cancelText?: string;
  confirmText?: string;
  confirmVariant?: 'primary' | 'danger';
  loading?: boolean;
}

export function ModalFooter({
  onCancel,
  onConfirm,
  cancelText = 'Annuler',
  confirmText = 'Confirmer',
  confirmVariant = 'primary',
  loading = false,
}: ModalFooterProps) {
  return (
    <>
      {onCancel && (
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm font-medium text-dark-400 hover:text-dark-100 hover:bg-dark-600 rounded-lg transition-colors"
          disabled={loading}
        >
          {cancelText}
        </button>
      )}
      {onConfirm && (
        <button
          type="button"
          onClick={onConfirm}
          disabled={loading}
          className={cn(
            'px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            confirmVariant === 'danger'
              ? 'bg-red-600 hover:bg-red-700'
              : 'bg-primary-600 hover:bg-primary-700'
          )}
        >
          {loading ? 'Chargement...' : confirmText}
        </button>
      )}
    </>
  );
}
