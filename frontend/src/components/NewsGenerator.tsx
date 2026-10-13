import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api, c, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import { Modal, clockTitle } from '../ui'
import { FieldEye } from './FieldEye'
import { usePickHits } from './EntityPicker'
import '../styles.news.css'

/** News link: a campaign entry or a clock. */
export type Attach = { type: 'entity' | 'clock'; id: string; name: string; kind: string }

export const attachOfEntity = (e: Dict): Attach =>
  ({ type: 'entity', id: e.id, name: e.name, kind: e.kind })
export const attachOfClock = (cl: Dict): Attach =>
  ({ type: 'clock', id: cl.id, name: clockTitle(cl), kind: 'clock' })

/* "Lazarus — anarchist" → "anarchist": the handle is right next to it anyway */
const after = (text: string, head: string) =>
  String(text || '').replace(head, '').replace(/^\s*[—–-]\s*/, '').trim()

/** While the condition holds, fn every ms. A dispatch order is written in the background; we poll its state. */
export function usePoll(on: boolean, fn: () => void, ms = 3000) {
  const ref = useRef(fn)
  ref.current = fn
  useEffect(() => {
    if (!on) return
    const t = setInterval(() => ref.current(), ms)
    return () => clearInterval(t)
  }, [on, ms])
}

/** The "Who and what it's about" field: picks as chips right in the field, with arrows and Backspace.
    Uses the same search as EntityPicker: entries and clocks in one list. */
