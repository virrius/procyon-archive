import { useEffect, useLayoutEffect, useRef } from 'react'
import { lang } from '../i18n'

const LATIN = 'ABCDEFGHJKLMNPQRSTUVWXYZ0123456789#$%&*+=<>/\\|'
// Cyrillic in the noise only for the Russian interface
const glyphs = () => (lang() === 'ru' ? LATIN + 'БГДЖЗИЛПФЦЧШЩЭЮЯ' : LATIN)
const FRAME_MS = 45

const noise = (text: string, from: number) => {
  const GLYPHS = glyphs()
  let s = text.slice(0, from)
  for (let i = from; i < text.length; i++) {
    const ch = text[i]
    s += /\s/.test(ch) ? ch : GLYPHS[(Math.random() * GLYPHS.length) | 0]
  }
  return s
}

const reduced = () => {
  try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches } catch { return false }
}

/** The text "prints out": until it's on screen it's masked with symbols; on screen it flickers and shows
    left to right. Spaces and line breaks stay in place, so lines don't jump. */
export function MatrixText({ text, className, as: Tag = 'span', off = false }: {
  text: string
  /** no effect: the finished text right away */
  off?: boolean
  className?: string
  as?: 'span' | 'div' | 'h2' | 'p'
}) {
  const ref = useRef<HTMLElement>(null)

  useLayoutEffect(() => {
    if (ref.current) ref.current.textContent = off || reduced() ? text : noise(text, 0)
  }, [text, off])

  useEffect(() => {
    const el = ref.current
    if (!el || off || reduced()) return
    let raf = 0
    let t0 = 0
    let last = 0
    const dur = Math.min(2000, Math.max(600, text.length * 4))
    const tick = (t: number) => {
      if (!t0) t0 = t
      const p = Math.min(1, (t - t0) / dur)
      if (p === 1) { el.textContent = text; return }
      if (t - last >= FRAME_MS) { last = t; el.textContent = noise(text, Math.floor(text.length * p)) }
      raf = requestAnimationFrame(tick)
    }
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return
      io.disconnect()
      raf = requestAnimationFrame(tick)
    }, { threshold: 0.1 })
    io.observe(el)
    return () => { io.disconnect(); cancelAnimationFrame(raf); el.textContent = text }
  }, [text, off])

  return <Tag ref={ref as never} className={className} aria-label={text} />
}
