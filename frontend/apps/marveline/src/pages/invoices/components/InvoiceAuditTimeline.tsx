import { History } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { formatDate, formatCents } from '@/lib/utils'
import { TimelineAudit } from '@shared/components/ui/TimelineAudit'
import type { TimelineEntry } from '@shared/components/ui/TimelineAudit'
import { PAYMENT_METHOD_LABELS } from '@/lib/constants'
import type { InvoiceDetail, CreditNote } from '@/types/invoice'
import type { Payment } from '@/types/payment'

interface InvoiceAuditTimelineProps {
  invoice: Pick<
    InvoiceDetail,
    | 'id'
    | 'created_at'
    | 'updated_at'
    | 'sent_at'
    | 'first_reminder_sent_at'
    | 'last_reminder_sent_at'
    | 'cancelled_at'
    | 'is_paid'
    | 'payment_date'
  >
  payments: Payment[]
  creditNotes: CreditNote[]
}

export function InvoiceAuditTimeline({ invoice, payments, creditNotes }: InvoiceAuditTimelineProps) {
  const entries: TimelineEntry[] = [
    { date: invoice.created_at, user: '', action: 'Facture créée', type: 'state' },
  ]

  if (invoice.sent_at) {
    entries.push({ date: invoice.sent_at, user: '', action: 'Facture envoyée', type: 'state' })
  }
  if (invoice.first_reminder_sent_at) {
    entries.push({ date: invoice.first_reminder_sent_at, user: '', action: 'Première relance envoyée', type: 'action' })
  }
  if (invoice.last_reminder_sent_at && invoice.last_reminder_sent_at !== invoice.first_reminder_sent_at) {
    entries.push({ date: invoice.last_reminder_sent_at, user: '', action: 'Dernière relance envoyée', type: 'action' })
  }

  payments.forEach((p) => {
    entries.push({
      date: p.payment_date,
      user: '',
      action: `Paiement reçu — ${formatCents(p.amount_cents)}`,
      detail: PAYMENT_METHOD_LABELS[p.payment_method],
      type: 'action',
    })
  })

  creditNotes.forEach((c) => {
    entries.push({
      date: c.issue_date,
      user: '',
      action: `Avoir émis — ${formatCents(c.amount_cents)}`,
      detail: c.reason,
      type: 'note',
    })
  })

  if (invoice.cancelled_at) {
    entries.push({ date: invoice.cancelled_at, user: '', action: 'Facture annulée', type: 'state' })
  } else if (invoice.is_paid) {
    entries.push({ date: invoice.payment_date || invoice.updated_at, user: '', action: 'Facture soldée', type: 'state' })
  }

  return (
    <div className="border-t border-dark-600 pt-4 space-y-2">
      <h4 className="text-sm font-medium text-dark-300 flex items-center gap-2 justify-between">
        <span className="flex items-center gap-2">
          <History className="w-4 h-4" />
          Historique
        </span>
        <Link
          to="/finance/invoices/$id/audit"
          params={{ id: String(invoice.id) }}
          className="text-xs text-primary-400 hover:underline"
        >
          Audit complet →
        </Link>
      </h4>
      <TimelineAudit entries={entries} />
      <div className="pt-2 flex gap-6 text-xs text-dark-500">
        <span>Créé le {formatDate(invoice.created_at)}</span>
        <span>Modifié le {formatDate(invoice.updated_at)}</span>
      </div>
    </div>
  )
}
