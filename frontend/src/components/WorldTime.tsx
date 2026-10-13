import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c } from '../api'
import { useApp } from '../ctx'
import { IconCalendar } from './icons'
import { useLayer } from '../layers'

// rulebook: "It is the year 1261 since the founding of the Galactic Hegemony"; no calendar, a year of 52 weeks
const YEAR0 = 1261
const WEEK = 7
const YEAR = 52 * WEEK
// players see the GM's shift without reloading
const POLL_MS = 30000
const STEPS = [{ days: 1, label: 'time.step_day' }, { days: WEEK, label: 'time.step_week' }]

export const stamp = (day: number) =>
  `${YEAR0 + Math.floor(day / YEAR)}.${Math.floor(day % YEAR / WEEK) + 1}.${day % WEEK + 1}`

export function parseStamp(s: string): number | null {
  const m = s.trim().match(/^(\d{4})\.(\d{1,2})\.(\d)$/)
  if (!m) return null
  const [y, w, d] = m.slice(1).map(Number)
  if (y < YEAR0 || w < 1 || w > 52 || d < 1 || d > WEEK) return null
  return (y - YEAR0) * YEAR + (w - 1) * WEEK + d - 1
}

/** In-game time in the header: year.week.day. The GM shifts it on click, players only see it. */
export function WorldTime({ canShift }: { canShift: boolean }) {
  const { campaign } = useApp()
  const { t } = useTranslation('map')
  const [day, setDay] = useState<number>(campaign?.world_day ?? 0)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState('')
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const t = setInterval(() => { api.get(`${c()}/time`).then(r => setDay(r.day)).catch(() => {}) }, POLL_MS)
    return () => clearInterval(t)
  }, [])

  useEffect(() => { setDraft(stamp(day)) }, [day, open])

  useEffect(() => {
    if (!open) return
    const away = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', away)
    return () => document.removeEventListener('mousedown', away)
  }, [open])
  useLayer(open, () => setOpen(false))

  const send = (req: Promise<any>) => {
    setBusy(true)
    req.then(r => setDay(r.day)).catch(() => {}).finally(() => setBusy(false))
  }
  const shift = (days: number) => send(api.post(`${c()}/time`, { days }))
  const target = parseStamp(draft)
  const setTo = () => { if (target !== null && target !== day) send(api.put(`${c()}/time`, { day: target })) }

  const now = stamp(day)
  const hint = t('time.hint', {
    now, year: YEAR0 + Math.floor(day / YEAR), week: Math.floor(day % YEAR / WEEK) + 1, day: day % WEEK + 1,
  })
  const face = <><IconCalendar size={14} /><span className="wt-date">{now}</span></>

  return (
    <div className="wt" ref={box}>
      {canShift
        ? <button className="wt-face" aria-expanded={open} aria-label={`${hint}. ${t('time.shift')}`}
            title={hint} onClick={() => setOpen(v => !v)}>{face}</button>
        : <div className="wt-face" title={hint} aria-label={hint}>{face}</div>}
      {open && (
        <div className="wt-pop" role="group" aria-label={t('time.shift')}>
          <input className={`wt-now${target === null ? ' bad' : ''}`} value={draft} disabled={busy}
            aria-label={t('time.input')} title={t('time.input_title')}
            onChange={e => setDraft(e.target.value)} onBlur={() => setDraft(now)}
            onKeyDown={e => { if (e.key === 'Enter') setTo() }} />
          {STEPS.map(s => (
            <div key={s.days} className="wt-row">
              <button className="ghost" disabled={busy || day < s.days} aria-label={t('time.back', { step: t(s.label) })}
                onClick={() => shift(-s.days)}>−</button>
              <span>{t(s.label)}</span>
              <button className="primary" disabled={busy} aria-label={t('time.forward', { step: t(s.label) })}
                onClick={() => shift(s.days)}>+</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
