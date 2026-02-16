import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import { cn } from '@/lib/utils'
import { useMultiModal } from '@/hooks/useModal'
import { UserFormModal, UserDeleteModal } from './components'
import type { User } from '@/types'
import {
  Search,
  Users,
  ChevronLeft,
  ChevronRight,
  Edit,
  Trash2,
  Plus,
  MoreVertical,
} from 'lucide-react'

type ModalType = 'create' | 'edit' | 'delete'

const ROLE_LABELS: Record<string, string> = {
  admin: 'Administrateur',
  manager: 'Manager',
  staff: 'Staff',
}

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-purple-500/10 text-purple-400',
  manager: 'bg-blue-500/10 text-blue-400',
  staff: 'bg-dark-700 text-dark-300',
}

export default function UsersPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<string | null>(null)
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)

  const modal = useMultiModal<User>()

  const { data, isLoading } = useQuery({
    queryKey: ['admin-users', page],
    queryFn: () => adminApi.getUsers(page, 20),
  })

  const users = data?.items || []
  const totalPages = data?.pages || 1

  // Filtrage client par recherche et rôle
  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      !search ||
      (u.first_name || '').toLowerCase().includes(search.toLowerCase()) ||
      (u.last_name || '').toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      u.full_name.toLowerCase().includes(search.toLowerCase())

    const matchesRole = !roleFilter || u.role === roleFilter

    return matchesSearch && matchesRole
  })

  const handleOpenModal = (type: ModalType, user?: User) => {
    setOpenMenuId(null)
    modal.open(type, user)
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Utilisateurs</h1>
          <p className="text-dark-400 mt-1">
            Administrez les comptes utilisateurs
          </p>
        </div>
        <button
          onClick={() => handleOpenModal('create')}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Nouvel utilisateur
        </button>
      </div>

      {/* Filters */}
      <div className="card space-y-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-400" />
          <input
            type="text"
            placeholder="Rechercher par nom ou email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-10"
          />
        </div>

        <div className="flex gap-4 flex-wrap">
          <select
            value={roleFilter || ''}
            onChange={(e) => setRoleFilter(e.target.value || null)}
            className="input"
          >
            <option value="">Tous les rôles</option>
            <option value="admin">Administrateur</option>
            <option value="manager">Manager</option>
            <option value="staff">Staff</option>
          </select>

          {(roleFilter || search) && (
            <button
              onClick={() => {
                setRoleFilter(null)
                setSearch('')
              }}
              className="btn-secondary"
            >
              Réinitialiser
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
                  Utilisateur
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Email
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Rôle
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Statut
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Créé le
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
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-dark-400">
                    <Users className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    Aucun utilisateur trouvé
                  </td>
                </tr>
              ) : (
                filteredUsers.map((user) => (
                  <tr
                    key={user.id}
                    className="border-b border-dark-700 hover:bg-dark-800/50"
                  >
                    <td className="py-3 px-4">
                      <div className="font-medium">
                        {user.first_name || user.last_name
                          ? `${user.first_name || ''} ${user.last_name || ''}`.trim()
                          : user.full_name}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm text-dark-300">{user.email}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={cn(
                          'inline-flex items-center px-2 py-1 rounded text-xs',
                          ROLE_COLORS[user.role] || 'bg-dark-700 text-dark-400'
                        )}
                      >
                        {ROLE_LABELS[user.role] || user.role}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={cn(
                          'inline-flex items-center px-2 py-1 rounded text-xs',
                          user.is_active
                            ? 'bg-green-500/10 text-green-500'
                            : 'bg-red-500/10 text-red-400'
                        )}
                      >
                        {user.is_active ? 'Actif' : 'Inactif'}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm text-dark-400">
                        {formatDate(user.created_at)}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end">
                        <div className="relative">
                          <button
                            onClick={() =>
                              setOpenMenuId(
                                openMenuId === user.id ? null : user.id
                              )
                            }
                            className="p-1 hover:bg-dark-700 rounded"
                          >
                            <MoreVertical className="w-4 h-4" />
                          </button>

                          {openMenuId === user.id && (
                            <>
                              <div
                                className="fixed inset-0 z-10"
                                onClick={() => setOpenMenuId(null)}
                              />
                              <div className="absolute right-0 mt-2 w-48 bg-dark-800 border border-dark-700 rounded-lg shadow-lg z-20">
                                <button
                                  onClick={() => handleOpenModal('edit', user)}
                                  className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 first:rounded-t-lg"
                                >
                                  <Edit className="w-4 h-4" />
                                  Modifier
                                </button>
                                <button
                                  onClick={() => handleOpenModal('delete', user)}
                                  className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 text-red-500 last:rounded-b-lg"
                                >
                                  <Trash2 className="w-4 h-4" />
                                  Désactiver
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
              {data?.total ? ` (${data.total} utilisateurs)` : ''}
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
      <UserFormModal
        isOpen={modal.isOpen('create') || modal.isOpen('edit')}
        onClose={modal.close}
        user={modal.data}
      />

      <UserDeleteModal
        isOpen={modal.isOpen('delete')}
        onClose={modal.close}
        user={modal.data ?? null}
      />
    </div>
  )
}
