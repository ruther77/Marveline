import type { InternalTransferRead } from '@/types/epicerie-v2'

export const DEFAULT_TRANSFER_TVA_PCT = 2000
export const RESTAURANT_TENANT_ID = 3

function pad(value: number, size: number): string {
  return String(value).padStart(size, '0')
}

function isSameLocalDay(left: Date, right: Date): boolean {
  return (
    left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate()
  )
}

export function getTransferReferencePrefix(date = new Date()): string {
  return `TRF-${date.getFullYear()}${pad(date.getMonth() + 1, 2)}${pad(date.getDate(), 2)}`
}

export function buildTransferReference(sequence: number, date = new Date()): string {
  return `${getTransferReferencePrefix(date)}-${pad(sequence, 3)}`
}

export function getNextTransferReference(
  transfers: Array<Pick<InternalTransferRead, 'reference' | 'created_at'>>,
  date = new Date(),
): string {
  const prefix = `${getTransferReferencePrefix(date)}-`
  let maxSequence = 0
  let sameDayCount = 0

  for (const transfer of transfers) {
    if (transfer.reference?.startsWith(prefix)) {
      const match = transfer.reference.match(/-(\d+)$/)
      const sequence = match ? Number(match[1]) : 0
      if (Number.isFinite(sequence)) {
        maxSequence = Math.max(maxSequence, sequence)
      }
      continue
    }

    if (isSameLocalDay(new Date(transfer.created_at), date)) {
      sameDayCount += 1
    }
  }

  return buildTransferReference(Math.max(maxSequence, sameDayCount) + 1, date)
}

export function getTransferTvaCts(
  totalHtCts: number,
  totalTtcCts?: number,
  tvaPct = DEFAULT_TRANSFER_TVA_PCT,
): number {
  if (typeof totalTtcCts === 'number') {
    return totalTtcCts - totalHtCts
  }
  return Math.round(totalHtCts * tvaPct / 10000)
}

export function getTransferTtcCts(totalHtCts: number, tvaPct = DEFAULT_TRANSFER_TVA_PCT): number {
  return totalHtCts + getTransferTvaCts(totalHtCts, undefined, tvaPct)
}

export function getTransferDisplayHtCts(transfer: Pick<InternalTransferRead, 'montant_ht' | 'lignes'>): number {
  return transfer.montant_ht || transfer.lignes.reduce((sum, line) => sum + line.montant_ht, 0)
}

export function getTransferDisplayTtcCts(transfer: Pick<InternalTransferRead, 'montant_ttc' | 'lignes'>): number {
  return transfer.montant_ttc || transfer.lignes.reduce((sum, line) => sum + line.montant_ttc, 0)
}
