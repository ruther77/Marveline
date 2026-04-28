import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { Star, Plus, Pencil, Trash2, ChevronDown, ChevronUp, Users } from 'lucide-react'
import {
  useFormulasList,
  useCreateFormula,
  useUpdateFormula,
  useDeleteFormula,
  useProductsList,
} from '@/api/queries'
import { Modal } from '@shared/components/ui/Modal'
import { formatCents } from '@/lib/utils'
import type { Formula, FormulaCreate, FormulaItemCreate, FormulaType } from '@/types/formula'
import { normalizeError } from '@shared/errors/normalizer'

// ── Constantes ───────────────────────────────────────────────────────────────

const FORMULA_TYPE_LABEL: Record<FormulaType, string> = {
  classic: 'Classique',
  vin_honneur: "Vin d'honneur",
}

// ── Formulaire formule ───────────────────────────────────────────────────────

interface FormulaFormState {
  name: string
  slug: string
  description: string
  formula_type: FormulaType
  price_per_person_euros: string
  featured: boolean
  sort_order: string
  items: FormulaItemCreate[]
}

const EMPTY_FORM: FormulaFormState = {
  name: '',
  slug: '',
  description: '',
  formula_type: 'classic',
  price_per_person_euros: '',
  featured: false,
  sort_order: '0',
  items: [],
}

function formulaToForm(f: Formula): FormulaFormState {
  return {
    name: f.name,
    slug: f.slug,
    description: f.description ?? '',
    formula_type: f.formula_type,
    price_per_person_euros: (f.price_per_person_cents / 100).toFixed(2),
    featured: f.featured,
    sort_order: String(f.sort_order),
    items: f.items.map((i) => ({ product_id: i.product_id, quantity_per_person: i.quantity_per_person })),
  }
}

function slugify(s: string): string {
  return s.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')
}

// ── Modal formulaire ─────────────────────────────────────────────────────────

interface ProductOption {
  id: number
  name: string
}

interface FormModalProps {
  isOpen: boolean
  onClose: () => void
  onCreated?: (formula: Formula) => void
  editing: Formula | null
  products: ProductOption[]
}

