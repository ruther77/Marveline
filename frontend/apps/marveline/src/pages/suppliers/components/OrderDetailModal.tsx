import { useState } from 'react'
import { Modal } from '@shared/components/ui/Modal'
import { useSupplierOrderMutations } from '@/api/queries/useSupplierOrders'
import { normalizeError } from '@shared/errors/normalizer'
import { formatCents, formatDate } from '@/lib/utils'
import { DomainStatusBadge } from '@shared/components/ui'
import type { SupplierOrder, SupplierOrderReceiptCreate } from '@/types/supplier_order'

interface OrderDetailModalProps {
  order: SupplierOrder | null
  isOpen: boolean
  onClose: () => void
}

export function OrderDetailModal({ order, isOpen, onClose }: OrderDetailModalProps) {
  const { confirm, receive, cancel } = useSupplierOrderMutations()
  const [recvQtys, setRecvQtys] = useState<Record<number, string>>({})
  const [recvDamaged, setRecvDamaged] = useState<Record<number, string>>({})
  const [recvMissing, setRecvMissing] = useState<Record<number, string>>({})
  const [recvNotes, setRecvNotes] = useState('')
  const [error, setError] = useState('')

  if (!order) return null

  const canConfirm = order.status === 'draft'
  const canReceive = order.status === 'ordered' || order.status === 'partially_received'
  const canCancel = order.status !== 'fully_received' && order.status !== 'cancelled'

  const totalCost = order.lines.reduce(
    (acc, l) => acc + l.unit_cost_cents * l.qty_ordered,
    0
  )

  const handleConfirm = async () => {
    setError('')
    try {
      await confirm.mutateAsync(order.id)
    } catch (err) {
      setError(
        normalizeError(err).message || 'Erreur.'
      )
    }
  }

  const handleReceive = async () => {
    setError('')
    const lines = order.lines
      .filter((l) => l.qty_remaining > 0 && recvQtys[l.id])
      .map((l) => {
        const qty = parseInt(recvQtys[l.id]) || 0
        const damaged = parseInt(recvDamaged[l.id] || '0') || 0
        const missing = parseInt(recvMissing[l.id] || '0') || 0
        return {
          line_id: l.id,
          qty_received: qty,
          ...(damaged > 0 ? { qty_damaged: damaged } : {}),
          ...(missing > 0 ? { qty_missing: missing } : {}),
        }
      })
      .filter((l) => l.qty_received > 0)

    if (!lines.length) return setError('Aucune quantite saisie.')

    const payload: SupplierOrderReceiptCreate = {
      lines,
      notes: recvNotes.trim() || undefined,
    }
    try {
      await receive.mutateAsync({ id: order.id, data: payload })
      setRecvQtys({})
      setRecvDamaged({})
      setRecvMissing({})
      setRecvNotes('')
    } catch (err) {
      setError(
        normalizeError(err).message || 'Erreur lors de la reception.'
      )
    }
  }

  const handleCancel = async () => {
    setError('')
    try {
      await cancel.mutateAsync(order.id)
      onClose()
    } catch (err) {
      setError(
        normalizeError(err).message || 'Erreur.'
      )
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Commande ${order.reference}`}>
      <div className="space-y-4">
        {/* Statut + infos */}
        <div className="flex items-center gap-4">
          <DomainStatusBadge status={order.status} />
          <span className="text-sm text-dark-400">
            Fournisseur #{order.supplier_id} · Créée le {formatDate(order.created_at)}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-sm text-dark-300">
          <div>
            <span className="font-medium text-dark-200">Date commande :</span>{' '}
            {formatDate(order.order_date)}
          </div>
          <div>
            <span className="font-medium text-dark-200">Livraison prévue :</span>{' '}
            {formatDate(order.expected_date)}
          </div>
        </div>

        {order.notes && (
          <p className="text-sm text-dark-300 bg-dark-900 rounded-lg p-2">{order.notes}</p>
        )}

        {/* Lignes */}
        <div>
          <p className="text-sm font-medium text-dark-200 mb-2">Lignes ({order.lines.length})</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-dark-400 border-b border-dark-600">
                  <th className="text-left py-1.5">Produit</th>
                  <th className="text-right py-1.5">Commandé</th>
                  <th className="text-right py-1.5">Reçu</th>
                  <th className="text-right py-1.5">Reliquat</th>
                  <th className="text-right py-1.5">P.U. HT</th>
                  {canReceive && (
                    <>
                      <th className="text-right py-1.5">Conforme</th>
                      <th className="text-right py-1.5">Abime</th>
                      <th className="text-right py-1.5">Manquant</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {order.lines.map((line) => (
                  <tr key={line.id} className="border-b border-dark-600">
                    <td className="py-1.5 text-dark-200">{line.product_name || `#${line.product_id}`}</td>
                    <td className="py-1.5 text-right text-dark-200">{line.qty_ordered}</td>
                    <td className="py-1.5 text-right text-green-400">{line.qty_received}</td>
                    <td className="py-1.5 text-right text-amber-400">{line.qty_remaining}</td>
                    <td className="py-1.5 text-right text-dark-200">
                      {formatCents(line.unit_cost_cents)}
                    </td>
                    {canReceive && line.qty_remaining > 0 ? (
                      <>
                        <td className="py-1.5 text-right">
                          <input
                            type="number"
                            min="0"
                            max={line.qty_remaining}
                            className="input w-14 text-right text-xs py-0.5"
                            placeholder={String(line.qty_remaining)}
                            value={recvQtys[line.id] ?? ''}
                            onChange={(e) =>
                              setRecvQtys((p) => ({ ...p, [line.id]: e.target.value }))
                            }
                          />
                        </td>
                        <td className="py-1.5 text-right">
                          <input
                            type="number"
                            min="0"
                            className="input w-14 text-right text-xs py-0.5"
                            placeholder="0"
                            value={recvDamaged[line.id] ?? ''}
                            onChange={(e) =>
                              setRecvDamaged((p) => ({ ...p, [line.id]: e.target.value }))
                            }
                          />
                        </td>
                        <td className="py-1.5 text-right">
                          <input
                            type="number"
                            min="0"
                            className="input w-14 text-right text-xs py-0.5"
                            placeholder="0"
                            value={recvMissing[line.id] ?? ''}
                            onChange={(e) =>
                              setRecvMissing((p) => ({ ...p, [line.id]: e.target.value }))
                            }
                          />
                        </td>
                      </>
                    ) : canReceive ? (
                      <>
                        <td className="py-1.5 text-right text-dark-600">—</td>
                        <td className="py-1.5 text-right text-dark-600">—</td>
                        <td className="py-1.5 text-right text-dark-600">—</td>
                      </>
                    ) : null}
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td
                    colSpan={4}
                    className="py-1.5 text-xs font-medium text-dark-300"
                  >
                    Total HT
                  </td>
                  <td className="py-1.5 text-right text-xs font-medium text-dark-100">
                    {formatCents(totalCost)}
                  </td>
                  {canReceive && <><td /><td /><td /></>}
                </tr>
              </tfoot>
            </table>
          </div>
        </div>

        {/* Bons de reception */}
        {order.receipts.length > 0 && (
          <div>
            <p className="text-sm font-medium text-dark-200 mb-2">
              Bons de reception ({order.receipts.length})
            </p>
            <div className="space-y-3">
              {order.receipts.map((r) => (
                <div key={r.id} className="bg-dark-900 rounded-lg p-3 space-y-2">
                  <div className="flex justify-between text-xs text-dark-400">
                    <span>{new Date(r.received_at).toLocaleString('fr-FR')}</span>
                    {r.notes && <span className="text-dark-500 italic">{r.notes}</span>}
                  </div>
                  {r.receipt_lines && r.receipt_lines.length > 0 && (
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-dark-500 border-b border-dark-700">
                          <th className="text-left py-1">Produit</th>
                          <th className="text-right py-1">Conforme</th>
                          <th className="text-right py-1">Abime</th>
                          <th className="text-right py-1">Manquant</th>
                        </tr>
                      </thead>
                      <tbody>
                        {r.receipt_lines.map((rl) => (
                          <tr key={rl.id} className="border-b border-dark-800">
                            <td className="py-1 text-dark-300">{rl.product_name || `#${rl.product_id}`}</td>
                            <td className="py-1 text-right text-green-400">{rl.qty_received}</td>
                            <td className="py-1 text-right text-red-400">{rl.qty_damaged || 0}</td>
                            <td className="py-1 text-right text-amber-400">{rl.qty_missing || 0}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Zone réception */}
        {canReceive && (
          <div className="bg-primary-500/10 border border-primary-500/20 rounded-lg p-4 space-y-2">
            <p className="text-sm font-medium text-primary-400">Enregistrer une réception</p>
            <textarea
              className="input resize-none"
              placeholder="Notes (optionnel)"
              rows={1}
              value={recvNotes}
              onChange={(e) => setRecvNotes(e.target.value)}
            />
            <button
              onClick={handleReceive}
              disabled={receive.isPending}
              className="px-4 py-1.5 text-sm bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium rounded-lg disabled:opacity-50"
            >
              {receive.isPending ? 'Réception…' : 'Valider la réception'}
            </button>
          </div>
        )}

        {error && (
          <p className="text-sm text-red-400 bg-red-900/20 border border-red-700/30 rounded-lg px-4 py-2">
            {error}
          </p>
        )}

        {/* Actions */}
        <div className="flex justify-between pt-2 border-t border-dark-600">
          <div className="flex gap-2">
            {canConfirm && (
              <button
                onClick={handleConfirm}
                disabled={confirm.isPending}
                className="px-4 py-1.5 text-sm bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium rounded-lg disabled:opacity-50"
              >
                {confirm.isPending ? '…' : 'Confirmer la commande'}
              </button>
            )}
            {canCancel && (
              <button
                onClick={handleCancel}
                disabled={cancel.isPending}
                className="px-4 py-1.5 text-sm border border-dark-600 text-dark-400 hover:text-red-400 hover:border-red-700/50 rounded-lg disabled:opacity-50"
              >
                Annuler
              </button>
            )}
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm text-dark-400 hover:text-dark-50"
          >
            Fermer
          </button>
        </div>
      </div>
    </Modal>
  )
}
