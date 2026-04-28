import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { devisApi } from '../devis'
import type { DevisStatsMap } from '../devis'
import type { DevisStatus, DevisCreate, DevisConvertPayload, DevisVersion, DevisModuleCreate, DevisModuleUpdate, DevisPhaseCreate, DevisPhaseUpdate, DevisCoverageItem, DevisCoverageItemCreate, DevisCoverageItemUpdate, DevisCoverageSummary, DevisModule, DevisPhase } from '@/types/devis'

export function useDevisStats() {
  return useQuery<DevisStatsMap>({
    queryKey: queryKeys.devis.stats(),
    queryFn: () => devisApi.getStats(),
    staleTime: 60 * 1000,
  })
}

export function useDevisList(params?: {
  skip?: number
  limit?: number
  status?: DevisStatus
  customer_id?: number
  date_from?: string
  date_to?: string
  search?: string
}) {
  return useQuery({
    queryKey: queryKeys.devis.list(params ?? {}),
    queryFn: () => devisApi.listDevis(params),
  })
}

export function useDevisDetail(id: number | null) {
  return useQuery({
    queryKey: queryKeys.devis.detail(id!),
    queryFn: () => devisApi.get(id!),
    enabled: id !== null,
  })
}

export function useDevisMutations() {
  const qc = useQueryClient()

  const invalidateDevis = () => {
    qc.invalidateQueries({ queryKey: queryKeys.devis.all })
  }

  const send = useMutation({
    mutationFn: (id: number) => devisApi.send(id),
    onSuccess: invalidateDevis,
  })

  const accept = useMutation({
    mutationFn: (id: number) => devisApi.accept(id),
    onSuccess: invalidateDevis,
  })

  const startNegotiation = useMutation({
    mutationFn: (id: number) => devisApi.startNegotiation(id),
    onSuccess: invalidateDevis,
  })

  const markVersionPending = useMutation({
    mutationFn: (id: number) => devisApi.markVersionPending(id),
    onSuccess: invalidateDevis,
  })

  const refuse = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason?: string }) =>
      devisApi.refuse(id, reason),
    onSuccess: invalidateDevis,
  })

  const cancel = useMutation({
    mutationFn: (id: number) => devisApi.cancel(id),
    onSuccess: invalidateDevis,
  })

  const duplicate = useMutation({
    mutationFn: (id: number) => devisApi.duplicate(id),
    onSuccess: invalidateDevis,
  })

  const renew = useMutation({
    mutationFn: (id: number) => devisApi.renew(id),
    onSuccess: (newDevis) => {
      // Prime le cache du nouveau devis pour une navigation immédiate sans écran vide.
      qc.setQueryData(queryKeys.devis.detail(newDevis.id), newDevis)
      invalidateDevis()
    },
  })

  const convertToReservation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: DevisConvertPayload }) =>
      devisApi.convertToReservation(id, payload),
    onSuccess: () => {
      invalidateDevis()
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
    },
  })

  return { send, accept, startNegotiation, markVersionPending, refuse, cancel, duplicate, renew, convertToReservation }
}

export function useCreateDevis() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: DevisCreate) => devisApi.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.devis.all }) },
  })
}

export function useUpdateDevis() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<DevisCreate> }) =>
      devisApi.update(id, data),
    onSuccess: (_r, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.devis.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.devis.lists() })
    },
  })
}

export function useDevisPdf() {
  return useMutation({
    mutationFn: (id: number) => devisApi.getPdf(id),
  })
}

export function useAddNegotiationEntry() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      message,
      proposed_amount_cents,
    }: {
      id: number
      message: string
      proposed_amount_cents?: number
    }) => devisApi.addNegotiationEntry(id, { message, proposed_amount_cents }),
    onSuccess: (_r, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.devis.detail(id) })
    },
  })
}

export function useConcludeNegotiation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, outcome, reason }: { id: number; outcome: 'accepted' | 'refused'; reason?: string }) =>
      devisApi.concludeNegotiation(id, outcome, reason),
    onSuccess: (_r, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.devis.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.devis.lists() })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
    },
  })
}

