import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { api, c, isPublicView, type Dict, thumb } from '../api'
import { useApp, useAsync } from '../ctx'
import {
  asList, ColorPicker, Modal, MultiPick, Select, VisChip, rankRoman, statusTone,
} from '../ui'
import { IconImage, IconPlus, IconSpark } from '../components/icons'
import CropModal from '../components/CropModal'
import EntityPicker from '../components/EntityPicker'
import { FieldEye } from '../components/FieldEye'
import { ImgActions, ImgFlags } from '../components/ImageTools'
import Studio, { type BrushSource } from '../components/studio/Studio'
import MediaPickModal from '../components/MediaPickModal'
import Lightbox from '../components/Lightbox'
import Stub from '../components/Stub'
import VisibilityMenu from '../components/VisibilityMenu'
import { ANY_PLAYER, OwnerMenu } from '../components/OwnerMenu'
import { AffiliationPicker, AffiliationView } from '../components/AffiliationPicker'
import PasteImage from '../paste'
import LinksPanel from '../components/LinksPanel'
import EntityMedia from '../components/EntityMedia'
import EntityClocks from '../components/EntityClocks'
import { RecordsPanel } from '../components/RecordsPanel'
import CharacterSheet from '../components/charsheet/CharacterSheet'

// the route still accepts /profile,/records,/links,/media — there are no subtabs anymore,
// all content renders as one page; the redirect is kept for old links
const SUBS: [string, string][] = [
  ['profile', ''], ['records', ''], ['links', ''], ['media', ''],
]

const BACK: Record<string, [string, string]> = {
  npc: ['/database/npc', 'back.npc'],
  faction: ['/database/factions', 'back.faction'],
  location: ['/database/locations', 'back.location'],
  character: ['/crew/team', 'back.character'],
  ship: ['/crew/ship', 'back.ship'],
  crew: ['/crew/team', 'back.crew'],
  item: ['/crew/items', 'back.item'],
}

// the portrait is the card's main mark: a frame across the full column width, height from the frame itself.
// no fixed aspect ratio: any frame fits the box snugly, with no empty margins at the edges
const PHOTO: Dict = { width: '100%', height: 'auto', display: 'block' }
// there is no frame placeholder — keep a vertical box for it
const NOIMG: Dict = {
  width: '100%', aspectRatio: '3 / 4', display: 'grid', placeItems: 'center',
  fontFamily: 'var(--util)', fontSize: 26, letterSpacing: '.12em', color: 'var(--dim2)',
}
const ERR: Dict = {
  color: '#e08a70', background: '#251712', border: '1px solid #5c3327', padding: '5px 8px',
}

// field hidden by the GM: it has a value, but the table doesn't know it
function Unknown() {
  const { t } = useTranslation('entity')
  return <span className="unknown" title={t('unknown_tip')}>?</span>
}
const UNKNOWN = <Unknown />

const text = (v: any): string =>
  v === null || v === undefined ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v)

/** Entity card: its own route /entity/:id and a window over the gallery (id + onClose).
 *  In the window the gallery stays mounted — search, filters and grouping are not reset. */
