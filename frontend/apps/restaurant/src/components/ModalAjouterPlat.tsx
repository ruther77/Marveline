import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { X, Plus, Check, ChevronRight, UtensilsCrossed } from 'lucide-react'
import { restaurantApi } from '@/api/restaurant'
import { normalizeError } from '@shared/errors/normalizer'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import type {
  VariantePlatRead,
  SideRead,
  VarianteSideRead,
  InstancePreparationRead,
  TypePreparationRead,
} from '@/types/restaurant-v2'

function Thumb({ src, alt, size = 40 }: { src: string | null; alt: string; size?: number }) {
  if (!src) {
    return (
      <div className="rounded-lg bg-stone-100 flex items-center justify-center shrink-0" style={{ width: size, height: size }}>
        <UtensilsCrossed className="h-4 w-4 text-stone-400" />
      </div>
    )
  }
  return (
    <img
      src={src}
      alt={alt}
      className="rounded-lg object-cover shrink-0"
      style={{ width: size, height: size }}
      loading="lazy"
      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
    />
  )
}

function fmtEur(cts: number): string {
  return (cts / 100).toFixed(2) + ' €'
}

type Step = 1 | 2 | 3

interface ModalAjouterPlatProps {
  commandeId: number
  onClose: () => void
  onAdded: () => void
}

const CAT_LABELS: Record<string, string> = {
  plats_sauce: 'Plats en sauce', grillades: 'Grillades', poissons: 'Poissons',
  entrees: 'Entrées', accompagnement: 'Accompagnement',
  biere: 'Bières', whisky: 'Whisky', vin: 'Vins', soft: 'Softs',
  champagne: 'Champagne', digestif: 'Digestifs', aperitif: 'Apéritifs', cafe: 'Café',
}

const CAT_ORDER: Record<string, number> = {
  plats_sauce: 1, grillades: 2, poissons: 3, entrees: 4, accompagnement: 5,
  biere: 1, whisky: 2, vin: 3, soft: 4, champagne: 5, digestif: 6, aperitif: 7, cafe: 8,
}

