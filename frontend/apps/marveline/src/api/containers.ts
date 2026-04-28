import { api } from './fetchClient'
import type {
  Container,
  ContainerContent,
  ContainerContentCreate,
  ContainerContentUpdate,
  ContainerCreate,
  ContainerDetail,
  ContainerMovementHistory,
  ContainerUpdate,
  ContainerAssignCreate,
  ContainerAssignment,
  BulkContentEntry,
  PaginatedContainers,
} from '@/types/container'

export const containersApi = {
  list: (params?: { skip?: number; limit?: number }) => {
    const qs = new URLSearchParams({ skip: String(params?.skip ?? 0), limit: String(params?.limit ?? 200) }).toString()
    return api.get<PaginatedContainers>(`/containers?${qs}`)
  },
  get: (id: number) => api.get<Container>(`/containers/${id}`),
  create: (data: ContainerCreate) => api.post<Container>('/containers', data),
  update: (id: number, data: ContainerUpdate) =>
    api.patch<Container>(`/containers/${id}`, data),
  delete: (id: number) => api.delete<void>(`/containers/${id}`),

  // Assignments
  assign: (data: ContainerAssignCreate) =>
    api.post<ContainerAssignment>('/containers/assign', data),
  listByMovement: (movementId: number) =>
    api.get<ContainerAssignment[]>(`/containers/movement/${movementId}`),
  removeAssignment: (assignmentId: number) =>
    api.delete<void>(`/containers/assignment/${assignmentId}`),

  // Contents (contenu persistant)
  getDetail: (id: number) =>
    api.get<ContainerDetail>(`/containers/${id}/detail`),
  getContents: (containerId: number) =>
    api.get<ContainerContent[]>(`/containers/${containerId}/contents`),
  addContent: (containerId: number, data: ContainerContentCreate) =>
    api.post<ContainerContent>(`/containers/${containerId}/contents`, data),
  updateContent: (containerId: number, contentId: number, data: ContainerContentUpdate) =>
    api.patch<ContainerContent>(`/containers/${containerId}/contents/${contentId}`, data),
  removeContent: (containerId: number, contentId: number) =>
    api.delete<void>(`/containers/${containerId}/contents/${contentId}`),
  getHistory: (containerId: number) =>
    api.get<ContainerMovementHistory[]>(`/containers/${containerId}/history`),
  bulkSetContents: (containerId: number, entries: BulkContentEntry[]) =>
    api.put<ContainerContent[]>(`/containers/${containerId}/contents/bulk`, { entries }),
}
