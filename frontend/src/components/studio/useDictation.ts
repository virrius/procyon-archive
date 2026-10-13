import { useEffect, useRef, useState } from 'react'
import i18n, { locale } from '../../i18n'

/** speech is transcribed by the browser (Web Speech API): Chrome/Edge have it, Firefox doesn't */
const SR: any = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
export const canDictate = !!SR

const isTyping = (el: EventTarget | null) => {
  const n = el as HTMLElement | null
  if (!n || !n.tagName) return false
  const t = n.tagName.toLowerCase()
  return t === 'input' || t === 'textarea' || t === 'select' || t === 'button' || n.isContentEditable
}

/** Dictation into a field: finished phrases go to onFinal, intermediate ones show in interim.
 *  space: the Space key outside input fields toggles the microphone. */
export function useDictation(onFinal: (text: string) => void, onError: (msg: string) => void,
                             space = false) {
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const rec = useRef<any>(null)
  const want = useRef(false)
  const sink = useRef(onFinal)
  sink.current = onFinal
  const fail = useRef(onError)
  fail.current = onError

  const start = () => {
    if (!SR) { fail.current(i18n.t('studio:dictation.unsupported')); return }
    if (want.current) return
    const r = new SR()
    r.lang = locale()
    r.continuous = true
    r.interimResults = true
    r.onresult = (ev: any) => {
      let fresh = '', live = ''
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const res = ev.results[i]
        if (res.isFinal) fresh += res[0].transcript
        else live += res[0].transcript
      }
      if (fresh.trim()) sink.current(fresh.trim())
      setInterim(live)
    }
    r.onerror = (ev: any) => {
      if (ev.error === 'no-speech' || ev.error === 'aborted') return
      want.current = false
      setListening(false)
      fail.current(ev.error === 'not-allowed'
        ? i18n.t('studio:dictation.mic_denied')
        : i18n.t('studio:dictation.error', { error: ev.error }))
    }
    r.onend = () => {
      setInterim('')
      // Chrome closes the session itself after a pause: restart it until turned off
      if (want.current) { try { r.start() } catch { /* noop */ } }
      else setListening(false)
    }
    rec.current = r
    want.current = true
    setListening(true)
    try { r.start() } catch { want.current = false; setListening(false) }
  }

  const stop = () => {
    want.current = false
    setInterim('')
    try { rec.current?.stop() } catch { /* noop */ }
    setListening(false)
  }

  const toggle = () => (want.current ? stop() : start())

  useEffect(() => () => { want.current = false; try { rec.current?.stop() } catch { /* noop */ } }, [])

  useEffect(() => {
    if (!space) return
    const h = (e: KeyboardEvent) => {
      if (e.code !== 'Space' || e.repeat || e.ctrlKey || e.metaKey || e.altKey) return
      if (isTyping(e.target)) return
      e.preventDefault()
      toggle()
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [space])

  return { listening, interim, toggle, stop }
}

export const append = (prev: string, add: string) =>
  (prev ? prev.replace(/\s+$/, '') + ' ' : '') + add
