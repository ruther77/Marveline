import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { useNavigate, Link } from '@tanstack/react-router'
import { ArrowLeft, Check, ChevronRight, FileText, Search, Shield, Package } from 'lucide-react'
import { useReservationsList, useCreateInvoice, useReservationDetail } from '@/api/queries'
import { formatDate, formatCents } from '@/lib/utils'
import { normalizeError } from '@shared/errors/normalizer'
import { useHasScope } from '@/hooks/useHasScope'
import type { ReservationDetailFull } from '@/types/reservation'

type Step = 1 | 2 | 3
type InvoiceType = 'full' | 'advance' | 'balance'

const INVOICE_TYPE_LABELS: Record<InvoiceType, string> = {
  full: '100% — Facture complète',
  advance: '40% — Acompte',
  balance: '60% — Solde',
}

const INVOICE_TYPE_DESCRIPTIONS: Record<InvoiceType, string> = {
  full: 'Facture du montant total de la réservation',
  advance: 'Acompte de 40% du montant total (CGV)',
  balance: 'Solde de 60% après paiement de l\'acompte',
}

function today() {
  return new Date().toISOString().split('T')[0]
}

function daysFromNow(n: number) {
  const d = new Date()
  d.setDate(d.getDate() + n)
  return d.toISOString().split('T')[0]
}

