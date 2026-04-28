import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import type { PricingRuleType, PricingTier, PricingRuleCreate } from '@/types/pricing'
import { useProductsList, useCategoriesList } from '@/api/queries'
import { centsToDecimal, decimalToCents } from '@/lib/utils'

interface PricingRuleBuilderProps {
  value: Partial<PricingRuleCreate>
  onChange: (v: Partial<PricingRuleCreate>) => void
}

const RULE_TYPE_LABELS: Record<PricingRuleType, string> = {
  flat: 'Prix fixe',
  per_day: 'Par jour',
  tiered: 'Paliers',
  volume: 'Volume',
  seasonal: 'Saisonnier',
  custom: 'Personnalisé',
}


export function PricingRuleBuilder({ value, onChange }: PricingRuleBuilderProps) {
  const ruleType = value.rule_type ?? 'flat'

  const set = (patch: Partial<PricingRuleCreate>) => onChange({ ...value, ...patch })

  const { data: productsData } = useProductsList({ limit: 1000 })
  const { data: categoriesData } = useCategoriesList()
  const products = productsData?.items ?? []
  const categories = categoriesData ?? []

  const dateError =
    value.valid_from && value.valid_to && value.valid_from >= value.valid_to
      ? 'La date de fin doit être postérieure à la date de début'
      : null

  const [tierPriceInputs, setTierPriceInputs] = useState<string[]>(
    (value.tiers ?? []).map((t) => centsToDecimal(t.unit_price_cents))
  )

  const addTier = () => {
    const tiers = [...(value.tiers ?? []), { min_qty: 1, unit_price_cents: 0 }]
    set({ tiers })
    setTierPriceInputs((prev) => [...prev, ''])
  }

  const removeTier = (i: number) => {
    const tiers = (value.tiers ?? []).filter((_, idx) => idx !== i)
    set({ tiers })
    setTierPriceInputs((prev) => prev.filter((_, idx) => idx !== i))
  }

  const updateTier = (i: number, patch: Partial<PricingTier>) => {
    const tiers = (value.tiers ?? []).map((t, idx) => (idx === i ? { ...t, ...patch } : t))
    set({ tiers })
  }

  const inputCls =
    'w-full card px-4 py-2 text-white text-sm focus:outline-none focus:border-gold-500'
  const labelCls = 'block text-xs text-dark-400 mb-1'

  return (
    <div className="space-y-4">
      {/* Nom */}
      <div>
        <label className={labelCls}>Nom de la règle *</label>
        <input
          type="text"
          value={value.name ?? ''}
          onChange={(e) => set({ name: e.target.value })}
          placeholder="Ex: Tarif weekend"
          className={inputCls}
        />
      </div>

      {/* Type */}
      <div>
        <label className={labelCls}>Type de règle *</label>
        <select
          value={ruleType}
          onChange={(e) => set({ rule_type: e.target.value as PricingRuleType, tiers: undefined })}
          className={inputCls}
        >
          {(Object.keys(RULE_TYPE_LABELS) as PricingRuleType[]).map((t) => (
            <option key={t} value={t}>
              {RULE_TYPE_LABELS[t]}
            </option>
          ))}
        </select>
      </div>

      {/* Champ conditionnel : remise flat/seasonal/custom */}
      {(ruleType === 'flat' || ruleType === 'seasonal' || ruleType === 'custom') && (
        <div>
          <label className={labelCls}>Remise (%)</label>
          <input
            type="number"
            min={0}
            max={100}
            step={0.5}
            value={value.discount_pct ?? ''}
            onChange={(e) => set({ discount_pct: parseFloat(e.target.value) || undefined })}
            placeholder="0"
            className={inputCls}
          />
        </div>
      )}

      {/* Champ conditionnel : prix par jour */}
      {ruleType === 'per_day' && (
        <div>
          <label className={labelCls}>Remise par jour (%)</label>
          <input
            type="number"
            min={0}
            max={100}
            step={0.5}
            value={value.discount_pct ?? ''}
            onChange={(e) => set({ discount_pct: parseFloat(e.target.value) || undefined })}
            placeholder="0"
            className={inputCls}
          />
        </div>
      )}

      {/* Champ conditionnel : paliers (tiered / volume) */}
      {(ruleType === 'tiered' || ruleType === 'volume') && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className={labelCls + ' mb-0'}>Paliers de prix</label>
            <button
              type="button"
              onClick={addTier}
              className="flex items-center gap-1 text-xs text-gold-400 hover:text-gold-300"
            >
              <Plus className="w-3 h-3" />
              Ajouter
            </button>
          </div>
          {(value.tiers ?? []).length === 0 && (
            <p className="text-xs text-dark-500 italic">Aucun palier — cliquez sur Ajouter</p>
          )}
          {(value.tiers ?? []).map((tier, i) => (
            <div key={i} className="flex items-center gap-2 bg-dark-900/60 rounded-lg p-2">
              <div className="flex-1">
                <label className="text-xs text-dark-500">Qté min</label>
                <input
                  type="number"
                  min={1}
                  value={tier.min_qty}
                  onChange={(e) => updateTier(i, { min_qty: parseInt(e.target.value) || 1 })}
                  className="w-full bg-dark-900 border border-dark-600 rounded px-2 py-1 text-white text-xs"
                />
              </div>
              <div className="flex-1">
                <label className="text-xs text-dark-500">Qté max</label>
                <input
                  type="number"
                  min={tier.min_qty + 1}
                  value={tier.max_qty ?? ''}
                  onChange={(e) =>
                    updateTier(i, { max_qty: parseInt(e.target.value) || undefined })
                  }
                  placeholder="∞"
                  className="w-full bg-dark-900 border border-dark-600 rounded px-2 py-1 text-white text-xs"
                />
              </div>
              <div className="flex-1">
                <label className="text-xs text-dark-500">Prix unitaire (€)</label>
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  value={tierPriceInputs[i] ?? ''}
                  onChange={(e) => {
                    const next = [...tierPriceInputs]
                    next[i] = e.target.value
                    setTierPriceInputs(next)
                    const cents = decimalToCents(e.target.value)
                    if (cents !== undefined) updateTier(i, { unit_price_cents: cents })
                  }}
                  placeholder="0.00"
                  className="w-full bg-dark-900 border border-dark-600 rounded px-2 py-1 text-white text-xs"
                />
              </div>
              <button
                type="button"
                onClick={() => removeTier(i)}
                className="text-red-400 hover:text-red-300 shrink-0 mt-4"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Plage de validité (seasonal obligatoire, optionnel sinon) */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelCls}>
            Valide du{ruleType === 'seasonal' ? ' *' : ''}
          </label>
          <input
            type="date"
            value={value.valid_from ?? ''}
            max={value.valid_to || undefined}
            onChange={(e) => set({ valid_from: e.target.value || undefined })}
            className={inputCls}
          />
        </div>
        <div>
          <label className={labelCls}>
            Au{ruleType === 'seasonal' ? ' *' : ''}
          </label>
          <input
            type="date"
            value={value.valid_to ?? ''}
            min={value.valid_from || undefined}
            onChange={(e) => set({ valid_to: e.target.value || undefined })}
            className={inputCls}
          />
        </div>
      </div>
      {dateError && (
        <p className="text-red-400 text-xs -mt-2">{dateError}</p>
      )}

      {/* Périmètre d'application */}
      <div>
        <label className={labelCls}>S'applique à</label>
        <select
          value={value.applies_to ?? 'all'}
          onChange={(e) => set({ applies_to: e.target.value as PricingRuleCreate['applies_to'] })}
          className={inputCls}
        >
          <option value="all">Tous les produits</option>
          <option value="category">Une catégorie</option>
          <option value="product">Un produit</option>
        </select>
      </div>

      {value.applies_to === 'product' && (
        <div>
          <label className={labelCls}>Produit cible *</label>
          <select
            value={value.target_id ?? ''}
            onChange={(e) => set({ target_id: parseInt(e.target.value) || undefined })}
            className={inputCls}
          >
            <option value="">— Sélectionner un produit —</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      )}
      {value.applies_to === 'category' && (
        <div>
          <label className={labelCls}>Catégorie cible *</label>
          <select
            value={value.target_id ?? ''}
            onChange={(e) => set({ target_id: parseInt(e.target.value) || undefined })}
            className={inputCls}
          >
            <option value="">— Sélectionner une catégorie —</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
      )}
    </div>
  )
}
