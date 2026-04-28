/**
 * ImageWithLoading — Progressive image loading (MID → HIGH fidelity)
 *
 * LOW  = Skeleton (animate-pulse, handled by page-level skeleton)
 * MID  = Gray placeholder with image icon while <img> loads
 * HIGH = Real image visible
 *
 * Usage:
 *   <ImageWithLoading src={url} alt="Product" className="h-36 w-full" />
 */

import { useState, useCallback } from 'react'
import { cn } from '../../lib/utils'

export interface ImageWithLoadingProps {
  src: string | null | undefined
  alt: string
  className?: string
  placeholderClassName?: string
  objectFit?: 'cover' | 'contain' | 'fill'
}

export function ImageWithLoading({
  src,
  alt,
  className,
  placeholderClassName,
  objectFit = 'cover',
}: ImageWithLoadingProps) {
  const [loaded, setLoaded] = useState(false)
  const [errored, setErrored] = useState(false)

  const handleLoad = useCallback(() => setLoaded(true), [])
  const handleError = useCallback(() => setErrored(true), [])

  const showPlaceholder = !src || errored || !loaded

  return (
    <div className={cn('relative overflow-hidden bg-dark-800', className)}>
      {/* MID state: placeholder */}
      {showPlaceholder && (
        <div
          className={cn(
            'absolute inset-0 flex items-center justify-center transition-opacity duration-300',
            loaded && !errored ? 'opacity-0' : 'opacity-100',
            placeholderClassName,
          )}
        >
          <svg
            className="w-8 h-8 text-dark-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z"
            />
          </svg>
        </div>
      )}

      {/* HIGH state: real image */}
      {src && !errored && (
        <img
          src={src}
          alt={alt}
          onLoad={handleLoad}
          onError={handleError}
          loading="lazy"
          className={cn(
            'w-full h-full transition-opacity duration-300',
            objectFit === 'cover' && 'object-cover',
            objectFit === 'contain' && 'object-contain',
            objectFit === 'fill' && 'object-fill',
            loaded ? 'opacity-100' : 'opacity-0',
          )}
        />
      )}
    </div>
  )
}
