import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { useUsers } from '@/api/queries'
import { cn } from '@/lib/utils'
import { useMultiModal } from '@/hooks/useModal'
import { useHasScope } from '@/hooks/useHasScope'
import { UserFormModal, UserDeleteModal } from './components'
import { InviteWizard } from './components/InviteWizard'
import type { User } from '@/types'
import { SwipeActions } from '@shared/components/ui/SwipeActions'
import {
  Search,
  Users,
  Edit,
  Trash2,
  Plus,
  ChevronRight,
  Shield,
  Briefcase,
  UserCheck,
  Eye,
} from 'lucide-react'

type ModalType = 'create' | 'edit' | 'delete'

const ROLE_LABELS: Record<string, string> = {
  admin: 'Admin',
  tenant_admin: 'Admin',
  manager: 'Manager',
  staff: 'Staff',
  viewer: 'Lecteur',
}

const ROLE_ICONS: Record<string, typeof Shield> = {
  admin: Shield,
  tenant_admin: Shield,
  manager: Briefcase,
  staff: UserCheck,
  viewer: Eye,
}

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  tenant_admin: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  manager: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  staff: 'bg-dark-800 text-dark-300 border-dark-600',
  viewer: 'bg-dark-800 text-dark-400 border-dark-600',
}

const FILTER_PILLS = [
  { key: null, label: 'Tous' },
  { key: 'admin', label: 'Admin' },
  { key: 'manager', label: 'Manager' },
  { key: 'staff', label: 'Staff' },
  { key: 'inactive', label: 'Inactifs' },
] as const

function UserAvatar({ user, size = 'md' }: { user: User; size?: 'sm' | 'md' | 'lg' }) {
  const initials = `${(user.first_name || user.full_name)?.[0] ?? ''}${(user.last_name || '')?.[0] ?? ''}`.toUpperCase()
  const sizes = { sm: 'w-8 h-8 text-xs', md: 'w-10 h-10 text-sm', lg: 'w-14 h-14 text-lg' }
  return (
    <div className={cn(
      sizes[size],
      'rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center font-semibold text-white shrink-0'
    )}>
      {initials || '?'}
    </div>
  )
}

function UserCardSkeleton() {
  return (
    <div className="flex items-center gap-3 px-4 py-4 animate-pulse">
      <div className="w-10 h-10 rounded-full bg-dark-800 shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="h-3.5 bg-dark-800 rounded w-32" />
        <div className="h-2.5 bg-dark-800 rounded w-48" />
      </div>
      <div className="h-5 w-16 bg-dark-800 rounded-full" />
    </div>
  )
}

