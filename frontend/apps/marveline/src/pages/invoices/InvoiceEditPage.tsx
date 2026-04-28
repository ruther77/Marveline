import { PageHeader } from '@/components/PageHeader'
import { useState, useEffect } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { useInvoiceFull, useUpdateInvoice, useAddCharge } from '@/api/queries/useInvoices'
import { useReservationDetail, useAddReservationLine, useRemoveReservationLine } from '@/api/queries/useReservations'
import { normalizeError } from '@shared/errors/normalizer'
import { formatCents } from '@/lib/utils'
import { ArrowLeft, Minus, Plus, Save, Package } from 'lucide-react'
import type { InvoiceUpdateRequest } from '@/types/invoice'
import type { ReservationLineCreate } from '@/types/reservation'
import { InvoiceChargesSection } from './components/InvoiceChargesSection'

const STATUS_LABELS: Record<string, string> = {
  draft: 'Brouillon',
  sent: 'Envoyée',
  paid: 'Payée',
  overdue: 'En retard',
  cancelled: 'Annulée',
}

const HOURLY_WEEKDAY_DEFAULT = 25
const HOURLY_WEEKEND_DEFAULT = 35

export default function InvoiceEditPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const invoiceId = Number(id)

  const { data: invoice, isLoading, error: loadError } = useInvoiceFull(invoiceId)
  const updateMutation = useUpdateInvoice()
  const addChargeMutation = useAddCharge()

  const reservationId = invoice?.reservation_id ?? null
  const { data: reservationDetail, isLoading: resLoading } = useReservationDetail(
    invoice?.status === 'draft' ? reservationId : null
  )
  const addLineMutation = useAddReservationLine()
  const removeLineMutation = useRemoveReservationLine()

  const [issueDate, setIssueDate] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  // Add-line form state
  const [showAddLine, setShowAddLine] = useState(false)
  const [addLineProductId, setAddLineProductId] = useState('')
  const [addLineQty, setAddLineQty] = useState('1')
  const [addLineError, setAddLineError] = useState<string | null>(null)

  useEffect(() => {
    if (!invoice) return
    setIssueDate(invoice.issue_date?.slice(0, 10) ?? '')
    setDueDate(invoice.due_date?.slice(0, 10) ?? '')
  }, [invoice])

  const isDraft = invoice?.status === 'draft'

  const handleSave = async () => {
    setSaveError(null)
    setSaved(false)
    const newTotal = reservationDetail?.lines?.reduce((s, l) => s + l.subtotal_cents, 0)
    try {
      const payload: InvoiceUpdateRequest = {
        issue_date: issueDate || undefined,
        due_date: dueDate || undefined,
        ...(newTotal != null ? { total_amount: newTotal } : {}),
      }
      await updateMutation.mutateAsync({ id: invoiceId, data: payload })
      setSaved(true)
    } catch (err) {
      setSaveError(normalizeError(err).message || 'Erreur lors de la sauvegarde')
    }
  }

  const handleAddLine = async () => {
    if (!reservationId || !addLineProductId) return
    setAddLineError(null)
    const qty = parseInt(addLineQty, 10)
    if (!qty || qty <= 0) {
      setAddLineError('Quantité invalide')
      return
    }
    const data: ReservationLineCreate = { product_id: parseInt(addLineProductId, 10), quantity: qty }
    try {
      await addLineMutation.mutateAsync({ reservationId, data })
      setShowAddLine(false)
      setAddLineProductId('')
      setAddLineQty('1')
      setSaved(false)
    } catch (err) {
      setAddLineError(normalizeError(err).message || 'Erreur lors de l\'ajout de la ligne')
    }
  }

  const handleRemoveLine = async (lineId: number) => {
    if (!reservationId) return
    try {
      await removeLineMutation.mutateAsync({ reservationId, lineId })
      setSaved(false)
    } catch (err) {
      setSaveError(normalizeError(err).message || 'Erreur lors de la suppression de la ligne')
    }
  }

  // ── Loading skeleton ───────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-4">
        <div className="h-8 w-48 skel rounded animate-pulse" />
        <div className="card p-6 space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-10 skel rounded animate-pulse" />
          ))}
        </div>
        <div className="card p-6 space-y-4">
          {[1, 2].map(i => (
            <div key={i} className="h-10 skel rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  // ── Error / not found ──────────────────────────────────────────────────────
  if (loadError || !invoice) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto">
        <div className="card p-8 text-center text-danger">
          {loadError ? normalizeError(loadError).message : 'Facture introuvable'}
        </div>
      </div>
    )
  }

  const lines = reservationDetail?.lines ?? []
  const linesTotal = lines.reduce((s, l) => s + l.subtotal_cents, 0)

  // ── Main view ──────────────────────────────────────────────────────────────
  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-4 pb-8">
      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <Link
          to="/finance/invoices/$id"
          params={{ id: String(invoiceId) }}
          className="btn-secondary btn-sm flex items-center gap-2 min-h-[44px]"
        >
          <ArrowLeft className="w-4 h-4" />
          Retour
        </Link>
        <div className="flex-1 min-w-0">
          <PageHeader title="Modifier la facture" subtitle={`${invoice.invoice_number} — ${invoice.customer_name ?? ''}`} />
        </div>
        {!isDraft && (
          <span className="text-xs font-medium px-2.5 py-1 rounded-lg bg-dark-900 text-dark-300">
            Non modifiable · {STATUS_LABELS[invoice.status] ?? invoice.status}
          </span>
        )}
      </div>

      {/* Résumé */}
      <div className="card p-6 space-y-4">
        <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide">Résumé</h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-dark-400 block mb-0.5">Statut</span>
            <span>{STATUS_LABELS[invoice.status] ?? invoice.status}</span>
          </div>
          <div>
            <span className="text-dark-400 block mb-0.5">Total TTC</span>
            <span className="font-semibold text-primary-400">
              {isDraft && linesTotal > 0
                ? formatCents(linesTotal)
                : formatCents(invoice.total_amount_cents)}
            </span>
          </div>
          <div>
            <span className="text-dark-400 block mb-0.5">Payé</span>
            <span>{formatCents(invoice.paid_amount_cents)}</span>
          </div>
          <div>
            <span className="text-dark-400 block mb-0.5">Restant</span>
            <span className={invoice.remaining_amount_cents > 0 ? 'text-amber-400' : 'text-green-400'}>
              {formatCents(invoice.remaining_amount_cents)}
            </span>
          </div>
        </div>
      </div>

      {/* Dates éditables */}
      <div className="card p-6 space-y-4">
        <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide">Dates</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">Date d&apos;émission</label>
            <input
              type="date"
              className="input w-full"
              value={issueDate}
              onChange={e => setIssueDate(e.target.value)}
              disabled={!isDraft}
            />
          </div>
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">Date d&apos;échéance</label>
            <input
              type="date"
              className="input w-full"
              value={dueDate}
              min={issueDate || undefined}
              onChange={e => setDueDate(e.target.value)}
              disabled={!isDraft}
            />
          </div>
        </div>
        {issueDate && dueDate && dueDate < issueDate && (
          <p className="text-sm text-red-400">La date d&apos;échéance doit être après la date d&apos;émission.</p>
        )}
      </div>

      {/* Lignes de la réservation (draft uniquement) */}
      {isDraft && (
        <div className="card p-6 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide">
              Lignes de la réservation
            </h2>
            <button
              onClick={() => setShowAddLine(!showAddLine)}
              className="btn-secondary btn-sm flex items-center gap-1.5 text-xs min-h-[44px]"
            >
              <Plus className="w-3.5 h-3.5" />
              Ajouter
            </button>
          </div>

          {resLoading ? (
            <div className="animate-pulse space-y-2">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-10 skel rounded" />
              ))}
            </div>
          ) : lines.length === 0 ? (
            <p className="text-sm text-dark-500 py-2">Aucune ligne sur cette réservation.</p>
          ) : (
            <div className="border border-dark-600 rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-dark-900">
                  <tr>
                    <th className="text-left px-4 py-2 text-dark-400 font-medium">Produit</th>
                    <th className="text-right px-4 py-2 text-dark-400 font-medium">Qté</th>
                    <th className="text-right px-4 py-2 text-dark-400 font-medium hidden sm:table-cell">P.U.</th>
                    <th className="text-right px-4 py-2 text-dark-400 font-medium">Total</th>
                    <th className="px-2 py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-600">
                  {lines.map((line) => {
                    const lineName = line.product?.name ?? line.bundle?.name ?? `Ligne #${line.id}`
                    return (
                    <tr key={line.id} className="hover:bg-dark-900/40">
                      <td className="px-4 py-2">
                        <div className="flex gap-3 items-center">
                          <div className="w-12 h-12 rounded-lg overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center">
                            {line.product?.image_url ? (
                              <img src={line.product.image_url} alt={lineName} className="w-full h-full object-cover" loading="lazy" />
                            ) : (
                              <Package className="w-5 h-5 text-dark-600" />
                            )}
                          </div>
                          <span className="truncate">{lineName}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2 text-right text-dark-400 whitespace-nowrap">
                        {line.quantity}
                      </td>
                      <td className="px-4 py-2 text-right text-dark-400 whitespace-nowrap hidden sm:table-cell">
                        {formatCents(line.unit_price_cents)}
                      </td>
                      <td className="px-4 py-2 text-right font-medium whitespace-nowrap">
                        {formatCents(line.subtotal_cents)}
                      </td>
                      <td className="px-2 py-2 text-right">
                        <button
                          type="button"
                          onClick={() => handleRemoveLine(line.id)}
                          disabled={removeLineMutation.isPending}
                          aria-label="Supprimer la ligne"
                          className="p-1.5 rounded text-dark-500 hover:text-red-400 hover:bg-red-500/10 transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                        >
                          <Minus className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                    )
                  })}
                </tbody>
              </table>
              <div className="px-4 py-2 border-t border-dark-600 flex justify-between items-center bg-dark-900/50 text-sm">
                <span className="text-dark-400">{lines.length} article{lines.length > 1 ? 's' : ''}</span>
                <span className="font-semibold">{formatCents(linesTotal)}</span>
              </div>
            </div>
          )}

          {/* Formulaire ajout ligne */}
          {showAddLine && (
            <div className="bg-dark-900 rounded-xl border border-dark-600 p-4 space-y-3">
              <p className="text-sm font-medium">Ajouter une ligne</p>
              {addLineError && (
                <p className="text-sm text-red-400">{addLineError}</p>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-dark-400 mb-1 block">ID Produit *</label>
                  <input
                    type="number"
                    min="1"
                    value={addLineProductId}
                    onChange={e => setAddLineProductId(e.target.value)}
                    placeholder="Ex : 42"
                    className="input w-full"
                  />
                </div>
                <div>
                  <label className="text-xs text-dark-400 mb-1 block">Quantité *</label>
                  <input
                    type="number"
                    min="1"
                    value={addLineQty}
                    onChange={e => setAddLineQty(e.target.value)}
                    className="input w-full"
                  />
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => { setShowAddLine(false); setAddLineError(null) }}
                  className="btn-secondary btn-sm"
                >
                  Annuler
                </button>
                <button
                  onClick={handleAddLine}
                  disabled={addLineMutation.isPending || !addLineProductId}
                  className="btn-primary btn-sm flex items-center gap-1.5"
                >
                  {addLineMutation.isPending ? (
                    <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <Plus className="w-3.5 h-3.5" />
                  )}
                  Ajouter
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Frais supplémentaires (draft + sent) */}
      <div className="card p-6">
        <InvoiceChargesSection
          invoiceId={invoiceId}
          status={invoice.status}
          charges={invoice.charges ?? []}
          isPending={addChargeMutation.isPending}
          error={addChargeMutation.error}
          effectiveHourlyWeekday={HOURLY_WEEKDAY_DEFAULT}
          effectiveHourlyWeekend={HOURLY_WEEKEND_DEFAULT}
          onSubmit={(charge) => {
            addChargeMutation.mutate({ invoiceId, charge })
            setSaved(false)
          }}
        />
      </div>

      {/* Actions */}
      {isDraft && (
        <div className="flex items-center gap-4 justify-end flex-wrap">
          {saveError != null && (
            <p className="text-sm text-danger">{saveError}</p>
          )}
          {saved && (
            <p className="text-sm text-green-400">Sauvegardé ✓</p>
          )}
          <button
            onClick={handleSave}
            disabled={updateMutation.isPending || (!!issueDate && !!dueDate && dueDate < issueDate)}
            className="btn-primary flex items-center gap-2 min-h-[44px]"
          >
            {updateMutation.isPending ? (
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Enregistrer
          </button>
        </div>
      )}
    </div>
  )
}
