import { useState } from 'react'
import { X, ClipboardCheck, AlertCircle, Plus, Trash2 } from 'lucide-react'
import { Button, MoneyInput } from '@shared/components/ui'
import { normalizeError } from '@shared/errors/normalizer'
import { useCreateInspection } from '@/api/queries'
import type {
  ReservationDetailFull,
  ReturnInspectionItemCreate,
} from '@/types/reservation'
import { useToast } from '@/hooks'

interface ReturnInspectionModalProps {
  open: boolean
  onClose: () => void
  reservation: ReservationDetailFull
}

type DraftItem = ReturnInspectionItemCreate & { _key: string }

const conditionOptions: Array<{ value: DraftItem['condition']; label: string }> = [
  { value: 'good', label: 'Bon état' },
  { value: 'damaged', label: 'Endommagé' },
  { value: 'missing', label: 'Manquant' },
  { value: 'partial', label: 'Partiel' },
]

function buildDraftFromLines(reservation: ReservationDetailFull): DraftItem[] {
  return reservation.lines.map((line) => ({
    _key: `line-${line.id}`,
    reservation_line_id: line.id,
    label:
      line.product?.name ??
      line.bundle?.name ??
      `Ligne #${line.id}`,
    quantity_expected: line.quantity,
    quantity_returned: line.quantity,
    quantity_damaged: 0,
    quantity_missing: 0,
    condition: 'good',
    damage_description: '',
    charge_cents: 0,
  }))
}

/**
 * Modale "Constater le retour" — saisie item-par-item du retour matériel.
 *
 * Pré-remplit avec les lignes de la résa (quantity_expected = qté commandée).
 * Si dégâts/manquants détectés → bascule auto en RETURNED_DISPUTE côté backend
 * et écriture d'une entrée `opened` dans le journal du litige.
 */
