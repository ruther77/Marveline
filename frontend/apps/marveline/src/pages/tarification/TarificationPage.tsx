import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { Plus, Edit2, Trash2, Tag, Play, CheckCircle, X } from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'
import { usePricingRules, usePricingByProduct, usePricingMutations, usePricingSimulate } from '@/api/queries/usePricing'
import { useFeatureCheck } from '@/api/queries'
import { useProductsList } from '@/api/queries/useProducts'
import { useDebounce } from '@/hooks/useDebounce'
import { ComboboxAsync } from '@shared/components/ui/ComboboxAsync'
import { PricingRuleBuilder } from '@/components/PricingRuleBuilder'
import { Modal } from '@shared/components/ui/Modal'
import { formatCents } from '@/lib/utils'
import type { PricingRule, PricingRuleCreate } from '@/types/pricing'

const RULE_TYPE_LABELS: Record<string, string> = {
  flat: 'Prix fixe',
  per_day: 'Par jour',
  tiered: 'Paliers',
  volume: 'Volume',
  seasonal: 'Saisonnier',
  custom: 'Personnalisé',
}

const APPLIES_TO_LABELS: Record<string, string> = {
  all: 'Tous',
  category: 'Catégorie',
  product: 'Produit',
}

const PRICING_UI_FLAG = 'pricing_ui'

function RuleFormModal({
  rule,
  onClose,
}: {
  rule: PricingRule | null
  onClose: () => void
}) {
  const { create, update } = usePricingMutations()
  const isEdit = rule !== null
  const [form, setForm] = useState<Partial<PricingRuleCreate>>(
    isEdit
      ? {
          name: rule.name,
          rule_type: rule.rule_type,
          applies_to: rule.applies_to,
          target_id: rule.target_id,
          discount_pct: rule.discount_pct,
          tiers: rule.tiers,
          valid_from: rule.valid_from,
          valid_to: rule.valid_to,
        }
      : { rule_type: 'flat', applies_to: 'all' }
  )
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = () => {
    if (!form.name?.trim()) { setError('Le nom est requis'); return }
    if (!form.rule_type) { setError('Le type est requis'); return }
    setError(null)
    const payload = form as PricingRuleCreate
    if (isEdit) {
      update.mutate({ id: rule.id, data: payload }, { onSuccess: onClose, onError: (err) => setError(normalizeError(err).message || 'Erreur lors de la mise à jour') })
    } else {
      create.mutate(payload, { onSuccess: onClose, onError: (err) => setError(normalizeError(err).message || 'Erreur lors de la création') })
    }
  }

  const isPending = create.isPending || update.isPending

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title={isEdit ? 'Modifier la règle' : 'Nouvelle règle de tarification'}
      footer={
        <div className="flex justify-end gap-4">
          <button onClick={onClose} className="px-4 py-2 text-sm text-dark-300 hover:text-dark-50">
            Annuler
          </button>
          <button
            onClick={handleSubmit}
            disabled={isPending}
            className="px-4 py-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-semibold text-sm rounded-lg disabled:opacity-50"
          >
            {isPending ? 'Enregistrement…' : isEdit ? 'Mettre à jour' : 'Créer'}
          </button>
        </div>
      }
    >
      <PricingRuleBuilder value={form} onChange={setForm} />
      {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
    </Modal>
  )
}

