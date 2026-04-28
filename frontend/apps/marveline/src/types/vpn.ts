// ── Peers ──────────────────────────────────────────────────────────────

export interface VpnPeer {
  id: string
  tenant_id: number
  name: string
  public_key: string
  assigned_ip: string | null
  allowed_ips: string
  dns: string | null
  persistent_keepalive: number
  peer_type: 'client' | 'site' | 'mobile' | 'temporary'
  is_enabled: boolean
  is_active: boolean
  expires_at: string | null
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface VpnPeerListResponse {
  items: VpnPeer[]
  total: number
}

export interface VpnPeerCreate {
  name: string
  peer_type?: 'client' | 'site' | 'mobile' | 'temporary'
  allowed_ips?: string | null
  dns?: string | null
  persistent_keepalive?: number
  expires_at?: string | null
}

export interface VpnPeerUpdate {
  name?: string
  allowed_ips?: string | null
  dns?: string | null
  persistent_keepalive?: number
  expires_at?: string | null
  is_enabled?: boolean
}

// ── Config ─────────────────────────────────────────────────────────────

export interface VpnConfig {
  peer_name: string
  config_text: string
  filename: string
}

// ── Status ─────────────────────────────────────────────────────────────

export interface VpnPeerStatus {
  public_key: string
  latest_handshake: number
  transfer_rx: number
  transfer_tx: number
  endpoint: string
  allowed_ips: string
}

export interface VpnServerStatus {
  backend_available: boolean
  interface: string
  active_peers_count: number
  peers: VpnPeerStatus[]
}

// ── IP Pools ───────────────────────────────────────────────────────────

export interface VpnIpPool {
  id: number
  tenant_id: number
  subnet: string
  gateway_ip: string
  next_ip: string
  subnet_mask: number
  description: string | null
  created_at: string
  updated_at: string
}

export interface VpnIpPoolListResponse {
  items: VpnIpPool[]
  total: number
}

export interface VpnIpPoolCreate {
  subnet: string
  gateway_ip: string
  description?: string | null
}