export function ReturnInspectionModal({
  open,
  onClose,
  reservation,
}: ReturnInspectionModalProps) {
  const toast = useToast()
  const mut = useCreateInspection()

  const [items, setItems] = useState<DraftItem[]>(() => buildDraftFromLines(reservation))
  const [error, setError] = useState<string | null>(null)

  if (!open) return null

  const updateItem = (key: string, patch: Partial<DraftItem>) => {
    setItems((prev) => prev.map((it) => (it._key === key ? { ...it, ...patch } : it)))
  }

  const removeItem = (key: string) => {
    setItems((prev) => prev.filter((it) => it._key !== key))
  }

  const addExtraItem = () => {
    setItems((prev) => [
      ...prev,
      {
        _key: `extra-${Date.now()}`,
        reservation_line_id: null,
        label: '',
        quantity_expected: 0,
        quantity_returned: 0,
        quantity_damaged: 0,
        quantity_missing: 0,
        condition: 'good',
        damage_description: '',
        charge_cents: 0,
      },
    ])
  }

  const totalCharge = items.reduce((acc, it) => acc + (it.charge_cents ?? 0), 0)
  const hasIssue = items.some(
    (it) => (it.quantity_damaged ?? 0) > 0 || (it.quantity_missing ?? 0) > 0,
  )
  const canSubmit =
    items.length > 0 &&
    items.every((it) => it.label.trim().length > 0) &&
    !mut.isPending

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const payload = {
      items: items.map(({ _key: _ignored, ...rest }) => rest),
    }

    mut.mutate(
      { reservationId: reservation.id, payload },
      {
        onSuccess: () => {
          toast.success(
            'Constat enregistré',
            hasIssue
              ? 'Litige ouvert sur la réservation.'
              : 'Retour clôturé sans incident.',
          )
          onClose()
        },
        onError: (err) => {
          setError(normalizeError(err).message || 'Erreur lors du constat')
        },
      },
    )
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
      onClick={onClose}
    >
      <div
        className="bg-dark-800 rounded-xl border border-dark-600 w-full max-w-3xl shadow-xl flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between px-5 py-4 border-b border-dark-600">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="w-5 h-5 text-primary-400" />
            <h2 className="font-bold">Constater le retour</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Fermer"
            className="text-dark-400 hover:text-dark-200"
          >
            <X className="w-5 h-5" />
          </button>
        </header>

        <form
          onSubmit={handleSubmit}
          className="px-5 py-4 space-y-4 overflow-y-auto flex-1"
        >
          <p className="text-sm text-dark-300">
            Vérifiez chaque article retourné. Les quantités endommagées ou
            manquantes basculent automatiquement la réservation en{' '}
            <strong>litige</strong>.
          </p>

          <div className="space-y-3">
            {items.map((it) => {
              const issue =
                (it.quantity_damaged ?? 0) > 0 || (it.quantity_missing ?? 0) > 0
              return (
                <div
                  key={it._key}
                  className={`rounded-lg border p-3 space-y-2 ${
                    issue
                      ? 'border-amber-600/50 bg-amber-900/10'
                      : 'border-dark-700 bg-dark-900/40'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <input
                      type="text"
                      value={it.label}
                      onChange={(e) => updateItem(it._key, { label: e.target.value })}
                      placeholder="Libellé article"
                      className="input flex-1"
                      required
                    />
                    {it.reservation_line_id == null && (
                      <button
                        type="button"
                        onClick={() => removeItem(it._key)}
                        className="text-dark-400 hover:text-red-400 p-2"
                        aria-label="Retirer cet item"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    <div>
                      <label className="text-xs text-dark-400 block mb-0.5">
                        Attendu
                      </label>
                      <input
                        type="number"
                        min={0}
                        value={it.quantity_expected ?? 0}
                        onChange={(e) =>
                          updateItem(it._key, {
                            quantity_expected: Number(e.target.value),
                          })
                        }
                        className="input w-full"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-dark-400 block mb-0.5">
                        Retourné
                      </label>
                      <input
                        type="number"
                        min={0}
                        value={it.quantity_returned ?? 0}
                        onChange={(e) =>
                          updateItem(it._key, {
                            quantity_returned: Number(e.target.value),
                          })
                        }
                        className="input w-full"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-dark-400 block mb-0.5">
                        Endommagé
                      </label>
                      <input
                        type="number"
                        min={0}
                        value={it.quantity_damaged ?? 0}
                        onChange={(e) =>
                          updateItem(it._key, {
                            quantity_damaged: Number(e.target.value),
                          })
                        }
                        className="input w-full"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-dark-400 block mb-0.5">
                        Manquant
                      </label>
                      <input
                        type="number"
                        min={0}
                        value={it.quantity_missing ?? 0}
                        onChange={(e) =>
                          updateItem(it._key, {
                            quantity_missing: Number(e.target.value),
                          })
                        }
                        className="input w-full"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs text-dark-400 block mb-0.5">
                        État
                      </label>
                      <select
                        value={it.condition}
                        onChange={(e) =>
                          updateItem(it._key, {
                            condition: e.target.value as DraftItem['condition'],
                          })
                        }
                        className="input w-full"
                      >
                        {conditionOptions.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <MoneyInput
                        label="Charge à imputer"
                        value={it.charge_cents ?? 0}
                        onChange={(cents) => updateItem(it._key, { charge_cents: cents })}
                      />
                    </div>
                  </div>

                  {issue && (
                    <textarea
                      rows={2}
                      value={it.damage_description ?? ''}
                      onChange={(e) =>
                        updateItem(it._key, { damage_description: e.target.value })
                      }
                      placeholder="Description du dégât / manquant…"
                      className="input w-full text-sm"
                      maxLength={500}
                    />
                  )}
                </div>
              )
            })}
          </div>

          <button
            type="button"
            onClick={addExtraItem}
            className="flex items-center gap-1 text-sm text-primary-400 hover:text-primary-300"
          >
            <Plus className="w-4 h-4" /> Ajouter un article hors-périmètre
          </button>

          {hasIssue && (
            <div className="rounded-lg bg-amber-900/20 border border-amber-600/40 px-3 py-2 text-sm text-amber-200 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>
                Total à imputer :{' '}
                <strong>{(totalCharge / 100).toFixed(2)} €</strong>. La résa
                basculera en litige.
              </span>
            </div>
          )}

          {error && (
            <div className="bg-red-900/30 border border-red-600/40 text-red-300 text-sm rounded-lg px-3 py-2">
              {error}
            </div>
          )}
        </form>

        <footer className="flex justify-end gap-2 px-5 py-4 border-t border-dark-600">
          <Button variant="ghost" onClick={onClose} disabled={mut.isPending}>
            Annuler
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit as unknown as () => void}
            disabled={!canSubmit}
          >
            {mut.isPending ? 'Enregistrement…' : 'Valider le constat'}
          </Button>
        </footer>
      </div>
    </div>
  )
}
