import { useState } from 'react'
import { useParams } from '@tanstack/react-router'
import {
  ChevronDown,
  ChevronRight,
  Plus,
  Pencil,
  Trash2,
  Layers,
  CheckCircle2,
  Clock,
  AlertCircle,
} from 'lucide-react'
import {
  useDevisModules,
  useAddDevisModule,
  useUpdateDevisModule,
  useDeleteDevisModule,
  useDevisCoverageItems,
  useAddDevisCoverageItem,
  useUpdateDevisCoverageItem,
  useDeleteDevisCoverageItem,
} from '@/api/queries/useDevis'
import { normalizeError } from '@shared/errors/normalizer'
import type {
  DevisModule,
  DevisModuleType,
  DevisModuleCreate,
  DevisModuleUpdate,
  DevisCoverageItem,
  DevisCoverageItemCreate,
} from '@/types/devis'

const MODULE_TYPE_LABELS: Record<DevisModuleType, string> = {
  socle: 'Socle',
  stock: 'Stock',
  facturation: 'Facturation',
  securite: 'Securite',
  services: 'Services',
}

const MODULE_TYPES: DevisModuleType[] = ['socle', 'stock', 'facturation', 'securite', 'services']

type DeliveryStatus = 'a_cadrer' | 'en_cours' | 'livre'

const DELIVERY_STATUS_CONFIG: Record<DeliveryStatus, { label: string; icon: typeof Clock; color: string; bg: string }> = {
  a_cadrer: { label: 'A cadrer', icon: AlertCircle, color: 'text-yellow-400', bg: 'bg-yellow-900/30 border-yellow-700/40' },
  en_cours: { label: 'En cours', icon: Clock, color: 'text-orange-400', bg: 'bg-orange-900/30 border-orange-700/40' },
  livre: { label: 'Livre', icon: CheckCircle2, color: 'text-green-400', bg: 'bg-green-900/30 border-green-700/40' },
}

type ModuleFormState = { module_type: DevisModuleType; label: string }
type ItemFormState = { title: string; status: DeliveryStatus }

