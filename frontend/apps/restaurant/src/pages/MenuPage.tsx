/**
 * /restaurant/menu — Configuration de la carte
 * 3 vues : Plats | Boissons | Accompagnements
 */
import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, X, UtensilsCrossed, Power, ChevronDown, ChevronRight } from 'lucide-react'
import { restaurantApi } from '@/api/restaurant'
import { normalizeError } from '@shared/errors/normalizer'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import { MoneyInput } from '@shared/components/ui/MoneyInput'
import type {
  VariantePlatRead,
  VarianteSideRead,
  SideRead,
  TypePreparationRead,
  IngredientRead,
  CategorieIngredientRead,
} from '@/types/restaurant-v2'

type VueMenu = 'plats' | 'boissons' | 'sides'

const CAT_LABELS: Record<string, string> = {
  plats_sauce: 'Plats en sauce', grillades: 'Grillades', poissons: 'Poissons',
  entrees: 'Entrées', accompagnement: 'Accompagnement',
  biere: 'Bières', whisky: 'Whisky', vin: 'Vins', soft: 'Softs',
  champagne: 'Champagne', digestif: 'Digestifs', aperitif: 'Apéritifs', cafe: 'Café',
}

const CAT_PLATS = ['plats_sauce', 'grillades', 'poissons', 'entrees', 'accompagnement']
const CAT_BOISSONS = ['biere', 'whisky', 'vin', 'soft', 'champagne', 'digestif', 'aperitif', 'cafe']

const TVA_OPTIONS = [
  { value: 550,  label: '5,5 % — Taux réduit (alimentaire)' },
  { value: 850,  label: '8,5 % — DOM' },
  { value: 1000, label: '10 % — Restauration sur place' },
  { value: 2000, label: '20 % — Standard' },
]

function fmtPrix(cts: number): string {
  return (cts / 100).toFixed(2) + ' €'
}

// ─── Thumb ──────────────────────────────────────────────────────────────────

function Thumb({ src, alt, size = 48 }: { src: string | null | undefined; alt: string; size?: number }) {
  if (!src) {
    return (
      <div className="rounded-lg bg-stone-100 flex items-center justify-center shrink-0" style={{ width: size, height: size }}>
        <UtensilsCrossed className="h-5 w-5 text-stone-400" />
      </div>
    )
  }
  return (
    <img src={src} alt={alt} className="rounded-lg object-cover shrink-0" style={{ width: size, height: size }} loading="lazy" />
  )
}

// ─── ItemCard (plats & boissons) ─────────────────────────────────────────────

