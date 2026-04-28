/**
 * SwipeActions — iOS-native swipe physics.
 *
 * - Phase 1 (0-20px): initial resistance (60% follow)
 * - Phase 2 (20px → maxWidth): 1:1 follow
 * - Phase 3 (> maxWidth): rubber band (20% follow)
 * - Spring release with velocity
 * - Progressive action reveal with cascade
 * - Destructive full-swipe with height collapse
 * - Direction lock at 10px
 */
import { useRef, useEffect, useCallback, type ReactNode } from 'react'
import { cn } from '../../lib/utils'

export interface SwipeAction {
  icon: ReactNode
  label: string
  color: string
  onClick: () => void
  /** If true, full-swipe triggers action + height collapse animation */
  destructive?: boolean
}

export interface SwipeActionsProps {
  children: ReactNode
  actions?: SwipeAction[]
  rightActions?: SwipeAction[]
  leftActions?: SwipeAction[]
  actionWidth?: number
  className?: string
}

// Close previously opened card
let globalClose: (() => void) | null = null

// ── Physics helpers ─────────────────────────────────────────────────────────

/** 3-phase physical offset: resistance → follow → rubber band */
function getPhysicalOffset(dragX: number, maxWidth: number): number {
  const abs = Math.abs(dragX)
  const sign = Math.sign(dragX)
  if (abs < 20) return dragX * 0.6
  const base = 20 * 0.6 // 12px
  if (abs < maxWidth + 20) return sign * (base + (abs - 20))
  const overflow = abs - maxWidth - 20
  return sign * (base + maxWidth + overflow * 0.2)
}

/** Spring animation to target with initial velocity */
function springTo(
  el: HTMLElement,
  target: number,
  initialVelocity: number,
  stiffness: number,
  damping: number,
  onComplete?: () => void,
) {
  // Read current position from transform
  const matrix = new DOMMatrix(getComputedStyle(el).transform)
  let pos = -matrix.m41
  let vel = initialVelocity
  let lastTime = performance.now()
  let settled = false

  el.style.transition = 'none'

  function step(time: number) {
    if (settled) return
    const dt = Math.min((time - lastTime) / 1000, 0.032)
    lastTime = time

    const force = -stiffness * (pos - target)
    const dampForce = -damping * vel
    vel += (force + dampForce) * dt
    pos += vel * dt

    el.style.transform = `translateX(${-pos}px)`

    if (Math.abs(vel) < 0.5 && Math.abs(pos - target) < 0.5) {
      el.style.transform = `translateX(${-target}px)`
      settled = true
      onComplete?.()
    } else {
      requestAnimationFrame(step)
    }
  }
  requestAnimationFrame(step)

  return () => { settled = true }
}

/** Collapse height animation for destructive actions */
function collapseAndRemove(container: HTMLElement, callback: () => void) {
  // Flash
  container.style.background = '#ff3b30'

  setTimeout(() => {
    const height = container.offsetHeight
    container.style.overflow = 'hidden'
    container.style.height = `${height}px`
    container.style.transition = 'height 280ms cubic-bezier(0.4, 0, 1, 1), opacity 200ms ease-out'

    requestAnimationFrame(() => {
      container.style.height = '0'
      container.style.opacity = '0'
    })

    setTimeout(() => {
      callback()
    }, 290)
  }, 80)
}

// ── Component ───────────────────────────────────────────────────────────────