export default function EntityPage({ id: idProp, onClose, fresh }: {
  id?: string; onClose?: () => void
  /** just-created card: open the name for editing right away */
  fresh?: boolean
}) {
  const { pathname } = useLocation()
  const parts = pathname.split('/').filter(Boolean)
  const routeId = useParams().id || parts[1] || ''
  const inModal = !!onClose
  const id = idProp || routeId
  const tab = inModal ? 'profile' : (SUBS.some(([k]) => k === parts[2]) ? parts[2] : '')

  const nav = useNavigate()
  const { meta, campaign, isGM, L } = useApp()
  const { t } = useTranslation('entity')

  const [loaded, , reload, loadErr] = useAsync<Dict>(
    () => api.get(`${c()}/entities/${id}`), [id])

  const [e, setE] = useState<Dict | null>(null)
  const [busy, setBusy] = useState(false)
  const [oops, setOops] = useState('')
  const [bump, setBump] = useState(0)
  const [genOpen, setGenOpen] = useState(false)
  const [brushSrc, setBrushSrc] = useState<BrushSource | null>(null)
  const [genJob, setGenJob] = useState<Dict | null>(null)
  const [pickOpen, setPickOpen] = useState(false)
  const [cropOpen, setCropOpen] = useState(false)
  const [fullPhoto, setFullPhoto] = useState(false)
  // the dossier is edited in place: clicking a value opens that one field, clicking outside or Esc closes it
  const [act, setAct] = useState<string | null>(null)
  const [sumOpen, setSumOpen] = useState(false)

  useEffect(() => { setE(loaded && loaded.id === id ? loaded : null); setOops('') }, [loaded, id])
  useEffect(() => { setAct(fresh ? 'name' : null) }, [id])  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!act) return
    const box = () => document.querySelector(`[data-act="${act}"]`)
    const first = box()?.querySelector<HTMLElement>('input, textarea')
    if (first) first.focus()
    else box()?.querySelector<HTMLElement>('.drop-btn')?.click()
    const close = () => {
      (document.activeElement as HTMLElement | null)?.blur()
      setAct(null)
    }
    // the click that opened the field still bubbles up to the document — ignore it
    const since = performance.now()
    const away = (ev: MouseEvent) => {
      if (ev.timeStamp < since) return
      const t = ev.target as HTMLElement
      // a button inside the field may already be gone after its own click — that's not "outside"
      if (!t.isConnected) return
      if (t.closest(`[data-act="${act}"]`) || t.closest('.drop-pop') || t.closest('.lnk-hits')) return
      close()
    }
    const esc = (ev: KeyboardEvent) => { if (ev.key === 'Escape') close() }
    document.addEventListener('click', away)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('click', away)
      document.removeEventListener('keydown', esc)
    }
  }, [act, !!e])

  const readonly = isPublicView()  // table view is read-only

  // edit rights: the GM always; the ship/crew is a shared resource any player can edit;
  // everything else only the card's owner (assigned by the GM).
  // Generation changes the card, so it needs the same rights — not GM-only
  const isShared = e?.kind === 'ship'
  const isOpenEdit = e?.owner_member_id === ANY_PLAYER
  const myMemberId = campaign?.my_member_id
  const isObserver = campaign?.my_role === 'observer'
  const canEdit = !!e && !readonly && !isObserver && (isGM || isShared || isOpenEdit ||
    (!!myMemberId && !!e.owner_member_id && e.owner_member_id === myMemberId))

  useEffect(() => {
    if (!canEdit || !id) { setGenJob(null); return }
    let dead = false
    api.get(`${c()}/entities/${id}/image-jobs/active`).then(r => { if (!dead) setGenJob(r.job) }).catch(() => {})
    return () => { dead = true }
  }, [canEdit, id, genOpen])

  if (!tab) return <Navigate to={`/entity/${id}/profile`} replace />
  const leave = () => (onClose ? onClose() : nav(BACK[e?.kind || '']?.[0] || '/database'))

  if (loadErr) {
    return (
      <div className="panel col">
        <h2>{t('page.unavailable')}</h2>
        <div className="dim">{loadErr}</div>
        <div>
          <button className="ghost tiny" onClick={leave}>← {t('page.back_section')}</button>
        </div>
      </div>
    )
  }
  if (!e) return <div className="dim">{t('common:loading')}</div>
  // a character is shown by its sheet: as its own page in the Team section, over a board in the same window
  if (e.kind === 'character') {
    return inModal ? <CharacterSheet id={id} onClose={onClose} /> : <Navigate to={`/crew/team/${id}`} replace />
  }

  const def: Dict = meta?.kinds?.[e.kind] || {}
  const kindLabel = def.label || L(e.kind) || e.kind
  const [backTo, backLabel] = BACK[e.kind] || ['/database', 'back.database']
  const own: Dict = e.fields || {}

  // own membership makes no sense: a location isn't inside a location, a faction isn't part of itself
  const showLoc = e.kind !== 'location'
  const showFac = e.kind !== 'faction'
  const locLabel = e.kind === 'faction' ? t('hq') : t('place')

  // per-field visibility: a key in hidden_fields = the GM has the field, the table doesn't get it
  const hidden = new Set<string>((e.hidden_fields || []) as string[])

  // Tier is a field shared by all kinds and shown in the header, so it's removed from the kind's own fields
  const rankDef: Dict | undefined = (def.fields || []).find((f: Dict) => f.key === 'rank')
  const rankVal = text(own.rank)
  // Tier sits on the right of the header: for editors always (dimmed when empty), for the table only when set
  const showRank = !!rankDef && (rankVal !== '' || hidden.has('rank') || (canEdit && (isGM || !hidden.has('rank'))))

  const showAlias = e.kind === 'npc'
  const hasStatuses = (def.statuses || []).length > 0


  // the server never sends gm_ keys to the table (strip_gm_fields) — so no label is drawn for them
  const defs: Dict[] = (def.fields || [])
    .filter((f: Dict) => f.key !== 'rank')
    .filter((f: Dict) => isGM || !String(f.key).startsWith('gm_'))
  // text() renders an empty list as "[]" — so multi fields are checked by length
  const filled = (f: Dict) => (f.type === 'multi' ? asList(own[f.key]).length > 0
    : f.type === 'ref' ? !!e.peer_names?.[text(own[f.key])]
    : text(own[f.key]) !== '')
  const shown = defs.filter(f => filled(f) || hidden.has(f.key) || act === f.key)


  const showVis = canEdit || (isGM && !!e.visibility)

  // in read mode an empty field is an orphaned label, so only filled ones are shown
  const showFacField = showFac && (act === 'faction_ids' || hidden.has('faction_ids') || (e.faction_ids || []).length > 0)
  const showLocField = showLoc && (act === 'location_ids' || hidden.has('location_ids') || (e.location_ids || []).length > 0)
  const showAff = showFacField || showLocField

  const push = async (patch: Dict) => {
    const prev = e
    setE({ ...e, ...patch, ...(patch.fields ? { fields: { ...own, ...patch.fields } } : {}) })
    setBusy(true); setOops('')
    try {
      const r = await api.patch(`${c()}/entities/${id}`, patch)
      if (r && r.id) setE(r)
    } catch (ex: any) {
      setE(prev); setOops(ex?.message || t('page.save_failed'))
    }
    setBusy(false)
  }
  // only one key is sent: fields someone else is editing at the same time aren't overwritten
  const setOwn = (key: string, v: any) => push({ fields: { [key]: v } })

  // the rust "hidden" mark is a GM working signal; display mode has none
  const shut = (key: string) => (isGM && hidden.has(key) ? ' shut' : '')
  // a player can't edit a hidden field: their value is empty, and the server would reject the edit
  const locked = (key: string) => !isGM && hidden.has(key)
  // field is open for in-place editing
  const on = (key: string) => canEdit && act === key && !locked(key)
  // a value you can click to edit
  const able = (key: string) => (canEdit && !locked(key)
    ? { className: 'ed-able', title: t('page.click_to_edit'), onClick: () => setAct(key) }
    : {})
  const setHidden = (key: string, hide: boolean) => {
    const next = new Set(hidden)
    if (hide) next.add(key)
    else next.delete(key)
    push({ hidden_fields: [...next] })
  }
  // a gm_ field never goes to the table — there is no "hide" eye to toggle
  const eye = (key: string) => isGM && !key.startsWith('gm_')
    && !(e.kind === 'faction' && key === 'stance') && (
    <FieldEye hidden={hidden.has(key)} onChange={hide => setHidden(key, hide)} />
  )
  // field label: the eye right after the word; a hidden field's label is rust-colored
  const fieldLabel = (key: string, label: string) => (
    <div className={`fld-lbl${shut(key) ? ' off' : ''}`}>{label}{eye(key)}</div>
  )

  // the normal status ("active") isn't shown — the mark appears only when it differs
  const statusWord = locked('status') ? '?' : L(e.status) || e.status || ''
  const canStamp = canEdit && !locked('status')

  const upload = async (file: File, asPhoto: boolean) => {
    setBusy(true); setOops('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('target_type', 'entity')
      fd.append('target_id', id)
      const up = await api.post(`${c()}/upload`, fd)
      setBump(b => b + 1)
      if (asPhoto && canEdit && up?.url) await push({ image_url: up.url })
    } catch (ex: any) {
      setOops(ex?.message || t('page.upload_failed'))
    }
    setBusy(false)
  }

  const purge = async () => {
    if (!confirm(t('page.purge_confirm', { name: e.name || t('no_name') }))) return
    setOops('')
    try { await api.del(`${c()}/entities/${id}/purge`); leave() }
    catch (ex: any) { setOops(ex?.message || t('page.purge_failed')) }
  }

  const archive = async () => {
    if (!confirm(t('page.archive_confirm', { name: e.name }))) return
    setOops('')
    try { await api.del(`${c()}/entities/${id}`); leave() }
    catch (ex: any) { setOops(ex?.message || t('page.archive_failed')) }
  }

  const ownEditor = (f: Dict) => {
    const v = own[f.key]
    if (f.type === 'multi') {
      return <MultiPick options={f.options || []} value={v} max={f.max} onChange={x => setOwn(f.key, x)} />
    }
    if (f.type === 'select') {
      return (
        <Select value={text(v)} options={f.options || []} title={f.label}
          onChange={x => setOwn(f.key, x)} />
      )
    }
    if (f.type === 'textarea') return <Area value={text(v)} rows={4} onSave={x => setOwn(f.key, x)} />
    if (f.type === 'ref') {
      // start with a search for the current name: picking replaces it, a cleared line (Enter or blur) clears it
      const was = e.peer_names?.[text(v)] || ''
      return (
        <EntityPicker label="" kind={f.kinds} exclude={e.id} listed
          placeholder={t('start_typing')} initialQ={was}
          value={null}
          onChange={x => { if (x) { setOwn(f.key, x.id); setAct(null) } }}
          onEmpty={() => { setOwn(f.key, ''); setAct(null) }} />
      )
    }
    return <Line value={text(v)} onSave={x => setOwn(f.key, x)} />
  }

  const readVal = (f: Dict) => {
    if (locked(f.key)) return UNKNOWN
    const v = own[f.key]
    if (f.type === 'multi') return asList(v).join(', ')
    if (f.type === 'select') return L(text(v)) || text(v)
    if (f.type === 'ref') return text(v) && (e.peer_names?.[text(v)] || '')
    return text(v)
  }
  const fact = (f: Dict) => (
    <div key={f.key} data-act={f.key}
      className={`dos-fact${f.type === 'ref' && on(f.key) ? ' wide' : ''}${shut(f.key)}`}>
      {fieldLabel(f.key, f.label)}
      {on(f.key)
        ? ownEditor(f)
        : <div {...able(f.key)}><div className="dos-val">{readVal(f) || <span className="dim2">—</span>}</div></div>}
    </div>
  )
  // empty fields are hidden in read mode — they can be added from here, the field opens in place
  const blanks: [string, string][] = [
    ...(showFac && !showFacField ? [['faction_ids', t('factions')] as [string, string]] : []),
    ...(showLoc && !showLocField ? [['location_ids', locLabel] as [string, string]] : []),
    ...defs.filter(f => !shown.includes(f) && !locked(f.key)).map(f => [f.key, f.label] as [string, string]),
  ]
  const short = shown.filter(f => f.type !== 'textarea')
  const long = shown.filter(f => f.type === 'textarea')
  const summaryLocked = locked('summary')
  // a long description reads collapsed and expands with a button
  const longSum = !summaryLocked && String(e.summary || '').length > 320

  const acts = (canEdit || isGM) && <>
    {canEdit && !e.archived && (
      <button className="ghost tiny" onClick={archive}>{t('page.to_archive')}</button>
    )}
    {canEdit && e.archived && (
      <button className="tiny" onClick={() => push({ archived: false })}>{t('page.unarchive')}</button>
    )}
    {isGM && (
      <button className="ghost tiny danger" onClick={purge}>{t('common:delete')}</button>
    )}
  </>

  return (
    <div className="col dos-page">
      {/* Ctrl+V right on the card — the pasted image becomes the portrait */}
      <PasteImage enabled={canEdit && !locked('image_url')}
        question={e.image_url
          ? t('page.paste_replace', { name: e.name })
          : t('page.paste_set', { name: e.name })}
        onFiles={files => upload(files[0], true)} />
      <div className="dos-bar">
        {!inModal && (
          <button className="ghost tiny" onClick={() => nav(backTo)}>← {t(backLabel)}</button>
        )}
        <div className="spacer" />
        {busy && <span className="dos-busy">{t('page.saving')}</span>}
        {isGM && !isShared && (
          <OwnerMenu value={e.owner_member_id} onChange={v => push({ owner_member_id: v })} />
        )}
        {showVis && (
          canEdit
            ? <VisibilityMenu value={e.visibility || 'crew'} visibleTo={e.visible_to || []}
                onChange={(v, to) => push({ visibility: v, visible_to: to })} />
            : <VisChip v={e.visibility} />
        )}
        {acts && <span className="dos-acts-row">{acts}</span>}
        {acts && (
          <details className="dos-acts" onToggle={ev => {
            const d = ev.currentTarget
            if (!d.open) return
            const shut = (x: MouseEvent) => {
              if (!d.contains(x.target as Node) || (x.target as HTMLElement).closest('button')) {
                d.open = false; document.removeEventListener('click', shut)
              }
            }
            setTimeout(() => document.addEventListener('click', shut))
          }}>
            <summary className="ghost tiny" aria-label={t('page.more')}>⋯</summary>
            <div className="dos-acts-list">{acts}</div>
          </details>
        )}
      </div>

      {oops && <div className="mono" style={ERR}>{oops}</div>}

      <div className="dos">
        <div className="dos-shot">
          <div className="ent-photo imgbox">
            {e.image_url
              ? <img className="avatar zoomable" style={PHOTO} src={thumb(e.image_url, 480, bump)}
                  alt={e.name}
                  title={t('view_full')} onClick={() => setFullPhoto(true)} />
              : <Stub kind={e.kind} sub={own.job_type} className="avatar" style={NOIMG} />}

            <ImgFlags hidden={isGM && hidden.has('image_url')} busy={!!genJob} mark={locked('image_url')} />
            {!locked('image_url') && (
              <ImgActions
                vis={isGM ? {
                  hidden: hidden.has('image_url'), onChange: hide => setHidden('image_url', hide),
                } : undefined}
                inpaint={isGM && e.image_url ? {
                  title: t('page.inpaint_portrait'), onClick: () => {
                    setBrushSrc({ id: e.image_url.split('/').pop() || '', url: e.image_url, title: t('page.portrait'), sub: '' })
                    setGenOpen(true)
                  },
                } : undefined}
                crop={canEdit && e.image_url ? {
                  title: t('page.crop'), onClick: () => setCropOpen(true),
                } : undefined}
                gen={canEdit ? {
                  title: genJob ? t('page.gen_running') : t('page.gen'),
                  onClick: () => { setBrushSrc(null); setGenOpen(true) }, on: !!genJob,
                } : undefined}
                upload={canEdit ? {
                  title: e.image_url ? t('page.replace_photo_tip') : t('page.upload_photo_tip'),
                  onFile: file => upload(file, true),
                } : undefined}
                pick={canEdit ? {
                  title: t('page.pick_media'), onClick: () => setPickOpen(true),
                } : undefined}
                remove={canEdit && e.image_url ? {
                  title: t('page.remove_photo'), onClick: () => push({ image_url: '' }),
                } : undefined} />
            )}
            {hasStatuses && (canStamp || !!statusWord) && (
              <div className={`ent-stamp-wrap${canStamp ? ' edit' : ''}`}>
                <div className={`ent-stamp t-${statusTone(e.status)}`
                  + (statusWord ? '' : ' blank')}>
                  <span className="t">{statusWord || t('page.status_blank')}</span>
                </div>
                {canStamp && (
                  <Select className="ent-stamp-pick" value={e.status || ''} title={t('status')}
                    options={def.statuses || []} onChange={v => push({ status: v })} />
                )}
              </div>
            )}
          </div>
          {canEdit && !locked('image_url') && (
            <div className="dos-shot-acts">
              <label className="dos-upload">
                <input type="file" accept="image/*"
                  onChange={ev => { ev.target.files?.[0] && upload(ev.target.files[0], true); ev.target.value = '' }} />
                <IconImage size={14} />{e.image_url ? t('page.replace_photo') : t('page.upload_photo')}
              </label>
              <button type="button" className="dos-upload" onClick={() => { setBrushSrc(null); setGenOpen(true) }}>
                <IconSpark size={14} />{t('page.generate')}
              </button>
            </div>
          )}
        </div>

        <div className="dos-main">
          <div className="dos-head">
            <div className="dos-id">
              <div className="dos-kicker">
                {!inModal && <span className="dos-kind">{kindLabel}</span>}
                {e.archived && <span className="stamp">{t('page.archived')}</span>}
                {e.kind === 'ship' && <Link className="small" to="/crew/ship">{t('page.ship_sheet')}</Link>}
              </div>

              {on('name')
                ? <div className="dos-nameedit" data-act="name">
                    <span className="ent-namebox">
                      <Line value={e.name} big placeholder={t('page.name_ph')} onSave={v => push({ name: v })} />
                    </span>
                    {showAlias && (
                      <span className="ent-aliasbox">
                        <Line value={e.alias} placeholder={t('page.alias_ph')} onSave={v => push({ alias: v })} />
                      </span>
                    )}
                  </div>
                : <div {...able('name')}>
                    <h1 className="dos-name">{e.name || (e.alias ? t('quoted', { s: e.alias }) : t('no_name'))}</h1>
                    {showAlias && e.alias && e.name && <div className="dos-alias">{t('quoted', { s: e.alias })}</div>}
                  </div>}

            </div>

            {showRank && (
              <div className={`rank-gauge dos-rank${shut('rank')}${rankVal === '' ? ' blank' : ''}`}>
                <span className="rg-lbl">{t('rank')}{eye('rank')}</span>
                <span className={`rg-read${canEdit && !locked('rank') ? ' edit' : ''}`} data-act="rank">
                  <span className={`rg-mark${rankVal === '' ? ' none' : ''}`}>
                    {locked('rank') ? '?' : rankVal === '' ? '—' : rankRoman(rankVal)}
                  </span>
                  {canEdit && !locked('rank') && (
                    <Select className="rg-pick" popCenter value={rankVal} title={t('rank')}
                      options={rankDef?.options || []} optionLabel={rankRoman}
                      onChange={v => setOwn('rank', v)} />
                  )}
                </span>
              </div>
            )}
          </div>

          {on('summary')
            ? <div className={`dos-summary-edit${shut('summary')}`} data-act="summary">
                {fieldLabel('summary', t('summary'))}
                <Area value={e.summary} rows={3}
                  placeholder={t('page.summary_ph')}
                  onSave={v => push({ summary: v })} />
              </div>
            : (summaryLocked || e.summary || canEdit) && (
              <div className={`dos-summary${shut('summary')}`}>
                <span {...able('summary')} className={`${able('summary').className || ''}${longSum && !sumOpen ? ' dos-clamp' : ''}`}>
                  {summaryLocked ? UNKNOWN : e.summary || <span className="dim2">{t('page.summary_empty')}</span>}
                </span>
                {isGM && <span className="dos-summary-eye">{eye('summary')}</span>}
                {longSum && (
                  <button type="button" className="dos-more" onClick={() => setSumOpen(o => !o)}>
                    {sumOpen ? t('page.collapse') : t('page.expand')}
                  </button>
                )}
              </div>
            )}

          {(short.length > 0 || showAff) && (
            <section className="dos-sec">
              <h4 className="dos-sec-t">{t('page.details')}</h4>
              <div className="dos-facts">
                {showFacField && (
                  <div className={`dos-fact${shut('faction_ids')}`} data-act="faction_ids">
                    {fieldLabel('faction_ids', t('factions'))}
                    {on('faction_ids')
                      ? <AffiliationPicker ids={e.faction_ids} kind="faction" names={e.peer_names}
                          onChange={(ids: string[]) => push({ faction_ids: ids })} />
                      : locked('faction_ids')
                        ? <div className="dos-val">{UNKNOWN}</div>
                        : <div {...able('faction_ids')}>
                            <AffiliationView ids={e.faction_ids} kind="faction" names={e.peer_names} />
                          </div>}
                  </div>
                )}
                {showLocField && (
                  <div className={`dos-fact${shut('location_ids')}`} data-act="location_ids">
                    {fieldLabel('location_ids', locLabel)}
                    {on('location_ids')
                      ? <AffiliationPicker ids={e.location_ids} kind="location" names={e.peer_names}
                          onChange={(ids: string[]) => push({ location_ids: ids })} />
                      : locked('location_ids')
                        ? <div className="dos-val">{UNKNOWN}</div>
                        : <div {...able('location_ids')}>
                            <AffiliationView ids={e.location_ids} kind="location" names={e.peer_names} />
                          </div>}
                  </div>
                )}
                {short.map(fact)}
              </div>
            </section>
          )}

          {long.map(f => (
            <section key={f.key} className={`dos-sec dos-prose${shut(f.key)}`} data-act={f.key}>
              {fieldLabel(f.key, f.label)}
              {on(f.key)
                ? ownEditor(f)
                : <p {...able(f.key)}>{readVal(f) || <span className="dim2">—</span>}</p>}
            </section>
          ))}

          {canEdit && blanks.length > 0 && (
            <div className="dos-add">
              {blanks.map(([key, label]) => (
                <button key={key} type="button" className="ghost tiny btn-ico" onClick={() => setAct(key)}>
                  <IconPlus size={11} />{label.toLowerCase()}
                </button>
              ))}
            </div>
          )}

          {/* side panels share the dossier's column — the portrait keeps the whole left edge */}
          <div className="ent-aside">
            <div className="ent-aside-col">
              <div className="ent-sub col">
                <LinksPanel entityId={id} kind={e.kind} name={e.name} />
              </div>
              <div className="ent-sub col">
                <EntityClocks entityId={id} />
              </div>
            </div>
            <div className="ent-sub col">
              <h3>{t('page.media')}</h3>
              <EntityMedia entityId={id} bump={bump} readonly={readonly}
                tail={!readonly && <>
                  <label className="att-add" title={t('page.add_file_tip')}>
                    <input type="file"
                      onChange={ev => { ev.target.files?.[0] && upload(ev.target.files[0], false); ev.target.value = '' }} />
                    <IconPlus size={18} /><span>{t('page.file')}</span>
                  </label>
                  {canEdit && (
                    <button type="button" className="att-add" title={t('page.gen_media')}
                      onClick={() => { setBrushSrc(null); setGenOpen(true) }}>
                      <IconSpark size={18} /><span>{t('page.generate')}</span>
                    </button>
                  )}
                </>}
                onChange={() => setBump(b => b + 1)}
                onBrush={a => {
                  setBrushSrc({ id: a.id, url: a.url, title: a.caption || a.filename || t('page.attachment'), sub: '' })
                  setGenOpen(true)
                }} />
            </div>
          </div>
        </div>
      </div>

      <div className="panel col" style={{ paddingBottom: 18 }}>
        <RecordsPanel entityType="entity" entityId={id}
          title={t('page.records')} />
      </div>

      {genOpen && (
        <Studio entity={e} source={brushSrc}
          onClose={() => setGenOpen(false)}
          onChanged={how => {
            reload(); setBump(b => b + 1)
            if (how === 'avatar') setGenOpen(false)
          }} />
      )}
      {pickOpen && (
        <MediaPickModal entityId={id} current={e.image_url}
          onClose={() => setPickOpen(false)}
          onPick={async url => { await push({ image_url: url }); setPickOpen(false) }} />
      )}
      {cropOpen && e.image_url && (
        <CropModal attachmentId={e.image_url.split('/').pop() || ''} src={e.image_url}
          title={e.name} ratio={e.kind === 'character' || e.kind === 'npc' ? 4 / 5 : 4 / 3}
          onClose={() => setCropOpen(false)}
          onDone={() => { setCropOpen(false); reload(); setBump(b => b + 1) }} />
      )}
      {fullPhoto && e.image_url && (
        <Lightbox src={e.image_url} alt={e.name} onClose={() => setFullPhoto(false)} />
      )}
    </div>
  )
}

