import { useState, useEffect } from 'react'
import {
  Plus,
  RefreshCw,
  Shield,
  ShieldOff,
  RotateCcw,
  Trash2,
  FileText,
  QrCode,
  Network,
  Server,
  Wifi,
  WifiOff,
  Copy,
  Download,
  Edit2,
} from 'lucide-react'
import { PageHeader } from '@shared/components/ui/Breadcrumb'
import { ActionError } from '@shared/components/ui/ActionError'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { Button } from '@shared/components/ui/Button'
import { Badge } from '@shared/components/ui/Badge'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { ConfirmDialog, DeleteConfirm } from '@shared/components/ui/ConfirmDialog'
import {
  useVpnPeers,
  useVpnIpPools,
  useVpnStatus,
  useCreateVpnPeer,
  useUpdateVpnPeer,
  useDeleteVpnPeer,
  useEnableVpnPeer,
  useDisableVpnPeer,
  useRotateVpnPeerKeys,
  useCreateVpnIpPool,
  useVpnPeerConfig,
  useVpnPeerQrCode,
} from '@/api/queries'
import type {
  VpnPeer,
  VpnPeerCreate,
  VpnPeerUpdate,
  VpnIpPoolCreate,
} from '@/types/vpn'
import { normalizeError } from '@shared/errors/normalizer'

type TabKey = 'peers' | 'pools' | 'status'

const PEER_TYPES = [
  { value: 'client', label: 'Client' },
  { value: 'site', label: 'Site-to-site' },
  { value: 'mobile', label: 'Mobile' },
  { value: 'temporary', label: 'Temporaire' },
] as const

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

