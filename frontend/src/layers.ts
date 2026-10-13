/* Overlay layers: modals, photo viewer, dropdowns.
   Escape closes only the top one — otherwise one press in a dropdown also closes the modal beneath. */

import { useEffect, useRef } from 'react'

type Layer = { order: number; close: () => void }

const stack: Layer[] = []
let seq = 0

// the listener is attached before any screen: the board and other Escape subscribers
// don't receive a press that already closed a layer
window.addEventListener('keydown', e => {
  if (e.key !== 'Escape' || !stack.length) return
  e.stopImmediatePropagation()
  stack[stack.length - 1].close()
})

/** A layer closed by Escape while open. Order follows render: a modal
 *  opened together with a nested one still stays beneath it. */
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
