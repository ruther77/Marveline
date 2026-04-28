/**
 * RAF-based scroll velocity tracking.
 * Tracks scrollY, velocity (px/frame), and direction.
 * Works on iOS Safari (touchmove fallback for momentum scroll).
 */
import { useRef, useEffect, useCallback } from 'react'

export interface ScrollState {
  scrollY: number
  velocity: number
  direction: 'up' | 'down' | 'idle'
}

type ScrollCallback = (state: ScrollState) => void

export function useScrollVelocity(callback: ScrollCallback) {
  const lastY = useRef(0)
  const lastTime = useRef(0)
  const velocity = useRef(0)
  const rafId = useRef(0)
  const callbackRef = useRef(callback)
  callbackRef.current = callback

  // Touch tracking for iOS momentum
  const touchStartY = useRef(0)
  const touchLastY = useRef(0)
  const isTouching = useRef(false)

  const tick = useCallback(() => {
    const now = performance.now()
    const y = Math.max(0, window.scrollY)
    const dt = now - lastTime.current

    if (dt > 0 && lastTime.current > 0) {
      // Smooth velocity with EMA (exponential moving average)
      const rawVel = ((y - lastY.current) / dt) * 16 // normalize to ~px/frame at 60fps
      velocity.current = velocity.current * 0.7 + rawVel * 0.3
    }

    const dir: ScrollState['direction'] =
      Math.abs(velocity.current) < 0.3 ? 'idle' :
      velocity.current > 0 ? 'down' : 'up'

    callbackRef.current({ scrollY: y, velocity: velocity.current, direction: dir })

    lastY.current = y
    lastTime.current = now
  }, [])

  useEffect(() => {
    const onScroll = () => {
      cancelAnimationFrame(rafId.current)
      rafId.current = requestAnimationFrame(tick)
    }

    const onTouchStart = (e: TouchEvent) => {
      touchStartY.current = e.touches[0].clientY
      touchLastY.current = e.touches[0].clientY
      isTouching.current = true
    }

    const onTouchMove = (e: TouchEvent) => {
      if (!isTouching.current) return
      const currentY = e.touches[0].clientY
      const delta = touchLastY.current - currentY // positive = scrolling down
      touchLastY.current = currentY

      // During touch, update velocity from finger movement
      velocity.current = velocity.current * 0.6 + delta * 0.4

      const y = Math.max(0, window.scrollY)
      const dir: ScrollState['direction'] =
        Math.abs(velocity.current) < 0.3 ? 'idle' :
        velocity.current > 0 ? 'down' : 'up'

      callbackRef.current({ scrollY: y, velocity: velocity.current, direction: dir })
      lastY.current = y
      lastTime.current = performance.now()
    }

    const onTouchEnd = () => {
      isTouching.current = false
    }

    window.addEventListener('scroll', onScroll, { passive: true })
    document.addEventListener('touchstart', onTouchStart, { passive: true })
    document.addEventListener('touchmove', onTouchMove, { passive: true })
    document.addEventListener('touchend', onTouchEnd, { passive: true })

    // Initial tick
    lastTime.current = performance.now()
    lastY.current = window.scrollY
    tick()

    return () => {
      cancelAnimationFrame(rafId.current)
      window.removeEventListener('scroll', onScroll)
      document.removeEventListener('touchstart', onTouchStart)
      document.removeEventListener('touchmove', onTouchMove)
      document.removeEventListener('touchend', onTouchEnd)
    }
  }, [tick])
}
