import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { api, c, isPublicView, store, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import { Chip, Input, Modal, VisChip, VisibilityPicker } from '../ui'
import { IconButton, IconTrash } from '../components/icons'
import ShipSheet from '../components/ShipSheet'
import EntityPicker, { Thumb } from '../components/EntityPicker'
import RelationsBoard from '../components/RelationsBoard'
import Team from './Characters'
import * as EntityGalleryMod from '../components/EntityGallery'
import { parseStamp, stamp } from '../components/WorldTime'
import '../styles.mail.css'

/** игровая дата письма; без неё — текущая дата кампании */
const mailDate = (m: Dict, today: number) => stamp(m.world_day ?? today)

// параллельные компоненты отдают то именованный, то дефолтный экспорт
const pick = (m: any, name: string): any => (m && m[name]) || (m && m.default)
const EntityGallery = pick(EntityGalleryMod, 'EntityGallery')

// дело закончено так или иначе — карточка уходит в бледный хвост
const JOB_CLOSED = ['done', 'failed', 'expired']

const SUBS: [string, string][] = [
  ['ship', 'tabs.ship'], ['team', 'tabs.team'], ['relations', 'tabs.relations'],
  ['mail', 'tabs.mail'], ['jobs', 'tabs.jobs'], ['items', 'tabs.items'],
]

export default function Crew() {
  const { t } = useTranslation('crew')
  const { pathname } = useLocation()
  const parts = pathname.split('/').filter(Boolean)
  const sub = parts[1] || ''
  const entry = SUBS.find(([k]) => k === sub)

  if (!entry) return <Navigate to="/crew/ship" replace />

  return (
    <div className="col">
      {!['team', 'jobs', 'items'].includes(sub) && <h1>{t(entry[1])}</h1>}

      {sub === 'ship' && <ShipTab />}
      {sub === 'team' && <Team cid={parts[2]} />}
      {sub === 'relations' && <RelationsBoard />}
      {sub === 'mail' && <MailTab />}
      {sub === 'jobs' && (
        <EntityGallery kind="job" title={t('tabs.jobs')} closed={JOB_CLOSED} />
      )}
      {sub === 'items' && <EntityGallery kind="item" title={t('tabs.items')} />}
    </div>
  )
}

/* --- корабль --------------------------------------------------------------- */

function ShipTab() {
  const [rows, loading] = useAsync<Dict[]>(() => api.get(`${c()}/entities?kind=ship`), [])
  const ship = (rows || []).find(e => e.kind === 'ship') || (rows || [])[0] || null
  return <ShipSheet ship={ship} loading={loading} />
}

/* --- входящие -------------------------------------------------------------- */

function MailTab() {
  const { meta, isGM, L, campaign } = useApp()
  const { t } = useTranslation('crew')
  const today = campaign?.world_day ?? 0
  const [msgs, loading, reload] = useAsync<Dict[]>(() => api.get(`${c()}/messages`), [])
  const [msg, setMsg] = useState<Dict | null>(null)
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [unsaved, setUnsaved] = useState(false)
  const readonly = isPublicView()  // витрина для стола — только чтение
  const canEdit = isGM && !readonly
  // ?open=<id> — приход из поиска: письмо открывается сразу
  const [params, setParams] = useSearchParams()
  const asked = params.get('open') || ''

  const all = msgs || []
  const unread = all.filter(m => !m.read).length
  const mail = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return all
      .filter(m => !needle || [m.subject, m.sender_display, m.body]
        .some(x => String(x || '').toLowerCase().includes(needle)))
      .sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned))
  }, [all, q])

  const show = async (m: Dict) => {
    setMsg(m)
    if (!m.read && !readonly) {
      await api.post(`${c()}/messages/${m.id}/state`, { read: true })
      reload()
    }
  }

  // новое письмо — пустое и закрытое от стола; открывает его ГМ выбором «кто видит»
  const createDraft = async () => {
    setBusy(true)
    try {
      await api.post(`${c()}/messages`, {
        sender_display: '', msg_type: 'crew', subject: '', body: '',
        visibility: 'gm', visible_to: [], status: 'delivered',
      })
      reload()
    } catch (e: any) { alert(e.message) } finally { setBusy(false) }
  }

  const save = async (patch: Dict) => {
    if (!msg) return
    const next: Dict = { ...msg, ...patch }
    setMsg(next)
    const body: Dict = {
      sender_display: next.sender_display || '', msg_type: next.msg_type,
      sender_entity_id: next.sender_entity_id || null,
      sender_reveal: !!next.sender_reveal,
      subject: next.subject || '', body: next.body || '', is_lead: !!next.is_lead,
      visibility: next.visibility || 'crew', visible_to: next.visible_to || [],
      status: next.status,
      ...(next.date !== undefined && parseStamp(next.date) !== null ? { world_day: parseStamp(next.date) } : {}),
    }
    await api.patch(`${c()}/messages/${msg.id}`, body)
    reload()
  }

  const dropMsg = async (m: Dict) => {
    if (!confirm(t('mail.delete_confirm', { subject: m.subject || t('mail.untitled') }))) return
    setBusy(true)
    try {
      await api.del(`${c()}/messages/${m.id}`)
      setMsg(cur => (cur && cur.id === m.id ? null : cur))
      reload()
    } catch (e: any) { alert(e.message) } finally { setBusy(false) }
  }

  const drop = async () => { if (msg) await dropMsg(msg) }

  useEffect(() => {
    if (!asked || !msgs) return
    const m = msgs.find(x => x.id === asked)
    if (m) show(m)
    setParams({}, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asked, msgs])

  return (
    <div className="col">
      <div className="row wrap">
        <h2>{t('mail.title')}</h2>
        {unread > 0 && <Chip tone="amber">{t('mail.new_count', { n: unread })}</Chip>}
        <div className="spacer" />
        {canEdit && (
          <button className="primary" disabled={busy} onClick={createDraft}>{t('mail.add')}</button>
        )}
      </div>

      {all.length > 0 && (
        <div className="row wrap">
          <input style={{ maxWidth: 280 }} placeholder={t('mail.search_ph')}
            value={q} onChange={e => setQ(e.target.value)} />
        </div>
      )}

      {loading && <div className="dim">{t('common:loading')}</div>}
      {!loading && all.length === 0 && <div className="empty">{t('mail.empty')}</div>}
      {!loading && all.length > 0 && mail.length === 0 && (
        <div className="empty">{t('no_match')}</div>
      )}

      {mail.length > 0 && (
        <div className="panel pad0">
          <table className="mail-tbl">
            <thead><tr>
              <th></th><th>{t('mail.sender')}</th><th>{t('mail.subject')}</th><th>{t('mail.date')}</th>
              {isGM && <th>{t('mail.who_sees')}</th>}
              {canEdit && <th></th>}
            </tr></thead>
            <tbody>
              {mail.map(m => (
                <tr key={m.id} className={isGM && m.visibility === 'gm' ? 'gm-only' : undefined}
                  style={{ cursor: 'pointer' }} onClick={() => show(m)}>
                  <td className="ml-mark">
                    {m.pinned ? '★' : m.read ? '' : <Chip tone="amber">{t('mail.new')}</Chip>}
                  </td>
                  <td className="mono ml-from">
                    <span className="row" style={{ gap: 8, flexWrap: 'nowrap' }}>
                      {m.sender_card && (
                        <Link to={`/entity/${m.sender_card.id}`} title={m.sender_card.name}
                          onClick={e => e.stopPropagation()}>
                          <Thumb e={m.sender_card} />
                        </Link>
                      )}
                      <span>{m.sender_display || m.sender_card?.name || t('mail.no_sender')}</span>
                    </span>
                  </td>
                  <td className="ml-subj">
                    <strong>{m.subject || t('mail.no_subject')}</strong>
                    {m.is_lead && <> <Chip tone="violet">{t('mail.lead_chip')}</Chip></>}
                  </td>
                  <td className="ml-meta mono">{mailDate(m, today)}</td>
                  {isGM && <td className="ml-meta"><VisChip v={m.visibility} /></td>}
                  {canEdit && (
                    <td className="ml-act"
                      onClick={e => e.stopPropagation()}>
                      <IconButton icon={<IconTrash />} title={t('mail.delete_title')} danger
                        disabled={busy} onClick={() => dropMsg(m)} />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* --- одно окно: чтение и правка --------------------------------------- */}
      {msg && (
        <Modal wide onClose={() => { setMsg(null); reload() }}
          title={msg.subject || t('mail.transmission')}
          dirty={canEdit && unsaved} dirtyAsk={t('mail.dirty_ask')}>
          {canEdit
            ? <MailEditor key={msg.id} msg={msg} types={meta?.message_types || []}
                onSave={save} onDelete={drop} onLeave={() => setMsg(null)} onDirty={setUnsaved} />
            : (
              <>
                <div className="row wrap">
                  {msg.sender_card && (
                    <Link to={`/entity/${msg.sender_card.id}`} className="row"
                      style={{ gap: 8, flexWrap: 'nowrap' }} onClick={() => setMsg(null)}>
                      <Thumb e={msg.sender_card} />
                      <strong>{msg.sender_card.name}</strong>
                    </Link>
                  )}
                  <Chip tone="cyan">{t('mail.from', { sender: msg.sender_display || t('mail.unknown') })}</Chip>
                  <span className="mono dim2 small">{mailDate(msg, today)}</span>
                  {msg.is_lead && <Chip tone="violet">{t('mail.lead_chip')}</Chip>}
                </div>
                <div className="panel" style={{ margin: '12px 0', whiteSpace: 'pre-wrap' }}>
                  {msg.body}
                </div>
                <Attachments messageId={msg.id} />
              </>
            )}

          {!readonly && (
            <div className="row wrap" style={{ marginTop: 12 }}>
              <button onClick={async () => {
                await api.post(`${c()}/messages/${msg.id}/state`, { pinned: !msg.pinned })
                setMsg({ ...msg, pinned: !msg.pinned }); reload()
              }}>{msg.pinned ? t('mail.unpin') : t('mail.pin')}</button>
            </div>
          )}
        </Modal>
      )}
    </div>
  )
}

/* одно окно правки: локальная форма, PATCH по кнопке */
function MailEditor({ msg, types, onSave, onDelete, onLeave, onDirty }: {
  msg: Dict
  types: string[]
  onSave: (patch: Dict, status?: string) => Promise<void>
  onDelete: () => Promise<void>
  /** уход на карточку отправителя закрывает окно письма */
  onLeave: () => void
  /** форма разошлась с последним сохранённым — окно спросит, прежде чем закрыться */
  onDirty: (dirty: boolean) => void
}) {
  const nav = useNavigate()
  const { campaign } = useApp()
  const { t } = useTranslation('crew')
  const [f, setF] = useState<Dict>({
    sender_display: msg.sender_display || '', msg_type: msg.msg_type || 'crew',
    sender_entity_id: msg.sender_entity_id || null, sender_reveal: !!msg.sender_reveal,
    subject: msg.subject || '', body: msg.body || '', is_lead: !!msg.is_lead,
    visibility: msg.visibility || 'crew', visible_to: msg.visible_to || [],
    date: stamp(msg.world_day ?? campaign?.world_day ?? 0),
  })
  const [who, setWho] = useState<Dict | null>(null)
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const [base, setBase] = useState(() => JSON.stringify(f))
  const dirty = JSON.stringify(f) !== base
  const set = (patch: Dict) => { setF({ ...f, ...patch }); setSaved(false) }

  useEffect(() => { onDirty(dirty) }, [dirty])  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => onDirty(false), [])  // eslint-disable-line react-hooks/exhaustive-deps

  // настоящего отправителя храним по id — карточку подтягиваем, чтобы показать имя
  useEffect(() => {
    const id = msg.sender_entity_id
    if (!id) return
    let alive = true
    api.get(`${c()}/entities/${id}`)
      .then(e => { if (alive) setWho(e) })
      .catch(() => { if (alive) setWho(null) })
    return () => { alive = false }
  }, [msg.sender_entity_id])

  const pickWho = (e: Dict | null) => {
    setWho(e)
    set({
      sender_entity_id: e?.id || null,
      ...(e ? {} : { sender_reveal: false }),
      ...(e && !String(f.sender_display || '').trim() ? { sender_display: e.name } : {}),
    })
  }

  const commit = async (status?: string): Promise<boolean> => {
    const snap = JSON.stringify(f)
    setBusy(true)
    try { await onSave(f, status); setBase(snap); setSaved(true); return true }
    catch (e: any) { alert(e.message); return false }
    finally { setBusy(false) }
  }

  // переход на карточку отправителя закрывает окно — несохранённое письмо сначала сохраняем
  const leave = async (ev: React.MouseEvent, to: string) => {
    if (!dirty) { onLeave(); return }
    ev.preventDefault()
    if (await commit()) { onLeave(); nav(to) }
  }

  return (
    <>
      <div className="grid g2">
        <div>
          <Input label={t('mail.sender')} value={f.sender_display}
            onChange={v => set({ sender_display: v })} />
          <EntityPicker label={t('mail.sender_card')} value={who}
            onChange={pickWho} kind="npc,faction,character,crew,ship"
            placeholder={t('mail.sender_ph')}
            vis={{ hidden: !f.sender_reveal, onChange: hide => set({ sender_reveal: !hide }) }} />
          {who && (
            <Link className="small" to={`/entity/${who.id}`}
              onClick={ev => leave(ev, `/entity/${who.id}`)}>
              {t('mail.open_card', { name: who.name })}
            </Link>
          )}
          <Input label={t('mail.subject')} value={f.subject} onChange={v => set({ subject: v })} />
          <Input label={t('mail.date')} value={f.date} placeholder={t('mail.date_ph')}
            onChange={v => set({ date: v })} />
          {!!String(f.date || '').trim() && parseStamp(f.date) === null && (
            <div className="eg-err">{t('mail.date_bad')}</div>
          )}
          <div className="field">
            <label>{t('mail.lead')}</label>
            <label className="row small" style={{ margin: 0, textTransform: 'none' }}>
              <input type="checkbox" style={{ width: 'auto' }} checked={!!f.is_lead}
                onChange={e => set({ is_lead: e.target.checked })} />
              {t('mail.lead_hint')}
            </label>
          </div>
          <VisibilityPicker visibility={f.visibility} visibleTo={f.visible_to}
            onChange={(v, to) => set({ visibility: v, visible_to: to })} />
        </div>
        <div>
          <Input label={t('mail.body')} type="textarea" rows={14} value={f.body}
            onChange={v => set({ body: v })} />
          <Attachments messageId={msg.id} />
        </div>
      </div>

      <div className="row wrap">
        <VisChip v={f.visibility} />
        <div className="spacer" />
        {saved && <span className="small dim2">{t('mail.saved')}</span>}
        <button className="ghost" disabled={busy} onClick={onDelete}>{t('common:delete')}</button>
        <button className="primary" disabled={busy} onClick={() => commit()}>{t('common:save')}</button>
      </div>
    </>
  )
}

function Attachments({ messageId }: { messageId: string }) {
  const { isGM } = useApp()
  const { t } = useTranslation('crew')
  const [rows, , reload] = useAsync<Dict[]>(
    () => api.get(`${c()}/messages/${messageId}/attachments`), [messageId])
  const [busy, setBusy] = useState(false)
  const readonly = isPublicView()  // витрина для стола — только чтение

  const upload = async (file: File) => {
    setBusy(true)
    const fd = new FormData()
    fd.append('file', file)
    fd.append('target_type', 'message')
    fd.append('target_id', messageId)
    try { await api.post(`${c()}/upload`, fd) } catch (e: any) { alert(e.message) }
    setBusy(false); reload()
  }

  return (
    <div className="col">
      {(rows || []).map(a => (
        <a key={a.id} className="small" href={a.url} target="_blank" rel="noreferrer">
          📎 {a.caption || a.filename}
        </a>
      ))}
      {isGM && !readonly && (
        <div className="field">
          <label>{t('mail.attachment')}</label>
          <input type="file" disabled={busy} onChange={e => {
            const f = e.target.files?.[0]
            if (f) upload(f)
          }} />
        </div>
      )}
    </div>
  )
}
