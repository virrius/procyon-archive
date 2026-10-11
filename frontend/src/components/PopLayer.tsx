/* Слой выпадающих меню: портал в body и фиксированные координаты.
   В потоке страницы такое меню режут прокручиваемая колонка и стековые контексты карточек. */

import { useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { useLayer } from '../layers'

const GAP = 4
const EDGE = 8

export type PopLayerProps = {
  anchor: RefObject<HTMLElement | null>
  popRef?: { current: HTMLDivElement | null }
  className?: string
  /** середина меню под серединой кнопки */
  center?: boolean
  role?: string
  /** закрыть меню по Escape: слой верхний, окно под ним остаётся */
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
      /* ширину кнопки отдаём в CSS — сам минимум задаёт стиль конкретного меню */
      const w = a.width
      setBox(o => (o && o.left === left && o.top === top && o.w === w ? o : { left, top, w }))
    }
    place()
    /* размер меню меняется на лету — у «выбранным» разворачивается список участников */
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