function formatHandshake(timestamp: number): string {
  if (timestamp === 0) return 'Jamais'
  const diff = Math.floor(Date.now() / 1000) - timestamp
  if (diff < 60) return `${diff}s`
  if (diff < 3600) return `${Math.floor(diff / 60)}min`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`
  return `${Math.floor(diff / 86400)}j`
}

export default function VpnPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('peers')

  // ── Error state ────────────────────────────────────────────────────
  const [peerError, setPeerError] = useState<string | null>(null)
  const [poolError, setPoolError] = useState<string | null>(null)

  const peerErrHandler = (err: unknown) => setPeerError(
    normalizeError(err).message || 'Une erreur est survenue'
  )

  // ── Peer state ─────────────────────────────────────────────────────
  const [showPeerModal, setShowPeerModal] = useState(false)
  const [editingPeer, setEditingPeer] = useState<VpnPeer | null>(null)
  const [peerForm, setPeerForm] = useState<VpnPeerCreate>({
    name: '',
    peer_type: 'client',
    persistent_keepalive: 25,
  })

  const [confirmDelete, setConfirmDelete] = useState<VpnPeer | null>(null)
  const [confirmRotate, setConfirmRotate] = useState<VpnPeer | null>(null)

  // Config / QR modal
  const [configPeer, setConfigPeer] = useState<VpnPeer | null>(null)
  const [qrBlobUrl, setQrBlobUrl] = useState<string | null>(null)
  const [configTab, setConfigTab] = useState<'config' | 'qr'>('config')

  // ── IP Pool state ──────────────────────────────────────────────────
  const [showPoolModal, setShowPoolModal] = useState(false)
  const [poolForm, setPoolForm] = useState<VpnIpPoolCreate>({
    subnet: '',
    gateway_ip: '',
  })

  // ── Queries ────────────────────────────────────────────────────────
  const peersQuery = useVpnPeers()
  const poolsQuery = useVpnIpPools()
  const statusQuery = useVpnStatus(30000)
  const peerConfigQuery = useVpnPeerConfig(configPeer?.id ?? null)
  const fetchPeerQrCode = useVpnPeerQrCode()
  const peerConfig = peerConfigQuery.data ?? null

  // ── Peer mutations ─────────────────────────────────────────────────
  const createPeer = useCreateVpnPeer()
  const updatePeer = useUpdateVpnPeer()
  const deletePeer = useDeleteVpnPeer()
  const enablePeer = useEnableVpnPeer()
  const disablePeer = useDisableVpnPeer()
  const rotatePeer = useRotateVpnPeerKeys()

  // ── IP Pool mutation ───────────────────────────────────────────────
  const createPool = useCreateVpnIpPool()

  // ── Peer modal helpers ─────────────────────────────────────────────
  function openCreatePeer() {
    setEditingPeer(null)
    setPeerForm({ name: '', peer_type: 'client', persistent_keepalive: 25 })
    setShowPeerModal(true)
  }

  function openEditPeer(peer: VpnPeer) {
    setEditingPeer(peer)
    setPeerForm({
      name: peer.name,
      peer_type: peer.peer_type as VpnPeerCreate['peer_type'],
      allowed_ips: peer.allowed_ips || undefined,
      dns: peer.dns || undefined,
      persistent_keepalive: peer.persistent_keepalive,
      expires_at: peer.expires_at || undefined,
    })
    setShowPeerModal(true)
  }

  function closePeerModal() {
    setShowPeerModal(false)
    setEditingPeer(null)
  }

  function submitPeer() {
    if (editingPeer) {
      const data: VpnPeerUpdate = {}
      if (peerForm.name !== editingPeer.name) data.name = peerForm.name
      if (peerForm.allowed_ips !== (editingPeer.allowed_ips || undefined))
        data.allowed_ips = peerForm.allowed_ips ?? null
      if (peerForm.dns !== (editingPeer.dns || undefined))
        data.dns = peerForm.dns ?? null
      if (peerForm.persistent_keepalive !== editingPeer.persistent_keepalive)
        data.persistent_keepalive = peerForm.persistent_keepalive
      if (peerForm.expires_at !== (editingPeer.expires_at || undefined))
        data.expires_at = peerForm.expires_at ?? null
      updatePeer.mutate(
        { id: editingPeer.id, data },
        {
          onSuccess: () => closePeerModal(),
          onError: peerErrHandler,
        }
      )
    } else {
      createPeer.mutate(peerForm, {
        onSuccess: () => closePeerModal(),
        onError: peerErrHandler,
      })
    }
  }

  // ── Config / QR helpers ────────────────────────────────────────────
  function openConfigModal(peer: VpnPeer) {
    setConfigPeer(peer)
    setConfigTab('config')
    setQrBlobUrl(null)
    fetchPeerQrCode.mutate(peer.id, {
      onSuccess: (qrBlob) => setQrBlobUrl(URL.createObjectURL(qrBlob)),
    })
  }

  function closeConfigModal() {
    if (qrBlobUrl) URL.revokeObjectURL(qrBlobUrl)
    setConfigPeer(null)
    setQrBlobUrl(null)
  }

  function copyConfig() {
    if (peerConfig) navigator.clipboard.writeText(peerConfig.config_text)
  }

  function downloadConfig() {
    if (!peerConfig) return
    const blob = new Blob([peerConfig.config_text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = peerConfig.filename
    a.click()
    URL.revokeObjectURL(url)
  }

  // Cleanup QR blob on unmount
  useEffect(() => {
    return () => {
      if (qrBlobUrl) URL.revokeObjectURL(qrBlobUrl)
    }
  }, [qrBlobUrl])

  // ── Tab content ────────────────────────────────────────────────────
  const tabs: { key: TabKey; label: string; icon: typeof Network }[] = [
    { key: 'peers', label: 'Peers', icon: Wifi },
    { key: 'pools', label: 'IP Pools', icon: Network },
    { key: 'status', label: 'Statut serveur', icon: Server },
  ]

  const peers = peersQuery.data?.items ?? []
  const pools = poolsQuery.data?.items ?? []
  const status = statusQuery.data

  return (
    <div className="space-y-6">
      <PageHeader
        title="VPN WireGuard"
        subtitle="Gestion des peers, pools IP et statut du serveur VPN"
        breadcrumbs={[
          { label: 'Admin', href: '/admin/users' },
          { label: 'VPN' },
        ]}
      />

      {/* Tabs */}
      <div className="border-b border-dark-600">
        <nav className="flex gap-4">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.key
                    ? 'border-primary-500 text-primary-400'
                    : 'border-transparent text-dark-400 hover:text-dark-200'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            )
          })}
        </nav>
      </div>

      <ActionError message={peerError} onDismiss={() => setPeerError(null)} />

      {/* ── Peers Tab ──────────────────────────────────────────────── */}
      {activeTab === 'peers' && (
        peersQuery.error ? (
          <ErrorState onRetry={() => peersQuery.refetch()} />
        ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-dark-400">
              {peers.length} peer{peers.length !== 1 ? 's' : ''} configuré{peers.length !== 1 ? 's' : ''}
            </p>
            <Button onClick={openCreatePeer} size="sm">
              <Plus className="w-4 h-4 mr-1" />
              Nouveau peer
            </Button>
          </div>

          <div className="card p-0 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-dark-600">
                  <th className="px-4 py-4 text-left text-xs font-medium text-dark-400 uppercase">Nom</th>
                  <th className="px-4 py-4 text-left text-xs font-medium text-dark-400 uppercase">Type</th>
                  <th className="px-4 py-4 text-left text-xs font-medium text-dark-400 uppercase">IP</th>
                  <th className="px-4 py-4 text-left text-xs font-medium text-dark-400 uppercase">Statut</th>
                  <th className="px-4 py-4 text-left text-xs font-medium text-dark-400 uppercase">Clé publique</th>
                  <th className="px-4 py-4 text-left text-xs font-medium text-dark-400 uppercase">Expiration</th>
                  <th className="px-4 py-4 text-right text-xs font-medium text-dark-400 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-600">
                {peers.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-dark-400">
                      Aucun peer VPN configuré
                    </td>
                  </tr>
                ) : (
                  peers.map((peer) => (
                    <tr key={peer.id} className="hover:bg-dark-750">
                      <td className="px-4 py-4">
                        <span className="text-sm font-medium">{peer.name}</span>
                      </td>
                      <td className="px-4 py-4">
                        <Badge variant="info" size="sm">{peer.peer_type}</Badge>
                      </td>
                      <td className="px-4 py-4">
                        <span className="text-sm text-dark-300 font-mono">
                          {peer.assigned_ip || '—'}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        {peer.is_enabled ? (
                          <Badge variant="success" size="sm" dot>Actif</Badge>
                        ) : (
                          <Badge variant="default" size="sm" dot>Désactivé</Badge>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        <span className="text-xs text-dark-400 font-mono">
                          {peer.public_key.slice(0, 12)}...
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <span className="text-sm text-dark-400">
                          {peer.expires_at
                            ? new Date(peer.expires_at).toLocaleDateString('fr-FR')
                            : '—'}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => openConfigModal(peer)}
                            className="p-1.5 min-h-[44px] min-w-[44px] flex items-center justify-center text-dark-400 hover:text-dark-50 rounded transition-colors"
                            title="Configuration"
                          >
                            <FileText className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => openEditPeer(peer)}
                            className="p-1.5 min-h-[44px] min-w-[44px] flex items-center justify-center text-dark-400 hover:text-dark-50 rounded transition-colors"
                            title="Modifier"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          {peer.is_enabled ? (
                            <button
                              onClick={() =>
                                disablePeer.mutate(peer.id, { onError: peerErrHandler })
                              }
                              className="p-1.5 min-h-[44px] min-w-[44px] flex items-center justify-center text-dark-400 hover:text-yellow-400 rounded transition-colors"
                              title="Désactiver"
                            >
                              <ShieldOff className="w-4 h-4" />
                            </button>
                          ) : (
                            <button
                              onClick={() =>
                                enablePeer.mutate(peer.id, { onError: peerErrHandler })
                              }
                              className="p-1.5 min-h-[44px] min-w-[44px] flex items-center justify-center text-dark-400 hover:text-green-400 rounded transition-colors"
                              title="Activer"
                            >
                              <Shield className="w-4 h-4" />
                            </button>
                          )}
                          <button
                            onClick={() => setConfirmRotate(peer)}
                            className="p-1.5 min-h-[44px] min-w-[44px] flex items-center justify-center text-dark-400 hover:text-orange-400 rounded transition-colors"
                            title="Rotation des clés"
                          >
                            <RotateCcw className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setConfirmDelete(peer)}
                            className="p-1.5 min-h-[44px] min-w-[44px] flex items-center justify-center text-dark-400 hover:text-red-400 rounded transition-colors"
                            title="Supprimer"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
        )
      )}

      {/* ── IP Pools Tab ───────────────────────────────────────────── */}
      {activeTab === 'pools' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-dark-400">
              {pools.length} pool{pools.length !== 1 ? 's' : ''} IP
            </p>
            <Button onClick={() => setShowPoolModal(true)} size="sm">
              <Plus className="w-4 h-4 mr-1" />
              Nouveau pool
            </Button>
          </div>

          <div className="card p-0 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-dark-600">
                  <th className="px-4 py-4 text-left text-xs font-medium text-dark-400 uppercase">Sous-réseau</th>
                  <th className="px-4 py-4 text-left text-xs font-medium text-dark-400 uppercase">Passerelle</th>
                  <th className="px-4 py-4 text-left text-xs font-medium text-dark-400 uppercase">Prochaine IP</th>
                  <th className="px-4 py-4 text-left text-xs font-medium text-dark-400 uppercase">Masque</th>
                  <th className="px-4 py-4 text-left text-xs font-medium text-dark-400 uppercase">Description</th>
                  <th className="px-4 py-4 text-left text-xs font-medium text-dark-400 uppercase">Créé le</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-600">
                {pools.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-dark-400">
                      Aucun pool IP configuré
                    </td>
                  </tr>
                ) : (
                  pools.map((pool) => (
                    <tr key={pool.id} className="hover:bg-dark-750">
                      <td className="px-4 py-4">
                        <span className="text-sm font-mono">{pool.subnet}</span>
                      </td>
                      <td className="px-4 py-4">
                        <span className="text-sm font-mono text-dark-300">{pool.gateway_ip}</span>
                      </td>
                      <td className="px-4 py-4">
                        <span className="text-sm font-mono text-dark-300">{pool.next_ip}</span>
                      </td>
                      <td className="px-4 py-4">
                        <span className="text-sm text-dark-400">/{pool.subnet_mask}</span>
                      </td>
                      <td className="px-4 py-4">
                        <span className="text-sm text-dark-400">{pool.description || '—'}</span>
                      </td>
                      <td className="px-4 py-4">
                        <span className="text-sm text-dark-400">
                          {new Date(pool.created_at).toLocaleDateString('fr-FR')}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Status Tab ─────────────────────────────────────────────── */}
      {activeTab === 'status' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-dark-400">
              Actualisation automatique toutes les 30 secondes
            </p>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => statusQuery.refetch()}
              loading={statusQuery.isFetching}
            >
              <RefreshCw className="w-4 h-4 mr-1" />
              Actualiser
            </Button>
          </div>

          {!status ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-pulse">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="card p-4 space-y-4">
                  <div className="flex items-center gap-4">
                    <div className="w-3 h-3 rounded-full skel" />
                    <div className="h-3 skel rounded w-20" />
                  </div>
                  <div className="h-7 skel rounded w-16" />
                </div>
              ))}
            </div>
          ) : (
            <>
              {/* Server info card */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="card p-4">
                  <div className="flex items-center gap-4 mb-2">
                    <div className={`w-3 h-3 rounded-full ${status.backend_available ? 'bg-green-500' : 'bg-red-500'}`} />
                    <span className="text-sm font-medium">Backend</span>
                  </div>
                  <p className="text-sm text-dark-400">
                    {status.backend_available ? 'Connecté' : 'Indisponible'}
                  </p>
                </div>
                <div className="card p-4">
                  <div className="flex items-center gap-4 mb-2">
                    <Server className="w-4 h-4 text-primary-400" />
                    <span className="text-sm font-medium">Interface</span>
                  </div>
                  <p className="text-sm text-dark-400 font-mono">{status.interface}</p>
                </div>
                <div className="card p-4">
                  <div className="flex items-center gap-4 mb-2">
                    <Wifi className="w-4 h-4 text-primary-400" />
                    <span className="text-sm font-medium">Peers actifs</span>
                  </div>
                  <p className="text-2xl font-bold">{status.active_peers_count}</p>
                </div>
              </div>

              {/* Realtime peer status */}
              {status.peers.length > 0 && (
                <div className="card p-0 overflow-hidden">
                  <div className="px-4 py-4 border-b border-dark-600">
                    <h3 className="text-sm font-medium">Statut temps réel des peers</h3>
                  </div>
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-dark-600">
                        <th className="px-4 py-2 text-left text-xs font-medium text-dark-400 uppercase">Clé publique</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-dark-400 uppercase">Endpoint</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-dark-400 uppercase">Dernier handshake</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-dark-400 uppercase">RX</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-dark-400 uppercase">TX</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-dark-600">
                      {status.peers.map((p) => (
                        <tr key={p.public_key} className="hover:bg-dark-750">
                          <td className="px-4 py-2">
                            <span className="text-xs font-mono text-dark-300">
                              {p.public_key.slice(0, 16)}...
                            </span>
                          </td>
                          <td className="px-4 py-2">
                            <span className="text-xs font-mono text-dark-400">
                              {p.endpoint || '—'}
                            </span>
                          </td>
                          <td className="px-4 py-2">
                            <span className="text-xs text-dark-400">
                              {formatHandshake(p.latest_handshake)}
                            </span>
                          </td>
                          <td className="px-4 py-2">
                            <span className="text-xs text-dark-400">{formatBytes(p.transfer_rx)}</span>
                          </td>
                          <td className="px-4 py-2">
                            <span className="text-xs text-dark-400">{formatBytes(p.transfer_tx)}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Create/Edit Peer Modal ─────────────────────────────────── */}
      <Modal
        isOpen={showPeerModal}
        onClose={closePeerModal}
        title={editingPeer ? 'Modifier le peer' : 'Nouveau peer VPN'}
        size="md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-dark-400 mb-1">Nom</label>
            <input
              type="text"
              value={peerForm.name}
              onChange={(e) => setPeerForm({ ...peerForm, name: e.target.value })}
              className="input"
              placeholder="mon-peer-vpn"
            />
          </div>

          {!editingPeer && (
            <div>
              <label className="block text-sm text-dark-400 mb-1">Type</label>
              <select
                value={peerForm.peer_type}
                onChange={(e) =>
                  setPeerForm({ ...peerForm, peer_type: e.target.value as VpnPeerCreate['peer_type'] })
                }
                className="input"
              >
                {PEER_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="block text-sm text-dark-400 mb-1">
              Allowed IPs <span className="text-dark-500">(optionnel)</span>
            </label>
            <input
              type="text"
              value={peerForm.allowed_ips ?? ''}
              onChange={(e) =>
                setPeerForm({ ...peerForm, allowed_ips: e.target.value || undefined })
              }
              className="input"
              placeholder="0.0.0.0/0"
            />
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">
              DNS <span className="text-dark-500">(optionnel)</span>
            </label>
            <input
              type="text"
              value={peerForm.dns ?? ''}
              onChange={(e) =>
                setPeerForm({ ...peerForm, dns: e.target.value || undefined })
              }
              className="input"
              placeholder="1.1.1.1, 8.8.8.8"
            />
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">
              Persistent Keepalive (s)
            </label>
            <input
              type="number"
              min={0}
              max={300}
              value={peerForm.persistent_keepalive ?? 25}
              onChange={(e) =>
                setPeerForm({ ...peerForm, persistent_keepalive: parseInt(e.target.value) || 0 })
              }
              className="input"
            />
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">
              Expiration <span className="text-dark-500">(optionnel)</span>
            </label>
            <input
              type="datetime-local"
              value={peerForm.expires_at ? peerForm.expires_at.slice(0, 16) : ''}
              onChange={(e) =>
                setPeerForm({
                  ...peerForm,
                  expires_at: e.target.value ? new Date(e.target.value).toISOString() : undefined,
                })
              }
              className="input"
            />
          </div>
        </div>
        <ModalFooter
          onCancel={closePeerModal}
          onConfirm={submitPeer}
          confirmText={editingPeer ? 'Enregistrer' : 'Créer'}
          loading={createPeer.isPending || updatePeer.isPending}
        />
      </Modal>

      {/* ── Config / QR Modal ──────────────────────────────────────── */}
      <Modal
        isOpen={!!configPeer}
        onClose={closeConfigModal}
        title={`Configuration — ${configPeer?.name ?? ''}`}
        size="lg"
      >
        <div className="space-y-4">
          {/* Config/QR tabs */}
          <div className="flex gap-2">
            <button
              onClick={() => setConfigTab('config')}
              className={`flex items-center gap-1.5 px-4 py-1.5 text-sm rounded-lg transition-colors ${
                configTab === 'config'
                  ? 'bg-primary-600 text-white'
                  : 'btn-ghost'
              }`}
            >
              <FileText className="w-4 h-4" />
              Configuration
            </button>
            <button
              onClick={() => setConfigTab('qr')}
              className={`flex items-center gap-1.5 px-4 py-1.5 text-sm rounded-lg transition-colors ${
                configTab === 'qr'
                  ? 'bg-primary-600 text-white'
                  : 'btn-ghost'
              }`}
            >
              <QrCode className="w-4 h-4" />
              QR Code
            </button>
          </div>

          {configTab === 'config' && (
            <>
              {peerConfig ? (
                <div className="relative">
                  <pre className="card p-4 text-xs text-green-400 font-mono overflow-x-auto max-h-80">
                    {peerConfig.config_text}
                  </pre>
                  <div className="flex gap-2 mt-4">
                    <Button variant="secondary" size="sm" onClick={copyConfig}>
                      <Copy className="w-4 h-4 mr-1" />
                      Copier
                    </Button>
                    <Button variant="secondary" size="sm" onClick={downloadConfig}>
                      <Download className="w-4 h-4 mr-1" />
                      {peerConfig.filename}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="animate-pulse divide-y divide-dark-600">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="flex items-center gap-4 px-4 py-4">
                      <div className="w-2 h-2 rounded-full skel" />
                      <div className="flex-1 space-y-2">
                        <div className="h-3 skel rounded w-32" />
                        <div className="h-2 skel rounded w-48" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {configTab === 'qr' && (
            <div className="flex flex-col items-center py-4">
              {qrBlobUrl ? (
                <img
                  src={qrBlobUrl}
                  alt="QR Code WireGuard"
                  loading="lazy"
                  className="w-64 h-64 rounded-lg border border-dark-600"
                />
              ) : (
                <div className="w-64 h-64 skel rounded-lg animate-pulse" />
              )}
              <p className="text-xs text-dark-500 mt-4">
                Scannez avec l'app WireGuard sur mobile
              </p>
            </div>
          )}
        </div>
      </Modal>

      {/* ── Create IP Pool Modal ───────────────────────────────────── */}
      <Modal
        isOpen={showPoolModal}
        onClose={() => setShowPoolModal(false)}
        title="Nouveau pool IP"
        size="sm"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-dark-400 mb-1">Sous-réseau (CIDR)</label>
            <input
              type="text"
              value={poolForm.subnet}
              onChange={(e) => setPoolForm({ ...poolForm, subnet: e.target.value })}
              className="input"
              placeholder="10.0.0.0/24"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">IP Passerelle</label>
            <input
              type="text"
              value={poolForm.gateway_ip}
              onChange={(e) => setPoolForm({ ...poolForm, gateway_ip: e.target.value })}
              className="input"
              placeholder="10.0.0.1"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">
              Description <span className="text-dark-500">(optionnel)</span>
            </label>
            <input
              type="text"
              value={poolForm.description ?? ''}
              onChange={(e) =>
                setPoolForm({ ...poolForm, description: e.target.value || undefined })
              }
              className="input"
              placeholder="Pool principal"
            />
          </div>
        </div>
        <ActionError message={poolError} onDismiss={() => setPoolError(null)} />
        <ModalFooter
          onCancel={() => setShowPoolModal(false)}
          onConfirm={() =>
            createPool.mutate(poolForm, {
              onSuccess: () => {
                setShowPoolModal(false)
                setPoolForm({ subnet: '', gateway_ip: '' })
                setPoolError(null)
              },
              onError: (err: unknown) =>
                setPoolError(normalizeError(err).message || 'Une erreur est survenue'),
            })
          }
          confirmText="Créer"
          loading={createPool.isPending}
        />
      </Modal>

      {/* ── Confirm dialogs ────────────────────────────────────────── */}
      <DeleteConfirm
        isOpen={!!confirmDelete}
        onClose={() => setConfirmDelete(null)}
        onConfirm={() =>
          confirmDelete &&
          deletePeer.mutate(confirmDelete.id, {
            onSuccess: () => setConfirmDelete(null),
            onError: peerErrHandler,
          })
        }
        itemName={confirmDelete?.name}
        loading={deletePeer.isPending}
      />

      <ConfirmDialog
        isOpen={!!confirmRotate}
        onClose={() => setConfirmRotate(null)}
        onConfirm={() =>
          confirmRotate &&
          rotatePeer.mutate(confirmRotate.id, {
            onSuccess: () => setConfirmRotate(null),
            onError: peerErrHandler,
          })
        }
        variant="warning"
        title="Rotation des clés ?"
        description={`La rotation des clés du peer "${confirmRotate?.name}" invalidera la configuration actuelle. Le peer devra être reconfiguré.`}
        confirmText="Tourner les clés"
        loading={rotatePeer.isPending}
      />
    </div>
  )
}