function StepIndicator({ current, step, label }: { current: Step; step: Step; label: string }) {
  const done = current > step
  const active = current === step
  return (
    <div className="flex items-center gap-2">
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 ${
        done ? 'bg-green-500 text-white' : active ? 'bg-primary-500 text-white' : 'bg-dark-900 text-dark-400'
      }`}>
        {done ? <Check className="w-3.5 h-3.5" /> : step}
      </div>
      <span className={`text-sm hidden sm:block ${active ? 'text-white font-medium' : done ? 'text-dark-300' : 'text-dark-500'}`}>
        {label}
      </span>
    </div>
  )
}

export default function InvoiceCreatePage() {
  const canWrite = useHasScope('invoices:write')
  const navigate = useNavigate()

  // Stepper state
  const [step, setStep] = useState<Step>(1)

  // Step 1 — Réservation
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)

  // Step 2 — Paramétrage
  const [invoiceType, setInvoiceType] = useState<InvoiceType>('full')
  const [issueDate, setIssueDate] = useState(today())
  const [dueDate, setDueDate] = useState(daysFromNow(30))

  const createMutation = useCreateInvoice()
  const [submitError, setSubmitError] = useState<string | null>(null)

  const { data: reservationsData } = useReservationsList({ limit: 100 })
  const allReservations = (reservationsData?.items ?? []).filter(
    (r) => r.status === 'confirmed' || r.status === 'completed'
  )
  const filtered = search
    ? allReservations.filter(
        (r) =>
          r.customer_name?.toLowerCase().includes(search.toLowerCase()) ||
          r.reference?.toLowerCase().includes(search.toLowerCase()) ||
          String(r.id).includes(search)
      )
    : allReservations

  const selected = allReservations.find((r) => r.id === selectedId)
  const { data: detail, isLoading: detailLoading } = useReservationDetail(selectedId)
  const totalCents = detail?.lines?.reduce((s, l) => s + l.subtotal_cents, 0) ?? 0

  const computedAmount = () => {
    if (invoiceType === 'full') return totalCents
    if (invoiceType === 'advance') return Math.ceil(totalCents * 0.4)
    return Math.ceil(totalCents * 0.6)
  }

  if (!canWrite) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <Shield className="w-12 h-12 text-dark-600 mb-4" />
        <h2 className="text-lg font-semibold text-dark-300">Accès restreint</h2>
        <p className="text-sm text-dark-500 mt-2">Vous n&apos;avez pas les droits pour créer des factures.</p>
      </div>
    )
  }

  const handleConfirm = async () => {
    if (!selectedId) return
    setSubmitError(null)
    try {
      await createMutation.mutateAsync({
        reservation_id: selectedId,
        issue_date: issueDate,
        due_date: dueDate,
        invoice_type: invoiceType,
      })
      navigate({ to: '/finance/invoices' })
    } catch (err) {
      setSubmitError(normalizeError(err).message || 'Une erreur est survenue lors de la création')
    }
  }

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6 pb-8">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          to="/finance/invoices"
          aria-label="Retour aux factures"
          className="p-2 hover:bg-dark-900 rounded-lg text-dark-400 hover:text-dark-50 transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <PageHeader title="Nouvelle facture" subtitle="Créer une facture depuis une réservation" />
      </div>

      {/* Stepper */}
      <div className="card p-4">
        <div className="flex items-center gap-3">
          <StepIndicator current={step} step={1} label="Réservation" />
          <ChevronRight className="w-4 h-4 text-dark-600 shrink-0" />
          <StepIndicator current={step} step={2} label="Paramétrage" />
          <ChevronRight className="w-4 h-4 text-dark-600 shrink-0" />
          <StepIndicator current={step} step={3} label="Récapitulatif" />
        </div>
      </div>

      {/* ── STEP 1 — Sélection réservation ─────────────────────────────────── */}
      {step === 1 && (
        <div className="card p-6 space-y-4">
          <h2 className="font-semibold">Choisir une réservation</h2>

          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400 pointer-events-none" />
            <input
              type="text"
              placeholder="Rechercher par client, référence…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input pl-9 w-full"
            />
          </div>

          {filtered.length === 0 ? (
            <div className="text-center py-6 text-sm text-dark-500">
              {search ? 'Aucune réservation trouvée.' : 'Aucune réservation confirmée ou terminée disponible.'}
            </div>
          ) : (
            <div className="border border-dark-600 rounded-xl overflow-hidden max-h-72 overflow-y-auto divide-y divide-dark-600">
              {filtered.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setSelectedId(r.id === selectedId ? null : r.id)}
                  className={`w-full text-left px-4 py-3.5 flex items-center justify-between hover:bg-dark-900/60 transition-colors min-h-[44px] ${
                    r.id === selectedId ? 'bg-primary-600/15 border-l-2 border-primary-500' : ''
                  }`}
                >
                  <div>
                    <p className="text-sm font-medium">{r.customer_name || `Client #${r.customer_id}`}</p>
                    <p className="text-xs text-dark-500">
                      {r.reference} · Événement le {formatDate(r.event_date)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      r.status === 'confirmed' ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'
                    }`}>
                      {r.status === 'confirmed' ? 'Confirmée' : 'Terminée'}
                    </span>
                    {r.id === selectedId && <Check className="w-4 h-4 text-primary-400" />}
                  </div>
                </button>
              ))}
            </div>
          )}

          {selected && (
            <div className="p-4 bg-primary-600/10 border border-primary-600/30 rounded-lg text-sm space-y-1">
              <p className="font-medium text-primary-400">
                {selected.reference} — {selected.customer_name}
              </p>
              <p className="text-dark-400">
                Livraison : {formatDate(selected.delivery_date)} → Retour : {formatDate(selected.return_date)}
              </p>
              <p className="text-dark-400">
                Montant réservation : <span className="font-medium text-white">{formatCents(selected.total_amount_cents)}</span>
              </p>
            </div>
          )}

          <div className="flex justify-end pt-2">
            <button
              onClick={() => setStep(2)}
              disabled={!selectedId}
              className="btn-primary flex items-center gap-2 min-h-[44px]"
            >
              Suivant
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 2 — Paramétrage ───────────────────────────────────────────── */}
      {step === 2 && (
        <div className="card p-6 space-y-6">
          <h2 className="font-semibold">Paramétrer la facture</h2>

          {/* Type de facturation */}
          <div className="space-y-2">
            <label className="block text-sm text-dark-400">Type de facture *</label>
            <div className="space-y-2">
              {(Object.keys(INVOICE_TYPE_LABELS) as InvoiceType[]).map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setInvoiceType(type)}
                  className={`w-full text-left p-4 rounded-xl border transition-colors min-h-[44px] ${
                    invoiceType === type
                      ? 'border-primary-500 bg-primary-600/10'
                      : 'border-dark-600 hover:border-dark-600'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium">{INVOICE_TYPE_LABELS[type]}</p>
                      <p className="text-xs text-dark-400 mt-0.5">{INVOICE_TYPE_DESCRIPTIONS[type]}</p>
                    </div>
                    {invoiceType === type && (
                      <Check className="w-4 h-4 text-primary-400 shrink-0 ml-4" />
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Aperçu montant */}
          {totalCents > 0 && (
            <div className="p-4 bg-dark-900 rounded-xl border border-dark-600 text-sm">
              <div className="flex justify-between items-center">
                <span className="text-dark-400">Montant total réservation</span>
                <span>{formatCents(totalCents)}</span>
              </div>
              <div className="flex justify-between items-center mt-2 font-semibold text-base">
                <span className="text-dark-300">Montant facturé</span>
                <span className="text-primary-400">{formatCents(computedAmount())}</span>
              </div>
            </div>
          )}

          {/* Dates */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1.5">Date d&apos;émission *</label>
              <input
                type="date"
                value={issueDate}
                onChange={(e) => setIssueDate(e.target.value)}
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1.5">Date d&apos;échéance *</label>
              <input
                type="date"
                value={dueDate}
                min={issueDate || undefined}
                onChange={(e) => setDueDate(e.target.value)}
                className="input w-full"
              />
            </div>
          </div>
          {issueDate && dueDate && dueDate < issueDate && (
            <p className="text-sm text-red-400">La date d&apos;échéance doit être après la date d&apos;émission.</p>
          )}

          <div className="flex justify-between pt-2">
            <button onClick={() => setStep(1)} className="btn-secondary flex items-center gap-2 min-h-[44px]">
              <ArrowLeft className="w-4 h-4" />
              Retour
            </button>
            <button
              onClick={() => setStep(3)}
              disabled={!issueDate || !dueDate || dueDate < issueDate}
              className="btn-primary flex items-center gap-2 min-h-[44px]"
            >
              Récapitulatif
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 3 — Récapitulatif ─────────────────────────────────────────── */}
      {step === 3 && selected && (
        <div className="space-y-4">
          <div className="card p-6 space-y-4">
            <h2 className="font-semibold">Récapitulatif</h2>

            <div className="divide-y divide-dark-600 text-sm">
              <div className="flex justify-between py-3">
                <span className="text-dark-400">Réservation</span>
                <span className="font-medium">{selected.reference} — {selected.customer_name}</span>
              </div>
              <div className="flex justify-between py-3">
                <span className="text-dark-400">Type</span>
                <span>{INVOICE_TYPE_LABELS[invoiceType]}</span>
              </div>
              <div className="flex justify-between py-3">
                <span className="text-dark-400">Date d&apos;émission</span>
                <span>{formatDate(issueDate)}</span>
              </div>
              <div className="flex justify-between py-3">
                <span className="text-dark-400">Date d&apos;échéance</span>
                <span>{formatDate(dueDate)}</span>
              </div>
              <div className="flex justify-between py-3 font-semibold text-base">
                <span>Montant facturé</span>
                <span className="text-primary-400">{formatCents(computedAmount())}</span>
              </div>
            </div>
          </div>

          {/* Lignes de la réservation */}
          {selectedId && (
            <div className="card p-6 space-y-3">
              <h3 className="text-sm font-semibold text-dark-400 uppercase tracking-wide">Lignes incluses</h3>
              {detailLoading ? (
                <div className="animate-pulse space-y-2">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-8 skel rounded" />
                  ))}
                </div>
              ) : detail?.lines && detail.lines.length > 0 ? (
                <div className="border border-dark-600 rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-dark-900">
                      <tr>
                        <th className="text-left px-4 py-2 text-dark-400 font-medium">Produit</th>
                        <th className="text-right px-4 py-2 text-dark-400 font-medium">Qté</th>
                        <th className="text-right px-4 py-2 text-dark-400 font-medium hidden sm:table-cell">P.U.</th>
                        <th className="text-right px-4 py-2 text-dark-400 font-medium">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-dark-600">
                      {detail.lines.map((line) => {
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
                        </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-dark-500">Aucune ligne sur cette réservation.</p>
              )}

              {(detail as ReservationDetailFull | undefined)?.devis_id && (
                <p className="text-xs text-dark-500 flex items-center gap-1">
                  <FileText className="w-3 h-3" />
                  Issue du devis #{(detail as ReservationDetailFull).devis_id}
                </p>
              )}
            </div>
          )}

          {submitError && (
            <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-sm text-red-400">
              {submitError}
            </div>
          )}

          <div className="flex justify-between">
            <button onClick={() => setStep(2)} className="btn-secondary flex items-center gap-2 min-h-[44px]">
              <ArrowLeft className="w-4 h-4" />
              Modifier
            </button>
            <button
              onClick={handleConfirm}
              disabled={createMutation.isPending}
              className="btn-primary flex items-center gap-2 min-h-[44px]"
            >
              {createMutation.isPending ? (
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <FileText className="w-4 h-4" />
              )}
              {createMutation.isPending ? 'Création…' : 'Créer la facture'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
