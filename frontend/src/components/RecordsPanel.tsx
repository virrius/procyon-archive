import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { locale } from '../i18n'
import { api, c, isPublicView, store, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import { Chip, Input, Modal, VIS_CLASS } from '../ui'
import { Link } from 'react-router-dom'
import { IconButton, IconClose, IconEdit, IconPlus, IconTrash } from './icons'
import VisibilityMenu from './VisibilityMenu'
import Foldable from './Foldable'
import EntityPicker from './EntityPicker'
import '../styles.records.css'

const FALLBACK_TYPES = ['text', 'rumor', 'secret', 'warning', 'quote']

function fmtWhen(s?: string | null): string {
  if (!s) return ''
  const d = new Date(/(Z|[+-]\d\d:?\d\d)$/.test(s) ? s : `${s}Z`)
  if (isNaN(d.getTime())) return ''
  return d.toLocaleString(locale(), {
    day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

export function RecordsPanel({ entityType, entityId, title, readOnly, onOpen }:
  {
    entityType: string; entityId: string; title?: string
    /** read only: a quick view of the card */
    readOnly?: boolean
    /** a record's link opens in place, without leaving the page */
    onOpen?: (id: string, name: string) => void
  }) {
  const { campaign, isGM, meta, memberName, L } = useApp()
  const { t } = useTranslation('entity')
  const readonly = isPublicView() || !!readOnly  // showcase for the table: read only
  const [rows, loading, reload, loadErr] = useAsync<Dict[]>(
    () => api.get(`${c()}/blocks/${entityType}/${entityId}`), [entityType, entityId])
  const [form, setForm] = useState<Dict | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [visNow, setVisNow] = useState<Dict>({})

  // the server reply is the source of truth; the local snapshot is only needed during the request
  useEffect(() => { setVisNow(m => (Object.keys(m).length ? {} : m)) }, [rows])

  const myId = campaign?.my_member_id
  const types: string[] = meta?.block_types?.length ? meta.block_types : FALLBACK_TYPES

  const list = useMemo(() => (rows || []).slice().sort((a, b) =>
    (a.order || 0) - (b.order || 0) ||
    String(a.created_at || '').localeCompare(String(b.created_at || ''))), [rows])

  const byGm = (b: Dict) => b.by_gm ?? b.created_by_gm ?? false
  const canEdit = (b: Dict) => b.can_edit ?? (isGM || (!!myId && b.created_by === myId))
  const canDrop = (b: Dict) => b.can_delete ?? canEdit(b)
  const canSetVis = canEdit

  const visOf = (b: Dict): Dict =>
    visNow[b.id] || { visibility: b.visibility || 'crew', visible_to: b.visible_to || [] }

  const startNew = () => {
    setErr('')
    setForm({
      block_type: types.includes('text') ? 'text' : types[0], title: '', content: '',
      links: [], link_names: {}, visibility: 'crew', visible_to: [], vis_open: true, fresh: true,
    })
  }

  const startEdit = (b: Dict) => {
    setErr('')
    setForm({
      id: b.id, block_type: b.block_type || 'text', title: b.title || '', content: b.content || '',
      links: Array.isArray(b.links) ? b.links : [], link_names: b.link_names || {},
      visibility: visOf(b).visibility, visible_to: visOf(b).visible_to,
      vis_open: canSetVis(b), vis_known: b.visibility != null, vis_touched: false,
    })
  }

  const save = async () => {
    if (!form || busy) return
    const body: Dict = {
      block_type: form.block_type || 'text',
      title: (form.title || '').trim(),
      content: form.content || '',
      links: Array.isArray(form.links) ? form.links : [],
    }
    if (form.vis_open && (form.fresh || form.vis_known || form.vis_touched)) {
      body.visibility = form.visibility || 'crew'
      body.visible_to = form.visibility === 'selected' ? (form.visible_to || []) : []
    }
    setBusy(true); setErr('')
    try {
      if (form.id) await api.patch(`${c()}/blocks/${form.id}`, body)
      else await api.post(`${c()}/blocks/${entityType}/${entityId}`, body)
      setForm(null); reload()
    } catch (e: any) {
      setErr(e?.message || t('rec.save_failed'))
    } finally { setBusy(false) }
  }

  const setVis = async (b: Dict, v: string, to: string[]) => {
    const next = { visibility: v, visible_to: v === 'selected' ? to : [] }
    setVisNow(m => ({ ...m, [b.id]: next }))
    setErr('')
    try {
      await api.patch(`${c()}/blocks/${b.id}`, next)
      reload()
    } catch (e: any) {
      setVisNow(m => { const n = { ...m }; delete n[b.id]; return n })
      setErr(e?.message || t('rec.vis_failed'))
    }
  }

  const drop = async (b: Dict) => {
    if (!confirm(b.title ? t('rec.delete_confirm_titled', { title: b.title }) : t('rec.delete_confirm'))) return
    setErr('')
    try { await api.del(`${c()}/blocks/${b.id}`); reload() } catch (e: any) {
      setErr(e?.message || t('rec.delete_failed'))
    }
  }


  return (
    <section className="rec-panel">
      <div className="rec-hd">
        <span className="t">{title || t('rec.title')}</span>
        {list.length > 0 && <span className="rec-count">{list.length}</span>}
        <div className="spacer" />
        {!readonly && (
          <button className="tiny btn-ico" onClick={startNew} title={t('rec.add_tip')}>
            <IconPlus size={13} />{t('rec.add')}
          </button>
        )}
      </div>

      {!form && (err || loadErr) && <div className="rec-err">{err || loadErr}</div>}
      {loading && !rows && <div className="rec-empty">{t('common:loading')}</div>}
      {!loading && !loadErr && list.length === 0 && (
        <div className="rec-empty">{t('rec.empty')}</div>
      )}

      <div className="rec-list">
        {list.map(b => {
          const gm = byGm(b)
          const author = b.author_name || memberName(b.created_by)
          const editor = b.editor_name || memberName(b.edited_by)
          const when = fmtWhen(b.updated_at || b.created_at)
          const vis = visOf(b)
          return (
            <article key={b.id} className={`rec ${VIS_CLASS[vis.visibility] || 'crew-block'} reveal`}>
              <div className="rec-top">
                {b.title && <h4 className="rec-title">{b.title}</h4>}
                {b.block_type && b.block_type !== 'text' && <Chip>{L(b.block_type)}</Chip>}
                {gm && (
                  <span className="rec-lock"
                    title={t('rec.gm_lock_tip')}>
                    <i />{t('rec.gm_lock')}
                  </span>
                )}
                <div className="spacer" />
                <VisibilityMenu value={vis.visibility} visibleTo={vis.visible_to}
                  disabled={readonly || !canEdit(b) || !canSetVis(b)}
                  hint={gm && !isGM ? t('rec.gm_vis_hint') : undefined}
                  onChange={(v, to) => setVis(b, v, to)} />
                {!readonly && (
                  <span className="rec-acts">
                    {canEdit(b) && (
                      <IconButton icon={<IconEdit />} title={t('rec.edit_tip')}
                        onClick={() => startEdit(b)} />
                    )}
                    {canDrop(b) && !(gm && !isGM) && (
                      <IconButton icon={<IconTrash />} title={t('rec.delete_tip')} danger
                        onClick={() => drop(b)} />
                    )}
                  </span>
                )}
              </div>

              {b.content
                ? <Foldable className="rec-text">{b.content}</Foldable>
                : <div className="rec-text none">{t('rec.no_text')}</div>}

              {Array.isArray(b.links) && b.links.length > 0 && (
                <div className="rec-links">
                  {b.links.map((lid: string) => {
                    const name = b.link_names?.[lid]
                    return name
                      ? <Link key={lid} className="rec-link" to={`/entity/${lid}/profile`}
                          onClick={onOpen && (ev => {
                            if (ev.ctrlKey || ev.metaKey || ev.shiftKey) return
                            ev.preventDefault(); onOpen(lid, name)
                          })}>{name}</Link>
                      : <span key={lid} className="rec-link off">{t('rec.card_unavailable')}</span>
                  })}
                </div>
              )}

              <div className="rec-meta">
                {author && <span className="who">{author}</span>}
                {editor && editor !== author && <>
                  {author && <span className="sep">·</span>}<span>{t('rec.edited_by', { name: editor })}</span>
                </>}
                {when && <>
                  {(author || editor) && <span className="sep">·</span>}<span>{when}</span>
                </>}
              </div>
            </article>
          )
        })}
      </div>

      {form && (
        <Modal title={form.id ? t('rec.edit_title') : t('rec.new_title')} onClose={() => setForm(null)}
          watch={form}
          dirtyAsk={t('rec.dirty')}>
          {err && <div className="rec-err" style={{ marginBottom: 11 }}>{err}</div>}
          <Input label={t('rec.f_title')} value={form.title}
            onChange={v => setForm({ ...form, title: v })} />
          <Input label={t('rec.f_text')} type="textarea" rows={9} value={form.content}
            onChange={v => setForm({ ...form, content: v })} />
          <LinkPick value={form.links || []} names={form.link_names || {}}
            onChange={(v: string[], names: Dict) => setForm({ ...form, links: v, link_names: names })} />
          {form.vis_open && (
            <div className="field">
              <label>{t('who_sees')}</label>
              <div className="row wrap">
                <VisibilityMenu value={form.visibility} visibleTo={form.visible_to || []}
                  onChange={(v, to) => setForm({ ...form, visibility: v, visible_to: to, vis_touched: true })} />
              </div>
            </div>
          )}
          <div className="rec-form-acts">
            <button className="primary" onClick={save}
              disabled={busy || (!String(form.content || '').trim() && !String(form.title || '').trim())}>
              {t('common:save')}
            </button>
            <button className="ghost" onClick={() => setForm(null)}>{t('rec.cancel')}</button>
          </div>
        </Modal>
      )}
    </section>
  )
}

export default RecordsPanel

/* --- picking linked entities -------------------------------------------------- */

/** Record links: picks as chips, new ones are found by the same picker as everywhere. Names of
    already linked cards come with the record. */
function LinkPick({ value, names, onChange }: {
  value: string[]
  names: Dict
  onChange: (v: string[], names: Dict) => void
}) {
  const { t } = useTranslation('entity')
  return (
    <div className="field">
      <label>{t('rec.links_label')}</label>
      {value.length > 0 && (
        <div className="rec-links">
          {value.map(id => (
            <span key={id} className="rec-link on">
              {names[id] || t('rec.no_card')}
              <IconButton icon={<IconClose />} title={t('rec.unlink')}
                onClick={() => onChange(value.filter(x => x !== id), names)} />
            </span>
          ))}
        </div>
      )}
      <EntityPicker label="" value={null} exclude={value} placeholder={t('rec.link_ph')}
        onChange={e => { if (e) onChange([...value, e.id], { ...names, [e.id]: e.name }) }} />
    </div>
  )
}
