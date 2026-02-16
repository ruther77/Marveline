import apiClient from './client'
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
    const response = await apiClient.get('/vpn/peers')
    return response.data
  },

  getPeer: async (id: string): Promise<VpnPeer> => {
    const response = await apiClient.get(`/vpn/peers/${id}`)
    return response.data
  },

  createPeer: async (data: VpnPeerCreate): Promise<VpnPeer> => {
    const response = await apiClient.post('/vpn/peers', data)
    return response.data
  },

  updatePeer: async (id: string, data: VpnPeerUpdate): Promise<VpnPeer> => {
    const response = await apiClient.patch(`/vpn/peers/${id}`, data)
    return response.data
  },

  deletePeer: async (id: string): Promise<void> => {
    await apiClient.delete(`/vpn/peers/${id}`)
  },

  rotatePeerKeys: async (id: string): Promise<VpnPeer> => {
    const response = await apiClient.post(`/vpn/peers/${id}/rotate`)
    return response.data
  },

  enablePeer: async (id: string): Promise<VpnPeer> => {
    const response = await apiClient.post(`/vpn/peers/${id}/enable`)
    return response.data
  },

  disablePeer: async (id: string): Promise<VpnPeer> => {
    const response = await apiClient.post(`/vpn/peers/${id}/disable`)
    return response.data
  },

  // ── Config & QR ────────────────────────────────────────────────────

  getPeerConfig: async (id: string): Promise<VpnConfig> => {
    const response = await apiClient.get(`/vpn/peers/${id}/config`)
    return response.data
  },

  getPeerQrCode: async (id: string): Promise<Blob> => {
    const response = await apiClient.get(`/vpn/peers/${id}/qrcode`, {
      responseType: 'blob',
    })
    return response.data
  },

  // ── Status ─────────────────────────────────────────────────────────

  getStatus: async (): Promise<VpnServerStatus> => {
    const response = await apiClient.get('/vpn/status')
    return response.data
  },

  // ── IP Pools ───────────────────────────────────────────────────────

  listIpPools: async (): Promise<VpnIpPoolListResponse> => {
    const response = await apiClient.get('/vpn/ip-pools')
    return response.data
  },

  createIpPool: async (data: VpnIpPoolCreate): Promise<VpnIpPool> => {
    const response = await apiClient.post('/vpn/ip-pools', data)
    return response.data
  },
}
