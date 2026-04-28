// Bouton validation rapide — 1-clic sur les imports 100% qualité

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { validateImport, fetchImages } from '@/api/etl_imports'
import { normalizeError } from '@shared/errors/normalizer'

interface QuickValidateButtonProps {
  importId: number
  onError: (msg: string) => void
}

export default function QuickValidateButton({ importId, onError }: QuickValidateButtonProps) {
  const qc = useQueryClient()
  const [confirmed, setConfirmed] = useState(false)

  const { mutate, isPending } = useMutation({
    mutationFn: () => validateImport(importId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['etl-imports'] })
      qc.invalidateQueries({ queryKey: ['epicerie-stock'] })
      qc.invalidateQueries({ queryKey: ['epicerie-stock-stats'] })
      fetchImages().catch(() => {})
      setConfirmed(false)
    },
    onError: (err) => {
      onError(normalizeError(err).message || 'Erreur de validation')
      setConfirmed(false)
    },
  })

  if (isPending) {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-100 text-emerald-700 text-xs rounded-lg">
        <span className="w-3 h-3 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
        Validation…
      </span>
    )
  }

  if (!confirmed) {
    return (
      <button
        onClick={e => { e.stopPropagation(); setConfirmed(true) }}
        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg transition-colors"
      >
        Valider ✓
      </button>
    )
  }

  return (
    <div className="flex items-center gap-1.5" onClick={e => e.stopPropagation()}>
      <button
        onClick={() => mutate()}
        className="px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg transition-colors"
      >
        Confirmer
      </button>
      <button
        onClick={() => setConfirmed(false)}
        className="px-2 py-1.5 text-slate-500 hover:text-slate-700 text-xs"
      >
        ×
      </button>
    </div>
  )
}
