import { useEffect, useRef, useState } from 'react'
import { BrowserQRCodeReader } from '@zxing/browser'
import { QRCodeSVG } from 'qrcode.react'
import { Spinner } from './Spinner'

export interface QRScannerProps {
  onScan: (value: string) => void
  onError?: (err: Error) => void
  active: boolean
  mode: 'scan' | 'generate'
  generateValue?: string
}

export function QRScanner({ onScan, onError, active, mode, generateValue }: QRScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const readerRef = useRef<BrowserQRCodeReader | null>(null)
  const controlsRef = useRef<{ stop: () => void } | null>(null)
  const [scanning, setScanning] = useState(false)

  useEffect(() => {
    if (mode !== 'scan' || !active || !videoRef.current) return

    const reader = new BrowserQRCodeReader()
    readerRef.current = reader
    setScanning(true)

    reader
      .decodeFromConstraints({ video: { facingMode: 'environment' } }, videoRef.current, (result, err, controls) => {
        controlsRef.current = controls
        if (result) {
          onScan(result.getText())
          controls.stop()
          setScanning(false)
        }
        if (err && !(err.message?.includes('No MultiFormat'))) {
          onError?.(err as Error)
        }
      })
      .catch((err: Error) => {
        onError?.(err)
        setScanning(false)
      })

    return () => {
      controlsRef.current?.stop()
      setScanning(false)
    }
  }, [active, mode]) // eslint-disable-line react-hooks/exhaustive-deps

  if (mode === 'generate') {
    return (
      <div className="flex items-center justify-center p-4 bg-white rounded-lg">
        {generateValue ? (
          <QRCodeSVG value={generateValue} size={200} />
        ) : (
          <p className="text-dark-400 text-sm">Aucune valeur à encoder</p>
        )}
      </div>
    )
  }

  return (
    <div className="relative rounded-lg overflow-hidden bg-black aspect-square max-w-xs mx-auto">
      <video ref={videoRef} className="w-full h-full object-cover" />
      {scanning && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/40">
          <Spinner size="lg" />
        </div>
      )}
      {!active && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/60">
          <p className="text-dark-50 text-sm">Scanner inactif</p>
        </div>
      )}
    </div>
  )
}