export default function DevisPrestationsPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const devisId = parseInt(id, 10)

  const { data: modules = [], isLoading: loadingModules } = useDevisModules(devisId)
  const { data: coverageItems = [], isLoading: loadingItems } = useDevisCoverageItems(devisId)
  const addModule = useAddDevisModule()
  const updateModule = useUpdateDevisModule()
  const deleteModule = useDeleteDevisModule()
  const addCoverageItem = useAddDevisCoverageItem()
  const updateCoverageItem = useUpdateDevisCoverageItem()
  const deleteCoverageItem = useDeleteDevisCoverageItem()

  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [moduleForm, setModuleForm] = useState<ModuleFormState | null>(null)
  const [editingModule, setEditingModule] = useState<DevisModule | null>(null)
  const [itemForm, setItemForm] = useState<{ moduleId: number; form: ItemFormState } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const toggle = (moduleId: number) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(moduleId)) next.delete(moduleId)
      else next.add(moduleId)
      return next
    })
  }

  const itemsByModule = (moduleId: number) =>
    coverageItems.filter((item) => item.module_id === moduleId)

  // KPIs
  const totalModules = modules.length
  const totalItems = coverageItems.length
  const itemsLivres = coverageItems.filter((i) => i.status === 'livre').length
  const itemsEnCours = coverageItems.filter((i) => i.status === 'en_cours').length
  const itemsACadrer = coverageItems.filter((i) => i.status === 'a_cadrer').length

  // Module CRUD
  const handleAddModule = () => {
    if (!moduleForm || !moduleForm.label.trim()) {
      setError('Le label est requis.')
      return
    }
    setError(null)
    const data: DevisModuleCreate = { module_type: moduleForm.module_type, label: moduleForm.label.trim() }
    addModule.mutate({ devisId, data }, {
      onSuccess: () => setModuleForm(null),
      onError: (err) => setError(normalizeError(err).message || 'Erreur lors de l\'ajout.'),
    })
  }

  const handleUpdateModule = () => {
    if (!editingModule || !moduleForm || !moduleForm.label.trim()) {
      setError('Le label est requis.')
      return
    }
    setError(null)
    const data: DevisModuleUpdate = { label: moduleForm.label.trim() }
    updateModule.mutate({ devisId, moduleId: editingModule.id, data }, {
      onSuccess: () => { setModuleForm(null); setEditingModule(null) },
      onError: (err) => setError(normalizeError(err).message || 'Erreur lors de la modification.'),
    })
  }

  const handleDeleteModule = (mod: DevisModule) => {
    deleteModule.mutate({ devisId, moduleId: mod.id }, {
      onError: (err) => setError(normalizeError(err).message || 'Erreur lors de la suppression.'),
    })
  }

  const handleUpdateDeliveryStatus = (mod: DevisModule, status: DeliveryStatus) => {
    updateModule.mutate({ devisId, moduleId: mod.id, data: { delivery_status: status } })
  }

  // Coverage item CRUD
  const handleAddItem = (moduleId: number) => {
    if (!itemForm || !itemForm.form.title.trim()) {
      setError('Le titre est requis.')
      return
    }
    setError(null)
    const data: DevisCoverageItemCreate = {
      title: itemForm.form.title.trim(),
      status: itemForm.form.status,
      module_id: moduleId,
    }
    addCoverageItem.mutate({ devisId, data }, {
      onSuccess: () => setItemForm(null),
      onError: (err) => setError(normalizeError(err).message || 'Erreur lors de l\'ajout.'),
    })
  }

  const handleUpdateItemStatus = (item: DevisCoverageItem, status: DeliveryStatus) => {
    updateCoverageItem.mutate({ devisId, itemId: item.id, data: { status } })
  }

  const handleDeleteItem = (item: DevisCoverageItem) => {
    deleteCoverageItem.mutate({ devisId, itemId: item.id })
  }

  if (loadingModules || loadingItems) {
    return (
      <div className="space-y-4 animate-pulse">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="card p-4 space-y-3">
            <div className="h-4 skel rounded w-40" />
            <div className="h-3 skel rounded w-64" />
            <div className="h-3 skel rounded w-48" />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="card p-3 text-center">
          <p className="text-2xl font-bold">{totalModules}</p>
          <p className="text-xs text-dark-400">Modules</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-2xl font-bold text-green-400">{itemsLivres}</p>
          <p className="text-xs text-dark-400">Livres</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-2xl font-bold text-orange-400">{itemsEnCours}</p>
          <p className="text-xs text-dark-400">En cours</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-2xl font-bold text-yellow-400">{itemsACadrer}</p>
          <p className="text-xs text-dark-400">A cadrer</p>
        </div>
      </div>

      {/* Liste modules depliables */}
      <div className="space-y-3">
        {modules.map((mod) => {
          const isOpen = expanded.has(mod.id)
          const items = itemsByModule(mod.id)
          const deliveryConfig = DELIVERY_STATUS_CONFIG[(mod.delivery_status ?? 'a_cadrer') as DeliveryStatus]
          const StatusIcon = deliveryConfig?.icon ?? AlertCircle

          return (
            <div key={mod.id} className="card overflow-hidden">
              {/* Header module */}
              <button
                type="button"
                onClick={() => toggle(mod.id)}
                className="w-full p-4 flex items-center gap-3 hover:bg-dark-700/30 transition-colors"
              >
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center shrink-0">
                  <Layers className="w-5 h-5 text-blue-400" />
                </div>
                <div className="flex-1 min-w-0 text-left">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm truncate">{mod.label}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-dark-700 text-dark-300 shrink-0">
                      {MODULE_TYPE_LABELS[mod.module_type]}
                    </span>
                  </div>
                  <p className="text-xs text-dark-400 mt-0.5">
                    {items.length} item{items.length !== 1 ? 's' : ''}
                  </p>
                </div>

                {/* Delivery status pills */}
                <div className="flex items-center gap-1.5 shrink-0">
                  {(['a_cadrer', 'en_cours', 'livre'] as DeliveryStatus[]).map((s) => {
                    const cfg = DELIVERY_STATUS_CONFIG[s]
                    const active = (mod.delivery_status ?? 'a_cadrer') === s
                    return (
                      <button
                        key={s}
                        type="button"
                        onClick={(e) => { e.stopPropagation(); handleUpdateDeliveryStatus(mod, s) }}
                        className={`text-[10px] px-2 py-0.5 rounded-full border font-medium transition-all ${
                          active ? `${cfg.bg} ${cfg.color}` : 'bg-dark-900/50 text-dark-500 border-dark-700 hover:text-dark-300'
                        }`}
                      >
                        {cfg.label}
                      </button>
                    )
                  })}
                </div>

                {/* Actions module */}
                <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => { setEditingModule(mod); setModuleForm({ module_type: mod.module_type, label: mod.label }) }}
                    className="p-1.5 hover:bg-dark-600 rounded text-dark-400 hover:text-dark-50"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleDeleteModule(mod)}
                    className="p-1.5 hover:bg-dark-600 rounded text-dark-400 hover:text-red-400"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>

                {isOpen ? <ChevronDown className="w-4 h-4 text-dark-500 shrink-0" /> : <ChevronRight className="w-4 h-4 text-dark-500 shrink-0" />}
              </button>

              {/* Contenu deplie : items de couverture */}
              {isOpen && (
                <div className="border-t border-dark-700 bg-dark-900/20 p-4 space-y-2">
                  {items.length === 0 && (
                    <p className="text-xs text-dark-500 text-center py-2">Aucun item de couverture</p>
                  )}
                  {items.map((item) => {
                    const itemCfg = DELIVERY_STATUS_CONFIG[(item.status ?? 'a_cadrer') as DeliveryStatus]
                    return (
                      <div key={item.id} className="flex items-center gap-3 py-1.5">
                        <StatusIcon className={`w-3.5 h-3.5 ${itemCfg.color} shrink-0`} />
                        <span className="flex-1 text-sm truncate">{item.title}</span>
                        <div className="flex items-center gap-1 shrink-0">
                          {(['a_cadrer', 'en_cours', 'livre'] as DeliveryStatus[]).map((s) => {
                            const cfg = DELIVERY_STATUS_CONFIG[s]
                            const active = (item.status ?? 'a_cadrer') === s
                            return (
                              <button
                                key={s}
                                onClick={() => handleUpdateItemStatus(item, s)}
                                className={`text-[9px] px-1.5 py-0.5 rounded-full border font-medium transition-all ${
                                  active ? `${cfg.bg} ${cfg.color}` : 'bg-dark-900/50 text-dark-600 border-dark-800 hover:text-dark-400'
                                }`}
                              >
                                {cfg.label}
                              </button>
                            )
                          })}
                          <button
                            onClick={() => handleDeleteItem(item)}
                            className="p-1 hover:bg-dark-600 rounded text-dark-500 hover:text-red-400 ml-1"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                    )
                  })}

                  {/* Ajouter item inline */}
                  {itemForm?.moduleId === mod.id ? (
                    <div className="flex items-center gap-2 mt-2">
                      <input
                        type="text"
                        placeholder="Titre de l'item..."
                        value={itemForm.form.title}
                        onChange={(e) => setItemForm({ moduleId: mod.id, form: { ...itemForm.form, title: e.target.value } })}
                        className="input flex-1 text-sm"
                        autoFocus
                        onKeyDown={(e) => { if (e.key === 'Enter') handleAddItem(mod.id); if (e.key === 'Escape') setItemForm(null) }}
                      />
                      <button
                        onClick={() => handleAddItem(mod.id)}
                        disabled={addCoverageItem.isPending}
                        className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg disabled:opacity-50"
                      >
                        Ajouter
                      </button>
                      <button onClick={() => setItemForm(null)} className="text-xs text-dark-400 hover:text-dark-50 px-2 py-1.5">
                        Annuler
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setItemForm({ moduleId: mod.id, form: { title: '', status: 'a_cadrer' } })}
                      className="flex items-center gap-1.5 text-xs text-dark-400 hover:text-blue-400 mt-2"
                    >
                      <Plus className="w-3 h-3" /> Ajouter un item
                    </button>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Formulaire ajout/edition module */}
      {moduleForm && !editingModule ? (
        <div className="card p-4 space-y-3 border border-blue-700/40">
          <p className="text-sm font-medium">Nouveau module</p>
          <div>
            <label className="block text-xs text-dark-400 mb-1">Type</label>
            <select
              value={moduleForm.module_type}
              onChange={(e) => setModuleForm({ ...moduleForm, module_type: e.target.value as DevisModuleType })}
              className="input"
            >
              {MODULE_TYPES.map((t) => (
                <option key={t} value={t}>{MODULE_TYPE_LABELS[t]}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-dark-400 mb-1">Label</label>
            <input
              type="text"
              placeholder="Nom du module..."
              value={moduleForm.label}
              onChange={(e) => setModuleForm({ ...moduleForm, label: e.target.value })}
              className="input"
              autoFocus
            />
          </div>
          {error && <p className="text-red-400 text-xs">{error}</p>}
          <div className="flex gap-2">
            <button onClick={() => { setModuleForm(null); setError(null) }} className="flex-1 text-sm text-dark-400 hover:text-dark-50 py-2 rounded-lg border border-dark-600">
              Annuler
            </button>
            <button onClick={handleAddModule} disabled={addModule.isPending} className="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 rounded-lg disabled:opacity-50">
              {addModule.isPending ? 'Enregistrement...' : 'Enregistrer'}
            </button>
          </div>
        </div>
      ) : editingModule && moduleForm ? (
        <div className="card p-4 space-y-3 border border-blue-700/40">
          <p className="text-sm font-medium">Modifier le module</p>
          <div>
            <label className="block text-xs text-dark-400 mb-1">Label</label>
            <input
              type="text"
              value={moduleForm.label}
              onChange={(e) => setModuleForm({ ...moduleForm, label: e.target.value })}
              className="input"
              autoFocus
            />
          </div>
          {error && <p className="text-red-400 text-xs">{error}</p>}
          <div className="flex gap-2">
            <button onClick={() => { setModuleForm(null); setEditingModule(null); setError(null) }} className="flex-1 text-sm text-dark-400 hover:text-dark-50 py-2 rounded-lg border border-dark-600">
              Annuler
            </button>
            <button onClick={handleUpdateModule} disabled={updateModule.isPending} className="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 rounded-lg disabled:opacity-50">
              {updateModule.isPending ? 'Enregistrement...' : 'Enregistrer'}
            </button>
          </div>
        </div>
      ) : null}

      {/* Bouton ajouter module */}
      {!moduleForm && (
        <button
          onClick={() => setModuleForm({ module_type: 'socle', label: '' })}
          className="w-full flex items-center justify-center gap-2 py-3 text-sm text-dark-400 hover:text-blue-400 border border-dashed border-dark-600 hover:border-blue-700/40 rounded-xl transition-colors"
        >
          <Plus className="w-4 h-4" /> Ajouter un module
        </button>
      )}

      {error && !moduleForm && <p className="text-red-400 text-xs text-center">{error}</p>}
    </div>
  )
}
