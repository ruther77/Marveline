import { useRef, useState, useCallback } from 'react'
import { useCustomersList, useImportCustomersCsv } from '@/api/queries'
import { ErrorState, NoData, NoSearchResults } from '@shared/components/ui/EmptyState'

import { useNavigate, useSearch, Link } from '@tanstack/react-router'
import { useMultiModal } from '@/hooks/useModal'
import { useToast } from '@/hooks'
import { CustomerFormModal, CustomerDeleteModal } from './components'
import type { CustomerList, CustomerType, CustomerImportReport } from '@/types/customer'
import { normalizeError } from '@shared/errors/normalizer'
import {
  Users,
  Plus,
  Edit,
  Trash2,
  ChevronLeft,
  ChevronRight,
  Search,
  Building2,
  User,
  Upload,
  Loader2,
  CheckCircle,
  AlertTriangle,
  Mail,
  Phone,
  MapPin,
  Bell,
  Briefcase,
  Heart,
  BarChart3,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useHeaderTitle } from '@/layout/HeaderTitleContext'
import { PageHeader } from '@shared/components/ui'
import { PAGE_SIZE_DEFAULT, CUSTOMER_TYPE_LABELS as TYPE_LABELS } from '@/lib/constants'
import { SwipeActions } from '@shared/components/ui'
import { useHasScope } from '@/hooks/useHasScope'
import type { SwipeAction } from '@shared/components/ui/SwipeActions'

/* ------------------------------------------------------------------ */
/*  Color mapping per customer type                                    */
/* ------------------------------------------------------------------ */

const TYPE_BORDER_COLOR: Record<CustomerType, string> = {
  company: 'border-l-blue-500',
  individual: 'border-l-primary-500',
  professional: 'border-l-amber-500',
  association: 'border-l-green-500',
}

const TYPE_AVATAR_BG: Record<CustomerType, string> = {
  company: 'bg-blue-500/10 text-blue-400',
  individual: 'bg-primary-500/10 text-primary-400',
  professional: 'bg-amber-500/10 text-amber-400',
  association: 'bg-green-500/10 text-green-400',
}

const TYPE_BADGE_STYLE: Record<CustomerType, string> = {
  company: 'bg-blue-500/10 text-blue-400',
  individual: 'bg-primary-500/10 text-primary-400',
  professional: 'bg-amber-500/10 text-amber-400',
  association: 'bg-green-500/10 text-green-400',
}

const TYPE_DOT_COLOR: Record<CustomerType | '', string> = {
  '': 'bg-dark-400',
  company: 'bg-blue-500',
  individual: 'bg-primary-500',
  professional: 'bg-amber-500',
  association: 'bg-green-500',
}

function TypeIcon({ type }: { type: CustomerType }) {
  const cls = 'w-4 h-4'
  switch (type) {
    case 'company':
      return <Building2 className={cls} />
    case 'professional':
      return <Briefcase className={cls} />
    case 'association':
      return <Heart className={cls} />
    default:
      return <User className={cls} />
  }
}

/* ------------------------------------------------------------------ */
/*  Card skeleton                                                      */
/* ------------------------------------------------------------------ */

function CustomerCardSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          className="animate-pulse rounded-xl border border-dark-600 border-l-4 border-l-dark-600 bg-dark-900 p-4"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full skel shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-4 skel rounded w-36" />
              <div className="h-3 skel rounded w-52" />
            </div>
            <div className="h-5 w-20 skel rounded-full" />
          </div>
        </div>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Type filter chips                                                  */
/* ------------------------------------------------------------------ */

const FILTER_TYPES: { value: CustomerType | ''; label: string }[] = [
  { value: '', label: 'Tous' },
  { value: 'individual', label: 'Particuliers' },
  { value: 'company', label: 'Entreprises' },
  { value: 'professional', label: 'Professionnels' },
  { value: 'association', label: 'Associations' },
]

