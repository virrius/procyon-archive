/* Слои поверх экрана: окна, просмотр фото, выпадающие списки.
   Escape закрывает только верхний — иначе одно нажатие в выпадашке схлопывает и окно под ней. */

import { useEffect, useRef } from 'react'

type Layer = { order: number; close: () => void }

const stack: Layer[] = []
let seq = 0

// слушатель вешается раньше любого экрана: доска и прочие подписчики на Escape
// нажатие, закрывшее слой, уже не получают
window.addEventListener('keydown', e => {
  if (e.key !== 'Escape' || !stack.length) return
  e.stopImmediatePropagation()
  stack[stack.length - 1].close()
})

/** Слой, который снимается Escape, пока open. Порядок — по рендеру: окно,
 *  открытое разом с вложенным, всё равно остаётся под ним. */
export function useLayer(open: boolean, close: () => void) {
  const fn = useRef(close)
  fn.current = close
  const order = useRef(0)
  if (!open) order.current = 0
  else if (!order.current) order.current = ++seq

  useEffect(() => {
    if (!open) return
    const me: Layer = { order: order.current, close: () => fn.current() }
    const at = stack.findIndex(l => l.order > me.order)
    if (at < 0) stack.push(me)
    else stack.splice(at, 0, me)
    return () => {
      const i = stack.indexOf(me)
      if (i >= 0) stack.splice(i, 1)
    }
  }, [open])
}
