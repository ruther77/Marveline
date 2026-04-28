import { useRef } from 'react'
import ReactSignatureCanvas from 'react-signature-canvas'
import { Button } from './Button'

export interface SignaturePadProps {
  onSign: (dataUrl: string) => void
  onClear?: () => void
  readOnly?: boolean
  label?: string
}

export function SignaturePad({ onSign, onClear, readOnly = false, label }: SignaturePadProps) {
  const ref = useRef<ReactSignatureCanvas>(null)

  function handleEnd() {
    if (ref.current && !ref.current.isEmpty()) {
      onSign(ref.current.toDataURL('image/png'))
    }
  }

  function handleClear() {
    ref.current?.clear()
    onClear?.()
  }

  return (
    <div className="flex flex-col gap-2">
      {label && <label className="text-sm font-medium text-dark-200">{label}</label>}
      <div className="rounded-lg border border-dark-600 bg-white overflow-hidden">
        <ReactSignatureCanvas
          ref={ref}
          penColor="#1a1a2e"
          canvasProps={{ className: 'w-full h-40', style: { touchAction: 'none' } }}
          onEnd={handleEnd}
        />
      </div>
      {!readOnly && (
        <Button variant="ghost" size="sm" onClick={handleClear} type="button">
          Effacer la signature
        </Button>
      )}
    </div>
  )
}
