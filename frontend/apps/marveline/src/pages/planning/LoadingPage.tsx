import { Link, useParams } from '@tanstack/react-router'
import { ArrowLeft, Package, Truck, Weight, AlertCircle } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/fetchClient'
import type { LoadingResponse } from '@/types/planning'

function useLoadingView(reservationId: number) {
  return useQuery({
    queryKey: ['planning', 'loading', reservationId],
    queryFn: () => api.get<LoadingResponse>(`/planning/loading/${reservationId}`),
    enabled: reservationId > 0,
  })
}

export default function LoadingPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const reservationId = Number(id)
  const { data, isLoading, error } = useLoadingView(reservationId)

  if (isLoading) {
    return (
      <div className="p-4 md:p-6 max-w-3xl mx-auto space-y-4 animate-pulse">
        <div className="h-6 bg-dark-700 rounded w-64" />
        <div className="card p-4 space-y-3">
          <div className="h-4 bg-dark-700 rounded w-48" />
          <div className="h-4 bg-dark-700 rounded w-32" />
        </div>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="card p-4 space-y-2">
            <div className="h-4 bg-dark-700 rounded w-40" />
            <div className="h-3 bg-dark-700 rounded w-56" />
          </div>
        ))}
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="p-4 md:p-6 max-w-3xl mx-auto">
        <div className="card p-8 text-center text-red-400">
          <AlertCircle size={40} className="mx-auto mb-3" />
          <p>Impossible de charger la vue chargement.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link to="/planning/today" className="p-2 rounded-lg hover:bg-dark-600 transition-colors">
          <ArrowLeft size={18} />
        </Link>
        <div>
          <h1 className="text-lg font-bold text-white">Chargement {data.reference}</h1>
          {data.customer_name && (
            <p className="text-sm text-dark-400">{data.customer_name}</p>
          )}
        </div>
      </div>

      {/* Info bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {data.delivery_date && (
          <div className="bg-dark-900/60 rounded-lg p-3">
            <div className="text-xs text-dark-500 mb-0.5">Livraison</div>
            <div className="text-sm font-medium">{data.delivery_date}</div>
          </div>
        )}
        {data.delivery_zone_name && (
          <div className="bg-dark-900/60 rounded-lg p-3">
            <div className="text-xs text-dark-500 mb-0.5">Zone</div>
            <div className="text-sm font-medium">{data.delivery_zone_name}</div>
          </div>
        )}
        {data.delivery_method && (
          <div className="bg-dark-900/60 rounded-lg p-3">
            <div className="text-xs text-dark-500 mb-0.5 flex items-center gap-1"><Truck size={10} /> Transport</div>
            <div className="text-sm font-medium">
              {data.delivery_method === 'self' ? 'Propre' : data.delivery_method === 'carrier' ? 'Transporteur' : 'Retrait'}
            </div>
          </div>
        )}
        {data.total_weight_grams != null && data.total_weight_grams > 0 && (
          <div className="bg-dark-900/60 rounded-lg p-3">
            <div className="text-xs text-dark-500 mb-0.5 flex items-center gap-1"><Weight size={10} /> Poids</div>
            <div className="text-sm font-medium">{(data.total_weight_grams / 1000).toFixed(1)} kg</div>
          </div>
        )}
      </div>

      {/* Containers */}
      {data.containers.length === 0 ? (
        <div className="card p-8 text-center text-dark-400">
          <Package size={40} className="mx-auto mb-3 text-dark-600" />
          <p>Aucun contenant affecté à cette réservation.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.containers.map((c) => (
            <div key={c.container_id} className="card overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-dark-600 bg-dark-900/40">
                <div className="flex items-center gap-2">
                  <Package size={16} className="text-primary-400" />
                  <span className="font-medium text-sm">{c.container_name}</span>
                  <span className="text-xs text-dark-500">{c.container_type}</span>
                  {c.serial_number && (
                    <span className="text-xs text-dark-500">· {c.serial_number}</span>
                  )}
                </div>
                <span className="text-xs bg-primary-500/10 text-primary-400 px-2 py-0.5 rounded-full">
                  {c.items.length} article{c.items.length !== 1 ? 's' : ''}
                </span>
              </div>
              {c.items.length === 0 ? (
                <p className="text-dark-500 text-sm px-4 py-4 text-center">Contenant vide</p>
              ) : (
                <ul className="divide-y divide-dark-600">
                  {c.items.map((item) => (
                    <li key={item.movement_item_id} className="flex items-center justify-between gap-3 px-4 py-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-11 h-11 rounded-lg overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center">
                          {item.image_url ? (
                            <img
                              src={item.image_url}
                              alt={item.product_name || `Article #${item.movement_item_id}`}
                              className="w-full h-full object-cover"
                              loading="lazy"
                            />
                          ) : (
                            <Package size={18} className="text-dark-600" />
                          )}
                        </div>
                        <div className="min-w-0 text-sm">
                          <div className="truncate">
                            {item.product_name || `Article #${item.movement_item_id}`}
                          </div>
                          {item.variant_label && (
                            <div className="text-xs text-dark-500 truncate">{item.variant_label}</div>
                          )}
                        </div>
                      </div>
                      <span className="text-sm font-medium text-dark-300">x{item.quantity}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Unassigned */}
      {data.unassigned_items_count > 0 && (
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-4 text-sm text-orange-400">
          <AlertCircle size={16} className="inline mr-1.5" />
          {data.unassigned_items_count} article{data.unassigned_items_count > 1 ? 's' : ''} non affecté{data.unassigned_items_count > 1 ? 's' : ''} à un contenant.
        </div>
      )}
    </div>
  )
}