function ItemCard({
  plat,
  typesPrep,
  onEdit,
  onToggle,
}: {
  plat: VariantePlatRead
  typesPrep: TypePreparationRead[]
  onEdit: (p: VariantePlatRead) => void
  onToggle: (p: VariantePlatRead) => void
}) {
  const hasSides = plat.type === 'plat'
  const [expanded, setExpanded] = useState(false)

  const { data: sides = [] } = useQuery({
    queryKey: ['variante-sides', plat.id],
    queryFn: () => restaurantApi.listVarianteSides(plat.id),
    enabled: hasSides && expanded,
    staleTime: 30_000,
  })

  return (
    <div className={`border rounded-xl overflow-hidden transition-shadow hover:shadow-md ${
      plat.is_active ? 'border-stone-200 bg-white' : 'border-stone-200 bg-stone-50 opacity-60'
    }`}>
      <div className="flex items-center gap-3 px-3 py-2.5">
        <Thumb src={plat.image_url} alt={plat.nom} size={44} />
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-semibold text-stone-900 truncate">{plat.nom}</div>
          <div className="flex items-center gap-2 text-[11px] text-stone-500">
            <span className="font-semibold text-stone-900">{fmtPrix(plat.prix_vente_cts)}</span>
            {plat.type_preparation_nom && <span className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 text-[10px] font-medium">{plat.type_preparation_nom}</span>}
            {plat.ingredient_proteine_nom && <span className="px-1.5 py-0.5 rounded bg-red-50 text-red-600 text-[10px] font-medium">{plat.ingredient_proteine_nom} {plat.quantite_proteine ? `${plat.quantite_proteine}kg` : ''}</span>}
            {plat.categorie && <span>{CAT_LABELS[plat.categorie] ?? plat.categorie}</span>}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {hasSides && (
            <button onClick={() => setExpanded(v => !v)} className="p-1.5 text-stone-400 hover:text-stone-700 transition-colors" title="Accompagnements">
              {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            </button>
          )}
          <button onClick={() => onEdit(plat)} className="p-1.5 text-stone-400 hover:text-amber-600 transition-colors" title="Modifier">
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button onClick={() => onToggle(plat)} className={`p-1.5 transition-colors hover:opacity-70 ${plat.is_active ? 'text-emerald-600' : 'text-stone-400'}`} title={plat.is_active ? 'Désactiver' : 'Activer'}>
            <Power className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      {hasSides && expanded && (
        <div className="border-t border-stone-100 px-3 py-2 bg-stone-50">
          <div className="text-[10px] font-semibold text-stone-400 uppercase mb-1.5">Accompagnements liés</div>
          {sides.length === 0 ? (
            <p className="text-[11px] text-stone-400 italic">Aucun side configuré — sides globaux utilisés</p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {sides.map((s: VarianteSideRead) => (
                <span key={s.side_id} className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-full bg-white border border-stone-200">
                  {s.side_nom}
                  {s.supplement_cts > 0 && <span className="text-amber-600 font-semibold">+{fmtPrix(s.supplement_cts)}</span>}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── ImageField ─────────────────────────────────────────────────────────────

function ImageField({ value, onChange }: { value: string; onChange: (url: string) => void }) {
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFile(file: File) {
    setUploading(true)
    setUploadError('')
    try {
      const { url } = await restaurantApi.uploadRestaurantImage(file)
      onChange(url)
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : 'Échec de l\'upload')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] font-semibold text-stone-600">Photo</label>
      <div className="flex items-center gap-3">
        {value ? (
          <div className="relative shrink-0">
            <img src={value} alt="aperçu" className="h-14 w-14 rounded-lg object-cover border border-stone-200" />
            <button type="button" onClick={() => onChange('')}
              className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-white border border-stone-200 rounded-full flex items-center justify-center text-stone-400 hover:text-red-500 text-[10px] leading-none transition-colors">
              ×
            </button>
          </div>
        ) : (
          <div className="h-14 w-14 rounded-lg border border-dashed border-stone-300 bg-stone-100 flex items-center justify-center text-stone-400 text-[10px] text-center leading-tight shrink-0">
            Pas de photo
          </div>
        )}
        <div className="flex flex-col gap-1.5 min-w-0">
          <button type="button" onClick={() => inputRef.current?.click()} disabled={uploading}
            className="px-3 py-1.5 text-[12px] font-medium bg-stone-100 border border-stone-200 rounded-lg text-stone-700 hover:bg-stone-200 disabled:opacity-50 transition-colors">
            {uploading ? 'Envoi...' : value ? 'Changer' : 'Ajouter une photo'}
          </button>
          {uploadError && <p className="text-[11px] text-red-600">{uploadError}</p>}
        </div>
      </div>
      <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
        onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = '' }} />
    </div>
  )
}

// ─── ModalEditPlat ──────────────────────────────────────────────────────────

function ModalEditPlat({
  plat,
  typesPrep,
  allSides,
  proteineIngredients,
  allIngredients,
  onClose,
  onCreated,
}: {
  plat: VariantePlatRead | null  // null = create mode
  typesPrep: TypePreparationRead[]
  allSides: SideRead[]
  proteineIngredients: IngredientRead[]
  allIngredients: IngredientRead[]
  onClose: () => void
  onCreated?: (plat: VariantePlatRead) => void
}) {
  const qc = useQueryClient()
  const trapRef = useFocusTrap<HTMLDivElement>(onClose)
  const isCreate = plat === null
  const [nom, setNom] = useState(plat?.nom ?? '')
  const [type, setType] = useState<'plat' | 'boisson' | 'formule'>(plat?.type as 'plat' ?? 'plat')
  const [prixCts, setPrixCts] = useState<number>(plat?.prix_vente_cts ?? 0)
  const [tvaCts, setTvaCts] = useState<number>(plat?.taux_tva ?? 1000)
  const [categorie, setCategorie] = useState(plat?.categorie ?? '')
  const [imageUrl, setImageUrl] = useState(plat?.image_url ?? '')
  const [baseLiee, setBaseLiee] = useState<number | ''>(plat?.type_preparation_id ?? '')
  const [proteineLiee, setProteineLiee] = useState<number | ''>(plat?.ingredient_proteine_id ?? '')
  const [qteProteine, setQteProteine] = useState(String(plat?.quantite_proteine ?? ''))
  const [error, setError] = useState<string | null>(null)

  const { data: linkedSides = [] } = useQuery({
    queryKey: ['variante-sides', plat?.id],
    queryFn: () => restaurantApi.listVarianteSides(plat!.id),
    enabled: !isCreate && plat !== null,
    staleTime: 30_000,
  })

  const createMut = useMutation({
    mutationFn: () => restaurantApi.createVariantePlat({
      nom, type,
      prix_vente_cts: prixCts,
      taux_tva: tvaCts,
      categorie: categorie || null,
      image_url: imageUrl || null,
      type_preparation_id: baseLiee || null,
      ingredient_proteine_id: proteineLiee || null,
      quantite_proteine: qteProteine ? Number(qteProteine) : undefined,
    }),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['menu-plats'] })
      qc.invalidateQueries({ queryKey: ['menu-boissons'] })
      if (onCreated) { onCreated(result) } else { onClose() }
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  const updateMut = useMutation({
    mutationFn: () => restaurantApi.updateVariantePlat(plat!.id, {
      nom: nom !== plat!.nom ? nom : undefined,
      prix_vente_cts: prixCts !== plat!.prix_vente_cts ? prixCts : undefined,
      taux_tva: tvaCts !== plat!.taux_tva ? tvaCts : undefined,
      categorie: categorie !== plat!.categorie ? (categorie || null) : undefined,
      image_url: imageUrl !== (plat!.image_url ?? '') ? (imageUrl || null) : undefined,
      type_preparation_id: (baseLiee || null) !== plat!.type_preparation_id ? (baseLiee || null) : undefined,
      ingredient_proteine_id: (proteineLiee || null) !== plat!.ingredient_proteine_id ? (proteineLiee || null) : undefined,
      quantite_proteine: qteProteine && Number(qteProteine) !== plat!.quantite_proteine ? Number(qteProteine) : undefined,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['menu-plats'] }); qc.invalidateQueries({ queryKey: ['menu-boissons'] }); onClose() },
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  const addSideMut = useMutation({
    mutationFn: ({ sideId, supplement }: { sideId: number; supplement: number }) =>
      restaurantApi.addVarianteSide(plat!.id, { side_id: sideId, supplement_cts: supplement }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['variante-sides', plat!.id] }),
    onError: (err) => setError(normalizeError(err).message || 'Erreur ajout accompagnement'),
  })

  const updateSideSupMut = useMutation({
    mutationFn: ({ sideId, supplement }: { sideId: number; supplement: number }) =>
      restaurantApi.updateVarianteSide(plat!.id, sideId, { supplement_cts: supplement }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['variante-sides', plat!.id] }),
    onError: (err) => setError(normalizeError(err).message || 'Erreur mise à jour supplément'),
  })

  const removeSideMut = useMutation({
    mutationFn: (sideId: number) => restaurantApi.removeVarianteSide(plat!.id, sideId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['variante-sides', plat!.id] }),
    onError: (err) => setError(normalizeError(err).message || 'Erreur retrait accompagnement'),
  })

  const isPending = createMut.isPending || updateMut.isPending
  const linkedSideIds = new Set(linkedSides.map(s => s.side_id))
  const catOptions = type === 'boisson' ? CAT_BOISSONS : type === 'plat' ? CAT_PLATS : [...CAT_PLATS, ...CAT_BOISSONS]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div ref={trapRef} role="dialog" aria-modal="true" className="bg-white rounded-2xl border border-stone-200 w-full max-w-lg max-h-[85vh] flex flex-col shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-100">
          <h2 className="text-[15px] font-bold text-stone-900">{isCreate ? 'Nouveau plat' : `Modifier — ${plat!.nom}`}</h2>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-900 transition-colors" aria-label="Fermer"><X className="h-4.5 w-4.5" /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3">
          {error && <p className="text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-semibold text-stone-600 mb-1 block">Nom</label>
              <input type="text" value={nom} onChange={e => setNom(e.target.value)}
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" />
            </div>
            <div>
              <label className="text-[11px] font-semibold text-stone-600 mb-1 block">Type</label>
              <select value={type} onChange={e => setType(e.target.value as 'plat')}
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 transition-colors">
                <option value="plat">Plat</option>
                <option value="boisson">Boisson</option>
                <option value="formule">Formule</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-semibold text-stone-600 mb-1 block">Prix de vente</label>
              <MoneyInput value={prixCts} onChange={setPrixCts} min={0} placeholder="0,00" />
            </div>
            <div>
              <label className="text-[11px] font-semibold text-stone-600 mb-1 block">TVA applicable</label>
              <select value={tvaCts} onChange={e => setTvaCts(Number(e.target.value))}
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 transition-colors">
                {TVA_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="text-[11px] font-semibold text-stone-600 mb-1 block">Catégorie</label>
            <select value={categorie} onChange={e => setCategorie(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 transition-colors">
              <option value="">— Sans catégorie —</option>
              {catOptions.map(k => (
                <option key={k} value={k}>{CAT_LABELS[k]}</option>
              ))}
            </select>
          </div>

          {/* Plats : base + protéine + quantité */}
          {type === 'plat' && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-semibold text-stone-600 mb-1 block">Base cuisinée liée</label>
                <select value={baseLiee} onChange={e => setBaseLiee(e.target.value ? Number(e.target.value) : '')}
                  className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 transition-colors">
                  <option value="">Aucune</option>
                  {typesPrep.map(tp => <option key={tp.id} value={tp.id}>{tp.nom}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[11px] font-semibold text-stone-600 mb-1 block">Protéine consommée</label>
                <select value={proteineLiee} onChange={e => setProteineLiee(e.target.value ? Number(e.target.value) : '')}
                  className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 transition-colors">
                  <option value="">Aucune</option>
                  {proteineIngredients.map(i => <option key={i.id} value={i.id}>{i.nom} ({i.unite_stock})</option>)}
                </select>
              </div>
            </div>
          )}

          {/* Boissons : ingrédient stock consommé (tous ingrédients, pas que protéines) */}
          {type === 'boisson' && (
            <div>
              <label className="text-[11px] font-semibold text-stone-600 mb-1 block">Ingrédient stock consommé</label>
              <select value={proteineLiee} onChange={e => setProteineLiee(e.target.value ? Number(e.target.value) : '')}
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 transition-colors">
                <option value="">Aucun — pas de suivi stock</option>
                {allIngredients.map(i => <option key={i.id} value={i.id}>{i.nom} ({i.unite_stock})</option>)}
              </select>
            </div>
          )}

          {/* Quantité par portion (plat + boisson si ingrédient choisi) */}
          {proteineLiee && (
            <div>
              <label className="text-[11px] font-semibold text-stone-600 mb-1 block">
                {type === 'boisson' ? 'Quantité consommée par commande' : 'Quantité protéine par portion (kg)'}
              </label>
              <input type="number" min={0} step={0.05} value={qteProteine} onChange={e => setQteProteine(e.target.value)}
                placeholder={type === 'boisson' ? '1' : '0.25'}
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" />
            </div>
          )}

          <ImageField value={imageUrl} onChange={setImageUrl} />

          {/* Sides liés avec supplément éditable (plats uniquement) */}
          {type === 'plat' && isCreate && (
            <div className="border border-stone-200 rounded-lg px-3 py-2.5 bg-stone-50">
              <p className="text-[11px] text-stone-500">
                Les accompagnements pourront être ajoutés après la création du plat.
              </p>
            </div>
          )}
          {type === 'plat' && !isCreate && (
            <div>
              <label className="text-[11px] font-semibold text-stone-600 mb-2 block">Accompagnements & suppléments</label>
              {linkedSides.length > 0 && (
                <div className="border border-stone-200 rounded-lg overflow-hidden mb-2">
                  <table className="w-full text-left">
                    <thead className="bg-stone-50">
                      <tr>
                        <th className="px-3 py-1.5 text-[10px] font-semibold text-stone-500 uppercase">Side</th>
                        <th className="px-3 py-1.5 text-[10px] font-semibold text-stone-500 uppercase w-28">Supplément</th>
                        <th className="px-3 py-1.5 w-8"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {linkedSides.map(s => (
                        <tr key={s.side_id} className="border-t border-stone-100">
                          <td className="px-3 py-2 text-[12px] font-medium text-stone-900">{s.side_nom}</td>
                          <td className="px-3 py-1.5">
                            <div className="flex items-center gap-1">
                              <input
                                type="number"
                                min={0}
                                step={50}
                                defaultValue={s.supplement_cts}
                                onBlur={e => {
                                  const val = Number(e.target.value)
                                  if (val !== s.supplement_cts) {
                                    updateSideSupMut.mutate({ sideId: s.side_id, supplement: val })
                                  }
                                }}
                                className="w-20 bg-stone-50 border border-stone-200 rounded px-2 py-1 text-[11px] font-mono focus:outline-none focus:border-amber-400 transition-colors"
                              />
                              <span className="text-[10px] text-stone-400">cts</span>
                            </div>
                          </td>
                          <td className="px-2 py-1.5">
                            <button onClick={() => removeSideMut.mutate(s.side_id)}
                              className="text-stone-400 hover:text-red-600 p-1 transition-colors"
                              aria-label="Retirer l'accompagnement">
                              <X className="h-3 w-3" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="flex flex-wrap gap-1">
                {allSides.filter(s => !linkedSideIds.has(s.id) && s.is_active).map(s => (
                  <button key={s.id} onClick={() => addSideMut.mutate({ sideId: s.id, supplement: 0 })}
                    className="text-[11px] px-2 py-1 rounded-full border border-dashed border-stone-300 text-stone-500 hover:border-amber-400 hover:text-amber-600 transition-colors">
                    + {s.nom}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 px-5 py-4 border-t border-stone-100">
          <button onClick={onClose} className="px-4 py-2 text-[13px] text-stone-500 hover:text-stone-900 font-medium transition-colors">Annuler</button>
          <button onClick={() => isCreate ? createMut.mutate() : updateMut.mutate()}
            disabled={!nom || prixCts <= 0 || isPending}
            className="px-4 py-2 text-[13px] font-semibold bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 transition-colors">
            {isPending ? 'Enregistrement...' : isCreate ? 'Créer' : 'Enregistrer'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── VueItemsMenu (plats & boissons) ─────────────────────────────────────────

function VueItemsMenu({ items, queryKey, titre, ctaLabel, emptyText, typesPrep, allSides, proteineIngredients, allIngredients, isFetching, isLoading }: {
  items: VariantePlatRead[]; queryKey: string; titre: string; ctaLabel: string; emptyText: string
  typesPrep: TypePreparationRead[]; allSides: SideRead[]; proteineIngredients: IngredientRead[]; allIngredients: IngredientRead[]; isFetching: boolean; isLoading: boolean
}) {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [filtreCat, setFiltreCat] = useState<string>('all')
  const [editItem, setEditItem] = useState<VariantePlatRead | null | 'create'>(null)
  const [toggleError, setToggleError] = useState('')

  const toggleMut = useMutation({
    mutationFn: (p: VariantePlatRead) => restaurantApi.updateVariantePlat(p.id, { is_active: !p.is_active }),
    onSuccess: () => { setToggleError(''); qc.invalidateQueries({ queryKey: [queryKey] }) },
    onError: (err) => setToggleError(normalizeError(err).message || 'Erreur activation'),
  })

  const categories = [...new Set(items.map(p => p.categorie).filter(Boolean))] as string[]
  const filtered = items.filter(p => {
    if (search && !p.nom.toLowerCase().includes(search.toLowerCase())) return false
    if (filtreCat !== 'all' && p.categorie !== filtreCat) return false
    return true
  })
  const actifs = items.filter(p => p.is_active).length

  return (
    <div className="px-5 py-4">
      {editItem !== null && (
        <ModalEditPlat
          plat={editItem === 'create' ? null : editItem}
          typesPrep={typesPrep}
          allSides={allSides}
          proteineIngredients={proteineIngredients}
          allIngredients={allIngredients}
          onClose={() => setEditItem(null)}
          onCreated={(p) => setEditItem(p)}
        />
      )}

      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <span className="text-[14px] font-semibold text-stone-900">
          {titre}
          <span className="ml-2 text-[12px] font-normal text-stone-400">{actifs} actif{actifs > 1 ? 's' : ''} / {items.length}</span>
        </span>
        <button onClick={() => setEditItem('create')}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 text-white text-[12px] font-semibold rounded-lg hover:bg-amber-700 transition-colors">
          <Plus className="h-3.5 w-3.5" /> {ctaLabel}
        </button>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Rechercher..."
          className="bg-stone-50 border border-stone-200 rounded-lg px-3 py-1.5 text-[12px] text-stone-900 placeholder:text-stone-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors w-48" />
        <select value={filtreCat} onChange={e => setFiltreCat(e.target.value)}
          className="bg-stone-50 border border-stone-200 rounded-lg px-2.5 py-1.5 text-[12px] text-stone-900 focus:outline-none focus:border-amber-400 transition-colors">
          <option value="all">Toutes catégories</option>
          {categories.map(c => <option key={c} value={c}>{CAT_LABELS[c] ?? c}</option>)}
        </select>
        {isFetching && <span className="text-[11px] text-stone-400 self-center">Chargement...</span>}
      </div>

      {toggleError && <p className="text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2 mb-2">{toggleError}</p>}

      <div className="flex flex-col gap-2">
        {isLoading ? (
          <div className="animate-pulse space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-stone-200 border border-stone-200 rounded-xl h-14" />
            ))}
          </div>
        ) : (
          <>
            {filtered.map(p => (
              <ItemCard key={p.id} plat={p} typesPrep={typesPrep} onEdit={setEditItem} onToggle={p => toggleMut.mutate(p)} />
            ))}
            {filtered.length === 0 && (
              <div className="border border-stone-200 rounded-xl py-8 text-center text-[13px] text-stone-400 bg-white">{emptyText}</div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ─── ModalEditSide ──────────────────────────────────────────────────────────

function ModalEditSide({
  side,
  ingredients,
  onClose,
}: {
  side: SideRead | null
  ingredients: IngredientRead[]
  onClose: () => void
}) {
  const qc = useQueryClient()
  const trapRef = useFocusTrap<HTMLDivElement>(onClose)
  const isCreate = side === null
  const [nom, setNom] = useState(side?.nom ?? '')
  const [imageUrl, setImageUrl] = useState(side?.image_url ?? '')
  const [ingredientId, setIngredientId] = useState<number | ''>(side?.ingredient_id ?? '')
  const [qtePortion, setQtePortion] = useState(String(side?.quantite_par_portion ?? ''))
  const [error, setError] = useState<string | null>(null)

  const selectedIng = ingredients.find(i => i.id === Number(ingredientId))

  const createMut = useMutation({
    mutationFn: () => {
      if (ingredientId && !qtePortion) {
        return Promise.reject(new Error('Quantité par portion requise quand un ingrédient est sélectionné'))
      }
      return restaurantApi.createSide({
        nom,
        image_url: imageUrl || null,
        ingredient_id: ingredientId || null,
        quantite_par_portion: ingredientId && qtePortion ? Number(qtePortion) : null,
      })
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['restaurant-sides'] }); onClose() },
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  const updateMut = useMutation({
    mutationFn: () => {
      if (ingredientId && !qtePortion) {
        return Promise.reject(new Error('Quantité par portion requise quand un ingrédient est sélectionné'))
      }
      // Toujours envoyer ingredient_id et quantite_par_portion ensemble (contrainte DB)
      return restaurantApi.updateSide(side!.id, {
        nom: nom !== side!.nom ? nom : undefined,
        image_url: imageUrl !== (side!.image_url ?? '') ? (imageUrl || null) : undefined,
        ingredient_id: ingredientId || null,
        quantite_par_portion: ingredientId && qtePortion ? Number(qtePortion) : null,
      })
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['restaurant-sides'] }); onClose() },
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  const isPending = createMut.isPending || updateMut.isPending

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div ref={trapRef} role="dialog" aria-modal="true" className="bg-white rounded-2xl border border-stone-200 w-full max-w-md shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-100">
          <h2 className="text-[15px] font-bold text-stone-900">{isCreate ? 'Nouvel accompagnement' : `Modifier — ${side!.nom}`}</h2>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-900 transition-colors" aria-label="Fermer"><X className="h-4.5 w-4.5" /></button>
        </div>
        <div className="px-5 py-4 flex flex-col gap-3">
          {error && <p className="text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
          <div>
            <label className="text-[11px] font-semibold text-stone-600 mb-1 block">Nom</label>
            <input type="text" value={nom} onChange={e => setNom(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" />
          </div>
          <ImageField value={imageUrl} onChange={setImageUrl} />
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-semibold text-stone-600 mb-1 block">Ingrédient consommé</label>
              <select value={ingredientId} onChange={e => setIngredientId(e.target.value ? Number(e.target.value) : '')}
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 transition-colors">
                <option value="">Aucun (informatif)</option>
                {ingredients.map(i => <option key={i.id} value={i.id}>{i.nom} ({i.unite_stock})</option>)}
              </select>
            </div>
            <div>
              <label className="text-[11px] font-semibold text-stone-600 mb-1 block">
                Quantité/portion{selectedIng ? ` (${selectedIng.unite_stock})` : ''}
              </label>
              <input type="number" min={0} step={0.05} value={qtePortion} onChange={e => setQtePortion(e.target.value)}
                placeholder="0.15" disabled={!ingredientId}
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors disabled:bg-stone-100 disabled:text-stone-400" />
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 px-5 py-4 border-t border-stone-100">
          <button onClick={onClose} className="px-4 py-2 text-[13px] text-stone-500 hover:text-stone-900 font-medium transition-colors">Annuler</button>
          <button onClick={() => isCreate ? createMut.mutate() : updateMut.mutate()}
            disabled={!nom || isPending || (!!ingredientId && !qtePortion)}
            className="px-4 py-2 text-[13px] font-semibold bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 transition-colors">
            {isPending ? 'Enregistrement...' : isCreate ? 'Créer' : 'Enregistrer'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── VueSidesMenu ───────────────────────────────────────────────────────────

function VueSidesMenu({ sides, ingredients }: { sides: SideRead[]; ingredients: IngredientRead[] }) {
  const qc = useQueryClient()
  const [editSide, setEditSide] = useState<SideRead | null | 'create'>(null)
  const [toggleError, setToggleError] = useState('')

  const toggleMut = useMutation({
    mutationFn: (s: SideRead) => restaurantApi.updateSide(s.id, { is_active: !s.is_active }),
    onSuccess: () => { setToggleError(''); qc.invalidateQueries({ queryKey: ['restaurant-sides'] }) },
    onError: (err) => setToggleError(normalizeError(err).message || 'Erreur activation'),
  })

  return (
    <div className="px-5 py-4">
      {toggleError && <p className="text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2 mb-3">{toggleError}</p>}
      {editSide !== null && (
        <ModalEditSide
          side={editSide === 'create' ? null : editSide}
          ingredients={ingredients}
          onClose={() => setEditSide(null)}
        />
      )}
      <div className="flex items-center justify-between mb-4">
        <span className="text-[14px] font-semibold text-stone-900">
          Accompagnements
          <span className="ml-2 text-[12px] font-normal text-stone-400">{sides.filter(s => s.is_active).length} actifs / {sides.length}</span>
        </span>
        <button onClick={() => setEditSide('create')}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 text-white text-[12px] font-semibold rounded-lg hover:bg-amber-700 transition-colors">
          <Plus className="h-3.5 w-3.5" /> Nouvel accompagnement
        </button>
      </div>
      <div className="flex flex-col gap-2">
        {sides.map(s => (
          <div key={s.id} className={`flex items-center gap-3 px-3 py-2.5 border rounded-xl transition-shadow hover:shadow-md ${
            s.is_active ? 'border-stone-200 bg-white' : 'border-stone-200 bg-stone-50 opacity-60'
          }`}>
            <Thumb src={s.image_url} alt={s.nom} size={40} />
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-semibold text-stone-900 truncate">{s.nom}</div>
              <div className="flex items-center gap-2 text-[11px] text-stone-500">
                {s.ingredient_nom ? (
                  <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 text-[10px] font-medium">
                    {s.ingredient_nom} · {s.quantite_par_portion}/{s.ingredient_nom ? 'portion' : ''}
                  </span>
                ) : (
                  <span className="text-stone-400 italic">Pas d'ingrédient lié</span>
                )}
                <span className="text-stone-400">{s.nb_plats_lies} plat{s.nb_plats_lies > 1 ? 's' : ''} lié{s.nb_plats_lies > 1 ? 's' : ''}</span>
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <button onClick={() => setEditSide(s)} className="p-1.5 text-stone-400 hover:text-amber-600 transition-colors" title="Modifier">
                <Pencil className="h-3.5 w-3.5" />
              </button>
              <button onClick={() => toggleMut.mutate(s)} className={`p-1.5 transition-colors hover:opacity-70 ${s.is_active ? 'text-emerald-600' : 'text-stone-400'}`} title={s.is_active ? 'Désactiver' : 'Activer'}>
                <Power className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ))}
        {sides.length === 0 && (
          <div className="border border-stone-200 rounded-xl py-8 text-center text-[13px] text-stone-400 bg-white">Aucun accompagnement</div>
        )}
      </div>
    </div>
  )
}

// ─── MenuPage ───────────────────────────────────────────────────────────────

export default function MenuPage() {
  const [vue, setVue] = useState<VueMenu>('plats')

  const { data: platsData = [], isFetching: platsFetching, isLoading: platsLoading } = useQuery({
    queryKey: ['menu-plats'],
    queryFn: () => restaurantApi.getVariantesPlat('plat', true),
    staleTime: 30_000,
  })

  const { data: boissonsData = [], isFetching: boissonsFetching, isLoading: boissonsLoading } = useQuery({
    queryKey: ['menu-boissons'],
    queryFn: () => restaurantApi.getVariantesPlat('boisson', true),
    staleTime: 30_000,
  })

  const { data: typesPrep = [] } = useQuery({
    queryKey: ['restaurant-types-prep'],
    queryFn: () => restaurantApi.listTypesPreparation(),
    staleTime: 60_000,
  })

  const { data: sidesData = [] } = useQuery({
    queryKey: ['restaurant-sides'],
    queryFn: () => restaurantApi.getSides(true),
    staleTime: 60_000,
  })

  // Tous les ingrédients pour le select side → ingrédient
  const { data: allIngredientsData } = useQuery({
    queryKey: ['restaurant-ingredients-all'],
    queryFn: () => restaurantApi.listIngredients({ per_page: 100 }),
    staleTime: 60_000,
  })
  const allIngredients = allIngredientsData?.items ?? []

  // Charger les catégories pour identifier les IDs protéine
  const { data: categoriesData = [] } = useQuery({
    queryKey: ['restaurant-categories-ingredient'],
    queryFn: () => restaurantApi.listCategoriesIngredient(),
    staleTime: 60_000,
  })

  const proteineCatNames = new Set(['Protéine', 'Viandes', 'Volaille', 'Poissons et fruits de mer', 'Abats'])
  const proteineCatIds = categoriesData.filter(c => proteineCatNames.has(c.nom)).map(c => c.id)

  // Charger ingrédients protéine par catégorie (une query par catégorie pour éviter la limite per_page)
  const { data: proteineData = [] } = useQuery({
    queryKey: ['restaurant-ingredients-proteines', proteineCatIds],
    queryFn: async () => {
      const results = await Promise.all(
        proteineCatIds.map(catId => restaurantApi.listIngredients({ categorie_id: catId, per_page: 100 }))
      )
      return results.flatMap(r => r.items)
    },
    enabled: proteineCatIds.length > 0,
    staleTime: 60_000,
  })

  const proteineIngredients = proteineData

  return (
    <div className="flex flex-col min-h-0 h-full">
      <div className="px-5 pt-5 pb-4 border-b border-stone-200 bg-white shrink-0">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-[17px] font-bold text-stone-900 tracking-tight">Carte</h1>
            <p className="text-[13px] text-stone-500 mt-0.5">Configuration des plats, boissons et accompagnements</p>
          </div>
        </div>
      </div>

      <div className="px-5 pt-3 pb-0 bg-white border-b border-stone-200 shrink-0">
        <div className="flex gap-1 bg-stone-100 rounded-lg p-0.5 w-fit">
          {[
            { key: 'plats' as const, label: 'Plats', count: platsData.length },
            { key: 'boissons' as const, label: 'Boissons', count: boissonsData.length },
            { key: 'sides' as const, label: 'Accompagnements', count: sidesData.length },
          ].map(v => (
            <button key={v.key} onClick={() => setVue(v.key)}
              className={`px-4 py-1.5 rounded-md text-[12px] font-semibold transition-colors ${
                vue === v.key ? 'bg-white text-stone-900 shadow-sm' : 'text-stone-500 hover:text-stone-900'
              }`}>
              {v.label}
              <span className="ml-1.5 text-[10px] text-stone-400">{v.count}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto bg-stone-50">
        {vue === 'plats' ? (
          <VueItemsMenu
            items={platsData} queryKey="menu-plats" titre="Carte plats" ctaLabel="Nouveau plat" emptyText="Aucun plat trouvé"
            typesPrep={typesPrep} allSides={sidesData} proteineIngredients={proteineIngredients} allIngredients={allIngredients}
            isFetching={platsFetching} isLoading={platsLoading}
          />
        ) : vue === 'boissons' ? (
          <VueItemsMenu
            items={boissonsData} queryKey="menu-boissons" titre="Carte boissons" ctaLabel="Nouvelle boisson" emptyText="Aucune boisson trouvée"
            typesPrep={typesPrep} allSides={sidesData} proteineIngredients={proteineIngredients} allIngredients={allIngredients}
            isFetching={boissonsFetching} isLoading={boissonsLoading}
          />
        ) : (
          <VueSidesMenu sides={sidesData} ingredients={allIngredients} />
        )}
      </div>
    </div>
  )
}
