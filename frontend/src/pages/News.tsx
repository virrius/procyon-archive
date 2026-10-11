import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { api, c, isPublicView, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import { locale } from '../i18n'
import { Input, Modal, VisChip, VisibilityPicker } from '../ui'
import { IconButton, IconTrash } from '../components/icons'
import { FieldEye } from '../components/FieldEye'
import { MatrixText } from '../components/MatrixText'
import { parseStamp, stamp } from '../components/WorldTime'
import NewsGenerator, { AttachField, CommentsField, JobView, usePoll, type Attach } from '../components/NewsGenerator'
import '../styles.news.css'

const when = (iso: string) =>
  new Date(iso).toLocaleString(locale(), { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })

const attachOf = (l: Dict): Attach => ({ type: l.type, id: l.id, name: l.name, kind: l.kind })

const BARE_KEY = 'pa_news_bare'
const readBare = () => { try { return localStorage.getItem(BARE_KEY) === '1' } catch { return false } }
const saveBare = (on: boolean) => { try { localStorage.setItem(BARE_KEY, on ? '1' : '0') } catch { /* приватное окно */ } }

/** Новости сектора: депеши журналистов и тексты ГМа. Пишутся плюсом здесь или с доски квеста;
    заказанные депеши ждут ГМа в черновиках над лентой. */
export default function News() {
  const { isGM } = useApp()
  const { t } = useTranslation('news')
  const [rows, loading, reload] = useAsync<Dict[]>(() => api.get(`${c()}/news`), [])
  const [edit, setEdit] = useState<Dict | null>(null)
  const [gen, setGen] = useState(false)
  const canEdit = isGM && !isPublicView()
  const [jobs, , reloadJobs] = useAsync<Dict[]>(
    () => (canEdit ? api.get(`${c()}/news/jobs`) : Promise.resolve([])), [canEdit])
  const drafting = jobs || []
  usePoll(drafting.some(j => j.status === 'pending'), () => reloadJobs(true), 4000)
  const refresh = () => { reload(true); reloadJobs(true) }

  // «убить журналиста»: от новости остаются заголовок и суть (и строка эфира с датой)
  const [bare, setBare] = useState(readBare)
  const toggleBare = () => { saveBare(!bare); setBare(!bare) }

  // ?open=<id> — приход из поиска: лента прокручивается к новости и подсвечивает её
  const [params, setParams] = useSearchParams()
  const asked = params.get('open') || ''
  const [lit, setLit] = useState('')
  useEffect(() => {
    if (!asked || !rows) return
    setParams({}, { replace: true })
    if (!rows.some(n => n.id === asked)) return
    setLit(asked)
    requestAnimationFrame(() => document.getElementById(`nw-${asked}`)
      ?.scrollIntoView({ block: 'start' }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asked, rows])

  const [chatting, setChatting] = useState('')
  const writeComments = async (n: Dict) => {
    setChatting(n.id)
    try { await api.post(`${c()}/news/${n.id}/comments`, {}); reload(true) }
    catch (e: any) { alert(e.message) } finally { setChatting('') }
  }

  const drop = async (n: Dict) => {
    if (!confirm(t('feed.drop_confirm', { headline: n.headline || t('feed.untitled') }))) return
    try { await api.del(`${c()}/news/${n.id}`); reload() } catch (e: any) { alert(e.message) }
  }

  const list = rows || []
  return (
    <div className="col">
      <div className="row wrap" style={{ alignItems: 'baseline' }}>
        <h1>{t('feed.title')}</h1>
        <button type="button" role="switch" aria-checked={bare} className="nw-slop" onClick={toggleBare}
          title={t('feed.bare_title')}>
          <span className="nw-slop-track" aria-hidden="true" />{t('feed.bare')}
        </button>
        <div className="spacer" />
        {canEdit && <button className="primary" onClick={() => setGen(true)}>{t('feed.add')}</button>}
      </div>

      {loading && <div className="dim">{t('common:loading')}</div>}
      {!loading && list.length === 0 && (
        <div className="empty">
          {canEdit ? t('feed.quiet_gm')
            : t('feed.quiet')}
        </div>
      )}

      {drafting.length > 0 && (
        <section className="nw nw-drafts">
          <div className="nw-lab">{t('feed.drafts')} <small>{t('feed.drafts_hint')}</small></div>
          {drafting.map(job => (
            <div className="nw-job" key={job.id}>
              {((job.links || []).length > 0 || job.gm_text) && (
                <div className="nw-job-about">
                  {(job.links || []).map((l: Dict) => l.name).join(', ')}
                  {job.gm_text && <i>{job.gm_text}</i>}
                </div>
              )}
              <JobView job={job} onJob={() => reloadJobs(true)}
                onResult={(_, r) => (r.news ? refresh() : reloadJobs(true))} />
            </div>
          ))}
        </section>
      )}

      <div className={bare ? 'nw-feed bare' : 'nw-feed'}>
        {list.map(n => (
          <article key={n.id} id={`nw-${n.id}`}
            className={`nw-item tone-${n.journalist || 'gm'}${bare ? ' bare' : ''}${lit === n.id ? ' lit' : ''}${canEdit && n.visibility === 'gm' ? ' gm-only' : ''}`}>
            <div className="nw-story">
              <div className="nw-item-meta">
                <span className="nw-onair">{t('feed.on_air')}</span>
                <b>{n.byline || t('feed.byline_air')}</b>
                <time dateTime={n.created_at} title={when(n.created_at)}>
                  {n.world_day != null ? stamp(n.world_day) : when(n.created_at)}
                </time>
                {canEdit && (
                  <span className="nw-item-tools">
                    {n.visibility !== 'crew' && <VisChip v={n.visibility} />}
                    <button className="ghost tiny" onClick={() => setEdit(n)}>{t('feed.edit')}</button>
                    <IconButton icon={<IconTrash />} title={t('feed.take_off')} danger onClick={() => drop(n)} />
                  </span>
                )}
              </div>
              {n.headline && <MatrixText as="h2" text={n.headline} off={bare} />}
              {n.lead && (
                <p className={`nw-lead${n.lead_hidden ? ' hidden' : ''}`}>
                  {n.lead_hidden && <span className="nw-lead-off">{t('feed.lead_off')}</span>}
                  <MatrixText text={n.lead} off={bare} />
                </p>
              )}
              {!bare && <NewsBody text={n.body} byline={n.byline} />}
              {!bare && (n.links || []).length > 0 && (
                <div className="nw-links">
                  {n.links.map((l: Dict) => (l.type === 'entity'
                    ? <Link key={l.id} className="nw-link" to={`/entity/${l.id}`}>{l.name}</Link>
                    : <span key={l.id} className="nw-link">{l.name}</span>))}
                </div>
              )}
            </div>
            {!bare && (n.comments || []).length === 0 && canEdit && (
              <aside className="nw-chatter empty">
                <h3>{t('chatter.title')}</h3>
                <p>{t('chatter.none')}</p>
                <button disabled={chatting === n.id} onClick={() => writeComments(n)}>
                  {chatting === n.id ? t('chatter.writing') : t('chatter.write')}
                </button>
              </aside>
            )}
            {!bare && (n.comments || []).length > 0 && (
              <aside className="nw-chatter">
                <h3>{t('chatter.title')}</h3>
                <ol>
                  {n.comments.map((x: Dict, i: number) => (
                    <li key={i}>
                      <MatrixText className="nw-chatter-name" text={x.handle || t('chatter.unsigned')} />
                      {x.who && <MatrixText className="nw-chatter-who" text={x.who} />}
                      <MatrixText as="p" text={String(x.text || '')} />
                    </li>
                  ))}
                </ol>
              </aside>
            )}
          </article>
        ))}
      </div>

      {gen && <NewsGenerator onClose={() => { setGen(false); refresh() }} onAired={refresh} />}
      {edit && <NewsEdit item={edit} onClose={() => setEdit(null)}
        onDone={() => { setEdit(null); reload() }} />}
    </div>
  )
}

// последний абзац, если это подпись журналиста, уходит под текст своей строкой
function NewsBody({ text, byline }: { text: string; byline?: string }) {
  const paras = String(text || '').split(/\n\s*\n/)
  const sign = byline && paras.length > 1 && new RegExp(`^${byline.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s+[—–-]`)
    .test(paras[paras.length - 1].trim()) ? paras.pop() : ''
  return (
    <>
      <MatrixText as="div" className="nw-item-body" text={paras.join('\n\n')} />
      {sign && <MatrixText as="div" className="nw-sign" text={sign} />}
    </>
  )
}

function NewsEdit({ item, onClose, onDone }: { item: Dict; onClose: () => void; onDone: () => void }) {
  const { t } = useTranslation('news')
  const [f, setF] = useState<Dict>({
    headline: item.headline || '', lead: item.lead || '', lead_hidden: !!item.lead_hidden,
    body: item.body || '', comments: item.comments || [], byline: item.byline || '',
    visibility: item.visibility || 'crew', visible_to: item.visible_to || [],
  })
  const [links, setLinks] = useState<Attach[]>((item.links || []).map(attachOf))
  const [date, setDate] = useState(item.world_day != null ? stamp(item.world_day) : '')
  const day = date.trim() ? parseStamp(date) : null
  const badDate = !!date.trim() && day === null
  const [busy, setBusy] = useState(false)
  const save = async () => {
    setBusy(true)
    try {
      await api.patch(`${c()}/news/${item.id}`, {
        ...f,
        ...(day !== null ? { world_day: day } : {}),
        comments: f.comments.filter((x: Dict) => String(x.text || '').trim()),
        entity_ids: links.filter(a => a.type === 'entity').map(a => a.id),
        clock_ids: links.filter(a => a.type === 'clock').map(a => a.id),
      })
      onDone()
    } catch (e: any) { alert(e.message); setBusy(false) }
  }
  return (
    <Modal wide title={t('edit.title')} onClose={onClose} watch={[f, links, date]}
      dirtyAsk={t('edit.dirty')}>
      <div className="nw">
        <div className="nw-edit-row">
          <Input label={t('edit.byline')} value={f.byline} onChange={v => setF({ ...f, byline: v })} />
          <div className="field">
            <label>{t('edit.date')}</label>
            <input className={badDate ? 'bad' : ''} value={date} placeholder={t('edit.date_placeholder')}
              title={t('edit.date_title')} onChange={e => setDate(e.target.value)} />
            {badDate && <span className="nw-err">{t('edit.date_bad')}</span>}
          </div>
        </div>
        <Input label={t('headline')} value={f.headline} onChange={v => setF({ ...f, headline: v })} />
        <div className="field">
          <div className={`fld-lbl${f.lead_hidden ? ' off' : ''}`}>
            {t('lead')}
            <FieldEye hidden={f.lead_hidden} onChange={hide => setF({ ...f, lead_hidden: hide })} />
          </div>
          <textarea className="nw-lead-edit" rows={3} value={f.lead} placeholder={t('lead_placeholder')}
            onChange={e => setF({ ...f, lead: e.target.value })} />
        </div>
        <Input label={t('edit.text')} type="textarea" rows={14} value={f.body}
          onChange={v => setF({ ...f, body: v })} />
        <div className="field">
          <label>{t('chatter.title')}</label>
          <CommentsField value={f.comments} onChange={v => setF({ ...f, comments: v })} />
        </div>
        <div className="field">
          <label>{t('about')}</label>
          <AttachField value={links} onChange={setLinks} />
        </div>
        <VisibilityPicker visibility={f.visibility} visibleTo={f.visible_to}
          onChange={(v, to) => setF({ ...f, visibility: v, visible_to: to })} />
        <button className="primary" disabled={busy || badDate} onClick={save}>
          {busy ? t('edit.saving') : t('edit.save')}
        </button>
      </div>
    </Modal>
  )
}