export function SwipeActions({
  children,
  actions,
  rightActions,
  leftActions,
  actionWidth = 84,
  className,
}: SwipeActionsProps) {
  const right = rightActions ?? actions ?? []
  const left = leftActions ?? []

  if (right.length === 0 && left.length === 0) {
    return <>{children}</>
  }

  const maxRight = right.length * actionWidth
  const maxLeft = left.length * actionWidth

  const containerRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const leftPanelRef = useRef<HTMLDivElement>(null)
  const rightPanelRef = useRef<HTMLDivElement>(null)
  const leftActionRefs = useRef<(HTMLButtonElement | null)[]>([])
  const rightActionRefs = useRef<(HTMLButtonElement | null)[]>([])

  const startX = useRef(0)
  const startY = useRef(0)
  const currentOffsetRef = useRef(0)
  const direction = useRef<'horizontal' | 'vertical' | null>(null)
  const isDragging = useRef(false)
  const didSwipe = useRef(false)
  const lastTouchX = useRef(0)
  const lastTouchTime = useRef(0)
  const velocityX = useRef(0)
  const cancelSpring = useRef<(() => void) | null>(null)

  const setOffset = useCallback((px: number) => {
    currentOffsetRef.current = px
    const el = contentRef.current
    if (!el) return
    el.style.transform = `translateX(${-px}px)`

    // Panel visibility
    if (leftPanelRef.current) {
      leftPanelRef.current.style.opacity = px < 0 ? '1' : '0'
      leftPanelRef.current.style.pointerEvents = px < 0 ? 'auto' : 'none'
    }
    if (rightPanelRef.current) {
      rightPanelRef.current.style.opacity = px > 0 ? '1' : '0'
      rightPanelRef.current.style.pointerEvents = px > 0 ? 'auto' : 'none'
    }

    // Progressive action reveal with cascade
    const absPx = Math.abs(px)
    const max = px > 0 ? maxRight : maxLeft
    const refs = px > 0 ? rightActionRefs : leftActionRefs
    if (max > 0) {
      const progress = Math.min(1, absPx / max)
      refs.current.forEach((btn, i) => {
        if (!btn) return
        const delay = i * 0.08
        const p = Math.max(0, Math.min(1, (progress - 0.15 - delay) / 0.35))
        btn.style.opacity = String(p)
        btn.style.transform = `scale(${0.6 + p * 0.4})`
      })
    }
  }, [maxRight, maxLeft])

  const close = useCallback(() => {
    cancelSpring.current?.()
    const el = contentRef.current
    if (!el) return
    cancelSpring.current = springTo(el, 0, 0, 500, 35)
    currentOffsetRef.current = 0
    // Reset action visibility
    ;[...leftActionRefs.current, ...rightActionRefs.current].forEach((btn) => {
      if (btn) { btn.style.opacity = '0'; btn.style.transform = 'scale(0.6)' }
    })
    if (leftPanelRef.current) { leftPanelRef.current.style.opacity = '0'; leftPanelRef.current.style.pointerEvents = 'none' }
    if (rightPanelRef.current) { rightPanelRef.current.style.opacity = '0'; rightPanelRef.current.style.pointerEvents = 'none' }
    if (globalClose === close) globalClose = null
  }, [])

  // Close when touching outside
  useEffect(() => {
    function onTouch(e: TouchEvent) {
      if (currentOffsetRef.current !== 0 && containerRef.current && !containerRef.current.contains(e.target as Node)) {
        close()
      }
    }
    document.addEventListener('touchstart', onTouch, { passive: true })
    return () => document.removeEventListener('touchstart', onTouch)
  }, [close])

  function onTouchStart(e: React.TouchEvent) {
    cancelSpring.current?.()
    if (globalClose && globalClose !== close) globalClose()
    startX.current = e.touches[0].clientX
    startY.current = e.touches[0].clientY
    lastTouchX.current = e.touches[0].clientX
    lastTouchTime.current = performance.now()
    velocityX.current = 0
    direction.current = null
    isDragging.current = false
    didSwipe.current = false
  }

  function onTouchMove(e: React.TouchEvent) {
    const touchX = e.touches[0].clientX
    const touchY = e.touches[0].clientY
    const dx = startX.current - touchX
    const dy = startY.current - touchY

    // Direction lock at 10px
    if (!direction.current) {
      const absDx = Math.abs(dx)
      const absDy = Math.abs(dy)
      if (absDx > 10 || absDy > 10) {
        direction.current = absDx > absDy ? 'horizontal' : 'vertical'
      }
    }

    if (direction.current !== 'horizontal') return

    isDragging.current = true
    didSwipe.current = true

    // Track velocity
    const now = performance.now()
    const dt = now - lastTouchTime.current
    if (dt > 0) {
      const rawVel = ((lastTouchX.current - touchX) / dt) * 1000 // px/s
      velocityX.current = velocityX.current * 0.6 + rawVel * 0.4
    }
    lastTouchX.current = touchX
    lastTouchTime.current = now

    // Apply physical offset
    const rawOffset = dx + currentOffsetRef.current
    const max = rawOffset > 0 ? maxRight : maxLeft
    const physical = getPhysicalOffset(rawOffset, max)

    const el = contentRef.current
    if (el) {
      el.style.transition = 'none'
      el.style.transform = `translateX(${-physical}px)`
    }

    // Update panels + action reveal
    const absPhy = Math.abs(physical)
    if (leftPanelRef.current) {
      leftPanelRef.current.style.opacity = physical < 0 ? '1' : '0'
    }
    if (rightPanelRef.current) {
      rightPanelRef.current.style.opacity = physical > 0 ? '1' : '0'
    }

    // Progressive action reveal
    const maxW = physical > 0 ? maxRight : maxLeft
    const refs = physical > 0 ? rightActionRefs : leftActionRefs
    if (maxW > 0) {
      const progress = Math.min(1, absPhy / maxW)
      refs.current.forEach((btn, i) => {
        if (!btn) return
        const delay = i * 0.08
        const p = Math.max(0, Math.min(1, (progress - 0.15 - delay) / 0.35))
        btn.style.opacity = String(p)
        btn.style.transform = `scale(${0.6 + p * 0.4})`
      })
    }
  }

  function onTouchEnd() {
    if (!isDragging.current) return
    isDragging.current = false

    const el = contentRef.current
    if (!el) return

    const matrix = new DOMMatrix(getComputedStyle(el).transform)
    const current = -matrix.m41

    // Determine snap target with 3 levels
    const vel = velocityX.current
    let snapped = 0
    let stiffness = 500
    let damping = 35

    if (current > 0) {
      // Swiped left → right actions
      const confirmThreshold = maxRight * 0.6
      if (current > confirmThreshold || vel > 800) {
        // Full swipe confirm — check for destructive action
        const destructiveAction = right.find((a) => a.destructive)
        if (destructiveAction && containerRef.current) {
          // Collapse + trigger
          collapseAndRemove(containerRef.current, destructiveAction.onClick)
          return
        }
        snapped = maxRight; stiffness = 600; damping = 30
      } else if (current > maxRight * 0.3 || vel > 300) {
        snapped = maxRight; stiffness = 300; damping = 22 // reveal with overshoot
      } else {
        snapped = 0; stiffness = 500; damping = 35 // snap back
      }
    } else if (current < 0) {
      // Swiped right → left actions
      const confirmThreshold = maxLeft * 0.6
      if (current < -confirmThreshold || vel < -800) {
        const destructiveAction = left.find((a) => a.destructive)
        if (destructiveAction && containerRef.current) {
          collapseAndRemove(containerRef.current, destructiveAction.onClick)
          return
        }
        snapped = -maxLeft; stiffness = 600; damping = 30
      } else if (current < -maxLeft * 0.3 || vel < -300) {
        snapped = -maxLeft; stiffness = 300; damping = 22
      } else {
        snapped = 0; stiffness = 500; damping = 35
      }
    }

    cancelSpring.current = springTo(el, snapped, vel * 0.001, stiffness, damping, () => {
      currentOffsetRef.current = snapped
      // Update panel visibility after spring settles
      if (leftPanelRef.current) {
        leftPanelRef.current.style.pointerEvents = snapped < 0 ? 'auto' : 'none'
      }
      if (rightPanelRef.current) {
        rightPanelRef.current.style.pointerEvents = snapped > 0 ? 'auto' : 'none'
      }
    })

    if (snapped !== 0) {
      globalClose = close
    } else if (globalClose === close) {
      globalClose = null
    }
  }

  function onClickCapture(e: React.MouseEvent) {
    if (didSwipe.current) {
      didSwipe.current = false
      e.stopPropagation()
      e.preventDefault()
    }
    if (currentOffsetRef.current !== 0) {
      e.stopPropagation()
      e.preventDefault()
      close()
    }
  }

  const renderAction = (action: SwipeAction, index: number, side: 'left' | 'right') => (
    <button
      key={index}
      ref={(el) => {
        if (side === 'left') leftActionRefs.current[index] = el
        else rightActionRefs.current[index] = el
      }}
      type="button"
      className={cn(
        'flex flex-col items-center justify-center gap-1',
        'text-white text-[11px] font-semibold',
        'active:brightness-110 transition-colors',
        action.color,
      )}
      style={{ width: actionWidth, opacity: 0, transform: 'scale(0.6)' }}
      onClick={(e) => {
        e.stopPropagation()
        if (action.destructive && containerRef.current) {
          collapseAndRemove(containerRef.current, action.onClick)
        } else {
          action.onClick()
          close()
        }
      }}
      aria-label={action.label}
    >
      <span className="w-10 h-10 flex items-center justify-center rounded-xl bg-white/20">
        {action.icon}
      </span>
      <span className="leading-none">{action.label}</span>
    </button>
  )

  return (
    <div ref={containerRef} className={cn('relative overflow-hidden', className)}>
      {/* Left actions (swipe right to reveal) */}
      {left.length > 0 && (
        <div
          ref={leftPanelRef}
          className="absolute inset-y-0 left-0 flex items-stretch"
          style={{ width: maxLeft, opacity: 0, pointerEvents: 'none' }}
        >
          {left.map((action, i) => renderAction(action, i, 'left'))}
        </div>
      )}

      {/* Right actions (swipe left to reveal) */}
      {right.length > 0 && (
        <div
          ref={rightPanelRef}
          className="absolute inset-y-0 right-0 flex items-stretch"
          style={{ width: maxRight, opacity: 0, pointerEvents: 'none' }}
        >
          {right.map((action, i) => renderAction(action, i, 'right'))}
        </div>
      )}

      {/* Content */}
      <div
        ref={contentRef}
        className="relative z-10 bg-[var(--s1)]"
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
        onClickCapture={onClickCapture}
      >
        {children}
      </div>
    </div>
  )
}
