import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { containersApi } from '../containers'
import type {
  ContainerCreate,
  ContainerUpdate,
  ContainerAssignCreate,
  ContainerContentCreate,
  ContainerContentUpdate,
  BulkContentEntry,
} from '@/types/container'

const keys = {
  all: ['containers'] as const,
  detail: (id: number) => ['containers', 'detail', id] as const,
  contents: (id: number) => ['containers', 'contents', id] as const,
  history: (id: number) => ['containers', 'history', id] as const,
  byMovement: (id: number) => ['containers', 'movement', id] as const,
}

export function useContainersList() {
  return useQuery({
    queryKey: keys.all,
    queryFn: () => containersApi.list({ limit: 200 }),
    staleTime: 5 * 60 * 1000,
  })
}

export function useContainerDetail(id: number | null) {
  return useQuery({
    queryKey: keys.detail(id!),
    queryFn: () => containersApi.get(id!),
    enabled: id !== null,
  })
}

export function useCreateContainer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ContainerCreate) => containersApi.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: keys.all }) },
  })
}

export function useUpdateContainer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ContainerUpdate }) =>
      containersApi.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: keys.all }) },
  })
}

export function useDeleteContainer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => containersApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: keys.all }) },
  })
}

export function useAssignContainer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ContainerAssignCreate) => containersApi.assign(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: keys.all }) },
  })
}

export function useContainersByMovement(movementId: number | null) {
  return useQuery({
    queryKey: keys.byMovement(movementId!),
    queryFn: () => containersApi.listByMovement(movementId!),
    enabled: movementId !== null,
  })
}

export function useRemoveAssignment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (assignmentId: number) => containersApi.removeAssignment(assignmentId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: keys.all }) },
  })
}

// ── Contents (contenu persistant) ───────────────────────────

export function useContainerDetailQuery(id: number | null) {
  return useQuery({
    queryKey: keys.detail(id!),
    queryFn: () => containersApi.getDetail(id!),
    enabled: id !== null && id > 0,
  })
}

export function useContainerContents(containerId: number | null) {
  return useQuery({
    queryKey: keys.contents(containerId!),
    queryFn: () => containersApi.getContents(containerId!),
    enabled: containerId !== null && containerId > 0,
  })
}

export function useContainerHistory(containerId: number | null) {
  return useQuery({
    queryKey: keys.history(containerId!),
    queryFn: () => containersApi.getHistory(containerId!),
    enabled: containerId !== null && containerId > 0,
  })
}

export function useAddContainerContent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ containerId, data }: { containerId: number; data: ContainerContentCreate }) =>
      containersApi.addContent(containerId, data),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: keys.contents(vars.containerId) })
      qc.invalidateQueries({ queryKey: keys.detail(vars.containerId) })
      qc.invalidateQueries({ queryKey: keys.all })
    },
  })
}

export function useUpdateContainerContent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ containerId, contentId, data }: { containerId: number; contentId: number; data: ContainerContentUpdate }) =>
      containersApi.updateContent(containerId, contentId, data),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: keys.contents(vars.containerId) })
      qc.invalidateQueries({ queryKey: keys.detail(vars.containerId) })
      qc.invalidateQueries({ queryKey: keys.all })
    },
  })
}

export function useRemoveContainerContent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ containerId, contentId }: { containerId: number; contentId: number }) =>
      containersApi.removeContent(containerId, contentId),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: keys.contents(vars.containerId) })
      qc.invalidateQueries({ queryKey: keys.detail(vars.containerId) })
      qc.invalidateQueries({ queryKey: keys.all })
    },
  })
}

export function useBulkSetContainerContents() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ containerId, entries }: { containerId: number; entries: BulkContentEntry[] }) =>
      containersApi.bulkSetContents(containerId, entries),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: keys.contents(vars.containerId) })
      qc.invalidateQueries({ queryKey: keys.detail(vars.containerId) })
      qc.invalidateQueries({ queryKey: keys.all })
    },
  })
}