/* --- in-place editing: save on leaving the field ---------------------------- */

function Line({ value, onSave, placeholder, big, mono }: {
  value?: string; onSave: (v: string) => void; placeholder?: string
  big?: boolean; mono?: boolean
}) {
  const [v, setV] = useState(value || '')
  useEffect(() => { setV(value || '') }, [value])
  const style: Dict | undefined = mono ? { fontFamily: 'var(--util)', fontSize: 12.5 } : undefined
  return (
    <input value={v} placeholder={placeholder} style={style} className={big ? 'dos-name-in' : undefined}
      onChange={ev => setV(ev.target.value)}
      onBlur={() => { if ((value || '') !== v) onSave(v) }}
      onKeyDown={ev => { if (ev.key === 'Enter') (ev.target as HTMLInputElement).blur() }} />
  )
}

function Area({ value, rows, placeholder, onSave }: {
  value?: string; rows?: number; placeholder?: string; onSave: (v: string) => void
}) {
  const [v, setV] = useState(value || '')
  useEffect(() => { setV(value || '') }, [value])
  // the field grows with the text: editing doesn't squeeze the description into three scrolling lines
  const box = useRef<HTMLTextAreaElement>(null)
  useEffect(() => {
    const el = box.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight + 2}px`
  }, [v])
  return (
    <textarea ref={box} rows={rows || 3} value={v} placeholder={placeholder}
      onChange={ev => setV(ev.target.value)}
      onBlur={() => { if ((value || '') !== v) onSave(v) }} />
  )
}
