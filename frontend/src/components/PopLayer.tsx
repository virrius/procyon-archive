/* Dropdown menu layer: a portal into body and fixed coordinates.
   In the page flow such a menu gets clipped by the scrolling column and the cards' stacking contexts. */

import { useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { useLayer } from '../layers'

const GAP = 4
const EDGE = 8

export type PopLayerProps = {
  anchor: RefObject<HTMLElement | null>
  popRef?: { current: HTMLDivElement | null }
  className?: string
  /** menu center under the button center */
  center?: boolean
  role?: string
  /** close the menu on Escape: the layer is on top, the window under it stays */
  onClose?: () => void
  children: ReactNode
}

export function PopLayer({
  anchor, popRef, className, center, role, onClose, children,
}: PopLayerProps) {
  const self = useRef<HTMLDivElement | null>(null)
  useLayer(!!onClose, () => onClose?.())
  const [box, setBox] = useState<{ left: number; top: number; w: number } | null>(null)

  useLayoutEffect(() => {
    const place = () => {
      const a = anchor.current?.getBoundingClientRect()
      const p = self.current?.getBoundingClientRect()
      if (!a || !p) return
      let left = center ? a.left + (a.width - p.width) / 2 : a.left
      if (left + p.width > window.innerWidth - EDGE || left < EDGE) {
        left = Math.max(EDGE, Math.min(left, window.innerWidth - EDGE - p.width))
      }
      let top = a.bottom + GAP
      if (top + p.height > window.innerHeight - EDGE) {
        top = a.top - GAP - p.height >= EDGE
          ? a.top - GAP - p.height
          : Math.max(EDGE, window.innerHeight - EDGE - p.height)
      }
      /* the button width goes to CSS: the menu's own style sets the minimum */
      const w = a.width
      setBox(o => (o && o.left === left && o.top === top && o.w === w ? o : { left, top, w }))
    }
    place()
    /* the menu size changes on the fly: "selected" expands the member list */
    const ro = new ResizeObserver(place)
    if (self.current) ro.observe(self.current)
    window.addEventListener('scroll', place, true)
    window.addEventListener('resize', place)
    return () => {
      ro.disconnect()
      window.removeEventListener('scroll', place, true)
      window.removeEventListener('resize', place)
    }
  }, [anchor, center])

  return createPortal(
    <div
      ref={el => { self.current = el; if (popRef) popRef.current = el }}
      className={className}
      role={role}
      style={{
        left: box ? box.left : 0,
        top: box ? box.top : 0,
        visibility: box ? undefined : 'hidden',
        ['--pop-w' as string]: `${box ? box.w : 0}px`,
      }}>
      {children}
    </div>,
    document.body,
  )
}

export default PopLayer
