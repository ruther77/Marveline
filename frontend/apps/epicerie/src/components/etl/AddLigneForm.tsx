// Formulaire ajout de ligne — inline avec auto-focus

import { useState } from 'react'
import type { LigneAddRequest } from '@/types/etl_import'

interface AddLigneFormProps {
  onAdd: (data: LigneAddRequest) => void
  isPending: boolean
}

export default function AddLigneForm({ onAdd, isPending }: AddLigneFormProps) {
  const [open, setOpen] = useState(false)
  const [designation, setDesignation] = useState('')

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="text-emerald-600 hover:text-emerald-700 text-sm font-medium"
      >
        + Ajouter une ligne
      </button>
    )
  }

  const submit = () => {
    if (designation.trim()) {
      onAdd({ designation: designation.trim() })
      setDesignation('')
      setOpen(false)
    }
  }

  return (
    <div className="flex items-center gap-2 bg-slate-50 rounded-lg p-2">
      <input
        type="text"
        placeholder="Désignation produit…"
        value={designation}
        onChange={e => setDesignation(e.target.value)}
        className="flex-1 bg-white border border-slate-300 rounded px-2 py-1.5 text-sm text-slate-700 outline-none focus:border-emerald-400"
        autoFocus
        onKeyDown={e => { if (e.key === 'Enter') submit() }}
      />
      <button
        onClick={submit}
        disabled={isPending || !designation.trim()}
        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm rounded transition-colors disabled:opacity-50"
      >
        Ajouter
      </button>
      <button
        onClick={() => { setOpen(false); setDesignation('') }}
        className="px-2 py-1.5 text-slate-500 hover:text-slate-700 text-sm"
      >
        Annuler
      </button>
    </div>
  )
}
