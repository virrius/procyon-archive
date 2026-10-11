import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import i18n from '../i18n'
import { Link } from 'react-router-dom'
import { api, c, isPublicView, store, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import { Chip, Modal } from '../ui'
import EntityPicker, { Thumb } from './EntityPicker'
import { IconButton, IconEdit, IconPlus, IconTrash } from './icons'
import VisibilityMenu from './VisibilityMenu'
import '../styles.entity.css'

// подпись направленная: её читают от лица from_id, поэтому в форме показываем,
// кто в этой фразе подлежащее, а кто дополнение
function LabelField({ value, onChange, subject, object }: {
  value: string; onChange: (v: string) => void; subject?: string; object?: string
}) {
  const { t } = useTranslation('entity')
  return (
    <div className="field">
      <label>{t('links.label_field')}</label>
      <input type="text" value={value} placeholder={t('links.label_ph')}
        onChange={e => onChange(e.target.value)} />
      {subject && object && (
        <div className="lnk-hint">
          {subject} <b>{value.trim() || '…'}</b> {object}
        </div>
      )}
    </div>
  )
}

const quoted = (s?: string) => (s ? i18n.t('entity:quoted', { s }) : '')

/** Фраза связи от лица карточки, на которой мы стоим. */
function phrase(r: Dict, selfName?: string): string {
  const label = String(r.label || '').trim()
  if (!label) return ''
  const me = quoted(selfName), peer = quoted(r.peer?.name)
  if (!me || !peer) return label
  return r.direction === 'in' ? `${peer} ${label} ${me}` : `${me} ${label} ${peer}`
}

export default function LinksPanel({ entityId, kind, name }: {
  entityId: string; kind?: string; name?: string
}) {
  const { L, isGM } = useApp()
  const { t } = useTranslation('entity')
  const readonly = isPublicView()  // витрина для стола — только чтение
  const [rows, loading, reload, err] = useAsync<Dict[]>(
    () => api.get(`${c()}/entities/${entityId}/links`), [entityId])
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState<Dict | null>(null)
  const [oops, setOops] = useState('')
  const [visNow, setVisNow] = useState<Dict>({})

  // ответ сервера — источник правды; локальный слепок нужен лишь на время запроса
  useEffect(() => { setVisNow(m => (Object.keys(m).length ? {} : m)) }, [rows])

  const list = (rows || []).filter(r => r && r.peer)
    .sort((a, b) => String(a.peer.name || '').localeCompare(String(b.peer.name || ''), 'ru'))

  const drop = async (r: Dict) => {
    if (!confirm(t('links.delete_confirm', { name: r.peer.name }))) return
    setOops('')
    try {
      await api.del(`${c()}/links/${r.id}`)
      reload()
    } catch (e: any) {
      setOops(e?.message || t('links.delete_failed'))
    }
  }

  const visOf = (r: Dict): Dict =>
    visNow[r.id] || { visibility: r.visibility || 'crew', visible_to: r.visible_to || [] }

  const setVis = async (r: Dict, v: string, to: string[]) => {
    const next = { visibility: v, visible_to: v === 'selected' ? to : [] }
    setVisNow(m => ({ ...m, [r.id]: next }))
    setOops('')
    try {
      await api.patch(`${c()}/links/${r.id}`, next)
      reload()
    } catch (e: any) {
      setVisNow(m => { const n = { ...m }; delete n[r.id]; return n })
      setOops(e?.message || t('links.vis_failed'))
    }
  }

  return (
    <div className="col">
      <div className="row">
        <h3>{t('links.title')}</h3>
        <div className="spacer" />
        {!readonly && !err && (
          <button className="tiny btn-ico" title={t('links.add_tip')}
            onClick={() => { setOops(''); setAdding(true) }}>
            <IconPlus size={13} />{t('links.add')}
          </button>
        )}
      </div>

      {err && <div className="empty">{t('links.unavailable')}</div>}
      {!err && loading && <div className="dim">{t('common:loading')}</div>}
      {!err && !loading && list.length === 0 && <div className="empty">{t('links.empty')}</div>}
      {oops && <div className="lnk-err">{oops}</div>}

      {!err && list.length > 0 && (
        <div className="lnk-list">
          {list.map(r => (
            <div key={r.id} className={`lnk${isGM && visOf(r).visibility === 'gm' ? ' gm-only' : ''}`}>
              <Link to={`/entity/${r.peer.id}`}><Thumb e={r.peer} /></Link>
              <div className="lnk-main">
                <div className="lnk-head">
                  <div className="lnk-id">
                    <Link className="lnk-name" to={`/entity/${r.peer.id}`}>{r.peer.name}</Link>
                    <span className="lnk-kind">{L(r.peer.kind)}</span>
                  </div>
                  <div className="lnk-side">
              {!readonly && (r.can_edit || r.can_delete) && (
                <div className="lnk-acts">
                  {r.can_edit && (
                    <IconButton icon={<IconEdit />} title={t('links.edit_tip')}
                      onClick={() => { setOops(''); setEditing(r) }} />
                  )}
                  {r.can_delete && (
                    <IconButton icon={<IconTrash />} title={t('links.delete_tip')} danger
                      onClick={() => drop(r)} />
                  )}
                </div>
              )}
                <VisibilityMenu value={visOf(r).visibility} visibleTo={visOf(r).visible_to} compact
                  disabled={readonly || !r.can_edit}
                  onChange={(v, to) => setVis(r, v, to)} />
                  </div>
                </div>
                {r.label && <div className="lnk-lbl" title={phrase(r, name)}>{phrase(r, name)}</div>}
                {r.peer.summary && <div className="lnk-sub" title={r.peer.summary}>{r.peer.summary}</div>}
              </div>
            </div>
          ))}
        </div>
      )}

      {adding && (
        <AddLink entityId={entityId} name={name}
          onClose={() => setAdding(false)}
          onDone={() => { setAdding(false); reload() }} />
      )}

      {editing && (
        <EditLink link={editing} name={name}
          onClose={() => setEditing(null)}
          onDone={() => { setEditing(null); reload() }} />
      )}
    </div>
  )
}

/* --- новая связь ----------------------------------------------------------- */

function AddLink({ entityId, name, onClose, onDone }: {
  entityId: string; name?: string; onClose: () => void; onDone: () => void
}) {
  const { t } = useTranslation('entity')
  const [picked, setPicked] = useState<Dict | null>(null)
  const [label, setLabel] = useState('')
  const [vis, setVis] = useState('crew')
  const [to, setTo] = useState<string[]>([])
  const [oops, setOops] = useState('')
  const [busy, setBusy] = useState(false)

  const save = async () => {
    if (!picked) return
    setBusy(true); setOops('')
    try {
      await api.post(`${c()}/links`, {
        from_id: entityId, to_id: picked.id, label: label.trim(),
        visibility: vis, visible_to: to,
      })
      onDone()
    } catch (e: any) {
      setOops(e?.message || t('links.create_failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={t('links.new_title')} onClose={onClose} watch={[picked?.id || '', label, vis, to]}
      dirtyAsk={t('links.new_dirty')}>
      <EntityPicker label={t('links.whom')} value={picked} onChange={setPicked}
        exclude={entityId} autoFocus />

      <LabelField value={label} onChange={setLabel}
        subject={quoted(name)} object={quoted(picked?.name) || t('links.whom_ph')} />

      <div className="field">
        <label>{t('who_sees')}</label>
        <div className="row wrap">
          <VisibilityMenu value={vis} visibleTo={to}
            onChange={(v, sel) => { setVis(v); setTo(sel) }} />
        </div>
      </div>

      {oops && <div className="lnk-err" style={{ marginBottom: 8 }}>{oops}</div>}
      <button className="primary" disabled={!picked || busy} onClick={save}>{t('links.add')}</button>
    </Modal>
  )
}

/* --- правка связи ---------------------------------------------------------- */

function EditLink({ link, name, onClose, onDone }: {
  link: Dict; name?: string; onClose: () => void; onDone: () => void
}) {
  const { t } = useTranslation('entity')
  const back = link.direction === 'in'
  const subject = back ? quoted(link.peer?.name) : quoted(name)
  const object = back ? quoted(name) : quoted(link.peer?.name)
  const [label, setLabel] = useState(String(link.label || ''))
  const [vis, setVis] = useState(String(link.visibility || 'crew'))
  const [to, setTo] = useState<string[]>(link.visible_to || [])
  const [oops, setOops] = useState('')
  const [busy, setBusy] = useState(false)

  const save = async () => {
    setBusy(true); setOops('')
    try {
      await api.patch(`${c()}/links/${link.id}`, {
        label: label.trim(), visibility: vis, visible_to: to,
      })
      onDone()
    } catch (e: any) {
      setOops(e?.message || t('links.save_failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={t('links.edit_title', { name: link.peer?.name || '' })} onClose={onClose} watch={[label, vis, to]}
      dirtyAsk={t('links.edit_dirty')}>
      <LabelField value={label} onChange={setLabel} subject={subject} object={object} />

      <div className="field">
        <label>{t('who_sees')}</label>
        <div className="row wrap">
          <VisibilityMenu value={vis} visibleTo={to}
            onChange={(v, sel) => { setVis(v); setTo(sel) }} />
        </div>
      </div>

      {oops && <div className="lnk-err" style={{ marginBottom: 8 }}>{oops}</div>}
      <button className="primary" disabled={busy} onClick={save}>{t('common:save')}</button>
    </Modal>
  )
}
