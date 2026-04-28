import { useRef, useCallback, type ReactNode, type TouchEvent } from 'react'
import { X } from 'lucide-react'
import { useResponsive } from '../../hooks/useMediaQuery'
import { Modal, type ModalProps } from './Modal'
import { cn } from '../../lib/utils'

type BottomSheetProps = ModalProps

const SWIPE_THRESHOLD = 80

export function BottomSheet(props: BottomSheetProps) {
  const { isMobile } = useResponsive()

  if (!isMobile) {
    return <Modal {...props} />
  }

  return <MobileSheet {...props} />
}

function MobileSheet({
  isOpen,
  onClose,
  title,
  description,
  children,
  showCloseButton = true,
  closeOnOverlayClick = true,
  footer,
}: BottomSheetProps) {
  const startY = useRef(0)
  const currentY = useRef(0)
  const sheetRef = useRef<HTMLDivElement>(null)

  const handleTouchStart = useCallback((e: TouchEvent) => {
    startY.current = e.touches[0].clientY
    currentY.current = e.touches[0].clientY
  }, [])

  const handleTouchMove = useCallback((e: TouchEvent) => {
    currentY.current = e.touches[0].clientY
    const delta = currentY.current - startY.current
    if (delta > 0 && sheetRef.current) {
      sheetRef.current.style.transform = `translateY(${delta}px)`
    }
  }, [])

  const handleTouchEnd = useCallback(() => {
    const delta = currentY.current - startY.current
    if (sheetRef.current) {
      if (delta > SWIPE_THRESHOLD) {
        onClose()
      }
      sheetRef.current.style.transform = ''
    }
  }, [onClose])

  if (!isOpen) return null

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 animate-in fade-in duration-200"
        onClick={closeOnOverlayClick ? onClose : undefined}
        aria-hidden="true"
      />

      {/* Sheet */}
      <div
        ref={sheetRef}
        className={cn(
          'fixed bottom-0 left-0 right-0 z-50',
          'bg-[var(--s1)] rounded-t-2xl shadow-2xl border-t border-[var(--border)]',
          'animate-sheetUp',
          'max-h-[85vh] flex flex-col',
          'safe-area-pb'
        )}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? 'sheet-title' : undefined}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Swipe indicator */}
        <div
          className="flex justify-center pt-4 pb-1 cursor-grab"
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
        >
          <div className="w-10 h-1 rounded-full bg-[var(--border2)]" />
        </div>

        {/* Header */}
        {(title || showCloseButton) && (
          <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border)]">
            <div>
              {title && (
                <h2
                  id="sheet-title"
                  className="text-lg font-semibold"
                >
                  {title}
                </h2>
              )}
              {description && (
                <p className="mt-0.5 text-sm text-[var(--muted)]">
                  {description}
                </p>
              )}
            </div>
            {showCloseButton && (
              <button
                onClick={onClose}
                className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--s2)] rounded-lg transition-colors"
                aria-label="Fermer"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto overscroll-contain px-6 py-4" style={{ WebkitOverflowScrolling: 'touch' }}>
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="px-6 py-4 border-t border-[var(--border)] flex items-center justify-end gap-4">
            {footer}
          </div>
        )}
      </div>
    </>
  )
}
