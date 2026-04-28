import { api } from './fetchClient'

export interface OfflineMutation {
  id: string
  method: string
  path: string
  body?: Record<string, unknown>
  client_timestamp: string
}

export interface MutationResult {
  id: string
  status: 'ok' | 'conflict' | 'error' | 'already_processed' | 'unsupported'
  detail: string
}

export interface OfflineSyncResponse {
  processed: number
  succeeded: number
  failed: number
  skipped: number
  results: MutationResult[]
}

export const offlineApi = {
  sync: (mutations: OfflineMutation[]) =>
    api.post<OfflineSyncResponse>('/offline/sync', { mutations }),
}
