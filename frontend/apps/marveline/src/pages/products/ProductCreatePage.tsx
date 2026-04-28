import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { useCreateProduct, useCategoriesList } from '@/api/queries'
import { MoneyInput } from '@shared/components/ui/MoneyInput'
import type { ProductCreate } from '@/types/product'
import { normalizeError } from '@shared/errors/normalizer'

const PRODUCT_CONDITIONS = [
  { value: 'new', label: 'Neuf' },
  { value: 'excellent', label: 'Excellent état' },
  { value: 'good', label: 'Bon état' },
  { value: 'fair', label: 'État correct' },
]

function generateSku(name: string, category: string): string {
  const cat = (category || 'GEN').substring(0, 3).toUpperCase()
  const suffix = Math.random().toString(36).substring(2, 7).toUpperCase()
  const prefix = name ? name.substring(0, 3).toUpperCase().replace(/[^A-Z]/g, 'X') : 'PRD'
  return `${cat}-${prefix}${suffix}`
}

const STEPS = ['Identité', 'Tarification', 'Stock']

export default function ProductCreatePage() {
  const navigate = useNavigate()
  const createMutation = useCreateProduct()
  const { data: categories } = useCategoriesList()

  const [step, setStep] = useState(0)
  const [errors, setErrors] = useState<Record<string, string>>({})

  // Step 1 — Identité
  const [name, setName] = useState('')
  const [category, setCategory] = useState('')
  const [sku, setSku] = useState('')
  const [skuManual, setSkuManual] = useState(false)

  // Step 2 — Tarification
  const [pricePerDayCents, setPricePerDayCents] = useState(0)
  const [depositAmountCents, setDepositAmountCents] = useState(0)

  // Step 3 — Stock
  const [stockQuantity, setStockQuantity] = useState(1)
  const [condition, setCondition] = useState('good')
  const [imageUrl, setImageUrl] = useState('')

  function validateStep(): boolean {
    const e: Record<string, string> = {}
    if (step === 0) {
      if (!name.trim()) e.name = 'Le nom est requis'
      if (!category) e.category = 'La catégorie est requise'
      if (!sku.trim()) e.sku = 'Le SKU est requis'
    } else if (step === 1) {
      if (pricePerDayCents <= 0) e.price = 'Le prix doit être supérieur à 0'
    } else if (step === 2) {
      if (stockQuantity < 1) e.stock = 'La quantité doit être au moins 1'
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  function handleNext() {
    if (!validateStep()) return
    if (step === 0 && !skuManual) {
      setSku(generateSku(name, category))
    }
    if (step < STEPS.length - 1) {
      setStep(step + 1)
    }
  }

  function handleSubmit() {
    if (!validateStep()) return
    const data: ProductCreate = {
      name: name.trim(),
      sku: sku.trim(),
      category,
      price_per_day_cents: pricePerDayCents,
      deposit_amount_cents: depositAmountCents || undefined,
      stock_quantity: stockQuantity,
      available_quantity: stockQuantity,
      condition,
      image_url: imageUrl || undefined,
    }
    createMutation.mutate(data, {
      onSuccess: (product) => {
        navigate({ to: '/catalogue/products/$id', params: { id: String(product.id) } })
      },
      onError: (err) => {
        setErrors({
          submit: normalizeError(err).message || 'Erreur lors de la création',
        })
      },
    })
  }

  const catList = categories ?? []

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          to="/catalogue/products"
          className="p-2 hover:bg-dark-600 rounded-lg text-dark-400 hover:text-dark-50 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <PageHeader title="Nouveau produit" />
      </div>

      {/* Stepper */}
      <div className="flex items-center gap-0">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center flex-1">
            <button
              onClick={() => i < step && setStep(i)}
              disabled={i >= step}
              className="flex items-center gap-2 text-sm disabled:cursor-default"
            >
              <span
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold border ${
                  i < step
                    ? 'bg-primary-500 border-primary-500 text-white'
                    : i === step
                    ? 'bg-dark-900 border-primary-500 text-primary-400'
                    : 'bg-dark-900 border-dark-600 text-dark-500'
                }`}
              >
                {i + 1}
              </span>
              <span
                className={`hidden sm:block ${
                  i === step ? 'text-white font-medium' : i < step ? 'text-primary-400' : 'text-dark-500'
                }`}
              >
                {label}
              </span>
            </button>
            {i < STEPS.length - 1 && (
              <div className={`flex-1 h-px mx-4 ${i < step ? 'bg-primary-500' : 'bg-dark-900'}`} />
            )}
          </div>
        ))}
      </div>

      {/* Contenu étape */}
      <div className="card p-6 space-y-4">
        {errors.submit && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {errors.submit}
          </div>
        )}

        {step === 0 && (
          <>
            <h2 className="text-sm font-semibold text-dark-300 uppercase tracking-wide">Identité</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-dark-400 mb-1">Nom du produit *</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value)
                    if (!skuManual) setSku(generateSku(e.target.value, category))
                  }}
                  className="input"
                  placeholder="ex: Table ronde 180cm"
                />
                {errors.name && <p className="text-xs text-red-400 mt-1">{errors.name}</p>}
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">Catégorie *</label>
                <select
                  value={category}
                  onChange={(e) => {
                    setCategory(e.target.value)
                    if (!skuManual) setSku(generateSku(name, e.target.value))
                  }}
                  className="input"
                >
                  <option value="">Sélectionner…</option>
                  {catList.map((c) => (
                    <option key={c.slug} value={c.slug}>{c.name}</option>
                  ))}
                </select>
                {errors.category && <p className="text-xs text-red-400 mt-1">{errors.category}</p>}
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">SKU *</label>
                <input
                  type="text"
                  value={sku}
                  onChange={(e) => { setSku(e.target.value); setSkuManual(true) }}
                  className="input font-mono"
                  placeholder="AUTO-GÉNÉRÉ"
                />
                {errors.sku && <p className="text-xs text-red-400 mt-1">{errors.sku}</p>}
                <p className="text-xs text-dark-500 mt-1">Modifiez pour personnaliser le SKU</p>
              </div>
            </div>
          </>
        )}

        {step === 1 && (
          <>
            <h2 className="text-sm font-semibold text-dark-300 uppercase tracking-wide">Tarification</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-dark-400 mb-1">Prix / jour *</label>
                <MoneyInput value={pricePerDayCents} onChange={setPricePerDayCents} placeholder="0,00" />
                {errors.price && <p className="text-xs text-red-400 mt-1">{errors.price}</p>}
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">Caution</label>
                <MoneyInput value={depositAmountCents} onChange={setDepositAmountCents} placeholder="0,00" />
              </div>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <h2 className="text-sm font-semibold text-dark-300 uppercase tracking-wide">Stock</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-dark-400 mb-1">Quantité totale *</label>
                <input
                  type="number"
                  min={1}
                  value={stockQuantity}
                  onChange={(e) => setStockQuantity(Number(e.target.value))}
                  className="input"
                />
                {errors.stock && <p className="text-xs text-red-400 mt-1">{errors.stock}</p>}
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">État initial</label>
                <select
                  value={condition}
                  onChange={(e) => setCondition(e.target.value)}
                  className="input"
                >
                  {PRODUCT_CONDITIONS.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">URL image principale</label>
                <input
                  type="url"
                  value={imageUrl}
                  onChange={(e) => setImageUrl(e.target.value)}
                  className="input"
                  placeholder="https://…"
                />
              </div>
            </div>
          </>
        )}
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between gap-3">
        <button
          onClick={() => step > 0 ? setStep(step - 1) : undefined}
          disabled={step === 0}
          className="btn-secondary disabled:opacity-40"
        >
          Précédent
        </button>

        {step < STEPS.length - 1 ? (
          <button onClick={handleNext} className="btn-primary">
            Suivant
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={createMutation.isPending}
            className="btn-primary"
          >
            {createMutation.isPending ? 'Création…' : 'Créer le produit'}
          </button>
        )}
      </div>
    </div>
  )
}
