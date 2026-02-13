import { useQuery } from '@tanstack/react-query'
import { eventsApi } from '@/api/events'
import { Modal } from '@/components/ui/Modal'
import { formatDate } from '@/lib/utils'
import { Calendar, MapPin, Users, Package, Plus, Edit, Trash2 } from 'lucide-react'
import { useMultiModal } from '@/hooks/useModal'
import { EventItemFormModal } from './EventItemFormModal'
import { EventItemDeleteModal } from './EventItemDeleteModal'
import type { EventItem } from '@/types/event'

interface EventDetailsModalProps {
  isOpen: boolean
  onClose: () => void
  eventId?: number
}

type ModalType = 'create' | 'edit' | 'delete'

export function EventDetailsModal({ isOpen, onClose, eventId }: EventDetailsModalProps) {
  const modal = useMultiModal<EventItem>()

  const { data: event, isLoading } = useQuery({
    queryKey: ['event', eventId],
    queryFn: () => eventsApi.getEvent(eventId!),
    enabled: isOpen && !!eventId,
  })

  const handleOpenModal = (type: ModalType, item?: EventItem) => {
    modal.open(type, item)
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Détails de l'événement"
      size="lg"
    >
      {isLoading ? (
        <div className="text-center py-8 text-dark-400">Chargement...</div>
      ) : event ? (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-dark-400">Client</label>
              <p className="font-medium mt-1">{event.customer_name}</p>
              {event.customer_email && <p className="text-sm text-dark-400">{event.customer_email}</p>}
            </div>

            <div>
              <label className="text-sm text-dark-400">Type</label>
              <p className="font-medium mt-1">{event.event_type}</p>
            </div>

            <div>
              <label className="text-sm text-dark-400">Date événement</label>
              <div className="flex items-center gap-2 mt-1">
                <Calendar className="w-4 h-4 text-dark-400" />
                <span>{formatDate(event.event_date)}</span>
              </div>
            </div>

            {event.guest_count && (
              <div>
                <label className="text-sm text-dark-400">Invités</label>
                <div className="flex items-center gap-2 mt-1">
                  <Users className="w-4 h-4 text-dark-400" />
                  <span>{event.guest_count} personnes</span>
                </div>
              </div>
            )}

            {event.event_location && (
              <div className="col-span-2">
                <label className="text-sm text-dark-400">Lieu</label>
                <div className="flex items-center gap-2 mt-1">
                  <MapPin className="w-4 h-4 text-dark-400" />
                  <span>{event.event_location}</span>
                </div>
              </div>
            )}
          </div>

          <div className="border-t border-dark-700 pt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-medium flex items-center gap-2">
                <Package className="w-4 h-4" />
                Articles ({event.items?.length || 0})
              </h3>
              <button
                onClick={() => handleOpenModal('create')}
                className="btn-primary btn-sm flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Ajouter un article
              </button>
            </div>
            {event.items && event.items.length > 0 ? (
              <div className="space-y-2">
                {event.items.map((item) => (
                  <div key={item.id} className="p-3 bg-dark-800 rounded-lg border border-dark-700">
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm text-dark-400">
                            {item.product_id ? 'Produit' : 'Formule'} #{item.product_id || item.bundle_id}
                          </span>
                        </div>
                        <div className="text-sm">
                          <span className="text-dark-300">Quantité: </span>
                          <span className="font-medium">{item.quantity}</span>
                          <span className="text-dark-400"> × </span>
                          <span className="font-medium">{Number(item.unit_price).toFixed(2)} €</span>
                        </div>
                        {item.cleaning_fee > 0 && (
                          <div className="text-sm text-blue-400">
                            + Frais nettoyage: {Number(item.cleaning_fee).toFixed(2)} €
                          </div>
                        )}
                        {item.notes && (
                          <div className="text-sm text-dark-400 mt-1 italic">
                            {item.notes}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="text-right space-y-1">
                          <div className="text-xs text-dark-400">
                            HT: {Number(item.total_price).toFixed(2)} €
                          </div>
                          <div className="text-xs text-dark-400">
                            TVA ({Number(item.tax_rate || 20).toFixed(0)}%): {(Number(item.total_price) * Number(item.tax_rate || 20) / 100).toFixed(2)} €
                          </div>
                          <div className="text-green-500 font-bold">
                            {(Number(item.total_price) * (1 + Number(item.tax_rate || 20) / 100)).toFixed(2)} € TTC
                          </div>
                        </div>
                        <div className="flex gap-1">
                          <button
                            onClick={() => handleOpenModal('edit', item)}
                            className="p-1 hover:bg-dark-700 rounded text-dark-400 hover:text-primary-500"
                            title="Modifier"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleOpenModal('delete', item)}
                            className="p-1 hover:bg-dark-700 rounded text-dark-400 hover:text-red-500"
                            title="Supprimer"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 border border-dashed border-dark-700 rounded-lg">
                <Package className="w-12 h-12 text-dark-600 mx-auto mb-2" />
                <p className="text-sm text-dark-400 mb-3">Aucun article ajouté</p>
                <button
                  onClick={() => handleOpenModal('create')}
                  className="btn-primary btn-sm"
                >
                  Ajouter le premier article
                </button>
              </div>
            )}
          </div>

          <div className="border-t border-dark-700 pt-4 space-y-2">
            <div className="flex justify-between text-sm text-dark-300">
              <span>Total HT</span>
              <span>{Number(event.total_amount).toFixed(2)} €</span>
            </div>
            <div className="flex justify-between text-sm text-dark-300">
              <span>TVA</span>
              <span>
                {(() => {
                  const totalTVA = event.items.reduce((sum, item) => {
                    return sum + (Number(item.total_price) * Number(item.tax_rate || 20) / 100)
                  }, 0)
                  return totalTVA.toFixed(2)
                })()} €
              </span>
            </div>
            <div className="flex justify-between items-center text-lg font-bold border-t border-dark-700 pt-2">
              <span>Total TTC</span>
              <span className="text-green-500">
                {(() => {
                  const totalTTC = event.items.reduce((sum, item) => {
                    const itemTTC = Number(item.total_price) * (1 + Number(item.tax_rate || 20) / 100)
                    return sum + itemTTC
                  }, 0)
                  return totalTTC.toFixed(2)
                })()} €
              </span>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-dark-400">Événement introuvable</div>
      )}

      {/* Modals de gestion des articles */}
      {eventId && (
        <>
          <EventItemFormModal
            isOpen={modal.isOpen('create') || modal.isOpen('edit')}
            onClose={modal.close}
            eventId={eventId}
            item={modal.data}
            mode={modal.isOpen('edit') ? 'edit' : 'create'}
          />

          <EventItemDeleteModal
            isOpen={modal.isOpen('delete')}
            onClose={modal.close}
            eventId={eventId}
            item={modal.data}
          />
        </>
      )}
    </Modal>
  )
}
