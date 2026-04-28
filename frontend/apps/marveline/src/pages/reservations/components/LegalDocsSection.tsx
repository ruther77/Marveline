import { CheckCircle, XCircle, FileText, CreditCard, Shield } from 'lucide-react'
import type { ReservationDetailFull } from '@/types/reservation'
import type { Deposit } from '@/types/deposit'
import { isDepositOk, isSignatureOk } from '../selectors/reservationPhase'

interface LegalDocsSectionProps {
  reservation: ReservationDetailFull
  deposits: Deposit[]
}

/**
 * Affiche l'état des documents contractuels (CGV, caution, clause casse) +
 * checklist signature/caution/pre-check.
 *
 * Remplace l'inline de LegalPage en corrigeant les classes var(--muted) non-DS.
 */
export function LegalDocsSection({ reservation, deposits }: LegalDocsSectionProps) {
  const hasSig = isSignatureOk(reservation)
  const hasDeposit = isDepositOk(reservation, deposits)
  const preCheckItems = reservation.pre_check_items ?? []
  const preCheckedCount = preCheckItems.filter((i) => i.checked).length
  const allPreChecked = preCheckItems.length > 0 && preCheckedCount === preCheckItems.length

  const documents = [
    { label: 'CGV location', detail: hasSig ? 'Signées' : 'Non signées', ok: hasSig, icon: FileText },
    { label: 'Engagement caution', detail: hasDeposit ? 'Encaissée' : 'En attente', ok: hasDeposit, icon: CreditCard },
    { label: 'Clause responsabilité casse', detail: hasSig ? 'Acceptée' : 'En attente', ok: hasSig, icon: Shield },
  ]

  return (
    <div className="space-y-4">
      {/* Checklist 3 conditions */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <ChecklistCard
          label="Signature"
          value={hasSig ? 'Signé' : 'Manquante'}
          color={hasSig ? 'text-green-400' : 'text-red-400'}
        />
        <ChecklistCard
          label="Caution"
          value={hasDeposit ? 'Encaissée' : 'En attente'}
          color={hasDeposit ? 'text-green-400' : 'text-amber-400'}
        />
        <ChecklistCard
          label="Pre-check"
          value={`${preCheckedCount}/${preCheckItems.length} cochés`}
          color={allPreChecked ? 'text-green-400' : 'text-amber-400'}
        />
      </div>

      {/* Documents contractuels */}
      <div className="space-y-2">
        <h3 className="font-medium text-sm text-dark-200">Documents contractuels</h3>
        {documents.map((d) => (
          <div
            key={d.label}
            className="card p-3 flex items-center gap-3"
          >
            {d.ok
              ? <CheckCircle className="w-4 h-4 text-green-400 shrink-0" />
              : <XCircle className="w-4 h-4 text-red-400 shrink-0" />
            }
            <d.icon className="w-4 h-4 text-dark-400 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-dark-100">{d.label}</p>
              <p className="text-xs text-dark-400">{d.detail}</p>
            </div>
            <span
              className={`text-xs px-2 py-0.5 rounded ${
                d.ok ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
              }`}
            >
              {d.ok ? 'OK' : 'Manquant'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ChecklistCard({
  label,
  value,
  color,
}: {
  label: string
  value: string
  color: string
}) {
  return (
    <div className="card p-3">
      <div className="text-xs text-dark-400 mb-1">{label}</div>
      <div className={`text-sm font-medium ${color}`}>{value}</div>
    </div>
  )
}
