import { useEffect, useState } from 'react'
import { TrendingUp, Mail, Loader2 } from 'lucide-react'
import { useClientRFM, useSendRfmCampaign } from '@/api/queries/useCustomers'
import { RFMMatrix } from '@/components/RFMMatrix'
import { formatCents } from '@/lib/utils'
import { normalizeError } from '@shared/errors/normalizer'
import { useToast } from '@/hooks'
import type { RFMSegment } from '@/types/customer'

export default function ClientsRFMPage() {
  const { data, isLoading } = useClientRFM()
  const [selectedSegment, setSelectedSegment] = useState<RFMSegment | null>(null)
  const [campaignSubject, setCampaignSubject] = useState('')
  const [campaignMessage, setCampaignMessage] = useState('')
  const [attemptedSubmit, setAttemptedSubmit] = useState(false)
  const toast = useToast()
  const campaignMutation = useSendRfmCampaign()

  const runCampaign = (payload: { segment: string; subject: string; message: string }) => {
    campaignMutation.mutate(payload, {
      onSuccess: (res) => {
        const msg = `${res.sent_count} email(s) envoyé(s)${res.failed_count > 0 ? `, ${res.failed_count} échec(s)` : ''}`
        if (res.failed_count > 0) {
          toast.error('Campagne partiellement envoyée', msg)
        } else {
          toast.success('Campagne envoyée', msg)
        }
      },
      onError: (err) => {
        toast.error('Erreur campagne', normalizeError(err).message || 'Erreur lors de l\'envoi')
      },
    })
  }

  const items = data?.items ?? []
  const filtered = selectedSegment
    ? items.filter((c) => c.segment === selectedSegment)
    : items
  const selectedRecipientsCount = selectedSegment
    ? items.filter((c) => c.segment === selectedSegment).length
    : 0

  useEffect(() => {
    if (!selectedSegment) return
    setCampaignSubject(`Offre spéciale — ${selectedSegment}`)
    setCampaignMessage(`Nous avons une offre exclusive pour nos clients ${selectedSegment}. Contactez-nous pour en savoir plus !`)
    setAttemptedSubmit(false)
  }, [selectedSegment])

  const normalizedSubject = campaignSubject.trim()
  const normalizedMessage = campaignMessage.trim()
  const subjectValid = normalizedSubject.length >= 3 && normalizedSubject.length <= 200
  const messageValid = normalizedMessage.length >= 10 && normalizedMessage.length <= 5000
  const canSendCampaign =
    !!selectedSegment &&
    selectedRecipientsCount > 0 &&
    subjectValid &&
    messageValid &&
    !campaignMutation.isPending

  const subjectError = attemptedSubmit && !subjectValid
    ? 'Le sujet doit contenir entre 3 et 200 caractères.'
    : null
  const messageError = attemptedSubmit && !messageValid
    ? 'Le message doit contenir entre 10 et 5000 caractères.'
    : null

  const handleCampaignSubmit = () => {
    setAttemptedSubmit(true)
    if (!selectedSegment) {
      toast.error('Campagne RFM', 'Sélectionnez un segment avant envoi.')
      return
    }
    if (selectedRecipientsCount === 0) {
      toast.warning('Campagne RFM', 'Aucun destinataire dans ce segment.')
      return
    }
    if (!subjectValid || !messageValid) {
      toast.error('Campagne invalide', 'Corrigez le sujet et le message avant envoi.')
      return
    }
    runCampaign({
      segment: selectedSegment,
      subject: normalizedSubject,
      message: normalizedMessage,
    })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold flex items-center gap-2 min-w-0">
          <TrendingUp className="w-5 h-5 text-gold-400" />
          Analyse RFM
        </h1>
        {data && (
          <div className="flex items-center gap-4">
            <span className="text-sm text-dark-400">{data.total} client(s) analysé(s)</span>
            {selectedSegment && (
              <span className="text-xs px-2 py-1 rounded-full border border-primary-700/40 text-primary-300">
                {selectedRecipientsCount} destinataire(s) · {selectedSegment}
              </span>
            )}
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-4 animate-pulse">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="card p-4 space-y-2">
                <div className="h-3 skel rounded w-20" />
                <div className="h-7 skel rounded w-10" />
              </div>
            ))}
          </div>
          <div className="card divide-y divide-dark-600">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 px-4 py-4">
                <div className="flex-1 space-y-2">
                  <div className="h-3 skel rounded w-36" />
                  <div className="h-2 skel rounded w-24" />
                </div>
                <div className="h-5 skel rounded w-16 shrink-0" />
                <div className="h-3 skel rounded w-20 shrink-0" />
              </div>
            ))}
          </div>
        </div>
      ) : items.length === 0 ? (
        <div className="card text-center py-10">
          <TrendingUp className="w-10 h-10 text-dark-500 mx-auto mb-4" />
          <p className="font-medium">Aucune donnée RFM disponible</p>
          <p className="text-dark-400 text-sm mt-1">Des données client et facturation sont nécessaires</p>
        </div>
      ) : (
        <>
          {/* Matrice */}
          <RFMMatrix
            items={items}
            selectedSegment={selectedSegment}
            onSegmentClick={setSelectedSegment}
          />

          {/* Filtre actif */}
          {selectedSegment && (
            <div className="flex items-center gap-2 text-sm text-dark-300">
              Segment affiché :
              <span className="font-medium">{selectedSegment}</span>
              <button
                onClick={() => setSelectedSegment(null)}
                className="text-xs text-gold-400 hover:text-gold-300 ml-1"
              >
                Effacer le filtre
              </button>
            </div>
          )}

          {selectedSegment && (
            <div className="card space-y-4">
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-primary-400" />
                <h2 className="text-sm font-semibold">Campagne RFM</h2>
              </div>
              <p className="text-xs text-dark-400">
                Segment cible: <span className="text-dark-200">{selectedSegment}</span> · {selectedRecipientsCount} destinataire(s)
              </p>
              <div className="space-y-1">
                <label className="text-xs text-dark-400">Sujet</label>
                <input
                  type="text"
                  value={campaignSubject}
                  onChange={(e) => setCampaignSubject(e.target.value)}
                  className={subjectError ? 'input w-full border-red-700/60' : 'input w-full'}
                  placeholder="Sujet de la campagne"
                />
                {subjectError && <p className="text-xs text-red-400">{subjectError}</p>}
              </div>
              <div className="space-y-1">
                <label className="text-xs text-dark-400">Message</label>
                <textarea
                  value={campaignMessage}
                  onChange={(e) => setCampaignMessage(e.target.value)}
                  className={messageError ? 'input w-full min-h-24 border-red-700/60' : 'input w-full min-h-24'}
                  placeholder="Message envoyé aux clients du segment"
                />
                {messageError && <p className="text-xs text-red-400">{messageError}</p>}
              </div>
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={handleCampaignSubmit}
                  disabled={!canSendCampaign}
                  className="btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {campaignMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Mail className="w-4 h-4" />
                  )}
                  Envoyer la campagne
                </button>
              </div>
            </div>
          )}

          {/* Table clients */}
          <div className="card p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-dark-600 text-dark-400 text-xs">
                  <th className="text-left px-4 py-4 font-medium">Client</th>
                  <th className="text-left px-4 py-4 font-medium hidden sm:table-cell">Récence</th>
                  <th className="text-left px-4 py-4 font-medium hidden md:table-cell">Fréquence</th>
                  <th className="text-left px-4 py-4 font-medium hidden md:table-cell">CA total</th>
                  <th className="text-left px-4 py-4 font-medium">Segment</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-dark-400">
                      Aucun client dans ce segment
                    </td>
                  </tr>
                ) : (
                  filtered.map((c) => (
                    <tr key={c.customer_id} className="border-b border-dark-600/50 hover:bg-dark-600/20">
                      <td className="px-4 py-4 font-medium">{c.customer_name}</td>
                      <td className="px-4 py-4 text-dark-300 hidden sm:table-cell">
                        {c.recency_days >= 9999 ? '—' : `${c.recency_days}j`}
                      </td>
                      <td className="px-4 py-4 text-dark-300 hidden md:table-cell">
                        {c.frequency} commande(s)
                      </td>
                      <td className="px-4 py-4 text-dark-300 hidden md:table-cell">
                        {formatCents(c.monetary_cents)}
                      </td>
                      <td className="px-4 py-4">
                        <span className="text-xs px-2 py-0.5 rounded-full bg-dark-900 text-dark-200">
                          {c.segment}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

    </div>
  )
}
