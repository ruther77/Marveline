import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { invoicesApi } from '@/api/invoices'
import { useMultiModal } from '@/hooks/useModal'
import { InvoiceDetailModal } from './components'
import type { InvoiceListItem, InvoiceStatus } from '@/types/invoice'
import {
  FileText,
  Eye,
  XCircle,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { cn, formatDate } from '@/lib/utils'

type ModalType = 'details'

const STATUS_LABELS: Record<InvoiceStatus, string> = {
  draft: 'Brouillon',
  sent: 'Envoyee',
  paid: 'Payee',
  overdue: 'En retard',
  cancelled: 'Annulee',
}

const STATUS_COLORS: Record<InvoiceStatus, string> = {
  draft: 'bg-dark-700 text-dark-300',
  sent: 'bg-blue-500/10 text-blue-500',
  paid: 'bg-green-500/10 text-green-500',
  overdue: 'bg-red-500/10 text-red-500',
  cancelled: 'bg-dark-700 text-dark-400',
}

function formatEuros(cents: number): string {
  return (cents / 100).toFixed(2) + ' EUR'
}

export default function InvoicesPage() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | ''>('')
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)
  const queryClient = useQueryClient()

  const modal = useMultiModal<InvoiceListItem>()

  const { data, isLoading } = useQuery({
    queryKey: ['invoices', page, statusFilter],
    queryFn: () =>
      invoicesApi.getInvoices({
        page,
        page_size: 20,
        status: statusFilter || undefined,
      }),
  })

  const cancelMutation = useMutation({
    mutationFn: (id: number) => invoicesApi.cancelInvoice(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
  })

  const invoices = data?.items || []
  const totalPages = data?.total_pages || 1

  const handleOpenModal = (type: ModalType, invoice?: InvoiceListItem) => {
    setOpenMenuId(null)
    modal.open(type, invoice as InvoiceListItem)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Factures</h1>
        <p className="text-dark-400 mt-1">
          Consultez et gerez les factures clients
        </p>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex gap-4 flex-wrap">
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as InvoiceStatus | '')
              setPage(1)
            }}
            className="input"
          >
            <option value="">Tous les statuts</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          {statusFilter && (
            <button
              onClick={() => {
                setStatusFilter('')
                setPage(1)
              }}
              className="btn-secondary"
            >
              Reinitialiser
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Numero
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Date emission
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Echeance
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Statut
                </th>
                <th className="text-right py-3 px-4 text-sm font-medium text-dark-400">
                  Total
                </th>
                <th className="text-right py-3 px-4 text-sm font-medium text-dark-400">
                  Paye
                </th>
                <th className="text-right py-3 px-4 text-sm font-medium text-dark-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-dark-400">
                    Chargement...
                  </td>
                </tr>
              ) : invoices.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-dark-400">
                    <FileText className="w-10 h-10 mx-auto mb-2 text-dark-600" />
                    Aucune facture trouvee
                  </td>
                </tr>
              ) : (
                invoices.map((invoice) => (
                  <tr
                    key={invoice.id}
                    className="border-b border-dark-700 hover:bg-dark-800/50"
                  >
                    <td className="py-3 px-4">
                      <span className="font-mono text-sm text-primary-400">
                        {invoice.invoice_number}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm">
                        {formatDate(invoice.issue_date)}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={cn(
                        'text-sm',
                        invoice.is_overdue && 'text-red-400 font-medium'
                      )}>
                        {formatDate(invoice.due_date)}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={cn(
                          'inline-flex items-center px-2 py-1 rounded text-xs',
                          STATUS_COLORS[invoice.status]
                        )}
                      >
                        {STATUS_LABELS[invoice.status]}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className="text-sm font-medium">
                        {formatEuros(invoice.total_amount_cents)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className={cn(
                        'text-sm',
                        invoice.is_paid ? 'text-green-400' : 'text-dark-400'
                      )}>
                        {formatEuros(invoice.paid_amount_cents)}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end">
                        <div className="relative">
                          <button
                            onClick={() =>
                              setOpenMenuId(
                                openMenuId === invoice.id ? null : invoice.id
                              )
                            }
                            className="p-1 hover:bg-dark-700 rounded"
                          >
                            <MoreVertical className="w-4 h-4" />
                          </button>

                          {openMenuId === invoice.id && (
                            <>
                              <div
                                className="fixed inset-0 z-10"
                                onClick={() => setOpenMenuId(null)}
                              />
                              <div className="absolute right-0 mt-2 w-48 bg-dark-800 border border-dark-700 rounded-lg shadow-lg z-20">
                                <button
                                  onClick={() =>
                                    handleOpenModal('details', invoice)
                                  }
                                  className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 first:rounded-t-lg"
                                >
                                  <Eye className="w-4 h-4" />
                                  Voir details
                                </button>
                                {invoice.status !== 'paid' && invoice.status !== 'cancelled' && (
                                  <button
                                    onClick={() => {
                                      setOpenMenuId(null)
                                      cancelMutation.mutate(invoice.id)
                                    }}
                                    className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 text-red-500 last:rounded-b-lg"
                                  >
                                    <XCircle className="w-4 h-4" />
                                    Annuler
                                  </button>
                                )}
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-dark-700">
            <div className="text-sm text-dark-400">
              Page {page} sur {totalPages} ({data?.total || 0} resultats)
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      <InvoiceDetailModal
        isOpen={modal.isOpen('details')}
        onClose={modal.close}
        invoiceId={modal.data?.id}
      />
    </div>
  )
}
