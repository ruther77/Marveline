import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { customersApi } from '@/api/customers'
import { useMultiModal } from '@/hooks/useModal'
import { CustomerFormModal, CustomerDeleteModal } from './components'
import type { CustomerList, CustomerType } from '@/types/customer'
import {
  Users,
  Plus,
  Edit,
  Trash2,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
  Search,
  Building2,
  User,
} from 'lucide-react'
import { cn, formatDate } from '@/lib/utils'

type ModalType = 'create' | 'edit' | 'delete'

const TYPE_LABELS: Record<CustomerType, string> = {
  individual: 'Particulier',
  company: 'Entreprise',
}

export default function CustomersPage() {
  const [page, setPage] = useState(1)
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<CustomerType | ''>('')
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)

  const modal = useMultiModal<CustomerList>()

  const { data, isLoading } = useQuery({
    queryKey: ['customers', page, searchQuery, typeFilter],
    queryFn: () =>
      customersApi.getCustomers({
        page,
        page_size: 20,
        search_query: searchQuery || undefined,
        customer_type: typeFilter || undefined,
      }),
  })

  const customers = data?.items || []
  const totalPages = data?.total_pages || 1

  const handleOpenModal = (type: ModalType, customer?: CustomerList) => {
    setOpenMenuId(null)
    modal.open(type, customer)
  }

  const handleSearch = (value: string) => {
    setSearchQuery(value)
    setPage(1)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Clients</h1>
          <p className="text-dark-400 mt-1">
            Gerez votre base de clients
          </p>
        </div>
        <button
          onClick={() => handleOpenModal('create')}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Nouveau client
        </button>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex gap-4 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder="Rechercher par nom, email..."
              className="input w-full pl-10"
            />
          </div>
          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value as CustomerType | '')
              setPage(1)
            }}
            className="input"
          >
            <option value="">Tous les types</option>
            <option value="individual">Particuliers</option>
            <option value="company">Entreprises</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Client
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Type
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Email
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Telephone
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Ville
                </th>
                <th className="text-right py-3 px-4 text-sm font-medium text-dark-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-dark-400">
                    Chargement...
                  </td>
                </tr>
              ) : customers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-dark-400">
                    <Users className="w-8 h-8 mx-auto mb-2 text-dark-600" />
                    Aucun client trouve
                  </td>
                </tr>
              ) : (
                customers.map((customer) => (
                  <tr
                    key={customer.id}
                    className="border-b border-dark-700 hover:bg-dark-800/50"
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          'w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium',
                          customer.customer_type === 'company'
                            ? 'bg-blue-500/10 text-blue-400'
                            : 'bg-primary-500/10 text-primary-400'
                        )}>
                          {customer.customer_type === 'company' ? (
                            <Building2 className="w-4 h-4" />
                          ) : (
                            <User className="w-4 h-4" />
                          )}
                        </div>
                        <span className="font-medium">{customer.display_name}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className={cn(
                        'inline-flex items-center px-2 py-1 rounded text-xs',
                        customer.customer_type === 'company'
                          ? 'bg-blue-500/10 text-blue-400'
                          : 'bg-dark-700 text-dark-300'
                      )}>
                        {TYPE_LABELS[customer.customer_type]}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm text-dark-300">{customer.email}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm text-dark-400">
                        {customer.phone || '-'}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm text-dark-400">
                        {customer.city || '-'}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end gap-2">
                        <div className="relative">
                          <button
                            onClick={() =>
                              setOpenMenuId(
                                openMenuId === customer.id ? null : customer.id
                              )
                            }
                            className="p-1 hover:bg-dark-700 rounded"
                          >
                            <MoreVertical className="w-4 h-4" />
                          </button>

                          {openMenuId === customer.id && (
                            <>
                              <div
                                className="fixed inset-0 z-10"
                                onClick={() => setOpenMenuId(null)}
                              />
                              <div className="absolute right-0 mt-2 w-48 bg-dark-800 border border-dark-700 rounded-lg shadow-lg z-20">
                                <button
                                  onClick={() => handleOpenModal('edit', customer)}
                                  className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 first:rounded-t-lg"
                                >
                                  <Edit className="w-4 h-4" />
                                  Modifier
                                </button>
                                <button
                                  onClick={() => handleOpenModal('delete', customer)}
                                  className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 text-red-500 last:rounded-b-lg"
                                >
                                  <Trash2 className="w-4 h-4" />
                                  Supprimer
                                </button>
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
              Page {page} sur {totalPages}
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
      <CustomerFormModal
        isOpen={modal.isOpen('create') || modal.isOpen('edit')}
        onClose={modal.close}
        customer={modal.data}
        mode={modal.isOpen('edit') ? 'edit' : 'create'}
      />

      <CustomerDeleteModal
        isOpen={modal.isOpen('delete')}
        onClose={modal.close}
        customer={modal.data}
      />
    </div>
  )
}
