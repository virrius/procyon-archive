import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api, c, type Dict } from '../api'
import { useApp } from '../ctx'
import i18n, { locale } from '../i18n'
import { Chip, Select } from '../ui'
import '../styles.history.css'

/** section chips: each collects several feed sources */
const GROUPS: [string, string[]][] = [
  ['cards', ['entity', 'block', 'link']],
  ['files', ['file']],
  ['clocks', ['clock']],
  ['mail', ['message', 'news']],
  ['map', ['map', 'marker', 'note']],
  ['misc', ['board', 'rules', 'account']],
]

const SEARCH_DELAY = 300

const tr = (key: string, fallback: string) =>
  (i18n.exists(`history:${key}`) ? i18n.t(`history:${key}`) : fallback)

const VIS = ['crew', 'selected', 'owner', 'gm']
const visLabel = (v: string) => (VIS.includes(v) ? i18n.t(`history:vis.${v}`) : v)

/** "source:action" → feed phrase; without a pair, use the generic word for the action */
const phrase = (e: Dict) => {
  const act = String(e.action || '').replace(/-/g, '_')
  return tr(`phrase.${e.source}.${act}`, tr(`fallback.${act}`, e.action))
}

/** ship sheet keys without a label in the schema: as in the sheet headings */
const sheetLabel = (f: string, other: string) => tr(`sheet.${f}`, other)

const val = (v: any): string => {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'boolean') return v ? i18n.t('history:yes') : i18n.t('history:no')
  if (Array.isArray(v)) return v.length ? v.map(val).join(', ') : '—'
  if (typeof v === 'object') {
    return Object.entries(v).map(([k, x]) => `${tr(`field.${k}`, k)}: ${val(x)}`).join('; ')
  }
  return visLabel(String(v))
}

type Change = { key: string; label: string; was: string; now: string }

/** "before → after": the fields dict is expanded by key, only changed ones stay;
    labels as on the card (type fields from the schema, then the shared dictionary) */
function changesOf(e: Dict, meta: Dict | null): Change[] {
  const kinds: Dict = meta?.kinds || {}
  // a card edit carries its type in detail; "relations" don't know the type, so search all
  const defs: Dict[] = e.source === 'entity'
    ? [kinds[e.detail], ...Object.values(kinds)].filter(Boolean) : []
  const name = (k: string): string => {
    for (const d of defs) {
      const f = (d.fields || []).find((x: Dict) => x.key === k)
      if (f) return f.label
    }
    return tr(`field.${k}`, meta?.labels?.[k] || k)
  }
  const show = (k: string, v: any) =>
    k === 'hidden_fields' && Array.isArray(v) ? val(v.map(x => name(String(x)))) : val(v)
  const keys = (a: Dict, b: Dict) => Array.from(new Set([...Object.keys(a), ...Object.keys(b)]))
  const isMap = (v: any) => !!v && typeof v === 'object' && !Array.isArray(v)

  const before: Dict = e.before || {}
  const after: Dict = e.after || {}
  const out: Change[] = []
  for (const k of keys(before, after)) {
    if (k === 'fields' && (isMap(before[k]) || isMap(after[k]))) {
      const was: Dict = isMap(before[k]) ? before[k] : {}
      const now: Dict = isMap(after[k]) ? after[k] : {}
      for (const f of keys(was, now)) {
        const a = val(was[f]), b = val(now[f])
        if (a !== b) out.push({ key: `fields.${f}`, label: sheetLabel(f, name(f)), was: a, now: b })
      }
      continue
    }
    out.push({ key: k, label: name(k), was: show(k, before[k]), now: show(k, after[k]) })
  }
  return out
}

const DAY = (iso: string) =>
  new Date(iso).toLocaleDateString(locale(), { day: '2-digit', month: 'long', year: 'numeric' })
const TIME = (iso: string) =>
  new Date(iso).toLocaleTimeString(locale(), { hour: '2-digit', minute: '2-digit' })

/** Campaign log: one feed of edits, comments and account actions.
    backend/app/history.py writes the data on every edit, so the feed
    keeps deleted entries too, with a snapshot of what was in them. */