function SimulatorPanel() {
  const [productSearch, setProductSearch] = useState('')
  const debouncedProductSearch = useDebounce(productSearch, 300)
  const { data: productsData, isLoading: loadingProducts } = useProductsList({
    limit: 20,
    search: debouncedProductSearch || undefined,
  })
  const products = productsData?.items ?? []

  const [productId, setProductId] = useState<number | ''>('')
  const [quantity, setQuantity] = useState('1')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [simParams, setSimParams] = useState<{
    product_id: number; quantity: number; date_from: string; date_to: string
  } | null>(null)

  const { data: simResult, isFetching } = usePricingSimulate(simParams)

  const handleSimulate = () => {
    const pid = productId === '' ? 0 : productId
    const qty = parseInt(quantity)
    if (!pid || !qty || !dateFrom || !dateTo) return
    setSimParams({ product_id: pid, quantity: qty, date_from: dateFrom, date_to: dateTo })
  }

  const inputCls = 'input'

  return (
    <div className="card space-y-4">
      <h2 className="text-sm font-semibold flex items-center gap-2">
        <Play className="w-4 h-4 text-gold-400" />
        Simulateur de prix
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <label className="block text-xs text-dark-400 mb-1">Produit</label>
          <ComboboxAsync
            value={productId}
            onChange={(id) => setProductId(id)}
            items={products.map((p) => ({ id: p.id, label: p.name }))}
            onSearchChange={setProductSearch}
            isLoading={loadingProducts}
            placeholder="Rechercher…"
            className="w-full"
          />
        </div>
        <div>
          <label className="block text-xs text-dark-400 mb-1">Quantité</label>
          <input type="number" min={1} value={quantity} onChange={(e) => setQuantity(e.target.value)} className={inputCls + ' w-full'} placeholder="1" />
        </div>
        <div>
          <label className="block text-xs text-dark-400 mb-1">Du</label>
          <input type="date" value={dateFrom} max={dateTo || undefined} onChange={(e) => setDateFrom(e.target.value)} className={inputCls + ' w-full'} />
        </div>
        <div>
          <label className="block text-xs text-dark-400 mb-1">Au</label>
          <input type="date" value={dateTo} min={dateFrom || undefined} onChange={(e) => setDateTo(e.target.value)} className={inputCls + ' w-full'} />
        </div>
      </div>
      <div className="flex items-center gap-4">
        <button
          onClick={handleSimulate}
          disabled={isFetching}
          className="flex items-center gap-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-semibold text-sm px-4 py-2 rounded-lg disabled:opacity-50"
        >
          <Play className="w-3.5 h-3.5" />
          {isFetching ? 'Calcul…' : 'Simuler'}
        </button>
        {simResult && (
          <div className="flex items-center gap-2 text-sm">
            <CheckCircle className="w-4 h-4 text-green-400" />
            <span className="text-dark-300">
              Prix unitaire : <span className="font-semibold">{formatCents(simResult.unit_price_cents)}</span>
              {' '}· Total : <span className="font-semibold">{formatCents(simResult.total_cents)}</span>
            </span>
            {simResult.rule_applied && (
              <span className="text-xs text-gold-400">({simResult.rule_applied})</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function TarificationPage() {
  const [filterProductId, setFilterProductId] = useState<number | null>(null)
  const [filterProductSearch, setFilterProductSearch] = useState('')
  const [modal, setModal] = useState<'create' | PricingRule | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  const pricingFeature = useFeatureCheck(PRICING_UI_FLAG, { defaultEnabled: true })
  const pricingUiEnabled = pricingFeature.isEnabled

  const debouncedFilterSearch = useDebounce(filterProductSearch, 300)
  const { data: filterProductsData, isLoading: filterProductsLoading } = useProductsList({
    limit: 20,
    search: debouncedFilterSearch || undefined,
  })
  const filterProductItems = (filterProductsData?.items ?? []).map((p) => ({ id: p.id, label: p.name }))

  const { data: allRules = [], isLoading: allLoading, error: allError, refetch: refetchAll } = usePricingRules({ enabled: pricingUiEnabled })
  const { data: productRules = [], isLoading: productLoading, error: productError, refetch: refetchProduct } = usePricingByProduct(filterProductId, { enabled: pricingUiEnabled })
  const { remove } = usePricingMutations()

  const rules = filterProductId !== null ? productRules : allRules
  const isLoading = filterProductId !== null ? productLoading : allLoading

  const handleDelete = (id: number) => {
    remove.mutate(id, {
      onSuccess: () => setConfirmDeleteId(null),
    })
  }

  if (!pricingUiEnabled) {
    return (
      <div className="p-4 md:p-6">
        <div className="card p-6 text-center space-y-2">
          <PageHeader title="Tarification" subtitle="Cette fonctionnalité est actuellement désactivée pour votre tenant." />
          <p className="text-xs text-dark-500">
            Gate: <span className="font-mono">{PRICING_UI_FLAG}</span>
            {' '}· raison: <span className="font-mono">{pricingFeature.reason}</span>
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 md:p-6 space-y-4">
      {pricingFeature.source === 'fallback' && (
        <div className="card p-4 text-xs text-dark-400">
          Vérification rollout indisponible (`features/check`) — mode fallback activé.
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Tarification</h1>
        <button
          onClick={() => setModal('create')}
          className="flex items-center gap-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-semibold text-sm px-4 py-2 rounded-lg"
        >
          <Plus className="w-4 h-4" />
          Nouvelle règle
        </button>
      </div>

      {/* Filtre par produit */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex-1 min-w-[220px] max-w-xs">
          <ComboboxAsync
            value={filterProductId ?? ''}
            onChange={(id) => setFilterProductId(id === '' ? null : id)}
            items={filterProductItems}
            onSearchChange={setFilterProductSearch}
            isLoading={filterProductsLoading}
            placeholder="Filtrer par produit…"
          />
        </div>
        {filterProductId !== null && (
          <button
            onClick={() => { setFilterProductId(null); setFilterProductSearch('') }}
            className="flex items-center gap-1.5 text-xs text-dark-400 hover:text-dark-50 border border-dark-600 rounded-lg px-4 py-2"
          >
            <X className="w-3 h-3" />
            Effacer le filtre
          </button>
        )}
        {filterProductId !== null && (
          <span className="text-xs text-dark-400">
            {rules.length} règle{rules.length !== 1 ? 's' : ''} applicable{rules.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Simulateur */}
      <SimulatorPanel />

      {/* Liste des règles */}
      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-dark-600 text-dark-400 text-xs">
              <th className="text-left px-4 py-4 font-medium">Nom</th>
              <th className="text-left px-4 py-4 font-medium hidden sm:table-cell">Type</th>
              <th className="text-left px-4 py-4 font-medium hidden md:table-cell">Périmètre</th>
              <th className="text-left px-4 py-4 font-medium hidden lg:table-cell">Validité</th>
              <th className="text-left px-4 py-4 font-medium">Statut</th>
              <th className="w-20" />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <tr key={i} className="border-b border-dark-600 animate-pulse">
                  <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-24" /></td>
                  <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-20" /></td>
                  <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-16" /></td>
                  <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-16" /></td>
                  <td className="py-4 px-4"><div className="h-5 bg-dark-900 rounded w-16" /></td>
                  <td className="py-4 px-4"><div className="h-6 bg-dark-900 rounded w-6 ml-auto" /></td>
                </tr>
              ))
            ) : (allError || productError) ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center">
                  <p className="text-red-400 mb-4">Erreur lors du chargement des règles.</p>
                  <button onClick={() => { refetchAll(); refetchProduct() }} className="btn-secondary text-sm">Réessayer</button>
                </td>
              </tr>
            ) : rules.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-dark-400">
                  Aucune règle de tarification
                </td>
              </tr>
            ) : (
              rules.map((rule) => (
                <tr key={rule.id} className="border-b border-dark-600/50 hover:bg-dark-600/20">
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2">
                      <Tag className="w-3.5 h-3.5 text-gold-400 shrink-0" />
                      <span className="font-medium">{rule.name}</span>
                    </div>
                    {rule.discount_pct != null && (
                      <span className="text-xs text-dark-400">-{rule.discount_pct}%</span>
                    )}
                  </td>
                  <td className="px-4 py-4 text-dark-300 hidden sm:table-cell">
                    {RULE_TYPE_LABELS[rule.rule_type] ?? rule.rule_type}
                  </td>
                  <td className="px-4 py-4 text-dark-400 text-xs hidden md:table-cell">
                    {APPLIES_TO_LABELS[rule.applies_to] ?? rule.applies_to}
                    {rule.target_id != null && ` #${rule.target_id}`}
                  </td>
                  <td className="px-4 py-4 text-dark-400 text-xs hidden lg:table-cell">
                    {rule.valid_from && rule.valid_to
                      ? `${new Date(rule.valid_from).toLocaleDateString('fr-FR')} → ${new Date(rule.valid_to).toLocaleDateString('fr-FR')}`
                      : rule.valid_from
                      ? `Dès le ${new Date(rule.valid_from).toLocaleDateString('fr-FR')}`
                      : '—'}
                  </td>
                  <td className="px-4 py-4">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${
                        rule.active
                          ? 'bg-green-900/30 text-green-400'
                          : 'bg-dark-900 text-dark-400'
                      }`}
                    >
                      {rule.active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2 justify-end">
                      <button
                        onClick={() => setModal(rule)}
                        className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center text-dark-400 hover:text-gold-400 rounded"
                        title="Modifier"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      {confirmDeleteId === rule.id ? (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleDelete(rule.id)}
                            disabled={remove.isPending}
                            className="text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded border border-red-700/50 hover:bg-red-900/20 disabled:opacity-50"
                          >
                            Oui
                          </button>
                          <button
                            onClick={() => setConfirmDeleteId(null)}
                            className="text-xs text-dark-400 hover:text-dark-50 px-2 py-1 rounded"
                          >
                            Non
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmDeleteId(rule.id)}
                          disabled={remove.isPending}
                          className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center text-dark-400 hover:text-red-400 rounded disabled:opacity-40"
                          title="Supprimer"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Modal création/édition */}
      {modal !== null && (
        <RuleFormModal
          rule={modal === 'create' ? null : modal}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  )
}