export function useRequestChange() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, description }: { id: number; description: string }) =>
      devisApi.requestChange(id, description),
    onSuccess: (_r, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.devis.detail(id) })
    },
  })
}

export function useDevisVersions(id: number) {
  return useQuery<DevisVersion[]>({
    queryKey: queryKeys.devis.versions(id),
    queryFn: () => devisApi.getVersions(id),
    enabled: id > 0,
  })
}

export function useDevisModules(devisId: number) {
  return useQuery<DevisModule[]>({
    queryKey: queryKeys.devis.modules(devisId),
    queryFn: () => devisApi.listModules(devisId),
    enabled: devisId > 0,
  })
}

export function useDevisPhases(devisId: number) {
  return useQuery<DevisPhase[]>({
    queryKey: queryKeys.devis.phases(devisId),
    queryFn: () => devisApi.listPhases(devisId),
    enabled: devisId > 0,
  })
}

export function useDevisCoverage(devisId: number) {
  return useQuery<DevisCoverageSummary>({
    queryKey: queryKeys.devis.coverage(devisId),
    queryFn: () => devisApi.getCoverage(devisId),
    enabled: devisId > 0,
  })
}

export function useSignDevis() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, signatureData }: { id: number; signatureData: string }) =>
      devisApi.uploadSignature(id, signatureData),
    onSuccess: (_r, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.devis.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
    },
  })
}

export function useAddDevisModule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ devisId, data }: { devisId: number; data: DevisModuleCreate }) =>
      devisApi.addModule(devisId, data),
    onSuccess: (_r, { devisId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.devis.detail(devisId) })
      qc.invalidateQueries({ queryKey: queryKeys.devis.modules(devisId) })
      qc.invalidateQueries({ queryKey: queryKeys.devis.coverage(devisId) })
    },
  })
}

export function useUpdateDevisModule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ devisId, moduleId, data }: { devisId: number; moduleId: number; data: DevisModuleUpdate }) =>
      devisApi.updateModule(devisId, moduleId, data),
    onSuccess: (_r, { devisId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.devis.detail(devisId) })
      qc.invalidateQueries({ queryKey: queryKeys.devis.modules(devisId) })
      qc.invalidateQueries({ queryKey: queryKeys.devis.coverage(devisId) })
    },
  })
}

export function useDeleteDevisModule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ devisId, moduleId }: { devisId: number; moduleId: number }) =>
      devisApi.deleteModule(devisId, moduleId),
    onSuccess: (_r, { devisId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.devis.detail(devisId) })
      qc.invalidateQueries({ queryKey: queryKeys.devis.modules(devisId) })
      qc.invalidateQueries({ queryKey: queryKeys.devis.coverage(devisId) })
    },
  })
}

export function useAddDevisPhase() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ devisId, data }: { devisId: number; data: DevisPhaseCreate }) =>
      devisApi.addPhase(devisId, data),
    onSuccess: (_r, { devisId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.devis.detail(devisId) })
      qc.invalidateQueries({ queryKey: queryKeys.devis.phases(devisId) })
      qc.invalidateQueries({ queryKey: queryKeys.devis.coverage(devisId) })
    },
  })
}

export function useUpdateDevisPhase() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ devisId, phaseId, data }: { devisId: number; phaseId: number; data: DevisPhaseUpdate }) =>
      devisApi.updatePhase(devisId, phaseId, data),
    onSuccess: (_r, { devisId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.devis.detail(devisId) })
      qc.invalidateQueries({ queryKey: queryKeys.devis.phases(devisId) })
      qc.invalidateQueries({ queryKey: queryKeys.devis.coverage(devisId) })
    },
  })
}

export function useDeleteDevisPhase() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ devisId, phaseId }: { devisId: number; phaseId: number }) =>
      devisApi.deletePhase(devisId, phaseId),
    onSuccess: (_r, { devisId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.devis.detail(devisId) })
      qc.invalidateQueries({ queryKey: queryKeys.devis.phases(devisId) })
      qc.invalidateQueries({ queryKey: queryKeys.devis.coverage(devisId) })
    },
  })
}

