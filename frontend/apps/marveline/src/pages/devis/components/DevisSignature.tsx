import { CheckCircle } from 'lucide-react'
import { SignaturePad } from '@shared/components/ui/SignaturePad'
import { formatDate } from '@/lib/utils'

interface DevisSignatureProps {
  status: string
  signedAt?: string
  onSign: (dataUrl: string) => void
}

export function DevisSignature({ status, signedAt, onSign }: DevisSignatureProps) {
  if (signedAt) {
    return (
      <div className="card flex items-center gap-4 bg-green-900/10 border-green-700/40">
        <CheckCircle className="w-4 h-4 text-green-400 shrink-0" />
        <span className="text-green-400 text-sm">
          Signé électroniquement le {formatDate(signedAt)}
        </span>
      </div>
    )
  }

  if (status === 'sent') {
    return (
      <div className="card space-y-4">
        <h2 className="font-medium text-sm">Signature électronique</h2>
        <SignaturePad label="Signer le devis" onSign={onSign} />
      </div>
    )
  }

  return null
}
