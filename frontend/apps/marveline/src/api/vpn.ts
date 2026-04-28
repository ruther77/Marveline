import { api, fetchBlob } from './fetchClient'
import type {
  VpnPeer,
  VpnPeerListResponse,
  VpnPeerCreate,
  VpnPeerUpdate,
  VpnConfig,
  VpnServerStatus,
  VpnIpPool,
  VpnIpPoolListResponse,
  VpnIpPoolCreate,
} from '@/types/vpn'

export const vpnApi = {
  // ── Peers ──────────────────────────────────────────────────────────

  listPeers: async (): Promise<VpnPeerListResponse> => {
    return api.get<VpnPeerListResponse>('/vpn/peers')
  },

  getPeer: async (id: string): Promise<VpnPeer> => {
    return api.get<VpnPeer>(`/vpn/peers/${id}`)
  },

  createPeer: async (data: VpnPeerCreate): Promise<VpnPeer> => {
    return api.post<VpnPeer>('/vpn/peers', data)
  },

  updatePeer: async (id: string, data: VpnPeerUpdate): Promise<VpnPeer> => {
    return api.patch<VpnPeer>(`/vpn/peers/${id}`, data)
  },

  deletePeer: async (id: string): Promise<void> => {
    await api.delete(`/vpn/peers/${id}`)
  },

  rotatePeerKeys: async (id: string): Promise<VpnPeer> => {
    return api.post<VpnPeer>(`/vpn/peers/${id}/rotate`)
  },

  enablePeer: async (id: string): Promise<VpnPeer> => {
    return api.post<VpnPeer>(`/vpn/peers/${id}/enable`)
  },

  disablePeer: async (id: string): Promise<VpnPeer> => {
    return api.post<VpnPeer>(`/vpn/peers/${id}/disable`)
  },

  // ── Config & QR ────────────────────────────────────────────────────

  getPeerConfig: async (id: string): Promise<VpnConfig> => {
    return api.get<VpnConfig>(`/vpn/peers/${id}/config`)
  },

  getPeerQrCode: async (id: string): Promise<Blob> => {
    return fetchBlob(`/vpn/peers/${id}/qrcode`)
  },

  // ── Status ─────────────────────────────────────────────────────────

  getStatus: async (): Promise<VpnServerStatus> => {
    return api.get<VpnServerStatus>('/vpn/status')
  },

  // ── IP Pools ───────────────────────────────────────────────────────

  listIpPools: async (): Promise<VpnIpPoolListResponse> => {
    return api.get<VpnIpPoolListResponse>('/vpn/ip-pools')
  },

  createIpPool: async (data: VpnIpPoolCreate): Promise<VpnIpPool> => {
    return api.post<VpnIpPool>('/vpn/ip-pools', data)
  },
}