function FormulaFormModal({ isOpen, onClose, onCreated, editing, products }: FormModalProps) {
  const [form, setForm] = useState<FormulaFormState>(
    editing ? formulaToForm(editing) : EMPTY_FORM,
  )
  const [error, setError] = useState('')

  const create = useCreateFormula()
  const update = useUpdateFormula()

  const isPending = create.isPending || update.isPending

  const setField = <K extends keyof FormulaFormState>(k: K, v: FormulaFormState[K]) =>
    setForm((f) => ({ ...f, [k]: v }))

  const handleNameChange = (v: string) => {
    setForm((f) => ({ ...f, name: v, slug: editing ? f.slug : slugify(v) }))
  }

  const addItem = () =>
    setForm((f) => ({ ...f, items: [...f.items, { product_id: 0, quantity_per_person: 1 }] }))

  const removeItem = (i: number) =>
    setForm((f) => ({ ...f, items: f.items.filter((_, idx) => idx !== i) }))

  const updateItem = (i: number, key: keyof FormulaItemCreate, value: number) =>
    setForm((f) => ({
      ...f,
      items: f.items.map((item, idx) => (idx === i ? { ...item, [key]: value } : item)),
    }))

  const handleSubmit = async () => {
    setError('')
    const priceCents = Math.round(parseFloat(form.price_per_person_euros) * 100)
    if (!form.name.trim()) { setError('Nom requis.'); return }
    if (!form.slug.trim()) { setError('Slug requis.'); return }
    if (isNaN(priceCents) || priceCents <= 0) { setError('Prix invalide.'); return }
    if (form.items.some((i) => i.product_id === 0)) { setError('Sélectionnez un produit pour chaque ligne.'); return }

    const payload: FormulaCreate = {
      name: form.name.trim(),
      slug: form.slug.trim(),
      description: form.description.trim() || null,
      formula_type: form.formula_type,
      price_per_person_cents: priceCents,
      featured: form.featured,
      sort_order: parseInt(form.sort_order) || 0,
      items: form.items,
    }

    try {
      if (editing) {
        await update.mutateAsync({ id: editing.id, data: payload })
        onClose()
      } else {
        const result = await create.mutateAsync(payload)
        onClose()
        onCreated?.(result)
      }
    } catch (err) {
      setError(normalizeError(err).message || 'Erreur lors de l\'enregistrement.')
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={editing ? 'Modifier la formule' : 'Nouvelle formule'}
      footer={
        <div className="flex justify-end gap-4">
          <button onClick={onClose} className="px-4 py-2 text-sm text-dark-400 hover:text-dark-100">
            Annuler
          </button>
          <button
            onClick={handleSubmit}
            disabled={isPending}
            className="btn btn-primary"
          >
            {isPending ? 'Enregistrement…' : editing ? 'Mettre à jour' : 'Créer'}
          </button>
        </div>
      }
    >
      <div className="space-y-4 p-1">
        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <label className="block text-sm font-medium text-dark-400 mb-1">Nom *</label>
            <input
              className="input"
              value={form.name}
              onChange={(e) => handleNameChange(e.target.value)}
              placeholder="Formule Prestige"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-400 mb-1">Slug *</label>
            <input
              className="input"
              value={form.slug}
              onChange={(e) => setField('slug', e.target.value)}
              placeholder="formule-prestige"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-400 mb-1">Type</label>
            <select
              className="input"
              value={form.formula_type}
              onChange={(e) => setField('formula_type', e.target.value as FormulaType)}
            >
              <option value="classic">Classique</option>
              <option value="vin_honneur">Vin d'honneur</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-400 mb-1">Prix / personne (€) *</label>
            <input
              type="number"
              min="0"
              step="0.01"
              className="input"
              value={form.price_per_person_euros}
              onChange={(e) => setField('price_per_person_euros', e.target.value)}
              placeholder="45.00"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-400 mb-1">Ordre d'affichage</label>
            <input
              type="number"
              min="0"
              className="input"
              value={form.sort_order}
              onChange={(e) => setField('sort_order', e.target.value)}
            />
          </div>
          <div className="col-span-2">
            <label className="block text-sm font-medium text-dark-400 mb-1">Description</label>
            <textarea
              className="input w-full h-20 resize-none"
              value={form.description}
              onChange={(e) => setField('description', e.target.value)}
              placeholder="Description de la formule…"
            />
          </div>
          <div className="col-span-2 flex items-center gap-2">
            <input
              type="checkbox"
              id="featured"
              checked={form.featured}
              onChange={(e) => setField('featured', e.target.checked)}
              className="w-4 h-4 rounded"
            />
            <label htmlFor="featured" className="text-sm text-dark-400 cursor-pointer">
              Formule mise en avant
            </label>
          </div>
        </div>

        {/* Lignes produits */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-semibold">Lignes produits</p>
            <button onClick={addItem} className="text-xs text-primary-400 hover:underline flex items-center gap-1">
              <Plus className="w-3.5 h-3.5" /> Ajouter
            </button>
          </div>
          {form.items.length === 0 ? (
            <p className="text-xs text-dark-400 italic">Aucune ligne — la formule sera vide.</p>
          ) : (
            <div className="space-y-2">
              {form.items.map((item, i) => (
                <div key={i} className="flex items-center gap-2">
                  <select
                    className="input flex-1 text-sm"
                    value={item.product_id || ''}
                    onChange={(e) => updateItem(i, 'product_id', Number(e.target.value))}
                  >
                    <option value="">— Produit —</option>
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    className="input w-24 text-sm"
                    value={item.quantity_per_person}
                    onChange={(e) => updateItem(i, 'quantity_per_person', parseFloat(e.target.value) || 0)}
                    title="Qté / pers"
                  />
                  <span className="text-xs text-dark-400 shrink-0">/ pers</span>
                  <button onClick={() => removeItem(i)} className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center text-red-400 hover:text-red-300 rounded">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}

// ── Modal suppression ────────────────────────────────────────────────────────

interface DeleteModalProps {
  formula: Formula | null
  onClose: () => void
}

function FormulaDeleteModal({ formula, onClose }: DeleteModalProps) {
  const del = useDeleteFormula()
  const [error, setError] = useState('')

  const handleDelete = async () => {
    if (!formula) return
    setError('')
    try {
      await del.mutateAsync(formula.id)
      onClose()
    } catch (err) {
      setError(normalizeError(err).message || 'Erreur lors de la suppression.')
    }
  }

  return (
    <Modal
      isOpen={!!formula}
      onClose={onClose}
      title="Supprimer la formule"
      footer={
        <div className="flex justify-end gap-4">
          <button onClick={onClose} className="px-4 py-2 text-sm text-dark-400 hover:text-dark-100">
            Annuler
          </button>
          <button
            onClick={handleDelete}
            disabled={del.isPending}
            className="btn btn-danger"
          >
            {del.isPending ? 'Suppression…' : 'Supprimer'}
          </button>
        </div>
      }
    >
      <div className="p-1 space-y-4">
        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}
        <p className="text-sm text-dark-400">
          Supprimer <span className="font-semibold">{formula?.name}</span> ?
          Cette action est irréversible.
        </p>
      </div>
    </Modal>
  )
}

// ── Carte formule ────────────────────────────────────────────────────────────

interface FormulaCardProps {
  formula: Formula
  onEdit: () => void
  onDelete: () => void
  products: ProductOption[]
}

function FormulaCard({ formula, onEdit, onDelete, products }: FormulaCardProps) {
  const [expanded, setExpanded] = useState(false)

  const productName = (pid: number) => products.find((p) => p.id === pid)?.name ?? `#${pid}`

  return (
    <div className="card p-0 overflow-hidden">
      <div className="flex items-start gap-4 p-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-base font-semibold truncate">{formula.name}</h3>
            {formula.featured && (
              <span className="inline-flex items-center gap-1 text-xs bg-amber-500/15 text-amber-400 border border-amber-500/30 rounded-full px-2 py-0.5">
                <Star className="w-3 h-3" /> Mise en avant
              </span>
            )}
            <span className="text-xs bg-dark-900 text-dark-400 border border-dark-600 rounded-full px-2 py-0.5">
              {FORMULA_TYPE_LABEL[formula.formula_type]}
            </span>
          </div>
          {formula.description && (
            <p className="text-sm text-dark-400 mt-0.5 line-clamp-2">{formula.description}</p>
          )}
          <div className="flex items-center gap-4 mt-2">
            <span className="text-lg font-bold text-primary-400">
              {formatCents(formula.price_per_person_cents)}
            </span>
            <span className="text-sm text-dark-400 flex items-center gap-1">
              <Users className="w-3.5 h-3.5" /> par personne
            </span>
            <span className="text-xs text-dark-400">
              {formula.items.length} produit{formula.items.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={onEdit}
            className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-dark-600 text-dark-400 hover:text-dark-100 transition-colors"
            title="Modifier"
          >
            <Pencil className="w-4 h-4" />
          </button>
          <button
            onClick={onDelete}
            className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-red-500/10 text-dark-400 hover:text-red-400 transition-colors"
            title="Supprimer"
          >
            <Trash2 className="w-4 h-4" />
          </button>
          {formula.items.length > 0 && (
            <button
              onClick={() => setExpanded((e) => !e)}
              className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-dark-600 text-dark-400 hover:text-dark-100 transition-colors"
            >
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          )}
        </div>
      </div>

      {expanded && formula.items.length > 0 && (
        <div className="border-t border-dark-600 divide-y divide-border">
          {formula.items.map((item) => (
            <div key={item.id} className="flex items-center justify-between px-4 py-2.5">
              <span className="text-sm">{productName(item.product_id)}</span>
              <span className="text-sm text-dark-400">
                ×{item.quantity_per_person} / pers
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Page principale ──────────────────────────────────────────────────────────

export default function FormulasPage() {
  const [typeFilter, setTypeFilter] = useState<string>('')
  const [formOpen, setFormOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Formula | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Formula | null>(null)

  // Products liftés ici — 1 seule query partagée par FormulaFormModal + FormulaCard
  const { data: productsData } = useProductsList({ limit: 500, active_only: true })
  const products: ProductOption[] = productsData?.items ?? []

  const { data: rawFormulas, isLoading, isError, refetch } = useFormulasList(
    typeFilter ? { formula_type: typeFilter } : undefined,
  )
  const formulas = Array.isArray(rawFormulas) ? rawFormulas : []

  const handleEdit = (f: Formula) => { setEditTarget(f); setFormOpen(true) }
  const handleCloseForm = () => { setFormOpen(false); setEditTarget(null) }
  const handleCreated = (formula: Formula) => { setEditTarget(formula); setFormOpen(true) }

  const classic = formulas.filter((f) => f.formula_type === 'classic')
  const vinHonneur = formulas.filter((f) => f.formula_type === 'vin_honneur')

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* En-tête */}
      <div className="flex items-center justify-between gap-3">
        <PageHeader title="Formules traiteur" subtitle="Prix par personne, générées depuis vos produits." />
        <button onClick={() => { setEditTarget(null); setFormOpen(true) }} className="btn btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> Nouvelle formule
        </button>
      </div>

      {/* Filtres */}
      <div className="flex gap-2">
        {[
          { value: '', label: 'Toutes' },
          { value: 'classic', label: 'Classique' },
          { value: 'vin_honneur', label: "Vin d'honneur" },
        ].map((opt) => (
          <button
            key={opt.value}
            onClick={() => setTypeFilter(opt.value)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              typeFilter === opt.value
                ? 'bg-primary-500 text-white'
                : 'btn-ghost'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Contenu */}
      {isLoading && (
        <div className="space-y-4 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="card p-4 space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div className="h-4 skel rounded w-40" />
                <div className="h-6 skel rounded w-16" />
              </div>
              <div className="h-3 skel rounded w-64" />
              <div className="flex gap-2">
                <div className="h-5 skel rounded w-20" />
                <div className="h-5 skel rounded w-24" />
              </div>
            </div>
          ))}
        </div>
      )}
      {isError && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm flex items-center justify-between gap-4">
          <span>Impossible de charger les formules.</span>
          <button onClick={() => refetch()} className="btn-secondary text-xs shrink-0">
            Réessayer
          </button>
        </div>
      )}

      {!isLoading && !isError && formulas.length === 0 && (
        <div className="text-center py-16">
          <p className="text-dark-400 text-sm">Aucune formule pour le moment.</p>
          <button
            onClick={() => { setEditTarget(null); setFormOpen(true) }}
            className="mt-4 btn btn-primary"
          >
            Créer la première formule
          </button>
        </div>
      )}

      {!typeFilter && classic.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wider px-1">
            Classiques ({classic.length})
          </h2>
          {classic.map((f) => (
            <FormulaCard key={f.id} formula={f} onEdit={() => handleEdit(f)} onDelete={() => setDeleteTarget(f)} products={products} />
          ))}
        </section>
      )}

      {!typeFilter && vinHonneur.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wider px-1">
            Vin d'honneur ({vinHonneur.length})
          </h2>
          {vinHonneur.map((f) => (
            <FormulaCard key={f.id} formula={f} onEdit={() => handleEdit(f)} onDelete={() => setDeleteTarget(f)} products={products} />
          ))}
        </section>
      )}

      {typeFilter && formulas.map((f) => (
        <FormulaCard key={f.id} formula={f} onEdit={() => handleEdit(f)} onDelete={() => setDeleteTarget(f)} products={products} />
      ))}

      {/* Modals */}
      <FormulaFormModal isOpen={formOpen} onClose={handleCloseForm} onCreated={handleCreated} editing={editTarget} products={products} />
      <FormulaDeleteModal formula={deleteTarget} onClose={() => setDeleteTarget(null)} />
    </div>
  )
}