function TypeFilterChips({
  active,
  onChange,
}: {
  active: CustomerType | ''
  onChange: (v: CustomerType | '') => void
}) {
  return (
    <div className="flex gap-2 flex-wrap">
      {FILTER_TYPES.map(({ value, label }) => {
        const isActive = active === value
        return (
          <button
            key={value}
            onClick={() => onChange(value)}
            className={cn(
              'inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all min-h-[36px]',
              isActive
                ? 'bg-primary-500 text-white shadow-lg shadow-primary-500/25'
                : 'bg-dark-900 text-dark-300 hover:bg-dark-600',
            )}
          >
            <span
              className={cn(
                'w-2 h-2 rounded-full shrink-0',
                isActive ? 'bg-white' : TYPE_DOT_COLOR[value],
              )}
            />
            {label}
          </button>
        )
      })}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Customer card                                                      */
/* ------------------------------------------------------------------ */

function CustomerCard({
  customer,
  showRelanceBadge,
}: {
  customer: CustomerList
  showRelanceBadge: boolean
}) {
  return (
    <div className="space-y-2.5 px-4 py-3.5">
      {/* Row 1: Avatar + Name + Type badge */}
      <div className="flex items-center gap-3">
        <div
          className={cn(
            'w-10 h-10 rounded-full flex items-center justify-center shrink-0',
            TYPE_AVATAR_BG[customer.customer_type],
          )}
        >
          <TypeIcon type={customer.customer_type} />
        </div>
        <div className="min-w-0 flex-1">
          <span className="font-semibold text-sm truncate block" title={customer.display_name}>
            {customer.display_name}
          </span>
        </div>
        <span
          className={cn(
            'inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium shrink-0',
            TYPE_BADGE_STYLE[customer.customer_type],
          )}
        >
          {TYPE_LABELS[customer.customer_type]}
        </span>
      </div>

      {/* Row 2: Contact info */}
      <div className="flex items-center gap-4 flex-wrap text-xs text-dark-400 min-w-0 overflow-hidden">
        {customer.email && (
          <span className="inline-flex items-center gap-1 min-w-0 max-w-full">
            <Mail className="w-3 h-3 shrink-0" />
            <span className="truncate">{customer.email}</span>
          </span>
        )}
        {customer.phone && (
          <span className="inline-flex items-center gap-1 shrink-0">
            <Phone className="w-3 h-3 shrink-0" />
            <span>{customer.phone}</span>
          </span>
        )}
        {customer.city && (
          <span className="inline-flex items-center gap-1 min-w-0">
            <MapPin className="w-3 h-3 shrink-0" />
            <span className="truncate">{customer.city}</span>
          </span>
        )}
      </div>

      {/* Row 3: Relance badge */}
      {showRelanceBadge && (
        <div>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium text-amber-400 bg-amber-500/10">
            <Bell className="w-3 h-3" />
            Relance planifiée
          </span>
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Main page                                                          */
/* ------------------------------------------------------------------ */

type ModalType = 'create' | 'edit' | 'delete'

export default function CustomersPage() {
  const { setTitle, setProgress } = useHeaderTitle()
  const onTitleChange = useCallback((t: string) => setTitle(t), [setTitle])
  const onProgressChange = useCallback((p: number) => setProgress(p), [setProgress])
  const navigate = useNavigate({ from: '/customers/' })
  const { page, q: searchQuery, type: typeFilter, relances: relancesOnly } = useSearch({
    strict: false,
  }) as { page: number; q: string; type: CustomerType | ''; relances: boolean }
  const [lastImportReport, setLastImportReport] = useState<CustomerImportReport | null>(null)
  const importInputRef = useRef<HTMLInputElement>(null)
  const canWrite = useHasScope('customers:write')
  const canDelete = useHasScope('customers:delete')
  const toast = useToast()
  const importMutation = useImportCustomersCsv()

  const setPage = (p: number) => navigate({ search: (prev) => ({ ...prev, page: p }) })
  const setSearchQuery = (v: string) =>
    navigate({ search: (prev) => ({ ...prev, q: v || undefined, page: 1 }) })
  const setTypeFilter = (v: CustomerType | '') =>
    navigate({ search: (prev) => ({ ...prev, type: v || undefined, page: 1 }) })
  const setRelancesOnly = (v: boolean) =>
    navigate({ search: (prev) => ({ ...prev, relances: v || undefined, page: 1 }) })

  const modal = useMultiModal<CustomerList>()

  const { data, isLoading, error, refetch } = useCustomersList({
    skip: ((page || 1) - 1) * PAGE_SIZE_DEFAULT,
    limit: PAGE_SIZE_DEFAULT,
    search_query: searchQuery || undefined,
    customer_type: typeFilter || undefined,
    has_scheduled_relances: relancesOnly || undefined,
  })

  const customers = data?.items || []
  const totalPages = Math.ceil((data?.total ?? 0) / PAGE_SIZE_DEFAULT) || 1

  const handleOpenModal = (type: ModalType, customer?: CustomerList) => {
    modal.open(type, customer)
  }

  const handleImportFile = (file: File) => {
    const isCsv =
      file.name.toLowerCase().endsWith('.csv') ||
      file.type === 'text/csv' ||
      file.type === 'text/plain' ||
      file.type === 'application/vnd.ms-excel'

    if (!isCsv) {
      toast.error('Import clients', 'Format invalide. Utilisez un fichier CSV.')
      return
    }

    importMutation.mutate(file, {
      onSuccess: (report) => {
        setLastImportReport(report)
        const summary = `${report.created} créé(s), ${report.skipped} ignoré(s), ${report.errors.length} erreur(s)`
        if (report.errors.length > 0) {
          toast.warning('Import clients terminé avec erreurs', summary)
        } else {
          toast.success('Import clients terminé', summary)
        }
      },
      onError: (err) => {
        toast.error('Import clients échoué', normalizeError(err).message)
      },
    })
  }

  const buildLeftActions = (customer: CustomerList): SwipeAction[] => [
    ...(customer.phone ? [{ icon: <Phone className="w-4 h-4" />, label: 'Appeler', color: 'bg-green-600', onClick: () => window.open(`tel:${customer.phone}`, '_self') }] : []),
    ...(customer.email ? [{ icon: <Mail className="w-4 h-4" />, label: 'Email', color: 'bg-blue-600', onClick: () => window.open(`mailto:${customer.email}`, '_self') }] : []),
  ]

  const buildRightActions = (customer: CustomerList): SwipeAction[] => [
    ...(canWrite
      ? [
          {
            icon: <Edit className="w-4 h-4" />,
            label: 'Modifier',
            color: 'bg-primary-600',
            onClick: () => handleOpenModal('edit', customer),
          },
        ]
      : []),
    ...(canDelete
      ? [
          {
            icon: <Trash2 className="w-4 h-4" />,
            label: 'Supprimer',
            color: 'bg-red-600',
            onClick: () => handleOpenModal('delete', customer),
          },
        ]
      : []),
  ]

  return (
    <div className="space-y-6">
      {/* Header — large title with inline crossfade */}
      <PageHeader
        title="Clients"
        subtitle="Gérez votre base de clients"
        onTitleChange={onTitleChange}
        onProgressChange={onProgressChange}
        actions={<div className="flex items-center gap-2 shrink-0">
          {canWrite && (
            <>
              <button
                type="button"
                onClick={() => importInputRef.current?.click()}
                disabled={importMutation.isPending}
                className="btn-secondary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {importMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Upload className="w-4 h-4" />
                )}
                <span className="hidden sm:inline">Importer CSV</span>
              </button>
              <input
                ref={importInputRef}
                type="file"
                accept=".csv,text/csv,text/plain"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) handleImportFile(file)
                  e.currentTarget.value = ''
                }}
              />
            </>
          )}
          <Link to="/customers/rfm" className="btn-secondary flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            <span className="hidden sm:inline">RFM</span>
          </Link>
          {canWrite && (
            <button
              onClick={() => handleOpenModal('create')}
              className="btn-primary flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              <span className="hidden sm:inline">Nouveau client</span>
            </button>
          )}
        </div>}
      />

      {/* Search + Relance toggle */}
      <div className="space-y-4">
        <div className="flex gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Rechercher par nom, email..."
              className="input w-full pl-10"
            />
          </div>
          <button
            onClick={() => setRelancesOnly(!relancesOnly)}
            className={cn(
              'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all min-h-[44px]',
              relancesOnly
                ? 'bg-amber-500/15 text-amber-400 ring-1 ring-amber-500/30'
                : 'btn-secondary',
            )}
          >
            <Bell className="w-4 h-4" />
            A relancer
          </button>
        </div>

        {/* Type filter chips */}
        <TypeFilterChips active={typeFilter || ''} onChange={setTypeFilter} />
      </div>

      {/* Import report */}
      {lastImportReport && (
        <div className="card space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-primary-400" />
              <h2 className="text-sm font-semibold">Dernier import clients</h2>
            </div>
            <button
              type="button"
              onClick={() => setLastImportReport(null)}
              className="text-xs text-dark-400 hover:text-dark-200"
            >
              Masquer
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <div className="rounded-lg border border-green-800/40 bg-green-900/20 p-4 text-center">
              <CheckCircle className="w-5 h-5 text-green-400 mx-auto mb-1" />
              <p className="text-lg font-semibold text-green-300">{lastImportReport.created}</p>
              <p className="text-xs text-green-500">créé(s)</p>
            </div>
            <div className="rounded-lg border border-dark-600 bg-dark-900/50 p-4 text-center">
              <p className="text-lg font-semibold text-dark-300">{lastImportReport.skipped}</p>
              <p className="text-xs text-dark-500">ignoré(s)</p>
            </div>
            <div
              className={cn(
                'rounded-lg border p-4 text-center',
                lastImportReport.errors.length > 0
                  ? 'border-red-800/40 bg-red-900/20'
                  : 'border-dark-600 bg-dark-900/50',
              )}
            >
              <AlertTriangle
                className={cn(
                  'w-5 h-5 mx-auto mb-1',
                  lastImportReport.errors.length > 0 ? 'text-red-400' : 'text-dark-500',
                )}
              />
              <p
                className={cn(
                  'text-lg font-semibold',
                  lastImportReport.errors.length > 0 ? 'text-red-300' : 'text-dark-300',
                )}
              >
                {lastImportReport.errors.length}
              </p>
              <p
                className={cn(
                  'text-xs',
                  lastImportReport.errors.length > 0 ? 'text-red-500' : 'text-dark-500',
                )}
              >
                erreur(s)
              </p>
            </div>
          </div>

          {lastImportReport.errors.length > 0 && (
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {lastImportReport.errors.slice(0, 10).map((err, idx) => (
                <div key={`${err.row}-${idx}`} className="text-xs text-red-300">
                  Ligne {err.row}
                  {err.field ? ` (${err.field})` : ''}: {err.message}
                </div>
              ))}
              {lastImportReport.errors.length > 10 && (
                <p className="text-xs text-dark-400">
                  + {lastImportReport.errors.length - 10} autre(s) erreur(s)
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {error && <ErrorState onRetry={() => refetch()} />}

      {/* Customer cards list */}
      {isLoading ? (
        <CustomerCardSkeleton />
      ) : customers.length === 0 ? (
        searchQuery || typeFilter || relancesOnly ? (
          <NoSearchResults
            searchTerm={searchQuery || undefined}
            onClear={() =>
              navigate({
                search: () => ({ q: undefined, type: undefined, relances: undefined, page: 1 }),
              })
            }
          />
        ) : (
          <NoData
            onAction={canWrite ? () => handleOpenModal('create') : undefined}
            actionLabel="Nouveau client"
          />
        )
      ) : (
        <div className="space-y-3">
          {customers.map((customer) => (
            <SwipeActions
              key={customer.id}
              leftActions={buildLeftActions(customer)}
              rightActions={buildRightActions(customer)}
            >
              <div
                className={cn(
                  'rounded-xl border border-dark-600 border-l-4 bg-dark-900 cursor-pointer transition-colors hover:bg-dark-600/80',
                  TYPE_BORDER_COLOR[customer.customer_type],
                )}
                onClick={() => navigate({ to: `/customers/${customer.id}` })}
              >
                <CustomerCard customer={customer} showRelanceBadge={!!relancesOnly} />
              </div>
            </SwipeActions>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-1 py-2">
          <div className="text-sm text-dark-400">
            Page {page || 1} sur {totalPages}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(1, (page || 1) - 1))}
              disabled={(page || 1) === 1}
              className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Page precedente"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages, (page || 1) + 1))}
              disabled={(page || 1) === totalPages}
              className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Page suivante"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

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
