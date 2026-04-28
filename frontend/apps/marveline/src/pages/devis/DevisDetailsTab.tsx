import { useState } from 'react'
import { useParams, useNavigate } from '@tanstack/react-router'
import { useDevisDetail, useSignDevis } from '@/api/queries/useDevis'
import { normalizeError } from '@shared/errors/normalizer'
import { formatCents } from '@/lib/utils'
import { ActionError } from '@shared/components/ui'
import { DevisInfoCard } from './components/DevisInfoCard'
import { DevisLinesTable } from './components/DevisLinesTable'
import { DevisNegotiationSummary } from './components/DevisNegotiationSummary'
import { DevisSignature } from './components/DevisSignature'

export default function DevisDetailsTab() {
  const { id } = useParams({ strict: false }) as { id: string }
  const navigate = useNavigate()
  const devisId = parseInt(id, 10)

  const { data: devis, isLoading } = useDevisDetail(devisId)
  const signMutation = useSignDevis()
  const [signError, setSignError] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div className="space-y-4 animate-pulse">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="card p-6 space-y-4">
            <div className="h-3 skel rounded w-36" />
            <div className="h-3 skel rounded w-52" />
          </div>
        ))}
      </div>
    )
  }

  if (!devis) return null

  return (
    <div className="space-y-6">
      <ActionError message={signError} onDismiss={() => setSignError(null)} />

      <DevisInfoCard devis={devis} />

      <DevisLinesTable devis={devis} />

      {devis.caution_required && (
        <div className="card flex items-center gap-4 bg-amber-900/10 border-amber-700/40">
          <span className="text-amber-400 text-sm">
            Caution requise :{' '}
            <span className="font-medium">{formatCents(devis.caution_amount_cents ?? 0)}</span>
          </span>
        </div>
      )}

      <DevisNegotiationSummary
        entries={devis.negotiations ?? []}
        devisId={devisId}
        onViewAll={() =>
          navigate({ to: '/devis/$id/negotiation', params: { id: String(devisId) } })
        }
      />

      <DevisSignature
        status={devis.status}
        signedAt={devis.signed_at}
        onSign={(dataUrl) =>
          signMutation.mutate(
            { id: devisId, signatureData: dataUrl },
            {
              onError: (err) =>
                setSignError(
                  normalizeError(err).message ||
                    'Erreur lors de la signature.'
                ),
            }
          )
        }
      />
    </div>
  )
}
