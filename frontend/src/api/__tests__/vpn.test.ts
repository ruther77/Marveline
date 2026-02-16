/**
 * Tests unitaires pour api/vpn.ts
 * Vérifie CRUD peers VPN + config + QR + status + IP pools
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { vpnApi } from '../vpn'
import apiClient from '../client'
import type { VpnPeer, VpnPeerCreate, VpnPeerUpdate, VpnConfig, VpnServerStatus, VpnIpPool, VpnIpPoolCreate } from '@/types/vpn'

// Mock apiClient
vi.mock('../client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('VPN API - Peers CRUD', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère liste de tous les peers VPN', async () => {
    const mockResponse = {
      peers: [
        { id: 'peer-1', name: 'Mobile Phone', public_key: 'key1...', is_enabled: true },
        { id: 'peer-2', name: 'Laptop', public_key: 'key2...', is_enabled: true },
      ],
      total: 2,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await vpnApi.listPeers()

    expect(apiClient.get).toHaveBeenCalledWith('/vpn/peers')
    expect(result.peers).toHaveLength(2)
    expect(result.total).toBe(2)
  })

  it('gère liste vide (0 peers)', async () => {
    const mockResponse = {
      peers: [],
      total: 0,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await vpnApi.listPeers()

    expect(result.peers).toEqual([])
    expect(result.total).toBe(0)
  })

  it('récupère un peer par ID', async () => {
    const mockPeer: VpnPeer = {
      id: 'peer-1',
      name: 'Mobile Phone',
      public_key: 'abcd1234...',
      allowed_ips: ['10.8.0.2/32'],
      endpoint: null,
      is_enabled: true,
      last_handshake: '2026-02-16T10:00:00Z',
      transfer_rx_bytes: 1024000,
      transfer_tx_bytes: 512000,
      created_at: '2026-01-01T00:00:00Z',
      tenant_id: 1,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockPeer })

    const result = await vpnApi.getPeer('peer-1')

    expect(apiClient.get).toHaveBeenCalledWith('/vpn/peers/peer-1')
    expect(result).toEqual(mockPeer)
    expect(result.name).toBe('Mobile Phone')
  })

  it('propage les erreurs 404 si peer non trouvé', async () => {
    const error = new Error('VPN peer not found')
    vi.mocked(apiClient.get).mockRejectedValue(error)

    await expect(vpnApi.getPeer('peer-999')).rejects.toThrow('VPN peer not found')
  })

  it('crée un nouveau peer VPN', async () => {
    const newPeer: VpnPeerCreate = {
      name: 'New Device',
      allowed_ips: ['10.8.0.10/32'],
    }
    const mockResponse: VpnPeer = {
      id: 'peer-3',
      name: 'New Device',
      public_key: 'newkey1234...',
      allowed_ips: ['10.8.0.10/32'],
      endpoint: null,
      is_enabled: true,
      last_handshake: null,
      transfer_rx_bytes: 0,
      transfer_tx_bytes: 0,
      created_at: '2026-02-16T00:00:00Z',
      tenant_id: 1,
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const result = await vpnApi.createPeer(newPeer)

    expect(apiClient.post).toHaveBeenCalledWith('/vpn/peers', newPeer)
    expect(result).toEqual(mockResponse)
    expect(result.id).toBe('peer-3')
  })

  it('propage les erreurs 400 si données invalides (createPeer)', async () => {
    const error = new Error('Invalid IP address')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    const newPeer: VpnPeerCreate = {
      name: 'Invalid',
      allowed_ips: ['invalid-ip'],
    }

    await expect(vpnApi.createPeer(newPeer)).rejects.toThrow('Invalid IP address')
  })

  it('met à jour un peer existant (PATCH partiel)', async () => {
    const updateData: VpnPeerUpdate = {
      name: 'Updated Device Name',
      allowed_ips: ['10.8.0.20/32'],
    }
    const mockResponse: VpnPeer = {
      id: 'peer-1',
      name: 'Updated Device Name',
      public_key: 'key1...',
      allowed_ips: ['10.8.0.20/32'],
      endpoint: null,
      is_enabled: true,
      last_handshake: null,
      transfer_rx_bytes: 0,
      transfer_tx_bytes: 0,
      created_at: '2026-01-01T00:00:00Z',
      tenant_id: 1,
    }
    vi.mocked(apiClient.patch).mockResolvedValue({ data: mockResponse })

    const result = await vpnApi.updatePeer('peer-1', updateData)

    expect(apiClient.patch).toHaveBeenCalledWith('/vpn/peers/peer-1', updateData)
    expect(result.name).toBe('Updated Device Name')
  })

  it('propage les erreurs 404 si peer non trouvé (updatePeer)', async () => {
    const error = new Error('VPN peer not found')
    vi.mocked(apiClient.patch).mockRejectedValue(error)

    await expect(vpnApi.updatePeer('peer-999', { name: 'Test' })).rejects.toThrow('VPN peer not found')
  })

  it('supprime un peer VPN', async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({})

    await vpnApi.deletePeer('peer-1')

    expect(apiClient.delete).toHaveBeenCalledWith('/vpn/peers/peer-1')
  })

  it('propage les erreurs 404 si peer non trouvé (deletePeer)', async () => {
    const error = new Error('VPN peer not found')
    vi.mocked(apiClient.delete).mockRejectedValue(error)

    await expect(vpnApi.deletePeer('peer-999')).rejects.toThrow('VPN peer not found')
  })

  it('effectue rotation des clés WireGuard d\'un peer', async () => {
    const mockResponse: VpnPeer = {
      id: 'peer-1',
      name: 'Mobile Phone',
      public_key: 'newrotatedkey1234...',
      allowed_ips: ['10.8.0.2/32'],
      endpoint: null,
      is_enabled: true,
      last_handshake: null,
      transfer_rx_bytes: 0,
      transfer_tx_bytes: 0,
      created_at: '2026-01-01T00:00:00Z',
      tenant_id: 1,
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const result = await vpnApi.rotatePeerKeys('peer-1')

    expect(apiClient.post).toHaveBeenCalledWith('/vpn/peers/peer-1/rotate')
    expect(result.public_key).toBe('newrotatedkey1234...')
  })

  it('active un peer VPN', async () => {
    const mockResponse: VpnPeer = {
      id: 'peer-1',
      name: 'Mobile Phone',
      public_key: 'key1...',
      allowed_ips: ['10.8.0.2/32'],
      endpoint: null,
      is_enabled: true,
      last_handshake: null,
      transfer_rx_bytes: 0,
      transfer_tx_bytes: 0,
      created_at: '2026-01-01T00:00:00Z',
      tenant_id: 1,
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const result = await vpnApi.enablePeer('peer-1')

    expect(apiClient.post).toHaveBeenCalledWith('/vpn/peers/peer-1/enable')
    expect(result.is_enabled).toBe(true)
  })

  it('désactive un peer VPN', async () => {
    const mockResponse: VpnPeer = {
      id: 'peer-1',
      name: 'Mobile Phone',
      public_key: 'key1...',
      allowed_ips: ['10.8.0.2/32'],
      endpoint: null,
      is_enabled: false,
      last_handshake: null,
      transfer_rx_bytes: 0,
      transfer_tx_bytes: 0,
      created_at: '2026-01-01T00:00:00Z',
      tenant_id: 1,
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const result = await vpnApi.disablePeer('peer-1')

    expect(apiClient.post).toHaveBeenCalledWith('/vpn/peers/peer-1/disable')
    expect(result.is_enabled).toBe(false)
  })
})

describe('VPN API - Config & QR', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère config WireGuard d\'un peer (.conf)', async () => {
    const mockConfig: VpnConfig = {
      config: '[Interface]\nPrivateKey = ...\n[Peer]\nPublicKey = ...\n',
      filename: 'peer-1.conf',
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockConfig })

    const result = await vpnApi.getPeerConfig('peer-1')

    expect(apiClient.get).toHaveBeenCalledWith('/vpn/peers/peer-1/config')
    expect(result.config).toContain('[Interface]')
    expect(result.filename).toBe('peer-1.conf')
  })

  it('récupère QR code d\'un peer (Blob)', async () => {
    const mockBlob = new Blob(['fake-qr-data'], { type: 'image/png' })
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockBlob })

    const result = await vpnApi.getPeerQrCode('peer-1')

    expect(apiClient.get).toHaveBeenCalledWith('/vpn/peers/peer-1/qrcode', {
      responseType: 'blob',
    })
    expect(result).toBeInstanceOf(Blob)
    expect(result.type).toBe('image/png')
  })
})

describe('VPN API - Status', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère statut serveur VPN', async () => {
    const mockStatus: VpnServerStatus = {
      is_running: true,
      interface_name: 'wg0',
      listening_port: 51820,
      peers_count: 5,
      active_peers_count: 3,
      total_transfer_rx_bytes: 10240000,
      total_transfer_tx_bytes: 5120000,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockStatus })

    const result = await vpnApi.getStatus()

    expect(apiClient.get).toHaveBeenCalledWith('/vpn/status')
    expect(result.is_running).toBe(true)
    expect(result.peers_count).toBe(5)
    expect(result.active_peers_count).toBe(3)
  })
})

describe('VPN API - IP Pools', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère liste des pools IP', async () => {
    const mockResponse = {
      pools: [
        { id: 1, name: 'Default Pool', cidr: '10.8.0.0/24', available_count: 250 },
        { id: 2, name: 'Guest Pool', cidr: '10.9.0.0/24', available_count: 200 },
      ],
      total: 2,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await vpnApi.listIpPools()

    expect(apiClient.get).toHaveBeenCalledWith('/vpn/ip-pools')
    expect(result.pools).toHaveLength(2)
    expect(result.total).toBe(2)
  })

  it('crée un nouveau pool IP', async () => {
    const newPool: VpnIpPoolCreate = {
      name: 'New Pool',
      cidr: '10.10.0.0/24',
      description: 'Pool for testing',
    }
    const mockResponse: VpnIpPool = {
      id: 3,
      name: 'New Pool',
      cidr: '10.10.0.0/24',
      description: 'Pool for testing',
      available_count: 254,
      tenant_id: 1,
      created_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const result = await vpnApi.createIpPool(newPool)

    expect(apiClient.post).toHaveBeenCalledWith('/vpn/ip-pools', newPool)
    expect(result).toEqual(mockResponse)
    expect(result.id).toBe(3)
  })
})
