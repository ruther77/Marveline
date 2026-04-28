import { useState } from 'react'
import { normalizeError } from '@shared/errors/normalizer'
import { Wrench } from 'lucide-react'
import { formatCents, cn } from '@/lib/utils'
import {
  INVOICE_CHARGE_TYPE_LABELS as CHARGE_TYPE_LABELS,
  INVOICE_DAY_TYPE_LABELS as DAY_TYPE_LABELS,
} from '@/lib/constants'
import type { InvoiceDetail, InvoiceChargeCreate } from '@/types/invoice'

interface InvoiceChargesSectionProps {
  invoiceId: number
  status: string
  charges: InvoiceDetail['charges']
  isPending: boolean
  error?: unknown | null
  effectiveHourlyWeekday: number
  effectiveHourlyWeekend: number
  onSubmit: (charge: InvoiceChargeCreate) => void
}

export function InvoiceChargesSection({
  invoiceId: _invoiceId,
  status,
  charges,
  isPending,
  error,
  effectiveHourlyWeekday,
  effectiveHourlyWeekend,
  onSubmit,
}: InvoiceChargesSectionProps) {
  const [showForm, setShowForm] = useState(false)
  const [chargeType, setChargeType] = useState<'DAMAGE' | 'LABOR'>('DAMAGE')
  const [description, setDescription] = useState('')
  const [amountEuros, setAmountEuros] = useState('')
  const [hours, setHours] = useState('')
  const [dayType, setDayType] = useState<'weekday' | 'weekend' | 'night'>('weekday')

  const canAdd = status === 'draft' || status === 'sent'

  const computedLaborAmount = () => {
    const h = parseFloat(hours)
    if (!h || h <= 0) return null
    const rate = dayType === 'weekday' ? effectiveHourlyWeekday : effectiveHourlyWeekend
    return Math.ceil(h * rate)
  }

  const handleSubmit = () => {
    if (!description.trim()) return
    const payload: InvoiceChargeCreate = {
      charge_type: chargeType,
      description: description.trim(),
    }
    if (chargeType === 'DAMAGE') {
      const cents = Math.round(parseFloat(amountEuros) * 100)
      if (!amountEuros || cents <= 0) return
      payload.amount_cents = cents
    } else {
      const h = parseFloat(hours)
      if (!hours || h <= 0) return
      payload.hours = h
      payload.day_type = dayType
    }
    onSubmit(payload)
    setShowForm(false)
    setDescription('')
    setAmountEuros('')
    setHours('')
  }

  const handleCancel = () => {
    setShowForm(false)
    setDescription('')
    setAmountEuros('')
    setHours('')
  }

  return (
    <div className="border-t border-dark-600 pt-4 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h4 className="font-medium flex items-center gap-2 text-sm">
          <Wrench className="w-4 h-4 text-dark-400" />
          Frais supplémentaires
          {charges && charges.length > 0 && (
            <span className="text-xs bg-dark-900 text-dark-300 px-1.5 py-0.5 rounded">
              {charges.length}
            </span>
          )}
        </h4>
        {canAdd && (
          <button
            onClick={() => setShowForm(!showForm)}
            className="btn-secondary btn-sm text-xs"
          >
            + Ajouter
          </button>
        )}
      </div>

      {charges && charges.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-dark-400 text-xs border-b border-dark-600">
                <th className="text-left pb-2">Type</th>
                <th className="text-left pb-2">Description</th>
                <th className="text-right pb-2">Montant</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-600">
              {charges.map((charge) => (
                <tr key={charge.id} className="py-1.5">
                  <td className="py-1.5 pr-4">
                    <span className={cn(
                      'text-xs px-1.5 py-0.5 rounded',
                      charge.charge_type === 'DAMAGE'
                        ? 'bg-orange-500/10 text-orange-400'
                        : 'bg-blue-500/10 text-blue-400'
                    )}>
                      {CHARGE_TYPE_LABELS[charge.charge_type]}
                    </span>
                    {charge.day_type && (
                      <span className="ml-1 text-xs text-dark-500">
                        {DAY_TYPE_LABELS[charge.day_type]}
                        {charge.hours != null && ` · ${charge.hours}h`}
                      </span>
                    )}
                  </td>
                  <td className="py-1.5 pr-4 text-dark-300">{charge.description}</td>
                  <td className="py-1.5 text-right font-medium">
                    {formatCents(charge.amount_cents)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && canAdd && (
        <div className="card p-4 space-y-4">
          {error != null && (
            <div className="p-2 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm">
              {normalizeError(error).message || "Erreur lors de l'ajout"}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">Type *</label>
              <select
                value={chargeType}
                onChange={(e) => setChargeType(e.target.value as 'DAMAGE' | 'LABOR')}
                className="input"
              >
                <option value="DAMAGE">Dommage</option>
                <option value="LABOR">Main d'œuvre</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">Description *</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Ex : Assiette cassée"
                className="input"
              />
            </div>
          </div>

          {chargeType === 'DAMAGE' ? (
            <div>
              <label className="block text-sm text-dark-400 mb-1">Montant (EUR) *</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={amountEuros}
                onChange={(e) => setAmountEuros(e.target.value)}
                placeholder="0.00"
                className="input"
              />
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-dark-400 mb-1">Heures *</label>
                <input
                  type="number"
                  step="0.25"
                  min="0.25"
                  value={hours}
                  onChange={(e) => setHours(e.target.value)}
                  placeholder="0.00"
                  className="input"
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">Type de jour *</label>
                <select
                  value={dayType}
                  onChange={(e) => setDayType(e.target.value as 'weekday' | 'weekend' | 'night')}
                  className="input"
                >
                  <option value="weekday">Semaine ({effectiveHourlyWeekday} EUR/h)</option>
                  <option value="weekend">Week-end ({effectiveHourlyWeekend} EUR/h)</option>
                  <option value="night">Nuit ({effectiveHourlyWeekend} EUR/h)</option>
                </select>
              </div>
            </div>
          )}

          {chargeType === 'LABOR' && computedLaborAmount() !== null && (
            <div className="text-sm text-dark-400 bg-dark-900 rounded px-4 py-2">
              Montant calculé : <span className="font-medium text-dark-200">{computedLaborAmount()} EUR</span>
            </div>
          )}

          <div className="flex gap-2 justify-end">
            <button onClick={handleCancel} className="btn-secondary btn-sm">
              Annuler
            </button>
            <button
              onClick={handleSubmit}
              disabled={isPending || !description.trim()}
              className="btn-primary btn-sm"
            >
              {isPending ? 'Ajout...' : 'Ajouter la charge'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
