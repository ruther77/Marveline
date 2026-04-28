import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { vpnApi } from '../vpn'
import type { VpnPeerCreate, VpnPeerUpdate, VpnIpPoolCreate } from '@/types/vpn'

// ── Peers ──────────────────────────────────────────────────────────────────

export function useVpnPeers() {
  return useQuery({
    queryKey: queryKeys.vpn.peers(),
    queryFn: () => vpnApi.listPeers(),
    staleTime: 30 * 1000,
  })
}

export function useVpnPeer(id: string | null) {
  return useQuery({
    queryKey: queryKeys.vpn.peer(id!),
    queryFn: () => vpnApi.getPeer(id!),
    enabled: id !== null,
  })
}

export function useVpnPeerConfig(id: string | null) {
  return useQuery({
    queryKey: ['vpn', 'peers', id, 'config'],
    queryFn: () => vpnApi.getPeerConfig(id!),
    enabled: id !== null,
  })
}

export function useVpnPeerQrCode() {
  return useMutation({
    mutationFn: (id: string) => vpnApi.getPeerQrCode(id),
  })
}

export function useCreateVpnPeer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: VpnPeerCreate) => vpnApi.createPeer(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.vpn.peers() }) },
  })
}

export function useUpdateVpnPeer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: VpnPeerUpdate }) =>
      vpnApi.updatePeer(id, data),
    onSuccess: (_r, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.vpn.peer(id) })
      qc.invalidateQueries({ queryKey: queryKeys.vpn.peers() })
    },
  })
}

export function useDeleteVpnPeer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => vpnApi.deletePeer(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.vpn.peers() }) },
  })
}

export function useRotateVpnPeerKeys() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => vpnApi.rotatePeerKeys(id),
    onSuccess: (_r, id) => {
      qc.invalidateQueries({ queryKey: queryKeys.vpn.peer(id) })
    },
  })
}

export function useEnableVpnPeer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => vpnApi.enablePeer(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.vpn.peers() }) },
  })
}

export function useDisableVpnPeer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => vpnApi.disablePeer(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.vpn.peers() }) },
  })
}

// ── Status ─────────────────────────────────────────────────────────────────

export function useVpnStatus(refetchInterval: number | false = false) {
  return useQuery({
    queryKey: queryKeys.vpn.status(),
    queryFn: () => vpnApi.getStatus(),
    staleTime: 15 * 1000,
    refetchInterval,
  })
}

// ── IP Pools ───────────────────────────────────────────────────────────────

export function useVpnIpPools() {
  return useQuery({
    queryKey: queryKeys.vpn.ipPools(),
    queryFn: () => vpnApi.listIpPools(),
    staleTime: 60 * 1000,
  })
}

export function useCreateVpnIpPool() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: VpnIpPoolCreate) => vpnApi.createIpPool(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.vpn.ipPools() }) },
  })
}
