import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { useDeliveryZonesList } from '@/api/queries'
import { useMultiModal } from '@/hooks/useModal'
import { DeliveryZoneFormModal, DeliveryZoneDeleteModal } from './components'
import { NoData, ErrorState } from '@shared/components/ui/EmptyState'
import type { DeliveryZone } from '@/types/delivery_zone'
import { MapPin, Plus, Edit, Trash2, MoreVertical } from 'lucide-react'
import { formatCents } from '@/lib/utils'

type ModalType = 'create' | 'edit' | 'delete'

function formatDeliveryFee(cents: number): string {
  if (cents === 0) return 'Sur devis'
  return formatCents(cents)
}

export default function DeliveryZonesPage() {
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)
  const modal = useMultiModal<DeliveryZone>()

  const { data: zones, isLoading, error, refetch } = useDeliveryZonesList()

  const handleOpenModal = (type: ModalType, zone?: DeliveryZone) => {
    setOpenMenuId(null)
    modal.open(type, zone)
  }

  const ZoneMenu = ({ zone }: { zone: DeliveryZone }) => (
    <div className="relative shrink-0">
      <button
        onClick={() => setOpenMenuId(openMenuId === zone.id ? null : zone.id)}
        className="p-1 hover:bg-dark-600 rounded min-h-[44px] min-w-[44px] flex items-center justify-center"
      >
        <MoreVertical className="w-4 h-4" />
      </button>
      {openMenuId === zone.id && (
        <>
          <div className="fixed inset-0 z-10" aria-hidden="true" onClick={() => setOpenMenuId(null)} />
          <div className="absolute right-0 mt-2 w-48 dropdown-menu">
            <button
              onClick={() => handleOpenModal('edit', zone)}
              className="w-full px-4 py-2 text-left hover:bg-dark-600 flex items-center gap-2 first:rounded-t-lg text-sm"
            >
              <Edit className="w-4 h-4" />
              Modifier
            </button>
            <button
              onClick={() => handleOpenModal('delete', zone)}
              className="w-full px-4 py-2 text-left hover:bg-dark-600 flex items-center gap-2 text-red-500 last:rounded-b-lg text-sm"
            >
              <Trash2 className="w-4 h-4" />
              Supprimer
            </button>
          </div>
        </>
      )}
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <PageHeader title="Zones de livraison" subtitle="Frais de livraison par département" />
        <button
          onClick={() => handleOpenModal('create')}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">Nouvelle zone</span>
        </button>
      </div>

      {/* Liste */}
      <div className="card p-0">
        {isLoading ? (
          <div className="divide-y divide-dark-600 animate-pulse">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 px-4 py-4">
                <div className="flex-1 space-y-2">
                  <div className="h-3 skel rounded w-36" />
                  <div className="h-2 skel rounded w-52" />
                </div>
                <div className="h-3 skel rounded w-16 shrink-0" />
                <div className="flex gap-2 shrink-0">
                  <div className="w-7 h-7 skel rounded" />
                  <div className="w-7 h-7 skel rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : error ? (
          <ErrorState onRetry={() => refetch()} />
        ) : !zones || zones.length === 0 ? (
          <div className="p-6">
            <NoData
              onAction={() => handleOpenModal('create')}
              actionLabel="Nouvelle zone"
            />
          </div>
        ) : (
          <>
            {/* Vue mobile */}
            <div className="sm:hidden">
              {zones.map((zone) => (
                <div
                  key={zone.id}
                  className="flex items-center justify-between px-4 py-4 border-b border-dark-600 last:border-0"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <MapPin className="w-3.5 h-3.5 text-primary-400 shrink-0" />
                      <span className="font-mono text-sm font-semibold text-primary-400">
                        {zone.department_code}
                      </span>
                      <span className="text-sm truncate">{zone.department_name}</span>
                    </div>
                    <div className="text-xs text-dark-400 mt-0.5">
                      {zone.delivery_fee_cents === 0 ? (
                        <span className="italic">Sur devis</span>
                      ) : (
                        formatDeliveryFee(zone.delivery_fee_cents)
                      )}
                      {zone.sunday_surcharge_cents > 0 && (
                        <span className="ml-2 text-dark-500">
                          +{formatCents(zone.sunday_surcharge_cents)} dim.
                        </span>
                      )}
                      {' · '}
                      {zone.is_active ? (
                        <span className="text-green-400">Active</span>
                      ) : (
                        <span className="text-dark-500">Inactive</span>
                      )}
                    </div>
                  </div>
                  <ZoneMenu zone={zone} />
                </div>
              ))}
            </div>

            {/* Vue desktop */}
            <div className="hidden sm:block overflow-x-visible">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-dark-600">
                    <th className="text-left px-4 py-4 text-sm font-medium text-dark-400">Dept</th>
                    <th className="text-left px-4 py-4 text-sm font-medium text-dark-400">Département</th>
                    <th className="text-left px-4 py-4 text-sm font-medium text-dark-400">Livraison</th>
                    <th className="text-left px-4 py-4 text-sm font-medium text-dark-400">Supplément dim.</th>
                    <th className="text-left px-4 py-4 text-sm font-medium text-dark-400 hidden md:table-cell">Notes</th>
                    <th className="text-left px-4 py-4 text-sm font-medium text-dark-400">Statut</th>
                    <th className="px-4 py-4" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-600/50">
                  {zones.map((zone) => (
                    <tr key={zone.id} className="hover:bg-dark-900/50">
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-2">
                          <MapPin className="w-4 h-4 text-primary-400 shrink-0" />
                          <span className="font-mono text-sm font-semibold">
                            {zone.department_code}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-sm">{zone.department_name}</td>
                      <td className="px-4 py-4 text-sm">
                        <span className={zone.delivery_fee_cents === 0 ? 'text-dark-400 italic' : ''}>
                          {formatDeliveryFee(zone.delivery_fee_cents)}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-sm">
                        {zone.sunday_surcharge_cents === 0 ? (
                          <span className="text-dark-500">—</span>
                        ) : (
                          <span>+{formatCents(zone.sunday_surcharge_cents)}</span>
                        )}
                      </td>
                      <td className="px-4 py-4 text-sm text-dark-400 hidden md:table-cell max-w-xs truncate">
                        {zone.notes || '—'}
                      </td>
                      <td className="px-4 py-4">
                        {zone.is_active ? (
                          <span className="px-2 py-0.5 bg-green-500/10 text-green-400 text-xs rounded-full">
                            Active
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 bg-dark-900 text-dark-400 text-xs rounded-full">
                            Inactive
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex justify-end">
                          <ZoneMenu zone={zone} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {/* Modals */}
      <DeliveryZoneFormModal
        isOpen={modal.isOpen('create') || modal.isOpen('edit')}
        onClose={modal.close}
        zone={modal.data}
        mode={modal.isOpen('edit') ? 'edit' : 'create'}
      />

      <DeliveryZoneDeleteModal
        isOpen={modal.isOpen('delete')}
        onClose={modal.close}
        zone={modal.data}
      />
    </div>
  )
}
