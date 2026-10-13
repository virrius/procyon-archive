import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c } from '../api'

type State = 'online' | 'degraded' | 'offline'
type Status = {
  state: State
  age_s: number | null
  comfy: string | null
  checkpoint: string | null
  job: { id: string; progress: string | null } | null
  edit: boolean
  queue: Record<string, number>
  last_error: string | null
}

const POLL_MS = 10000
// the network hiccups more often than the worker goes down: hide the badge only on the second miss in a row
const MISSES_TO_OFFLINE = 2

const LABEL: Record<State | 'unknown', string> = {
  unknown: 'worker.unknown',
  online: 'worker.online',
  degraded: 'worker.degraded',
  offline: 'worker.offline',
}

const SHORT: Record<State | 'unknown', string> = {
  unknown: 'worker.short',
  online: 'worker.short',
  degraded: 'worker.short_comfy',
  offline: 'worker.short',
}

/** compact: the header variant, a dot and one word, the full status in the tooltip */
export function GenWorkerBadge({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation('studio')
  const [st, setSt] = useState<Status | null>(null)
  const [known, setKnown] = useState(false)
  const misses = useRef(0)
  const stopped = useRef(false)

  useEffect(() => {
    stopped.current = false
    let timer = 0
    const tick = async () => {
      try {
        const s: Status = await api.get(`${c()}/image-worker/status`)
        if (stopped.current) return
        if (s.state === 'offline') misses.current += 1
        else misses.current = 0
        if (s.state !== 'offline' || misses.current >= MISSES_TO_OFFLINE) {
          setSt(s); setKnown(true)
        }
      } catch {
        if (stopped.current) return
        misses.current += 1
        if (misses.current >= MISSES_TO_OFFLINE) { setSt(null); setKnown(true) }
      }
      if (!stopped.current) timer = window.setTimeout(tick, POLL_MS)
    }
    tick()
    return () => { stopped.current = true; window.clearTimeout(timer) }
  }, [])

  const state: State | 'unknown' = !known ? 'unknown' : st?.state ?? 'offline'
  const waiting = (st?.queue?.pending ?? 0) + (st?.queue?.claimed ?? 0)
  const drawing = state !== 'offline' && state !== 'unknown' && st?.job?.progress

  let note = ''
  if (drawing) note = t('worker.drawing', { progress: st!.job!.progress })
  else if (waiting) note = t('worker.queued', { n: waiting })

  const hint = [
    t(LABEL[state]), note, st?.checkpoint,
    state !== 'offline' && st?.edit === false && t('worker.no_edit'),
    st?.last_error && t('worker.last_error', { error: st.last_error }),
  ].filter(Boolean).join(' · ')

  return (
    <span className={`gw-badge ${state}${compact ? ' compact' : ''}`} title={hint}>
      <i className="gw-dot" />
      {compact ? t(SHORT[state]) : t(LABEL[state])}
      {note && <span className="gw-note"> · {note}</span>}
    </span>
  )
}
