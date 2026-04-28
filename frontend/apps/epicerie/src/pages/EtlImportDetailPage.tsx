// Route : /_app/etl-imports/$id
// Orchestrateur — revue d'import ETL avec onglets

import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import { useParams, useNavigate, Link } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getImportDetail, validateImport, rejectImport, revertImport,
  updateImportPreview, updateLignes, addLigne, deleteLigne,
  getPdfUrl, getCategories, fetchImages,
  editValidatedLignes, reopenImport, reclassifyImport,
} from '@/api/etl_imports'
import type {
  EtlImportDetail, EtlImportUpdateRequest,
  LigneFactureRead, LigneFactureUpdate, LigneAddRequest,
  LigneValidationStatus, ValidatedLigneEdit,
} from '@/types/etl_import'
import { validateLigne } from '@/types/etl_import'
import { normalizeError } from '@shared/errors/normalizer'

// Components
import ImportReviewHeader from '@/components/etl/ImportReviewHeader'
import ValidationProgress from '@/components/etl/ValidationProgress'
import ReconciliationBar from '@/components/etl/ReconciliationBar'
import IssuesPanel from '@/components/etl/IssuesPanel'
import LignesTable from '@/components/etl/LignesTable'
import BatchActionsBar from '@/components/etl/BatchActionsBar'
import AddLigneForm from '@/components/etl/AddLigneForm'
import BottomProgressBar from '@/components/etl/BottomProgressBar'
import Confetti from '@/components/etl/Confetti'
import PdfHighlightViewer from '@/components/PdfHighlightViewer'
import ValidationConfirmModal from '@/components/ValidationConfirmModal'
import { useCelebration } from '@/hooks/useCelebration'
import { ValidationError } from '@shared/errors/types'

// ── Types locaux ────────────────────────────────────────────────────────────

type TabKey = 'issues' | 'lignes' | 'pdf' | 'conflits'

const TAB_LABELS: Record<TabKey, string> = {
  issues: 'À corriger',
  lignes: 'Toutes les lignes',
  pdf: 'PDF',
  conflits: 'Conflits',
}

function getApiDetail(error: unknown): Record<string, unknown> | null {
  if (!(error instanceof ValidationError)) return null
  const original = error.original
  if (!original || typeof original !== 'object') return null
  const obj = original as Record<string, unknown>
  if (!obj.detail || typeof obj.detail !== 'object' || Array.isArray(obj.detail)) return null
  return obj.detail as Record<string, unknown>
}

// ── Skeleton ────────────────────────────────────────────────────────────────

function DetailSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-24 bg-slate-100 rounded-xl" />
      <div className="grid grid-cols-2 gap-4">
        <div className="h-16 bg-slate-100 rounded-xl" />
        <div className="h-16 bg-slate-100 rounded-xl" />
      </div>
      <div className="h-[500px] bg-slate-100 rounded-xl" />
    </div>
  )
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function EtlImportDetailPage() {
  const { id } = useParams({ from: '/_app/etl-imports/$id' })
  const navigate = useNavigate()
  const qc = useQueryClient()
  const importId = Number(id)

  // ── State ─────────────────────────────────────────────────────────────
  const [error, setError] = useState<string | null>(null)
  const [selectedIdxs, setSelectedIdxs] = useState<Set<number>>(new Set())
  const [ligneFilter, setLigneFilter] = useState<LigneValidationStatus | 'all'>('all')
  const [localLignes, setLocalLignes] = useState<LigneFactureRead[] | null>(null)
  const [dirty, setDirty] = useState(false)
  const [showConfirmModal, setShowConfirmModal] = useState(false)
  const [showRevertConfirm, setShowRevertConfirm] = useState(false)
  const [selectedLineIdx, setSelectedLineIdx] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>('issues')
  const [validating, setValidating] = useState(false)
  // Option B — édition post-validation
  const [postValidatedEditing, setPostValidatedEditing] = useState(false)
  const [postValidatedDirty, setPostValidatedDirty] = useState(false)
  const [postValidatedSaving, setPostValidatedSaving] = useState(false)
  const [recentlyCorrectedIdxs, setRecentlyCorrectedIdxs] = useState<Set<number>>(new Set())
  const [postValidatedFeedback, setPostValidatedFeedback] = useState<
    { kind: 'success' | 'warning'; message: string; warnings?: { code: string; message: string }[] } | null
  >(null)
  // P7 — reopen modal
  const [showReopenConfirm, setShowReopenConfirm] = useState(false)
  const [reclassifyFeedback, setReclassifyFeedback] = useState<string | null>(null)
  // Feedback transient après clic "Appliquer" sur ProductMatchBanner
  const [matchFeedback, setMatchFeedback] = useState<string | null>(null)
  // État auto-save : "saving" pendant le flush, "saved" 2s après succès
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

  // ── Queries ───────────────────────────────────────────────────────────
  const { data: detail, isLoading } = useQuery({
    queryKey: ['etl-import-detail', importId],
    queryFn: () => getImportDetail(importId),
    enabled: importId > 0,
    refetchInterval: (query) => query.state.data?.statut === 'RUNNING' ? 2000 : false,
  })

  const { data: categoriesData } = useQuery({
    queryKey: ['etl-categories'],
    queryFn: getCategories,
    staleTime: 600_000,
  })

  const isPreview = detail?.statut === 'PREVIEW'
  const groups = categoriesData?.groups ?? []
  const lignes = localLignes ?? detail?.lignes ?? []
  const { showCelebration, triggerCelebration } = useCelebration(detail?.statut)

  // ── Default tab based on quality ──────────────────────────────────────
  useEffect(() => {
    if (!detail) return
    const hasIssues = lignes.some(l => validateLigne(l).status !== 'valid')
    setActiveTab(hasIssues && isPreview ? 'issues' : 'lignes')
  }, [detail?.id]) // Only on first load

  // ── Sync server → local ───────────────────────────────────────────────
  // Sync uniquement quand detail.lignes arrive du serveur (initial load, invalidate,
  // refetch). Si on a nous-même écrit cette ref via qc.setQueryData après un save,
  // on skip pour ne pas écraser localLignes (qui reflète déjà les edits).
  useEffect(() => {
    if (!detail?.lignes || dirty) return
    if (detail.lignes === lastSavedRef.current) return
    setLocalLignes(detail.lignes)
  }, [detail, dirty])

  // ── Invalidation ──────────────────────────────────────────────────────
  const invalidate = useCallback(async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ['etl-import-detail', importId] }),
      qc.invalidateQueries({ queryKey: ['etl-imports'] }),
      qc.invalidateQueries({ queryKey: ['etl-conflicts'] }),
      qc.invalidateQueries({ queryKey: ['etl-conflicts-stats'] }),
      qc.invalidateQueries({ queryKey: ['epicerie-stock'] }),
      qc.invalidateQueries({ queryKey: ['epicerie-stock-stats'] }),
      qc.invalidateQueries({ queryKey: ['epicerie-catalogue-pos'] }),
    ])
  }, [qc, importId])

  // ── Totaux locaux ─────────────────────────────────────────────────────
  const enrichedDetail = useMemo(() => {
    if (!detail) return null
    let ht = 0, ttc = 0
    for (const l of lignes) { ht += l.montant_ht_cts ?? 0; ttc += l.montant_ttc_cts ?? 0 }
    return { ...detail, lignes, montant_ht_calcule: ht, montant_ttc_calcule: ttc }
  }, [detail, lignes])

  // ── Keyboard shortcuts ────────────────────────────────────────────────
  useEffect(() => {
    function handleKeys(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        if (dirty && localLignes && isPreview) handleSave()
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        if (isPreview) setShowConfirmModal(true)
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.preventDefault()
        if (dirty) { setLocalLignes(detail?.lignes ?? null); setDirty(false) }
      }
    }
    document.addEventListener('keydown', handleKeys)
    return () => document.removeEventListener('keydown', handleKeys)
  })

  // ── Mutations ─────────────────────────────────────────────────────────
  // Ref synchronisé avec localLignes : garantit que handleValidate/handleSave
  // lisent toujours la dernière version, évitant les closures React obsolètes
  // quand un edit et un click Valider arrivent dans le même macro-task.
  const localLignesRef = useRef<LigneFactureRead[] | null>(localLignes)
  useEffect(() => { localLignesRef.current = localLignes }, [localLignes])

  // Référence de la dernière version qu'on a nous-même écrite dans le cache
  // (via qc.setQueryData après un save). L'effet de sync serveur→local compare
  // par référence et ne réinitialise pas localLignes si detail.lignes vient de nous.
  // Sans ça, setDirty(false) après auto-save déclenche un resync qui écrase les edits visibles.
  const lastSavedRef = useRef<LigneFactureRead[] | null>(null)

  const buildUpdates = useCallback((src: LigneFactureRead[]): LigneFactureUpdate[] =>
    src.map(l => ({
      idx: l.idx, designation: l.designation, ean: l.ean ?? undefined,
      marque: l.marque ?? undefined, conditionnement: l.conditionnement ?? undefined,
      categorie_code: l.categorie_code ?? undefined, quantite: l.quantite ?? undefined,
      prix_unitaire_cts: l.prix_unitaire_cts ?? undefined, taux_tva_centieme: l.taux_tva_centieme ?? undefined,
      auto_applied_fields: l.auto_applied_fields ?? undefined,
    })), [])

  // ── Auto-save debounced (1.5s après dernière édition) ────────────────
  const autoSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const savingRef = useRef(false)

  const doAutoSave = useCallback(async () => {
    const current = localLignesRef.current
    if (!current || savingRef.current || !isPreview) return
    savingRef.current = true
    setSaveState('saving')
    try {
      const updated = await updateLignes(importId, { updates: buildUpdates(current) })
      lastSavedRef.current = updated.lignes ?? null
      qc.setQueryData(['etl-import-detail', importId], updated)
      if (localLignesRef.current === current) setDirty(false)
      setSaveState('saved')
      window.setTimeout(() => setSaveState(s => (s === 'saved' ? 'idle' : s)), 2000)
    } catch {
      setSaveState('error')
    } finally {
      savingRef.current = false
    }
  }, [importId, qc, buildUpdates, isPreview])

  useEffect(() => {
    if (!dirty || !isPreview) return
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current)
    autoSaveTimer.current = setTimeout(doAutoSave, 1500)
    return () => { if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current) }
  }, [dirty, localLignes, doAutoSave, isPreview])

  // Sauvegarde au démontage (navigation away)
  useEffect(() => {
    return () => {
      if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current)
      if (localLignesRef.current && dirty) {
        updateLignes(importId, { updates: buildUpdates(localLignesRef.current) }).catch(() => {})
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = useCallback(async () => {
    const current = localLignesRef.current
    if (!current) return
    try {
      const updated = await updateLignes(importId, { updates: buildUpdates(current) })
      lastSavedRef.current = updated.lignes ?? null
      qc.setQueryData(['etl-import-detail', importId], updated)
      if (localLignesRef.current === current) setDirty(false)
    } catch (err) { setError(normalizeError(err).message || 'Erreur sauvegarde') }
  }, [importId, qc, buildUpdates])

  const handleValidate = useCallback(async () => {
    setError(null)
    try {
      // On compare à detail.lignes (source serveur) plutôt qu'au flag `dirty`,
      // qui peut être obsolète via une closure React capturée avant que setDirty(true)
      // ne soit committé (cas: blur de BrandAutocomplete → click Valider dans le même tick).
      const current = localLignesRef.current
      const server = detail?.lignes
      const hasLocalChanges =
        !!current && (!server || JSON.stringify(current) !== JSON.stringify(server))
      if (hasLocalChanges && current) {
        const updated = await updateLignes(importId, { updates: buildUpdates(current) })
        lastSavedRef.current = updated.lignes ?? null
        qc.setQueryData(['etl-import-detail', importId], updated)
      }
      const validated = await validateImport(importId)
      // Mettre à jour le cache avec la réponse plutôt que 8 refetches parallèles.
      // validated (EtlImportRead) n'inclut pas les lignes → lignes restent celles
      // du save ci-dessus (lastSavedRef) → sync effect skippe via comparaison ref.
      qc.setQueryData(['etl-import-detail', importId], (old: EtlImportDetail | undefined) =>
        old ? { ...old, ...validated } : old
      )
      triggerCelebration()
      setDirty(false)
      // Invalider en série les caches secondaires (évite token replay)
      qc.invalidateQueries({ queryKey: ['etl-imports'] })
      qc.invalidateQueries({ queryKey: ['epicerie-stock'] })
      qc.invalidateQueries({ queryKey: ['epicerie-stock-stats'] })
      qc.invalidateQueries({ queryKey: ['epicerie-catalogue-pos'] })
      fetchImages().catch(() => {})
    } catch (err) {
      const apiDetail = getApiDetail(err)
      if (apiDetail?.code === 'CONFLICTS_PENDING') {
        setActiveTab('conflits')
        await invalidate()
      }
      setError(normalizeError(err).message || 'Erreur de validation')
    }
  }, [importId, invalidate, detail?.lignes, buildUpdates, triggerCelebration])

  const rejectMut = useMutation({
    mutationFn: () => rejectImport(importId),
    onSuccess: () => { setDirty(false); invalidate() },
    onError: (err) => setError(normalizeError(err).message || 'Erreur de rejet'),
  })

  const updateMetaMut = useMutation({
    mutationFn: (data: EtlImportUpdateRequest) => updateImportPreview(importId, data),
    onSuccess: invalidate,
    onError: (err) => setError(normalizeError(err).message || 'Erreur de mise à jour'),
  })

  // ── Ligne editing ─────────────────────────────────────────────────────
  const handleUpdateLigne = useCallback((idx: number, field: string, value: string | number) => {
    setLocalLignes(prev => {
      if (!prev) return prev
      return prev.map(l => {
        if (l.idx !== idx) return l
        const updated = { ...l, [field]: value }
        if (field === 'quantite' || field === 'prix_unitaire_cts' || field === 'taux_tva_centieme') {
          const qte = field === 'quantite' ? Number(value) : (updated.quantite ?? 0)
          const pu = field === 'prix_unitaire_cts' ? Number(value) : (updated.prix_unitaire_cts ?? 0)
          const tva = field === 'taux_tva_centieme' ? Number(value) : (updated.taux_tva_centieme ?? 0)
          updated.montant_ht_cts = Math.round(qte * pu)
          updated.montant_ttc_cts = Math.round(qte * pu * (1 + tva / 10000))
        }
        return updated
      })
    })
    if (postValidatedEditing) setPostValidatedDirty(true)
    else setDirty(true)
  }, [postValidatedEditing])

  // Add/Delete passent par les endpoints dédiés — PATCH /lignes n'est pas
  // destructif, un filtre local ne synchronise ni les totaux ni la validation.
  const addLigneMut = useMutation({
    mutationFn: (data: LigneAddRequest) => addLigne(importId, data),
    onSuccess: (updated) => {
      lastSavedRef.current = updated.lignes ?? null
      qc.setQueryData(['etl-import-detail', importId], updated)
      // Préserver les edits locaux en cours (dirty) sur les lignes existantes :
      // on merge — server source pour les nouvelles idx, local pour les existantes.
      setLocalLignes(prev => {
        if (!prev) return updated.lignes ?? null
        const localIdxs = new Set(prev.map(l => l.idx))
        const serverNew = (updated.lignes ?? []).filter(l => !localIdxs.has(l.idx))
        return [...prev, ...serverNew]
      })
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur ajout ligne'),
  })

  const deleteLigneMut = useMutation({
    mutationFn: (idx: number) => deleteLigne(importId, idx),
    onMutate: async (idx) => {
      // Optimistic : filtrer localLignes immédiatement pour feedback instantané.
      const snapshot = localLignesRef.current
      setLocalLignes(prev => prev?.filter(l => l.idx !== idx) ?? null)
      return { snapshot }
    },
    onSuccess: (updated) => {
      lastSavedRef.current = updated.lignes ?? null
      qc.setQueryData(['etl-import-detail', importId], updated)
      // localLignes reste au filtrage optimiste ; le sync effect est bloqué
      // par la comparaison ref (lastSavedRef === detail.lignes).
    },
    onError: (err, _idx, context) => {
      if (context?.snapshot) setLocalLignes(context.snapshot)
      setError(normalizeError(err).message || 'Erreur suppression ligne')
    },
  })

  const handleAddLigne = useCallback((data: LigneAddRequest) => {
    addLigneMut.mutate(data)
  }, [addLigneMut])

  const handleDeleteLigne = useCallback((idx: number) => {
    deleteLigneMut.mutate(idx)
  }, [deleteLigneMut])

  // ── Selection ─────────────────────────────────────────────────────────
  const handleToggleSelect = useCallback((idx: number) => {
    setSelectedIdxs(prev => { const n = new Set(prev); if (n.has(idx)) n.delete(idx); else n.add(idx); return n })
  }, [])

  const handleToggleAll = useCallback(() => {
    const all = lignes.map(l => l.idx)
    setSelectedIdxs(all.every(i => selectedIdxs.has(i)) ? new Set() : new Set(all))
  }, [lignes, selectedIdxs])

  const handleBatchCategory = useCallback((code: string) => {
    setLocalLignes(prev => prev?.map(l => selectedIdxs.has(l.idx) ? { ...l, categorie_code: code } : l) ?? null)
    setDirty(true); setSelectedIdxs(new Set())
  }, [selectedIdxs])

  const handleBatchBrand = useCallback((marque: string) => {
    setLocalLignes(prev => prev?.map(l => selectedIdxs.has(l.idx) ? { ...l, marque } : l) ?? null)
    setDirty(true); setSelectedIdxs(new Set())
  }, [selectedIdxs])

  const handleBatchEan = useCallback((ean: string) => {
    setLocalLignes(prev => prev?.map(l => selectedIdxs.has(l.idx) ? { ...l, ean } : l) ?? null)
    setDirty(true); setSelectedIdxs(new Set())
  }, [selectedIdxs])

  const handleBatchDelete = useCallback(async () => {
    const ids = Array.from(selectedIdxs)
    if (ids.length === 0) return
    const snapshot = localLignesRef.current
    // Optimistic visuel
    setLocalLignes(prev => prev?.filter(l => !selectedIdxs.has(l.idx)) ?? null)
    setSelectedIdxs(new Set())
    try {
      let latest = null
      for (const idx of ids) {
        latest = await deleteLigne(importId, idx)
      }
      if (latest) {
        lastSavedRef.current = latest.lignes ?? null
        qc.setQueryData(['etl-import-detail', importId], latest)
      }
    } catch (err) {
      setLocalLignes(snapshot)
      setError(normalizeError(err).message || 'Erreur suppression batch')
    }
  }, [selectedIdxs, importId, qc])

  // ── Édition post-validation (Option B) ────────────────────────────────
  // Diff local vs serveur par idx → ne construit que les champs modifiés,
  // puis envoie un PATCH /validated-lignes avec header If-Match (updated_at).
  const buildPostValidatedUpdates = useCallback((
    current: LigneFactureRead[],
    server: LigneFactureRead[],
  ): ValidatedLigneEdit[] => {
    const serverByIdx = new Map(server.map(l => [l.idx, l]))
    const updates: ValidatedLigneEdit[] = []
    for (const l of current) {
      const orig = serverByIdx.get(l.idx)
      if (!orig) continue
      const diff: ValidatedLigneEdit = { idx: l.idx }
      let changed = false
      if (l.quantite !== orig.quantite && l.quantite != null) {
        diff.quantite = l.quantite; changed = true
      }
      if (l.prix_unitaire_cts !== orig.prix_unitaire_cts && l.prix_unitaire_cts != null) {
        diff.prix_unitaire_cts = l.prix_unitaire_cts; changed = true
      }
      if (l.taux_tva_centieme !== orig.taux_tva_centieme && l.taux_tva_centieme != null) {
        diff.taux_tva_centieme = l.taux_tva_centieme; changed = true
      }
      if ((l.marque ?? null) !== (orig.marque ?? null) && l.marque) {
        diff.marque = l.marque; changed = true
      }
      if ((l.categorie_code ?? null) !== (orig.categorie_code ?? null) && l.categorie_code) {
        diff.categorie_code = l.categorie_code; changed = true
      }
      if (changed) updates.push(diff)
    }
    return updates
  }, [])

  const handleStartPostValidatedEdit = useCallback(() => {
    setLocalLignes(detail?.lignes ?? null)
    setPostValidatedDirty(false)
    setPostValidatedEditing(true)
  }, [detail?.lignes])

  const handleCancelPostValidatedEdit = useCallback(() => {
    setLocalLignes(detail?.lignes ?? null)
    setPostValidatedDirty(false)
    setPostValidatedEditing(false)
  }, [detail?.lignes])

  const reclassifyMut = useMutation({
    mutationFn: () => reclassifyImport(importId),
    onSuccess: (updated) => {
      // Merge : on applique uniquement les nouvelles catégoriesserveur dans localLignes
      // pour préserver les saisies non sauvegardées sur les autres champs.
      const serverByIdx = new Map((updated.lignes ?? []).map(l => [l.idx, l.categorie_code]))
      const before = localLignesRef.current ?? updated.lignes ?? []
      let newlyClassified = 0
      const merged = before.map(l => {
        const serverCat = serverByIdx.get(l.idx)
        const hadCat = l.categorie_code && l.categorie_code !== 'AUTRE'
        if (serverCat && serverCat !== 'AUTRE' && !hadCat) {
          newlyClassified++
          return { ...l, categorie_code: serverCat }
        }
        return l
      })
      // lastSavedRef AVANT setQueryData : le sync effect compare par ref et skip,
      // préservant ainsi `merged` (qui contient les edits non sauvegardés + les nouvelles cat).
      lastSavedRef.current = updated.lignes ?? null
      setLocalLignes(merged)
      qc.setQueryData(['etl-import-detail', importId], updated)
      const msg = newlyClassified > 0
        ? `${newlyClassified} ligne${newlyClassified > 1 ? 's classées' : ' classée'} automatiquement`
        : 'Aucune nouvelle classification — catégories déjà complètes ou désignations insuffisantes'
      setReclassifyFeedback(msg)
      window.setTimeout(() => setReclassifyFeedback(null), 5000)
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur lors de la reclassification'),
  })

  // P7 — Reopen REJECTED/REVERTED → PREVIEW
  const handleReopen = useCallback(async () => {
    if (!detail) return
    setError(null)
    try {
      await reopenImport(importId)
      setShowReopenConfirm(false)
      await invalidate()
    } catch (err) {
      setError(normalizeError(err).message || 'Erreur lors de la réouverture')
    }
  }, [importId, detail, invalidate])

  const handleSavePostValidatedEdits = useCallback(async () => {
    setError(null)
    setPostValidatedFeedback(null)
    const current = localLignesRef.current
    const server = detail?.lignes
    if (!current || !server || !detail) return
    const updates = buildPostValidatedUpdates(current, server)
    if (updates.length === 0) {
      setPostValidatedDirty(false)
      setPostValidatedEditing(false)
      return
    }
    setPostValidatedSaving(true)
    try {
      const resp = await editValidatedLignes(importId, { updates }, detail.updated_at)
      const correctedIdxs = new Set(updates.map(u => u.idx))
      setRecentlyCorrectedIdxs(correctedIdxs)
      // Bordure emerald 2s sur les lignes corrigées (pattern cohérent avec selection violette)
      window.setTimeout(() => {
        setRecentlyCorrectedIdxs(prev => {
          if (prev === correctedIdxs) return new Set()
          const next = new Set(prev)
          correctedIdxs.forEach(i => next.delete(i))
          return next
        })
      }, 2000)
      // Feedback inline (success/warning selon warnings backend)
      const warnings = resp.warnings ?? []
      const count = updates.length
      if (warnings.length > 0) {
        setPostValidatedFeedback({
          kind: 'warning',
          message: `${count} ligne${count > 1 ? 's' : ''} corrigée${count > 1 ? 's' : ''} — ${warnings.length} avertissement${warnings.length > 1 ? 's' : ''}`,
          warnings: warnings as { code: string; message: string }[],
        })
      } else {
        setPostValidatedFeedback({
          kind: 'success',
          message: `${count} ligne${count > 1 ? 's' : ''} corrigée${count > 1 ? 's' : ''} • stock ajusté • facture recalculée`,
        })
      }
      window.setTimeout(() => setPostValidatedFeedback(null), 6000)
      setPostValidatedDirty(false)
      setPostValidatedEditing(false)
      await invalidate()
    } catch (err) {
      const e = normalizeError(err)
      setError(e.message || 'Erreur lors de la sauvegarde des corrections')
    } finally {
      setPostValidatedSaving(false)
    }
  }, [importId, detail, invalidate, buildPostValidatedUpdates])

  // ── Feedback Appliquer (ProductMatchBanner) ──────────────────────────
  const handleMatchApplied = useCallback((idx: number, fieldsApplied: string[]) => {
    // Flash vert sur la ligne (pattern cohérent avec post-validated edit)
    setRecentlyCorrectedIdxs(prev => {
      const next = new Set(prev)
      next.add(idx)
      return next
    })
    window.setTimeout(() => {
      setRecentlyCorrectedIdxs(prev => {
        if (!prev.has(idx)) return prev
        const next = new Set(prev)
        next.delete(idx)
        return next
      })
    }, 2000)
    // Toast non bloquant
    const msg = fieldsApplied.length === 0
      ? 'Produit lié — aucun champ à compléter (déjà rempli)'
      : `Appliqué : ${fieldsApplied.join(', ')}`
    setMatchFeedback(msg)
    window.setTimeout(() => setMatchFeedback(null), 3000)
  }, [])

  // ── Révoque un auto-fill : vide le champ + retire la meta ────────────
  const handleRevokeAutoFill = useCallback((idx: number, field: string) => {
    setLocalLignes(prev => {
      if (!prev) return prev
      return prev.map(l => {
        if (l.idx !== idx) return l
        const newLigne: typeof l = { ...l, [field]: null as never }
        if (l.auto_applied_fields) {
          const { [field]: _removed, ...rest } = l.auto_applied_fields
          newLigne.auto_applied_fields = Object.keys(rest).length ? rest : null
        }
        return newLigne
      })
    })
    if (postValidatedEditing) setPostValidatedDirty(true)
    else setDirty(true)
  }, [postValidatedEditing])

  // ── beforeunload : avertir si edits non sauvegardés ──────────────────
  useEffect(() => {
    if (!dirty) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [dirty])

  // ── Focus line from IssuesPanel ───────────────────────────────────────
  const handleFocusLine = useCallback((idx: number, _field: string) => {
    setActiveTab('lignes')
    setSelectedLineIdx(idx)
    requestAnimationFrame(() => {
      document.querySelector(`[data-ligne-idx="${idx}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  }, [])

  // ── Render ────────────────────────────────────────────────────────────
  if (isLoading) return <div className="w-full px-4 sm:px-6 py-4"><DetailSkeleton /></div>
  if (!detail || !enrichedDetail) return <div className="w-full px-4 sm:px-6 py-8 text-slate-400 text-center">Import introuvable</div>

  const isActing = validating || rejectMut.isPending
  const tableActions = {
    onUpdateLigne: handleUpdateLigne,
    onDeleteLigne: handleDeleteLigne,
    onToggleSelect: handleToggleSelect,
    onSelectLine: setSelectedLineIdx,
    onMatchApplied: handleMatchApplied,
    onRevokeAutoFill: handleRevokeAutoFill,
  }
  const conflictCount = detail.nb_lignes_conflit ?? 0
  const issueCount = lignes.filter(l => validateLigne(l).status !== 'valid').length
  const visibleTabs = (Object.keys(TAB_LABELS) as TabKey[]).filter(key => {
    if (key === 'issues' && issueCount === 0) return false
    if (key === 'conflits' && conflictCount === 0) return false
    return true
  })

  return (
    <div className="flex flex-col min-h-0">
      <Confetti active={showCelebration} />

      {/* Header sticky */}
      <ImportReviewHeader
        detail={enrichedDetail} importId={importId} isPreview={isPreview}
        dirty={dirty} isActing={isActing} showCelebration={showCelebration}
        onSave={handleSave} onValidate={() => setShowConfirmModal(true)}
        onReject={() => rejectMut.mutate()} onRevert={() => setShowRevertConfirm(true)}
        onCancelEdits={() => { setLocalLignes(detail?.lignes ?? null); setDirty(false) }}
        onUpdateMeta={data => updateMetaMut.mutate(data)}
        postValidatedEditing={postValidatedEditing}
        postValidatedDirty={postValidatedDirty}
        postValidatedSaving={postValidatedSaving}
        onStartPostValidatedEdit={handleStartPostValidatedEdit}
        onSavePostValidatedEdits={handleSavePostValidatedEdits}
        onCancelPostValidatedEdit={handleCancelPostValidatedEdit}
        onReopen={() => setShowReopenConfirm(true)}
        onReclassify={isPreview ? () => reclassifyMut.mutate() : undefined}
        isReclassifying={reclassifyMut.isPending}
      />

      {/* Feedback inline post-validation : success ou warning */}
      {postValidatedFeedback && (
        <div className={`mx-4 mt-3 rounded-lg p-3 text-sm border transition-opacity ${
          postValidatedFeedback.kind === 'success'
            ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
            : 'bg-amber-50 border-amber-200 text-amber-700'
        }`}>
          <div className="font-medium">{postValidatedFeedback.message}</div>
          {postValidatedFeedback.warnings && postValidatedFeedback.warnings.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs">
              {postValidatedFeedback.warnings.map((w, i) => (
                <li key={i}>⚠ {w.message}</li>
              ))}
            </ul>
          )}
          <button
            onClick={() => setPostValidatedFeedback(null)}
            className="mt-2 text-xs underline hover:no-underline"
          >
            Fermer
          </button>
        </div>
      )}

      {/* Feedback reclassification */}
      {reclassifyFeedback && (
        <div className="mx-4 mt-3 bg-violet-50 border border-violet-200 rounded-lg p-3 text-violet-700 text-sm flex items-center justify-between">
          <span>✦ {reclassifyFeedback}</span>
          <button onClick={() => setReclassifyFeedback(null)} className="ml-2 underline text-xs">fermer</button>
        </div>
      )}

      {/* Toast "Appliquer" ProductMatchBanner */}
      {matchFeedback && (
        <div className="fixed bottom-6 right-6 z-50 bg-violet-600 text-white text-sm font-medium rounded-lg shadow-lg px-4 py-2.5 flex items-center gap-2">
          <span>✦ {matchFeedback}</span>
        </div>
      )}

      {/* Indicateur auto-save persistant (bas-gauche, discret) */}
      {saveState !== 'idle' && (
        <div className={`fixed bottom-6 left-6 z-40 text-[11px] font-medium rounded-md px-2.5 py-1 shadow-sm ${
          saveState === 'saving' ? 'bg-slate-100 text-slate-600' :
          saveState === 'saved' ? 'bg-emerald-100 text-emerald-700' :
          'bg-red-100 text-red-700'
        }`}>
          {saveState === 'saving' && 'Sauvegarde en cours…'}
          {saveState === 'saved' && '✓ Sauvegardé'}
          {saveState === 'error' && '✗ Erreur sauvegarde — cliquez sur Sauvegarder'}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mx-4 mt-3 bg-red-50 border border-red-200 rounded-lg p-3 text-red-600 text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">fermer</button>
        </div>
      )}

      {/* Conflict banner */}
      {isPreview && conflictCount > 0 && (
        <div className="mx-4 mt-3 flex items-center justify-between gap-3 px-4 py-3 bg-amber-50 border border-amber-200 rounded-xl">
          <div className="flex items-center gap-2">
            <span className="text-amber-600 text-lg leading-none">⚠</span>
            <span className="text-[13px] text-amber-800 font-medium">
              {conflictCount} produit{conflictCount > 1 ? 's similaires' : ' similaire'} trouvé{conflictCount > 1 ? 's' : ''} dans votre catalogue — à résoudre avant de valider
            </span>
          </div>
          <Link
            to="/etl-conflits"
            search={{ import_id: importId }}
            className="shrink-0 px-3 py-1.5 bg-amber-600 text-white text-[12px] font-semibold rounded-lg hover:bg-amber-700 transition-colors whitespace-nowrap"
          >
            Résoudre les conflits →
          </Link>
        </div>
      )}

      {/* Running indicator */}
      {detail.statut === 'RUNNING' && (
        <div className="mx-4 mt-3 flex items-start gap-3 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-xl">
          <div className="w-4 h-4 shrink-0 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mt-0.5" />
          <div>
            <span className="text-[13px] font-semibold text-emerald-700 block">Validation en cours…</span>
            <span className="text-[12px] text-emerald-600">Correspondance produits, mise à jour des stocks et génération du bon de réception.</span>
          </div>
        </div>
      )}

      {/* Validation + Reconciliation */}
      <div className="px-4 mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ValidationProgress lignes={lignes} />
        <ReconciliationBar detail={enrichedDetail} />
      </div>

      {/* Tabs */}
      <div className="px-4 mt-4">
        <div className="flex gap-1 bg-slate-100 rounded-lg p-1">
          {visibleTabs.map(key => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`flex-1 px-3 py-2 rounded text-sm font-medium transition-colors ${
                activeTab === key ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {TAB_LABELS[key]}
              {key === 'conflits' && conflictCount > 0 && (
                <span className="ml-1.5 text-xs text-red-500 font-bold">{conflictCount}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 px-4 mt-3 pb-20 min-h-0 overflow-y-auto">
        {activeTab === 'issues' && (
          <IssuesPanel lignes={lignes} onFocusLine={handleFocusLine} />
        )}

        {activeTab === 'lignes' && (
          <div className="space-y-3">
            {/* Filter pills */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-500">{lignes.length} lignes</span>
              <div className="flex gap-1 ml-auto">
                {(['all', 'valid', 'warning', 'error'] as const).map(f => (
                  <button key={f} onClick={() => setLigneFilter(f)}
                    className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                      ligneFilter === f ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                    }`}>
                    {f === 'all' ? 'Tout' : f === 'valid' ? 'Complètes' : f === 'warning' ? 'À compléter' : 'À corriger'}
                  </button>
                ))}
              </div>
            </div>

            <BatchActionsBar count={selectedIdxs.size} groups={groups}
              onBatchCategory={handleBatchCategory}
              onBatchBrand={handleBatchBrand}
              onBatchEan={handleBatchEan}
              onBatchDelete={handleBatchDelete} />

            <LignesTable lignes={lignes} groups={groups} isPreview={isPreview}
              isPostValidatedEditing={postValidatedEditing}
              recentlyCorrectedIdxs={recentlyCorrectedIdxs}
              selectedIdxs={selectedIdxs} selectedLineIdx={selectedLineIdx}
              actions={tableActions} onToggleAll={handleToggleAll} filter={ligneFilter} />

            {isPreview && <AddLigneForm onAdd={handleAddLigne} isPending={addLigneMut.isPending} />}
          </div>
        )}

        {activeTab === 'pdf' && (
          <div className="h-[700px]">
            <PdfHighlightViewer
              pdfUrl={getPdfUrl(enrichedDetail.fichier_path)}
              highlightLine={
                selectedLineIdx !== null && lignes[selectedLineIdx]?.page_number != null
                  ? { page: lignes[selectedLineIdx].page_number!, y: lignes[selectedLineIdx].y_position ?? 0 }
                  : null
              }
            />
          </div>
        )}

        {activeTab === 'conflits' && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 text-center text-slate-500">
            {conflictCount > 0 ? (
              <div>
                <p className="text-lg font-semibold text-slate-800 mb-2">{conflictCount} conflit{conflictCount > 1 ? 's' : ''}</p>
                <p className="text-sm text-slate-500 mb-4">Des produits similaires existent déjà dans le catalogue.</p>
                <Link to="/etl-conflits" search={{ import_id: importId }} className="text-emerald-600 hover:underline font-medium text-sm">
                  Résoudre les conflits →
                </Link>
              </div>
            ) : (
              <p className="text-sm">Aucun conflit pour cet import.</p>
            )}
          </div>
        )}
      </div>

      {/* Bottom progress bar */}
      {isPreview && <BottomProgressBar lignes={lignes} showCelebration={showCelebration} />}

      {/* Modals */}
      {showConfirmModal && detail && (
        <ValidationConfirmModal
          lignes={lignes} detail={detail} loading={validating}
          onConfirm={async () => {
            setValidating(true)
            await handleValidate()
            setValidating(false)
            setShowConfirmModal(false)
          }}
          onCancel={() => setShowConfirmModal(false)}
        />
      )}

      {showRevertConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
          <div className="bg-white rounded-2xl border border-slate-200 w-full max-w-sm shadow-xl p-5 space-y-3">
            <h2 className="text-[15px] font-bold text-slate-900">Annuler cet import ?</h2>
            <p className="text-[12px] text-slate-500">
              Les mouvements de stock seront compensés, la facture fournisseur sera annulée
              et les prix catalogue seront restaurés.
            </p>
            <div className="flex gap-2 justify-end pt-2">
              <button onClick={() => setShowRevertConfirm(false)} className="px-4 py-2 text-[13px] text-slate-600 hover:bg-slate-100 rounded-lg">
                Annuler
              </button>
              <button
                onClick={async () => {
                  try {
                    await revertImport(importId)
                    setShowRevertConfirm(false)
                    invalidate()
                  } catch (err) {
                    setError(normalizeError(err).message || 'Erreur revert')
                    setShowRevertConfirm(false)
                  }
                }}
                className="px-4 py-2 text-[13px] font-semibold text-white bg-amber-600 hover:bg-amber-500 rounded-lg"
              >
                Confirmer l'annulation
              </button>
            </div>
          </div>
        </div>
      )}

      {showReopenConfirm && detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
          <div className="bg-white rounded-2xl border border-slate-200 w-full max-w-md shadow-xl p-5 space-y-3">
            <h2 className="text-[15px] font-bold text-slate-900">Reprendre en édition ?</h2>
            {detail.statut === 'REJECTED' ? (
              <p className="text-[12px] text-slate-500">
                L'import va repasser en <strong>PREVIEW</strong>. Tu pourras corriger
                les lignes puis revalider normalement. Aucun mouvement de stock
                n'était créé, rien à compenser.
              </p>
            ) : (
              <div className="text-[12px] text-slate-500 space-y-2">
                <p>L'import va repasser en <strong>PREVIEW</strong>. Voici les implications :</p>
                <ul className="list-disc pl-4 space-y-1">
                  <li>Les mouvements de stock du revert sont <strong>conservés</strong></li>
                  <li>À la re-validation, de nouveaux mouvements ENTREE seront créés ;
                    ils compensent comptablement les AJUSTEMENT existants (net +N cohérent)</li>
                  <li>Une <strong>nouvelle facture</strong> sera émise — la précédente
                    reste ANNULEE pour la traçabilité</li>
                  <li>Si des ventes ont eu lieu depuis le revert, le stock actuel sera
                    modifié par les nouveaux ENTREE comme dans un import frais</li>
                </ul>
                <p className="italic text-[11px]">
                  Le validateur original et le reverteur recevront une notification.
                </p>
              </div>
            )}
            <div className="flex gap-2 justify-end pt-2">
              <button
                onClick={() => setShowReopenConfirm(false)}
                className="px-4 py-2 text-[13px] text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Annuler
              </button>
              <button
                onClick={handleReopen}
                className="px-4 py-2 text-[13px] font-semibold text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg"
              >
                Reprendre en édition
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