export function AttachField({ value, onChange }: { value: Attach[]; onChange: (v: Attach[]) => void }) {
  const { L } = useApp()
  const { t } = useTranslation('news')
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [hot, setHot] = useState(0)
  const box = useRef<HTMLDivElement>(null)
  const { hits: found } = usePickHits({
    q, on: open, limit: 12, clocks: 'all', exclude: value.map(a => a.id),
  })

  // a click outside the field closes the suggestions
  useEffect(() => {
    if (!open) return
    const h = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [open])

  const needle = q.trim()
  const hits: Attach[] = found.map(h => (h.type === 'clock' ? attachOfClock(h) : attachOfEntity(h)))

  const pick = (a: Attach) => { onChange([...value, a]); setQ(''); setHot(0) }
  const kindOf = (a: Attach) => (a.type === 'clock' ? t('clock') : L(a.kind))

  const keys = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setHot(h => Math.min(h + 1, hits.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHot(h => Math.max(h - 1, 0)) }
    else if (e.key === 'Enter' && open && hits[hot]) { e.preventDefault(); pick(hits[hot]) }
    else if (e.key === 'Escape' && open) { e.stopPropagation(); setOpen(false) }
    else if (e.key === 'Backspace' && !q && value.length) onChange(value.slice(0, -1))
  }

  return (
    <div className="nw-attach" ref={box}>
      {value.map(a => (
        <span className="nw-tag" key={`${a.type}:${a.id}`}>
          <span>{a.name}</span>
          <span className="nw-tag-kind">{kindOf(a)}</span>
          <button type="button" className="nw-tag-x" aria-label={t('attach.remove', { name: a.name })}
            onClick={() => onChange(value.filter(x => x !== a))}>×</button>
        </span>
      ))}
      <input value={q} placeholder={value.length ? t('attach.more') : t('attach.placeholder')}
        onChange={e => { setQ(e.target.value); setOpen(true); setHot(0) }}
        onFocus={() => setOpen(true)} onKeyDown={keys} />
      {open && (
        <div className="nw-pop">
          {hits.map((a, i) => (
            <button type="button" key={`${a.type}:${a.id}`} className={i === hot ? 'nw-hit hot' : 'nw-hit'}
              onMouseEnter={() => setHot(i)} onClick={() => pick(a)}>
              <span>{a.name}</span><span className="nw-hit-kind">{kindOf(a)}</span>
            </button>
          ))}
          {!hits.length && <div className="nw-pop-note">{needle ? t('attach.nothing') : t('attach.all_linked')}</div>}
        </div>
      )}
    </div>
  )
}

/** Server reply to a draft action: the order after it (null: order closed) and the aired story. */
export type DraftResult = { job: Dict | null; news?: Dict }

/** Net chatter comments: handle, who they are and where from, comment. */
export function CommentsField({ value, onChange }: { value: Dict[]; onChange: (v: Dict[]) => void }) {
  const { t } = useTranslation('news')
  const set = (i: number, patch: Dict) => onChange(value.map((x, j) => (j === i ? { ...x, ...patch } : x)))
  return (
    <div className="nw-comments-edit">
      {value.map((x, i) => (
        <div key={i} className="nw-comment-edit">
          <input value={x.handle || ''} placeholder={t('comment.handle')} aria-label={t('comment.handle_label')}
            onChange={e => set(i, { handle: e.target.value })} />
          <input value={x.who || ''} placeholder={t('comment.who')} aria-label={t('comment.who_label')}
            onChange={e => set(i, { who: e.target.value })} />
          <button type="button" className="ghost tiny" title={t('comment.remove')} aria-label={t('comment.remove')}
            onClick={() => onChange(value.filter((_, j) => j !== i))}>×</button>
          <textarea rows={2} value={x.text || ''} placeholder={t('comment.text')} aria-label={t('comment.text_label')}
            onChange={e => set(i, { text: e.target.value })} />
        </div>
      ))}
      <button type="button" className="ghost tiny" onClick={() => onChange([...value, { handle: '', who: '', text: '' }])}>
        {t('comment.add')}
      </button>
    </div>
  )
}

const said = (xs: Dict[]) => xs.filter(x => String(x.text || '').trim())

/** Order draft. Edits save themselves a second after typing; the window can be closed at any moment. */
export function DraftSlip({ job, draft, onResult }: {
  job: Dict
  draft: Dict
  onResult: (r: DraftResult) => void
}) {
  const { t } = useTranslation('news')
  const [headline, setHeadline] = useState(draft.headline || '')
  const [lead, setLead] = useState(draft.lead || '')
  const [leadHidden, setLeadHidden] = useState(!!draft.lead_hidden)
  const [text, setText] = useState(draft.text || '')
  const [comments, setComments] = useState<Dict[]>(draft.comments || [])
  const [busy, setBusy] = useState(false)
  const [chatting, setChatting] = useState(false)
  const [err, setErr] = useState('')
  const typed = useRef(false)
  const url = `${c()}/news/jobs/${job.id}/drafts/${draft.i}`

  useEffect(() => {
    if (!typed.current) return
    const t = setTimeout(() => {
      api.patch(url, { headline, lead, lead_hidden: leadHidden, text, comments }).catch(() => {})
    }, 900)
    return () => clearTimeout(t)
  }, [headline, lead, leadHidden, text, comments])

  const act = async (run: () => Promise<DraftResult>, fail: string) => {
    setBusy(true); setErr('')
    try { onResult(await run()) } catch (e: any) { setErr(e?.message || fail) } finally { setBusy(false) }
  }
  const air = () => act(() => api.post(`${url}/air`, {
    headline, lead, lead_hidden: leadHidden, text, comments: said(comments),
  }),
    t('draft.air_failed'))
  const edit = (set: (v: any) => void) => (v: any) => { typed.current = true; set(v) }
  const drop = () => act(() => api.del(url), t('draft.drop_failed'))
  const writeComments = async () => {
    setChatting(true); setErr('')
    try {
      // the commenters read the fresh text: save edits first
      await api.patch(url, { headline, lead, lead_hidden: leadHidden, text, comments })
      setComments((await api.post(`${url}/comments`, {})).comments || [])
    } catch (e: any) { setErr(e?.message || t('draft.comments_failed')) }
    finally { setChatting(false) }
  }

  return (
    <div className={`nw-slip tone-${job.journalist}`}>
      <div className="nw-slip-meta">
        <b>{job.byline || t('draft.no_byline')}</b>
        {draft.lens && <span>{t('draft.lens', { lens: draft.lens })}</span>}
        {draft.manual && <span>{t('draft.manual')}</span>}
        {draft.angle && <i>{draft.angle}</i>}
      </div>
      <div className="nw-slip-grid">
        <div className="nw-slip-main">
          <input className="nw-head" value={headline} placeholder={t('headline')} aria-label={t('headline')}
            onChange={e => edit(setHeadline)(e.target.value)} />
          <div className={`nw-sub lbl-row${leadHidden ? ' off' : ''}`}>
            {t('lead')}
            <FieldEye hidden={leadHidden} onChange={edit(setLeadHidden)} />
            <small>{t('draft.lead_hint')}</small>
          </div>
          <textarea className="nw-lead-edit" rows={3} value={lead} placeholder={t('lead_placeholder')}
            aria-label={t('lead')} onChange={e => edit(setLead)(e.target.value)} />
          <textarea className="nw-body" rows={10} value={text} placeholder={t('draft.body')} aria-label={t('draft.body')}
            onChange={e => edit(setText)(e.target.value)} />
        </div>
        <div className="nw-slip-side">
          <div className="nw-sub">{t('chatter.title')}</div>
          {comments.length === 0 && (
            <button className="nw-chat-go" disabled={chatting} onClick={writeComments}>
              {chatting ? t('chatter.writing') : t('chatter.write')}
            </button>
          )}
          <CommentsField value={comments} onChange={edit(setComments)} />
        </div>
      </div>
      <div className="nw-slip-foot">
        {err && <span className="nw-err">{err}</span>}
        <div className="spacer" />
        <button className="ghost" disabled={busy} onClick={drop}>{t('draft.remove')}</button>
        <button disabled={busy || !(headline.trim() || lead.trim() || text.trim())} onClick={air}>
          {busy ? t('draft.wait') : t('draft.air')}
        </button>
      </div>
    </div>
  )
}

/** The whole order: writing shows blank sheets, failed shows the reason and retry, ready shows drafts. */
export function JobView({ job, toFeed, onJob, onResult }: {
  job: Dict
  toFeed?: boolean
  /** the order changed state (retry) or was closed (null) */
  onJob: (job: Dict | null) => void
  onResult: (draft: Dict, r: DraftResult) => void
}) {
  const { t } = useTranslation('news')
  const [busy, setBusy] = useState(false)
  const retry = async () => {
    setBusy(true)
    try { onJob(await api.post(`${c()}/news/jobs/${job.id}/retry`, {})) } catch (e: any) { alert(e.message) }
    finally { setBusy(false) }
  }
  const drop = async () => {
    setBusy(true)
    try { await api.del(`${c()}/news/jobs/${job.id}`); onJob(null) } catch (e: any) { alert(e.message) }
    finally { setBusy(false) }
  }

  if (job.status === 'pending') {
    return (
      <>
        <div className="nw-wait-note">
          {t('job.writing', { who: job.byline || t('job.journalist') })}
        </div>
        {[0, 1, 2].map(i => <div key={i} className={`nw-slip wait tone-${job.journalist}`} aria-hidden />)}
      </>
    )
  }
  if (job.status === 'failed') {
    return (
      <div className={`nw-slip tone-${job.journalist}`}>
        <div className="nw-slip-meta"><b>{job.byline}</b><span>{t('job.failed')}</span></div>
        <div className="nw-err">{job.error || t('job.failed_text')}</div>
        <div className="nw-slip-foot">
          <div className="spacer" />
          <button className="ghost" disabled={busy} onClick={drop}>{t('draft.remove')}</button>
          <button disabled={busy} onClick={retry}>{t('job.retry')}</button>
        </div>
      </div>
    )
  }
  return (
    <>
      {(job.drafts || []).filter((d: Dict) => !d.gone).map((d: Dict) => (d.aired
        ? <div key={`${job.id}:${d.i}`} className="nw-aired">
            {t('job.aired', { headline: d.headline || t('job.untitled') })}
            {toFeed && <Link to="/news">{t('job.open_feed')}</Link>}
          </div>
        : <DraftSlip key={`${job.id}:${d.i}`} job={job} draft={d} onResult={r => onResult(d, r)} />))}
    </>
  )
}

/** Story: three dispatches by the chosen journalist about what happened, or the GM's own text.
    Opens from the plus in "News" and from a story board, with entries already linked.
    The order is written on the server: the window can be closed, the drafts will wait in "News". */
export default function NewsGenerator({ attach = [], onClose, onAired, toFeed }: {
  attach?: Attach[]
  onClose: () => void
  /** the story aired or the order changed: time for the feed to reload */
  onAired?: () => void
  /** the window was opened outside the feed: show the way to it */
  toFeed?: boolean
}) {
  const { t } = useTranslation('news')
  const [opts] = useAsync<Dict>(() => api.get(`${c()}/dispatch-options`), [])
  const journalists: Dict[] = opts?.journalists || []
  const [journalist, setJournalist] = useState('')
  const [links, setLinks] = useState<Attach[]>(attach)
  const [gmText, setGmText] = useState('')
  const [jobs, setJobs] = useState<Dict[]>([])
  const [ordering, setOrdering] = useState(false)
  const [err, setErr] = useState('')

  const who = journalist || journalists[0]?.key || ''
  const ready = !!who && (!!gmText.trim() || links.length > 0)
  const pending = jobs.filter(j => j.status === 'pending')

  usePoll(pending.length > 0, () => {
    pending.forEach(j => api.get(`${c()}/news/jobs/${j.id}`)
      .then(fresh => setJobs(js => js.map(x => (x.id === j.id ? fresh : x))))
      .catch(() => setJobs(js => js.filter(x => x.id !== j.id))))
  })

  const ids = (type: Attach['type']) => links.filter(a => a.type === type).map(a => a.id)

  const order = async (manual: boolean) => {
    setOrdering(true); setErr('')
    try {
      const job = await api.post(`${c()}/news/jobs`, {
        manual, gm_text: gmText, entity_ids: ids('entity'), clock_ids: ids('clock'), journalist: who,
      })
      setJobs(js => [job, ...js])
      onAired?.()
    } catch (e: any) { setErr(e?.message || t('gen.order_failed')) }
    finally { setOrdering(false) }
  }

  const setJob = (id: string, job: Dict | null) =>
    setJobs(js => (job ? js.map(x => (x.id === id ? job : x)) : js.filter(x => x.id !== id)))

  // in the window an aired draft turns into an "on the air" line; in the drafts feed it just disappears
  const result = (job: Dict, draft: Dict, r: DraftResult) => {
    setJobs(js => js.map(x => (x.id !== job.id ? x : {
      ...x, drafts: x.drafts.map((d: Dict) => (d.i !== draft.i ? d : r.news ? { ...d, aired: true } : { ...d, gone: true })),
    })))
    onAired?.()
  }

  return (
    <Modal wide title={t('gen.title')} onClose={onClose}>
      <div className="nw">
        <div className="nw-grid">
          <div className="nw-brief">
            <div>
              <div className="nw-lab">{t('gen.who')}</div>
              <div className="nw-voices">
                {journalists.map(j => (
                  <button type="button" key={j.key}
                    className={`nw-voice tone-${j.key}${who === j.key ? ' on' : ''}`}
                    aria-pressed={who === j.key} onClick={() => setJournalist(j.key)}>
                    <span className="nw-voice-name">{j.byline}</span>
                    <span className="nw-voice-side">{after(j.title, j.byline)}</span>
                    <span className="nw-voice-sig">{after(j.signature, j.byline)}</span>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="nw-lab">{t('about')}</div>
              <AttachField value={links} onChange={setLinks} />
            </div>

            <div>
              <div className="nw-lab">{t('gen.what')} <small>{t('gen.what_hint')}</small></div>
              <textarea rows={5} value={gmText} onChange={e => setGmText(e.target.value)}
                placeholder={t('gen.what_placeholder')} />
            </div>

            <div className="nw-go">
              <button className="primary" disabled={!ready || ordering} onClick={() => order(false)}>
                {jobs.length ? t('gen.write_more') : t('gen.write_three')}
              </button>
              <button className="ghost" disabled={!who || ordering} onClick={() => order(true)}>{t('gen.write_self')}</button>
            </div>
            {!ready && who && (
              <div className="nw-pop-note" style={{ padding: 0 }}>{t('gen.need')}</div>
            )}
            {err && <div className="nw-err">{err}</div>}
          </div>

          <div className="nw-air">
            {!jobs.length && (
              <div className="nw-idle">
                <strong>{t('gen.idle_title')}</strong>
                {t('gen.idle_text')}
              </div>
            )}
            {jobs.map(job => (
              <JobView key={job.id} job={job} toFeed={toFeed}
                onJob={next => { setJob(job.id, next); onAired?.() }}
                onResult={(d, r) => result(job, d, r)} />
            ))}
          </div>
        </div>
      </div>
    </Modal>
  )
}