export default function ModalAjouterPlat({ commandeId, onClose, onAdded }: ModalAjouterPlatProps) {
  const qc = useQueryClient()
  const trapRef = useFocusTrap<HTMLDivElement>(onClose)
  const [step, setStep] = useState<Step>(1)
  const [typeFiltre, setTypeFiltre] = useState<'plat' | 'boisson'>('plat')
  const [sousCategorie, setSousCategorie] = useState<string | null>('plats_sauce')
  const [selectedTypePrepId, setSelectedTypePrepId] = useState<number | null>(null)
  const [selectedTypePrepNom, setSelectedTypePrepNom] = useState<string | null>(null)
  const [selectedVariante, setSelectedVariante] = useState<VariantePlatRead | null>(null)
  const [selectedInstanceId, setSelectedInstanceId] = useState<number | null>(null)
  const [selectedSideId, setSelectedSideId] = useState<number | null>(null)
  const [quantite, setQuantite] = useState(1)
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')

  const { data: variantes = [], isLoading: loadingVar } = useQuery({
    queryKey: ['restaurant-variantes', typeFiltre],
    queryFn: () => restaurantApi.getVariantesPlat(typeFiltre),
    staleTime: 60_000,
  })

  const { data: typesPrep = [] } = useQuery({
    queryKey: ['restaurant-types-prep'],
    queryFn: () => restaurantApi.listTypesPreparation(),
    staleTime: 60_000,
    enabled: typeFiltre === 'plat',
  })

  const { data: sides = [] } = useQuery<SideRead[]>({
    queryKey: ['restaurant-sides'],
    queryFn: () => restaurantApi.getSides(),
    staleTime: 60_000,
    enabled: typeFiltre === 'plat',
  })

  // Sides spécifiques au plat sélectionné (avec supplément)
  const { data: varianteSides } = useQuery<VarianteSideRead[]>({
    queryKey: ['variante-sides', selectedVariante?.id],
    queryFn: () => restaurantApi.listVarianteSides(selectedVariante!.id),
    enabled: selectedVariante !== null,
    staleTime: 30_000,
  })

  // Si le plat a des sides configurés → les utiliser, sinon fallback global
  const effectiveSides: { id: number; nom: string; image_url: string | null; supplement_cts: number }[] =
    varianteSides && varianteSides.length > 0
      ? varianteSides.map(vs => ({ id: vs.side_id, nom: vs.side_nom, image_url: vs.side_image_url, supplement_cts: vs.supplement_cts }))
      : sides.map(s => ({ id: s.id, nom: s.nom, image_url: s.image_url, supplement_cts: 0 }))

  const { data: marmitesData } = useQuery({
    queryKey: ['restaurant-marmites'],
    queryFn: () => restaurantApi.getMarmites(),
    staleTime: 30_000,
    enabled: step === 2 && (selectedTypePrepId != null || selectedVariante?.type_preparation_id != null),
  })

  const marmites: InstancePreparationRead[] = (marmitesData?.items ?? []).filter(
    (m: InstancePreparationRead) => m.type_preparation_id === (selectedTypePrepId ?? selectedVariante?.type_preparation_id)
  )

  const sousCategories = [...new Set(variantes.map((v: VariantePlatRead) => v.categorie).filter(Boolean))]
    .filter(cat => cat === 'plats_sauce' || variantes.some((v: VariantePlatRead) => v.categorie === cat && !v.type_preparation_id))
    .sort((a, b) => (CAT_ORDER[a as string] ?? 99) - (CAT_ORDER[b as string] ?? 99)) as string[]

  const isBaseSauceMode = typeFiltre === 'plat' && sousCategorie === 'plats_sauce'
  const variantesFiltrees = (sousCategorie
    ? variantes.filter((v: VariantePlatRead) => v.categorie === sousCategorie)
    : variantes
  ).filter((v: VariantePlatRead) => !v.type_preparation_id)
  const proteineVariantes = selectedTypePrepId
    ? variantes.filter((v: VariantePlatRead) => v.type_preparation_id === selectedTypePrepId)
    : []

  const ajouterMutation = useMutation({
    mutationFn: () => restaurantApi.ajouterLigne(commandeId, {
      variante_plat_id: selectedVariante!.id,
      instance_preparation_id: selectedInstanceId,
      side_id: selectedSideId,
      quantite,
      notes: notes.trim() || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-commande', commandeId] })
      qc.invalidateQueries({ queryKey: ['restaurant-tables'] })
      qc.invalidateQueries({ queryKey: ['restaurant-bar-tickets'] })
      onAdded()
      onClose()
    },
    onError: (err) => setError(normalizeError(err).message || "Erreur lors de l'ajout"),
  })

  function handleSelectBase(tp: TypePreparationRead) {
    setSelectedTypePrepId(tp.id)
    setSelectedTypePrepNom(tp.nom)
    const matching = variantes.filter((v: VariantePlatRead) => v.type_preparation_id === tp.id)
    if (matching.length === 1) setSelectedVariante(matching[0])
    else setSelectedVariante(null)
    setSelectedInstanceId(null)
    setSelectedSideId(null)
    setStep(2)
  }

  function handleSelectVariante(v: VariantePlatRead) {
    setSelectedVariante(v)
    setSelectedInstanceId(null)
    setSelectedSideId(null)
    setStep(v.type === 'boisson' ? 3 : 2)
  }

  function handleChangeType(t: 'plat' | 'boisson') {
    setTypeFiltre(t)
    setSousCategorie(t === 'plat' ? 'plats_sauce' : null)
    setSelectedTypePrepId(null)
    setSelectedTypePrepNom(null)
    setSelectedVariante(null)
    setSelectedInstanceId(null)
    setSelectedSideId(null)
    setStep(1)
  }

  function handleBack() {
    if (step === 3) {
      setStep(typeFiltre === 'boisson' ? 1 : 2)
    } else if (step === 2) {
      setSelectedTypePrepId(null)
      setSelectedTypePrepNom(null)
      setSelectedVariante(null)
      setSelectedInstanceId(null)
      setSelectedSideId(null)
      setStep(1)
    }
  }

  const TYPE_FILTRES = [
    { key: 'plat' as const, label: 'Plats' },
    { key: 'boisson' as const, label: 'Boissons' },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center bg-black/40">
      <div
        ref={trapRef}
        role="dialog"
        aria-modal="true"
        className="bg-white border border-stone-200 rounded-t-2xl sm:rounded-2xl w-full max-w-md sm:max-w-lg max-h-[92vh] sm:max-h-[85vh] flex flex-col shadow-xl pb-[env(safe-area-inset-bottom)] sm:pb-0"
      >
        {/* Drag handle mobile */}
        <div className="sm:hidden flex justify-center pt-2 pb-1">
          <div className="w-10 h-1 rounded-full bg-stone-300" />
        </div>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-stone-200">
          <div className="flex items-center gap-2">
            {step > 1 && (
              <button onClick={handleBack}
                className="text-stone-600 hover:text-stone-900 min-h-[44px] min-w-[44px] flex items-center justify-center -ml-2"
                aria-label="Retour">
                <ChevronRight className="h-5 w-5 rotate-180" />
              </button>
            )}
            <h3 className="text-[16px] font-bold text-stone-900">
              {step === 1 && (typeFiltre === 'plat' ? 'Choisir un plat' : 'Choisir une boisson')}
              {step === 2 && (selectedTypePrepNom ? `${selectedTypePrepNom} — Protéine` : 'Options')}
              {step === 3 && 'Confirmer'}
            </h3>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex gap-1" aria-hidden="true">
              {(typeFiltre === 'boisson' ? [1, 2] as const : [1, 2, 3] as const).map(s => (
                <div key={s} className={`h-1.5 w-5 rounded-full ${
                  typeFiltre === 'boisson'
                    ? (s === 1 ? (step >= 1 ? 'bg-amber-600' : 'bg-stone-200') : (step >= 3 ? 'bg-amber-600' : 'bg-stone-200'))
                    : (step >= s ? 'bg-amber-600' : 'bg-stone-200')
                }`} />
              ))}
            </div>
            <button onClick={onClose}
              className="text-stone-500 hover:text-stone-900 min-h-[44px] min-w-[44px] flex items-center justify-center -mr-2"
              aria-label="Fermer">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Step 1 — Choix variante */}
        {step === 1 && (
          <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3">
            <div className="flex gap-2">
              {TYPE_FILTRES.map(f => (
                <button key={f.key} onClick={() => handleChangeType(f.key)}
                  className={`flex-1 text-[14px] font-semibold h-12 rounded-xl transition-colors ${
                    typeFiltre === f.key ? 'bg-stone-900 text-white' : 'bg-stone-50 text-stone-600 hover:bg-stone-100 border border-stone-200'
                  }`}>
                  {f.label}
                </button>
              ))}
            </div>

            {sousCategories.length > 1 && (
              <div className="flex gap-2 flex-wrap">
                {sousCategories.map(cat => (
                  <button key={cat} onClick={() => setSousCategorie(cat)}
                    className={`text-[13px] font-medium px-4 h-10 rounded-full transition-colors ${
                      sousCategorie === cat ? 'bg-amber-600 text-white' : 'bg-stone-50 text-stone-600 hover:bg-stone-100 border border-stone-200'
                    }`}>
                    {CAT_LABELS[cat] ?? cat}
                  </button>
                ))}
              </div>
            )}

            {loadingVar ? (
              <div className="flex flex-col gap-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="animate-pulse bg-stone-50 border border-stone-200 rounded-xl h-14" />
                ))}
              </div>
            ) : isBaseSauceMode ? (
              <div className="flex flex-col gap-2">
                {typesPrep.map((tp: TypePreparationRead) => (
                  <button key={tp.id} onClick={() => handleSelectBase(tp)}
                    className="flex items-center gap-3 px-3 py-2.5 bg-stone-50 border border-stone-200 rounded-xl hover:border-amber-600/40 hover:bg-amber-600/5 transition-colors text-left">
                    <Thumb src={tp.image_url} alt={tp.nom} />
                    <div className="flex-1 min-w-0 text-[13px] font-semibold text-stone-900 truncate">{tp.nom}</div>
                    <ChevronRight className="h-4 w-4 text-stone-400 shrink-0" />
                  </button>
                ))}
                {typesPrep.length === 0 && (
                  <div className="text-center py-6 text-stone-600 text-[13px]">Aucune base sauce disponible</div>
                )}
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {variantesFiltrees.map((v: VariantePlatRead) => (
                  <button key={v.id} onClick={() => handleSelectVariante(v)}
                    className="flex items-center gap-3 px-3 py-2.5 bg-stone-50 border border-stone-200 rounded-xl hover:border-amber-600/40 hover:bg-amber-600/5 transition-colors text-left">
                    <Thumb src={v.image_url} alt={v.nom} />
                    <div className="flex-1 min-w-0">
                      <div className="text-[13px] font-semibold text-stone-900 truncate">{v.nom}</div>
                      {v.categorie && !sousCategorie && <div className="text-[11px] text-stone-600">{CAT_LABELS[v.categorie] ?? v.categorie}</div>}
                    </div>
                    <span className="text-[12.5px] font-bold text-stone-900 shrink-0 ml-2">{fmtEur(v.prix_vente_cts)}</span>
                  </button>
                ))}
                {variantesFiltrees.length === 0 && (
                  <div className="text-center py-6 text-stone-600 text-[13px]">Aucun article disponible</div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Step 2 — Protéine + marmite + side */}
        {step === 2 && (
          <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4">
            {selectedTypePrepId && !selectedVariante && (
              <div>
                <div className="text-[11.5px] font-semibold text-stone-600 mb-2">Choisir la protéine</div>
                <div className="flex flex-col gap-1.5">
                  {proteineVariantes.map((v: VariantePlatRead) => (
                    <button key={v.id} onClick={() => setSelectedVariante(v)}
                      className="flex items-center gap-3 px-3 py-2.5 bg-stone-50 border border-stone-200 rounded-xl hover:border-amber-600/40 hover:bg-amber-600/5 transition-colors text-left">
                      <Thumb src={v.image_url} alt={v.nom} size={36} />
                      <div className="flex-1 min-w-0 text-[13px] font-semibold text-stone-900 truncate">{v.nom}</div>
                      <span className="text-[12.5px] font-bold text-stone-900 shrink-0 ml-2">{fmtEur(v.prix_vente_cts)}</span>
                    </button>
                  ))}
                  {proteineVariantes.length === 0 && (
                    <div className="text-center py-6 text-stone-600 text-[13px]">Aucune protéine disponible</div>
                  )}
                </div>
              </div>
            )}

            {selectedVariante && (
              <div className="px-3 py-2 bg-stone-50 rounded-xl text-[12.5px] font-semibold text-stone-900">
                {selectedVariante.nom} — {fmtEur(selectedVariante.prix_vente_cts)}
              </div>
            )}

            {selectedVariante && marmites.length > 0 && (
              <div>
                <div className="text-[11.5px] font-semibold text-stone-600 mb-2">Marmite</div>
                <div className="flex flex-col gap-1.5">
                  <button onClick={() => setSelectedInstanceId(null)}
                    className={`px-3 py-2 rounded-xl border text-[12px] text-left transition-colors ${
                      selectedInstanceId === null ? 'bg-amber-600/10 border-amber-600/40 text-amber-600' : 'bg-stone-50 border-stone-200 text-stone-600 hover:bg-stone-100'
                    }`}>
                    Sans marmite (stock général)
                  </button>
                  {marmites.map(m => (
                    <button key={m.instance_id} onClick={() => setSelectedInstanceId(m.instance_id)}
                      className={`px-3 py-2 rounded-xl border text-left transition-colors ${
                        selectedInstanceId === m.instance_id ? 'bg-amber-600/10 border-amber-600/40' : 'bg-stone-50 border-stone-200 hover:bg-stone-100'
                      }`}>
                      <div className="text-[12px] font-semibold text-stone-900">{m.type_preparation_nom}</div>
                      <div className="text-[11px] text-stone-600">{m.portions_restantes} portions · {m.date_cuisine}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {selectedVariante && effectiveSides.length > 0 && (
              <div>
                <div className="text-[11.5px] font-semibold text-stone-600 mb-2">Accompagnement (optionnel)</div>
                <div className="flex flex-col gap-1.5">
                  <button onClick={() => setSelectedSideId(null)}
                    className={`px-3 py-2 rounded-xl border text-[12px] text-left transition-colors ${
                      selectedSideId === null ? 'bg-amber-600/10 border-amber-600/40 text-amber-600' : 'bg-stone-50 border-stone-200 text-stone-600 hover:bg-stone-100'
                    }`}>
                    Sans accompagnement
                  </button>
                  {effectiveSides.map(s => (
                    <button key={s.id} onClick={() => setSelectedSideId(s.id)}
                      className={`flex items-center gap-3 px-3 py-2 rounded-xl border text-left transition-colors ${
                        selectedSideId === s.id ? 'bg-amber-600/10 border-amber-600/40' : 'bg-stone-50 border-stone-200 hover:bg-stone-100'
                      }`}>
                      <Thumb src={s.image_url} alt={s.nom} size={32} />
                      <div className="flex-1 min-w-0">
                        <div className="text-[12px] font-semibold text-stone-900">{s.nom}</div>
                      </div>
                      {s.supplement_cts > 0 && (
                        <span className="text-[11px] font-semibold text-amber-700 shrink-0">+{fmtEur(s.supplement_cts)}</span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {selectedVariante && (
              <button onClick={() => setStep(3)}
                className="w-full flex items-center justify-center gap-2 bg-amber-600 text-white text-[15px] font-semibold rounded-xl h-14 hover:opacity-90">
                Suivant <ChevronRight className="h-5 w-5" />
              </button>
            )}
          </div>
        )}

        {/* Step 3 — Confirmer */}
        {step === 3 && selectedVariante && (
          <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4">
            <div className="px-4 py-3 bg-stone-50 border border-stone-200 rounded-xl">
              <div className="text-[13px] font-semibold text-stone-900 mb-0.5">{selectedVariante.nom}</div>
              {selectedSideId && (
                <div className="text-[11.5px] text-stone-600">+ {sides.find((s: SideRead) => s.id === selectedSideId)?.nom}</div>
              )}
              <div className="text-[12px] text-stone-900 font-semibold mt-1">{fmtEur(selectedVariante.prix_vente_cts)}</div>
            </div>

            <div>
              <label className="text-[12px] font-semibold text-stone-600 mb-1.5 block">Quantité</label>
              <div className="flex items-center gap-4">
                <button onClick={() => setQuantite(q => Math.max(1, q - 1))}
                  aria-label="Diminuer la quantité"
                  className="h-12 w-12 rounded-full bg-stone-50 border border-stone-200 text-stone-900 hover:bg-stone-100 text-[20px] font-bold flex items-center justify-center">
                  −
                </button>
                <span className="text-[20px] font-bold text-stone-900 w-10 text-center" aria-live="polite">{quantite}</span>
                <button onClick={() => setQuantite(q => q + 1)}
                  aria-label="Augmenter la quantité"
                  className="h-12 w-12 rounded-full bg-stone-50 border border-stone-200 text-stone-900 hover:bg-stone-100 text-[20px] font-bold flex items-center justify-center">
                  +
                </button>
              </div>
            </div>

            <div>
              <label className="text-[11.5px] font-semibold text-stone-600 mb-1.5 block">Notes (optionnel)</label>
              <textarea
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="Instructions particulières…"
                rows={2}
                maxLength={500}
                className="w-full bg-white border border-stone-200 rounded-xl px-3 py-2 text-[13px] text-stone-900 placeholder-stone-400 focus:outline-none focus:border-amber-600/60 resize-none"
              />
            </div>

            {error && <div className="text-[12px] text-red-600 bg-red-50 rounded-xl px-3 py-2">{error}</div>}

            <button
              onClick={() => { setError(''); ajouterMutation.mutate() }}
              disabled={ajouterMutation.isPending}
              className="w-full flex items-center justify-center gap-2 bg-amber-600 text-white text-[15px] font-semibold rounded-xl h-14 hover:opacity-90 disabled:opacity-50">
              <Check className="h-5 w-5" />
              {ajouterMutation.isPending ? 'Envoi…' : `Envoyer ${quantite > 1 ? `×${quantite}` : ''}`}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