export default function HistoryFeed() {
  const { campaign } = useApp()
  const { t } = useTranslation('history')
  const [picked, setPicked] = useState<string[]>([])
  const [member, setMember] = useState('')
  const [query, setQuery] = useState('')
  const [applied, setApplied] = useState('')
  const [rows, setRows] = useState<Dict[]>([])
  const [next, setNext] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const seq = useRef(0)

  useEffect(() => {
    const t = setTimeout(() => setApplied(query.trim()), SEARCH_DELAY)
    return () => clearTimeout(t)
  }, [query])

  const load = useCallback(async (cursor?: string | null) => {
    const mine = ++seq.current
    setBusy(true); setErr('')
    const p = new URLSearchParams()
    const sources = GROUPS.filter(([k]) => picked.includes(k)).flatMap(([, s]) => s)
    if (sources.length) p.set('source', sources.join(','))
    if (member) p.set('member', member)
    if (applied) p.set('q', applied)
    if (cursor) p.set('before', cursor)
    try {
      const r = await api.get(`${c()}/history?${p.toString()}`)
      if (seq.current !== mine) return
      setRows(old => (cursor ? [...old, ...(r.events || [])] : r.events || []))
      setNext(r.next || null)
    } catch (e: any) {
      if (seq.current === mine) setErr(e.message || t('error'))
    } finally {
      if (seq.current === mine) setBusy(false)
    }
  }, [picked, member, applied])

  useEffect(() => { load() }, [load])

  const toggle = (k: string) =>
    setPicked(v => (v.includes(k) ? v.filter(x => x !== k) : [...v, k]))

  const members: Dict[] = campaign?.members || []
  let day = ''

  return (
    <div className="panel col">
      <div className="row">
        <h3>{t('title')}</h3>
        <div className="spacer" />
        <button className="tiny ghost" onClick={() => load()}>{t('refresh')}</button>
      </div>

      <div className="hist-filters">
        <div className="row wrap">
          {GROUPS.map(([k]) => (
            <button key={k} type="button"
              className={`pick${picked.includes(k) ? ' on' : ''}`}
              onClick={() => toggle(k)}>{t(`group.${k}`)}</button>
          ))}
          {!!picked.length && (
            <button className="tiny ghost" onClick={() => setPicked([])}>{t('all')}</button>
          )}
        </div>
        <div className="row wrap hist-controls">
          <div className="hist-pick">
            <Select value={member} options={members.map((m: Dict) => m.id)}
              optionLabel={id => members.find((m: Dict) => m.id === id)?.display_name || id}
              empty={t('anyone')} title={t('author')} onChange={setMember} />
          </div>
          <input className="hist-q" value={query} placeholder={t('search')}
            onChange={e => setQuery(e.target.value)} />
          {(!!query || !!member || !!picked.length) && (
            <button className="tiny ghost" onClick={() => {
              setPicked([]); setMember(''); setQuery(''); setApplied('')
            }}>{t('reset')}</button>
          )}
        </div>
      </div>

      {err && <div className="hist-err">{err}</div>}

      <div className="hist-list">
        {rows.map(e => {
          const d = DAY(e.at)
          const head = d !== day
          day = d
          return (
            <div key={e.id}>
              {head && <div className="hist-day">{d}</div>}
              <Row e={e} />
            </div>
          )
        })}
      </div>

      {!rows.length && !busy && <div className="empty">{t('empty')}</div>}
      {busy && <div className="dim small">{t('common:loading')}</div>}
      {next && !busy && (
        <button className="tiny" onClick={() => load(next)}>{t('more')}</button>
      )}
    </div>
  )
}

function Row({ e }: { e: Dict }) {
  const { meta, L } = useApp()
  const { t, i18n: { language } } = useTranslation('history')
  const [open, setOpen] = useState(false)
  const diff = useMemo(() => changesOf(e, meta), [e, meta, language])
  const target = e.title || e.entity_name || ''

  return (
    <div className="hist-row">
      <div className="hist-line">
        <span className="hist-time mono">{TIME(e.at)}</span>
        <Chip tone={e.by_gm ? 'red' : ''}>{e.actor || t('system')}</Chip>
        <span className="hist-what">{phrase(e)}</span>
        {target && (e.entity_id
          ? <Link className="hist-target" to={`/entity/${e.entity_id}`}>{target}</Link>
          : <span className="hist-target plain">{target}</span>)}
        {e.entity_name && e.entity_name !== target && (
          <span className="dim2 small">{t('in_entity', { name: e.entity_name })}</span>
        )}
        <div className="spacer" />
        {e.visibility && <Chip tone={e.visibility === 'gm' ? 'red' : ''}>
          {visLabel(e.visibility)}</Chip>}
        <Chip tone="black">{tr(`source.${e.source}`, e.source)}</Chip>
        {!!diff.length && (
          <button className="tiny ghost" onClick={() => setOpen(o => !o)}>
            {open ? t('collapse') : t('what_changed')}
          </button>
        )}
      </div>
      {e.detail && <div className="hist-detail">{L(e.detail)}</div>}
      {open && !!diff.length && (
        <div className="hist-diff">
          {diff.map(d => (
            <div className="hist-diff-row" key={d.key}>
              <div className="hist-key">{d.label}</div>
              <div className="hist-was">{d.was}</div>
              <div className="hist-now">{d.now}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
