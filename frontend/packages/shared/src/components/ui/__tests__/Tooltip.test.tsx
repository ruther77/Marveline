/**
 * Tests unitaires pour components/ui/Tooltip.tsx
 * Tooltip, InfoTooltip
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { Tooltip, InfoTooltip } from '../Tooltip'

// ─── Tooltip ──────────────────────────────────────────────────────────────────

describe('Tooltip - visible après délai', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('tooltip absent avant mouseEnter', () => {
    render(
      <Tooltip content="Info bulle">
        <button>Hover me</button>
      </Tooltip>
    )
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('tooltip visible après mouseEnter + délai (200ms)', () => {
    render(
      <Tooltip content="Info bulle">
        <button>Hover me</button>
      </Tooltip>
    )
    fireEvent.mouseEnter(screen.getByText('Hover me').closest('div')!)
    act(() => { vi.advanceTimersByTime(200) })
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    expect(screen.getByRole('tooltip')).toHaveTextContent('Info bulle')
  })

  it('tooltip masqué après mouseLeave', () => {
    render(
      <Tooltip content="Info bulle">
        <button>Hover me</button>
      </Tooltip>
    )
    const wrapper = screen.getByText('Hover me').closest('div')!
    fireEvent.mouseEnter(wrapper)
    act(() => { vi.advanceTimersByTime(200) })
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    fireEvent.mouseLeave(wrapper)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('disabled=true : tooltip ne s\'affiche jamais', () => {
    render(
      <Tooltip content="Info bulle" disabled>
        <button>Hover me</button>
      </Tooltip>
    )
    fireEvent.mouseEnter(screen.getByText('Hover me').closest('div')!)
    act(() => { vi.advanceTimersByTime(500) })
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('délai personnalisé delay=0 : tooltip visible immédiatement', () => {
    render(
      <Tooltip content="Rapide" delay={0}>
        <button>Hover</button>
      </Tooltip>
    )
    fireEvent.mouseEnter(screen.getByText('Hover').closest('div')!)
    act(() => { vi.advanceTimersByTime(0) })
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
  })

  it('tooltip via onFocus', () => {
    render(
      <Tooltip content="Focus tooltip">
        <button>Focus me</button>
      </Tooltip>
    )
    fireEvent.focus(screen.getByText('Focus me').closest('div')!)
    act(() => { vi.advanceTimersByTime(200) })
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
  })

  it('tooltip masqué via onBlur', () => {
    render(
      <Tooltip content="Focus tooltip">
        <button>Focus me</button>
      </Tooltip>
    )
    const wrapper = screen.getByText('Focus me').closest('div')!
    fireEvent.focus(wrapper)
    act(() => { vi.advanceTimersByTime(200) })
    fireEvent.blur(wrapper)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })
})

describe('Tooltip - positions', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  const positions = ['top', 'bottom', 'left', 'right'] as const

  for (const pos of positions) {
    it(`position ${pos} se rend`, () => {
      render(
        <Tooltip content={`Tooltip ${pos}`} position={pos}>
          <button>Hover</button>
        </Tooltip>
      )
      fireEvent.mouseEnter(screen.getByText('Hover').closest('div')!)
      act(() => { vi.advanceTimersByTime(200) })
      expect(screen.getByRole('tooltip')).toBeInTheDocument()
    })
  }
})

describe('Tooltip - content vide', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it('content vide : tooltip non affiché même après délai', () => {
    render(
      <Tooltip content="">
        <button>Hover</button>
      </Tooltip>
    )
    fireEvent.mouseEnter(screen.getByText('Hover').closest('div')!)
    act(() => { vi.advanceTimersByTime(200) })
    expect(screen.queryByRole('tooltip')).toBeNull()
  })
})

// ─── InfoTooltip ──────────────────────────────────────────────────────────────

describe('InfoTooltip', () => {
  it('rend une icône SVG (Info)', () => {
    const { container } = render(<InfoTooltip content="Information" />)
    expect(container.querySelector('svg')).not.toBeNull()
  })

  it('affiche le tooltip au hover', () => {
    vi.useFakeTimers()
    render(<InfoTooltip content="Aide contextuelle" />)
    const wrapper = document.querySelector('.relative.inline-flex')!
    fireEvent.mouseEnter(wrapper)
    act(() => { vi.advanceTimersByTime(200) })
    expect(screen.getByRole('tooltip')).toHaveTextContent('Aide contextuelle')
    vi.useRealTimers()
  })
})