export default function UsersPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<string | null>(null)
  const [wizardOpen, setWizardOpen] = useState(false)

  const canManageUsers = useHasScope('users:manage')
  const modal = useMultiModal<User>()

  const { data, isLoading } = useUsers({ skip: (page - 1) * 20, limit: 20 })

  const users = data?.items || []
  const total = data?.total ?? 0

  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      !search ||
      (u.first_name || '').toLowerCase().includes(search.toLowerCase()) ||
      (u.last_name || '').toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      u.full_name.toLowerCase().includes(search.toLowerCase())

    if (roleFilter === 'inactive') return matchesSearch && !u.is_active
    const matchesRole = !roleFilter || u.role === roleFilter || (roleFilter === 'admin' && u.role === 'tenant_admin')
    return matchesSearch && matchesRole && u.is_active
  })

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return ''
    return new Date(dateStr).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2 min-w-0">
            <Users className="w-5 h-5 text-primary-400" />
            Equipe
            <span className="text-sm font-normal text-dark-400">{total}</span>
          </h1>
        </div>
        {canManageUsers && (
          <button
            onClick={() => setWizardOpen(true)}
            className="btn-primary flex items-center gap-2 text-sm"
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">Inviter</span>
          </button>
        )}
      </div>

      {/* Recherche */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
        <input
          type="text"
          placeholder="Rechercher..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input pl-10 py-2.5 text-sm"
        />
      </div>

      {/* Filtres pills */}
      <div className="flex gap-2 flex-wrap">
        {FILTER_PILLS.map((pill) => {
          const active = roleFilter === pill.key
          return (
            <button
              key={pill.key ?? 'all'}
              onClick={() => setRoleFilter(active ? null : pill.key)}
              className={cn(
                'px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-150 active:scale-95',
                active
                  ? 'bg-primary-500 border-primary-500 text-white'
                  : 'bg-[var(--s1)] border-[var(--border2)] text-[var(--muted)] hover:text-[var(--text)]'
              )}
            >
              {pill.label}
            </button>
          )
        })}
      </div>

      {/* Liste mobile */}
      <div className="space-y-2 lg:hidden">
        {isLoading ? (
          Array.from({ length: 6 }).map((_, i) => <UserCardSkeleton key={i} />)
        ) : filteredUsers.length === 0 ? (
          <div className="text-center py-16 text-dark-400">
            <Users className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p className="text-sm">Aucun membre trouv&eacute;</p>
          </div>
        ) : (
          filteredUsers.map((user) => {
            const RoleIcon = ROLE_ICONS[user.role] || UserCheck
            return (
              <SwipeActions
                key={user.id}
                actions={canManageUsers ? [
                  {
                    icon: <Edit className="w-5 h-5" />,
                    label: 'Modifier',
                    color: 'bg-primary-500',
                    onClick: () => modal.open('edit', user),
                  },
                  {
                    icon: <Trash2 className="w-5 h-5" />,
                    label: user.is_active ? 'Desactiver' : 'Reactiver',
                    color: user.is_active ? 'bg-red-600' : 'bg-green-600',
                    onClick: () => modal.open('delete', user),
                  },
                ] : []}
              >
                <Link
                  to={`/admin/users/${user.id}` as never}
                  className="card flex items-center gap-3 px-4 py-3 active:scale-[0.98] transition-transform"
                >
                  <UserAvatar user={user} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm truncate">
                        {user.first_name || user.last_name
                          ? `${user.first_name || ''} ${user.last_name || ''}`.trim()
                          : user.full_name}
                      </span>
                      {!user.is_active && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400">Inactif</span>
                      )}
                    </div>
                    <p className="text-xs text-dark-400 truncate">{user.email}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={cn(
                        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border',
                        ROLE_COLORS[user.role] || ROLE_COLORS.staff
                      )}>
                        <RoleIcon className="w-3 h-3" />
                        {ROLE_LABELS[user.role] || user.role}
                      </span>
                      {user.created_at && (
                        <span className="text-[10px] text-dark-500">
                          Depuis {formatDate(user.created_at)}
                        </span>
                      )}
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-dark-500 shrink-0" />
                </Link>
              </SwipeActions>
            )
          })
        )}
      </div>

      {/* Table desktop */}
      <div className="hidden lg:block card p-0 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[var(--border)]">
              <th className="text-left py-3 px-4 text-xs font-medium text-dark-400 uppercase tracking-wide">Membre</th>
              <th className="text-left py-3 px-4 text-xs font-medium text-dark-400 uppercase tracking-wide">Role</th>
              <th className="text-left py-3 px-4 text-xs font-medium text-dark-400 uppercase tracking-wide">Statut</th>
              <th className="text-left py-3 px-4 text-xs font-medium text-dark-400 uppercase tracking-wide">Depuis</th>
              <th className="py-3 px-4" />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <tr key={i} className="animate-pulse border-b border-[var(--border)]/50">
                  <td className="px-4 py-3"><div className="flex items-center gap-3"><div className="w-8 h-8 rounded-full bg-dark-800" /><div className="h-3 bg-dark-800 rounded w-32" /></div></td>
                  <td className="px-4 py-3"><div className="h-5 bg-dark-800 rounded-full w-16" /></td>
                  <td className="px-4 py-3"><div className="h-5 bg-dark-800 rounded-full w-12" /></td>
                  <td className="px-4 py-3"><div className="h-3 bg-dark-800 rounded w-20" /></td>
                  <td />
                </tr>
              ))
            ) : (
              filteredUsers.map((user) => {
                const RoleIcon = ROLE_ICONS[user.role] || UserCheck
                return (
                  <tr key={user.id} className="border-b border-[var(--border)]/50 hover:bg-[var(--s2)] transition-colors">
                    <td className="px-4 py-3">
                      <Link to={`/admin/users/${user.id}` as never} className="flex items-center gap-3">
                        <UserAvatar user={user} size="sm" />
                        <div>
                          <p className="text-sm font-medium">{user.first_name} {user.last_name}</p>
                          <p className="text-xs text-dark-400">{user.email}</p>
                        </div>
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn(
                        'inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border',
                        ROLE_COLORS[user.role] || ROLE_COLORS.staff
                      )}>
                        <RoleIcon className="w-3 h-3" />
                        {ROLE_LABELS[user.role] || user.role}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn(
                        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
                        user.is_active ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
                      )}>
                        {user.is_active ? 'Actif' : 'Inactif'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-dark-400">{formatDate(user.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      {canManageUsers && (
                        <div className="flex items-center gap-1 justify-end">
                          <button onClick={() => modal.open('edit', user)} className="p-2 hover:bg-[var(--s2)] rounded-lg transition-colors" aria-label="Modifier">
                            <Edit className="w-4 h-4 text-dark-400" />
                          </button>
                          <button onClick={() => modal.open('delete', user)} className="p-2 hover:bg-red-500/10 rounded-lg transition-colors" aria-label="Desactiver">
                            <Trash2 className="w-4 h-4 text-dark-400" />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 20 && (
        <div className="flex justify-center gap-2 py-2">
          {Array.from({ length: Math.ceil(total / 20) }, (_, i) => (
            <button
              key={i}
              onClick={() => setPage(i + 1)}
              className={cn(
                'w-8 h-8 rounded-lg text-xs font-medium transition-colors',
                page === i + 1 ? 'bg-primary-500 text-white' : 'text-dark-400 hover:bg-[var(--s2)]'
              )}
            >
              {i + 1}
            </button>
          ))}
        </div>
      )}

      {/* FAB mobile */}
      {canManageUsers && (
        <button
          onClick={() => setWizardOpen(true)}
          className="fixed z-40 w-14 h-14 rounded-full flex items-center justify-center shadow-lg active:scale-90 transition-all duration-200 lg:hidden"
          style={{
            bottom: 'calc(var(--nav-offset, 80px) + 16px)',
            right: '22px',
            background: 'linear-gradient(135deg, var(--pink), var(--purple))',
          }}
          aria-label="Inviter un collaborateur"
        >
          <Plus className="w-6 h-6 text-white" />
        </button>
      )}

      {/* Modales */}
      {modal.isOpen('edit') && modal.data && (
        <UserFormModal isOpen user={modal.data} onClose={modal.close} />
      )}
      {modal.isOpen('delete') && modal.data && (
        <UserDeleteModal isOpen user={modal.data} onClose={modal.close} />
      )}

      {/* Wizard invitation */}
      <InviteWizard isOpen={wizardOpen} onClose={() => setWizardOpen(false)} />
    </div>
  )
}
