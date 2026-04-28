interface ActionErrorProps {
  message: string | null
  onDismiss: () => void
}

export function ActionError({ message, onDismiss }: ActionErrorProps) {
  if (!message) return null
  return (
    <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 flex items-center justify-between text-sm">
      <span>{message}</span>
      <button
        onClick={onDismiss}
        className="ml-4 text-red-400 hover:text-red-300 transition-colors"
        aria-label="Fermer"
      >
        ✕
      </button>
    </div>
  )
}