export function useDevisCoverageItems(devisId: number) {
  return useQuery<DevisCoverageItem[]>({
    queryKey: [...queryKeys.devis.detail(devisId), 'coverage-items'],
    queryFn: () => devisApi.listCoverageItems(devisId),
    enabled: devisId > 0,
  })
}

export function useAddDevisCoverageItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ devisId, data }: { devisId: number; data: DevisCoverageItemCreate }) =>
      devisApi.addCoverageItem(devisId, data),
    onSuccess: (_r, { devisId }) => {
      qc.invalidateQueries({ queryKey: [...queryKeys.devis.detail(devisId), 'coverage-items'] })
    },
  })
}

export function useUpdateDevisCoverageItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ devisId, itemId, data }: { devisId: number; itemId: number; data: DevisCoverageItemUpdate }) =>
      devisApi.updateCoverageItem(devisId, itemId, data),
    onSuccess: (_r, { devisId }) => {
      qc.invalidateQueries({ queryKey: [...queryKeys.devis.detail(devisId), 'coverage-items'] })
    },
  })
}

export function useDeleteDevisCoverageItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ devisId, itemId }: { devisId: number; itemId: number }) =>
      devisApi.deleteCoverageItem(devisId, itemId),
    onSuccess: (_r, { devisId }) => {
      qc.invalidateQueries({ queryKey: [...queryKeys.devis.detail(devisId), 'coverage-items'] })
    },
  })
}

export function useDevisChangeRequests(devisId: number) {
  return useQuery({
    queryKey: [...queryKeys.devis.detail(devisId), 'change-requests'],
    queryFn: () => devisApi.listChangeRequests(devisId),
    enabled: devisId > 0,
  })
}

export function useUpdateDevisChangeRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ devisId, crId, status }: { devisId: number; crId: number; status: string }) =>
      devisApi.updateChangeRequest(devisId, crId, status),
    onSuccess: (_r, { devisId }) => {
      qc.invalidateQueries({ queryKey: [...queryKeys.devis.detail(devisId), 'change-requests'] })
      qc.invalidateQueries({ queryKey: queryKeys.devis.detail(devisId) })
    },
  })
}

// ── G31 — Bundle preview ───────────────────────────────────────────────────

export function useBundlePreview(bundleId: number | null | undefined) {
  return useQuery({
    queryKey: ['bundles', 'preview', bundleId],
    queryFn: () => devisApi.previewBundleItems(bundleId!),
    enabled: bundleId != null && bundleId > 0,
  })
}

// ── G28 — Historique lignes ────────────────────────────────────────────────

export function useDevisLineHistory(devisId: number | null) {
  return useQuery({
    queryKey: [...queryKeys.devis.detail(devisId!), 'line-history'],
    queryFn: () => devisApi.getLineHistory(devisId!),
    enabled: devisId !== null,
  })
}

// ── G7 — Pieces jointes ───────────────────────────────────────────────────

export function useDevisAttachments(devisId: number | null) {
  return useQuery({
    queryKey: [...queryKeys.devis.detail(devisId!), 'attachments'],
    queryFn: () => devisApi.listAttachments(devisId!),
    enabled: devisId !== null,
  })
}

export function useUploadDevisAttachment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ devisId, file }: { devisId: number; file: File }) =>
      devisApi.uploadAttachment(devisId, file),
    onSuccess: (_r, { devisId }) => {
      qc.invalidateQueries({ queryKey: [...queryKeys.devis.detail(devisId), 'attachments'] })
    },
  })
}

export function useDeleteDevisAttachment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ devisId, attachmentId }: { devisId: number; attachmentId: number }) =>
      devisApi.deleteAttachment(devisId, attachmentId),
    onSuccess: (_r, { devisId }) => {
      qc.invalidateQueries({ queryKey: [...queryKeys.devis.detail(devisId), 'attachments'] })
    },
  })
}
