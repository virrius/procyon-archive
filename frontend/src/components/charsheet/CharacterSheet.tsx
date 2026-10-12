import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'
import { api, c, isPublicView, type Dict, thumb } from '../../api'
import { useApp, useAsync } from '../../ctx'
import { Select, statusTone, VisChip } from '../../ui'
import { IconPlus, IconSpark } from '../icons'
import CropModal from '../CropModal'
import EntityClocks from '../EntityClocks'
import EntityMedia from '../EntityMedia'
import { FieldEye } from '../FieldEye'
import { ImgActions, ImgFlags } from '../ImageTools'
import Lightbox from '../Lightbox'
import LinksPanel from '../LinksPanel'
import MediaPickModal from '../MediaPickModal'
import { ANY_PLAYER, OwnerMenu } from '../OwnerMenu'
import { RecordsPanel } from '../RecordsPanel'
import Studio, { type BrushSource } from '../studio/Studio'
import Stub from '../Stub'
import { stamp } from '../WorldTime'
import VisibilityMenu from '../VisibilityMenu'
import PasteImage from '../../paste'
import { changedKeys, dict, Lane, Line, readContacts, serContacts, usePhone } from '../sheet/parts'
import { DossierFile } from './Dossier'
import {
  AbilitiesLane, AbilityCards, ActionsLane, ContactsLane, type Ctx, GearLane, IdLine, Identity, PlaybookPick, Rail,
  Reference, Steps, TraumaPick,
} from './lanes'
import { bookOf, effective, playbookKey, pointsOf } from './model'
import '../../styles.entity.css'
import '../../styles.char.css'

const AUTOSAVE_MS = 700
const TABS = ['sheet', 'setup', 'dossier'] as const
type Tab = typeof TABS[number]
// имя, прозвище и описание лежат в карточке, а не в fields — правятся тем же черновиком
const TOP = ['name', 'alias', 'summary'] as const
const topOf = (e: Dict): Dict => ({ name: e.name || '', alias: e.alias || '', summary: e.summary || '' })
const norm = (k: string, v: any) => (k === 'name' ? String(v ?? '').trim() : String(v ?? ''))

/** Персонаж — три вкладки: «Бланк» (игровые отметки, кликаются всегда), «Настройка» (разовые
 *  выборы: бланк, происхождение, навыки, таланты, знакомые) и «Досье». Автосохранение — как у корабля. */
export default function CharacterSheet({ id, onClose }: { id: string; onClose?: () => void }) {
  const nav = useNavigate()
  const { pathname } = useLocation()
  const { meta, campaign, isGM, L } = useApp()
  const { t } = useTranslation('char')
  const { t: te } = useTranslation('entity')
  const phone = usePhone()

  const [loaded, , reload, loadErr] = useAsync<Dict>(() => api.get(`${c()}/entities/${id}`), [id])
  const [e, setE] = useState<Dict | null>(null)
  const [fields, setFields] = useState<Dict>({})
  const [saved, setSaved] = useState<Dict>({})
  const [top, setTop] = useState<Dict>({})
  const [savedTop, setSavedTop] = useState<Dict>({})
  const [modalTab, setModalTab] = useState('')
  const [phase, setPhase] = useState<'' | 'busy' | 'ok'>('')
  const [err, setErr] = useState('')
  const [npcs, setNpcs] = useState<Dict[]>([])
  const [repick, setRepick] = useState(false)
  const [bump, setBump] = useState(0)
  const [genOpen, setGenOpen] = useState(false)
  const [brushSrc, setBrushSrc] = useState<BrushSource | null>(null)
  const [genJob, setGenJob] = useState<Dict | null>(null)
  const [pickOpen, setPickOpen] = useState(false)
  const [cropOpen, setCropOpen] = useState(false)
  const [fullPhoto, setFullPhoto] = useState(false)
  const [pbAdv, setPbAdv] = useState(false)

  const dirtyTop = TOP.some(k => norm(k, top[k]) !== norm(k, savedTop[k]) && !(k === 'name' && !norm(k, top[k])))
  const dirty = JSON.stringify(fields) !== JSON.stringify(saved) || dirtyTop
  const dirtyRef = useRef(dirty)
  dirtyRef.current = dirty

  // перезагрузка после студии или кадрирования не затирает ненаписанный черновик
  const seen = useRef('')
  useEffect(() => {
    if (!loaded || loaded.id !== id) return
    setE(loaded)
    if (seen.current === id && dirtyRef.current) return
    seen.current = id
    setFields(loaded.fields || {}); setSaved(loaded.fields || {})
    setTop(topOf(loaded)); setSavedTop(topOf(loaded))
    setPhase(''); setErr(''); setRepick(false); setPbAdv(false)
  }, [loaded, id])

  useEffect(() => {
    let alive = true
    api.get(`${c()}/entities?kind=npc`)
      .then(r => { if (alive) setNpcs(Array.isArray(r) ? r : []) })
      .catch(() => { if (alive) setNpcs([]) })
    return () => { alive = false }
  }, [id])

  const readonly = isPublicView()
  const isObserver = campaign?.my_role === 'observer'
  const myMemberId = campaign?.my_member_id
  const canEdit = !!e && !readonly && !isObserver && (isGM || e.owner_member_id === ANY_PLAYER
    || (!!myMemberId && e.owner_member_id === myMemberId))

  useEffect(() => {
    if (!canEdit || !id) { setGenJob(null); return }
    let dead = false
    api.get(`${c()}/entities/${id}/image-jobs/active`).then(r => { if (!dead) setGenJob(r.job) }).catch(() => {})
    return () => { dead = true }
  }, [canEdit, id, genOpen])

  // вкладка: своя страница держит её в адресе, окно поверх доски — у себя
  const urlTab = onClose ? modalTab : pathname.split('/').filter(Boolean)[3] || ''
  const goTab = useCallback((k: Tab, replace = false) => {
    if (onClose) setModalTab(k)
    else nav(`/crew/team/${id}${k === 'sheet' ? '' : `/${k}`}`, { replace })
  }, [onClose, nav, id])
  const pb = playbookKey(meta, fields.playbook)
  const hiddenPb = !isGM && (e?.hidden_fields || []).includes('playbook')
  // новый персонаж без бланка сразу открывается на настройке
  useEffect(() => {
    if (e && canEdit && !urlTab && !pb && !hiddenPb && meta) goTab('setup', true)
  }, [e, canEdit, urlTab, pb, hiddenPb, meta, goTab])
  const tab: Tab = (TABS as readonly string[]).includes(urlTab) && (urlTab !== 'setup' || canEdit)
    ? urlTab as Tab : 'sheet'

  const save = useCallback(async (next: Dict, nextTop: Dict) => {
    const diff = changedKeys(next, saved)
    const tp: Dict = {}
    for (const k of TOP) {
      const v = norm(k, nextTop[k])
      if (v !== norm(k, savedTop[k]) && !(k === 'name' && !v)) tp[k] = v
    }
    if (!Object.keys(diff).length && !Object.keys(tp).length) { setSaved(next); return }
    setPhase('busy'); setErr('')
    try {
      const r = await api.patch(`${c()}/entities/${id}`, {
        ...(Object.keys(diff).length ? { fields: diff } : {}), ...tp,
      })
      setSaved(next)
      setSavedTop(prev => ({ ...prev, ...tp }))
      if (r?.id) setE(r)
      setPhase('ok')
    } catch (ex: any) {
      setErr(ex?.message || t('err.save')); setPhase('')
    }
  }, [id, saved, savedTop, t])

  /* правки уходят сами: пауза в наборе, смена вкладки, уход со страницы */
  const saveRef = useRef(save)
  saveRef.current = save
  const draft = useRef({ fields, top })
  draft.current = { fields, top }

  useEffect(() => {
    if (!dirty) return
    const h = window.setTimeout(() => void saveRef.current(draft.current.fields, draft.current.top), AUTOSAVE_MS)
    return () => window.clearTimeout(h)
  }, [dirty, fields, top])

  useEffect(() => () => {
    if (dirtyRef.current) void saveRef.current(draft.current.fields, draft.current.top)
  }, [])

  useEffect(() => {
    if (!dirty) return
    const warn = (ev: BeforeUnloadEvent) => { ev.preventDefault(); ev.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  // телефон: панель уезжает с прокруткой, у края остаются «назад» и «наверх»
  const floaty = phone && !onClose
  const [toolsEl, setToolsEl] = useState<HTMLDivElement | null>(null)
  const [away, setAway] = useState(false)
  useEffect(() => {
    if (!floaty || !toolsEl) { setAway(false); return }
    const bar = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--navbar-h')) || 0
    const io = new IntersectionObserver(([x]) => setAway(!x.isIntersecting), { rootMargin: `-${bar}px 0px 0px 0px` })
    io.observe(toolsEl)
    return () => io.disconnect()
  }, [floaty, toolsEl])

  const leave = () => (onClose ? onClose() : nav('/crew/team'))

  if (loadErr) {
    return (
      <div className="panel col">
        <h2>{te('page.unavailable')}</h2>
        <div className="dim">{loadErr}</div>
        <div><button className="ghost tiny" onClick={leave}>← {t('back')}</button></div>
      </div>
    )
  }
  if (!e) return <div className="dim">{t('common:loading')}</div>

  /* --- черновик и мгновенные правки ------------------------------------------ */

  const touched = () => { setPhase(''); setErr('') }
  const set = (k: string, v: any) => { setFields(f => ({ ...f, [k]: v })); touched() }
  const patch = (part: Dict) => { setFields(f => ({ ...f, ...part })); touched() }
  const setTopKey = (k: string, v: string) => { setTop(p => ({ ...p, [k]: v })); touched() }

  // владелец, видимость, статус, портрет, принадлежность — сразу одним ключом
  const push = async (part: Dict) => {
    const prev = e
    setE({ ...e, ...part })
    setPhase('busy'); setErr('')
    try {
      const r = await api.patch(`${c()}/entities/${id}`, part)
      if (r?.id) setE(r)
      setPhase('ok')
    } catch (ex: any) {
      setE(prev); setErr(ex?.message || t('err.save')); setPhase('')
    }
  }

  const switchTab = (k: Tab) => {
    if (dirty) void save(fields, top)
    setRepick(false)
    goTab(k)
  }

  /* --- доступ к полям ---------------------------------------------------------- */

  const hidden = new Set<string>((e.hidden_fields || []) as string[])
  const locked = (k: string) => !isGM && hidden.has(k)
  const setHidden = (k: string, hide: boolean) => {
    const next = new Set(hidden)
    if (hide) next.add(k)
    else next.delete(k)
    void push({ hidden_fields: [...next] })
  }
  // глаз — на настройке и в досье; на бланке только у закрытого поля, чтобы ГМ видел, что закрыто
  const eye = (k: string) => isGM && !readonly && (tab !== 'sheet' || hidden.has(k)) && (
    <FieldEye hidden={hidden.has(k)} onChange={hide => setHidden(k, hide)} />
  )

  /* --- бланк ------------------------------------------------------------------- */

  const def: Dict = meta?.kinds?.character || {}
  const sheet: Dict = dict(meta?.char_sheet)
  const setup: Dict = dict(campaign?.sheet_setup)
  const book = bookOf(meta, pb)
  const eff = effective(book, sheet, setup)
  const base = { f: fields, set, patch, isGM, phone, meta, sheet, book, pb, eff, setup, locked, eye }
  const play: Ctx = { ...base, marks: canEdit, pick: false }
  const pick: Ctx = { ...base, marks: false, pick: canEdit }

  const pickPlaybook = (k: string) => {
    const b = bookOf(meta, k)
    if (!b) return
    if (pb && pb !== k && !confirm(t('pick.change_confirm', { pb: b.label }))) return
    const own = effective(b, sheet, setup)
    setFields(f => {
      const next: Dict = { ...f, playbook: b.label }
      if (!pointsOf(dict(f.actions))) next.actions = { ...b.start }
      // снаряжение прежнего бланка уходит, обычные предметы остаются
      next.items = Object.fromEntries(Object.entries(dict(f.items))
        .filter(([key]) => !key.startsWith('pb:') || own.items.some(x => `pb:${x.key}` === key)))
      return next
    })
    touched()
    setRepick(false)
  }

  const finish = () => {
    set('created', true)
    switchTab('sheet')
  }

  const addContact = async (npc: Dict) => {
    setFields(f => {
      const rows = readContacts(f.contacts)
      return rows.some(r => r.entity_id === npc.id)
        ? f : { ...f, contacts: serContacts([...rows, { entity_id: npc.id, state: 'neutral' }]) }
    })
    touched()
    setNpcs(prev => (prev.some(n => n.id === npc.id) ? prev : [...prev, npc]))
    try {
      await api.post(`${c()}/links`, { from_id: id, to_id: npc.id, label: t('contact_link'), visibility: 'crew' })
    } catch { /* связь необязательна: знакомый уже записан в бланк */ }
  }

  /* --- портрет и файлы ----------------------------------------------------------- */

  const shotLocked = locked('image_url')
  const upload = async (file: File, asPhoto: boolean) => {
    setPhase('busy'); setErr('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('target_type', 'entity')
      fd.append('target_id', id)
      const up = await api.post(`${c()}/upload`, fd)
      setBump(b => b + 1)
      if (asPhoto && up?.url) await push({ image_url: up.url })
      else setPhase('ok')
    } catch (ex: any) {
      setErr(ex?.message || t('err.upload')); setPhase('')
    }
  }
  const gen = () => { setBrushSrc(null); setGenOpen(true) }

  const archive = async () => {
    if (!confirm(te('page.archive_confirm', { name: e.name }))) return
    try { await api.del(`${c()}/entities/${id}`); leave() } catch (ex: any) { setErr(ex?.message || te('page.archive_failed')) }
  }
  const purge = async () => {
    if (!confirm(te('page.purge_confirm', { name: e.name || te('no_name') }))) return
    try { await api.del(`${c()}/entities/${id}/purge`); leave() } catch (ex: any) { setErr(ex?.message || te('page.purge_failed')) }
  }

  const name = String(top.name || '')
  const alias = String(top.alias || '')
  const statusWord = locked('status') ? '?' : L(e.status) || e.status || ''
  const contactIds = readContacts(fields.contacts).map(r => r.entity_id)
  const inSetup = tab === 'setup'

  const acts = (canEdit || isGM) && <>
    {canEdit && !e.archived && <button className="ghost tiny" onClick={archive}>{te('page.to_archive')}</button>}
    {canEdit && e.archived && (
      <button className="tiny" onClick={() => push({ archived: false })}>{te('page.unarchive')}</button>
    )}
    {isGM && !readonly && <button className="ghost tiny danger" onClick={purge}>{t('common:delete')}</button>}
  </>

  const photo = (small: boolean) => (
    e.image_url && !shotLocked
      ? <img className="cs-shot-img zoomable" src={thumb(e.image_url, small ? 240 : 480, bump)} alt={e.name}
          title={te('view_full')} onClick={() => setFullPhoto(true)} />
      : <Stub kind="character" className="cs-shot-none" />
  )
  const portrait = (cls: string) => (
    <section className={`ss-p cs-shot imgbox ${cls}`}>
      {photo(false)}
      <ImgFlags hidden={isGM && hidden.has('image_url')} busy={!!genJob} mark={shotLocked} />
      {!shotLocked && canEdit && (
        <ImgActions
          vis={isGM ? { hidden: hidden.has('image_url'), onChange: hide => setHidden('image_url', hide) } : undefined}
          inpaint={isGM && e.image_url ? {
            title: te('page.inpaint_portrait'), onClick: () => {
              setBrushSrc({ id: e.image_url.split('/').pop() || '', url: e.image_url, title: te('page.portrait'), sub: '' })
              setGenOpen(true)
            },
          } : undefined}
          crop={e.image_url ? { title: te('page.crop'), onClick: () => setCropOpen(true) } : undefined}
          gen={{ title: genJob ? te('page.gen_running') : te('page.gen'), onClick: gen, on: !!genJob }}
          upload={{
            title: e.image_url ? te('page.replace_photo_tip') : te('page.upload_photo_tip'),
            onFile: file => void upload(file, true),
          }}
          pick={{ title: te('page.pick_media'), onClick: () => setPickOpen(true) }}
          remove={e.image_url ? { title: te('page.remove_photo'), onClick: () => push({ image_url: '' }) } : undefined} />
      )}
    </section>
  )

  return (
    <div className={`ss cs tab-${tab}`}>
      <PasteImage enabled={canEdit && !shotLocked}
        question={e.image_url ? te('page.paste_replace', { name: e.name }) : te('page.paste_set', { name: e.name })}
        onFiles={files => void upload(files[0], true)} />

      <div className={`ss-tools cs-tools${floaty ? ' flow' : ''}`} ref={setToolsEl}>
        {!onClose && <button className="ghost tiny cs-back" onClick={() => nav('/crew/team')}>← {t('back')}</button>}
        <span className="cs-tabs">
          {TABS.filter(k => k !== 'setup' || canEdit).map(k => (
            <button key={k} className={tab === k ? 'on' : ''} onClick={() => switchTab(k)}>{t(`tabs.${k}`)}</button>
          ))}
        </span>
        <div className="spacer" />
        {err
          ? <span className="ss-state bad">{err}</span>
          : phase === 'busy' || dirty
            ? <span className="ss-state">{t('saving')}</span>
            : phase === 'ok' && <span className="ss-state">{t('saved')}</span>}
        {isGM && !readonly && (
          <OwnerMenu value={e.owner_member_id} onChange={v => push({ owner_member_id: v })} />
        )}
        {(canEdit || (isGM && !!e.visibility)) && (
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
            <summary className="ghost tiny" aria-label={te('page.more')}>⋯</summary>
            <div className="dos-acts-list">{acts}</div>
          </details>
        )}
      </div>

      {floaty && away && (
        <div className="cs-float">
          <button className="ghost" aria-label={t('back')} title={t('back')} onClick={() => nav('/crew/team')}>←</button>
          <button className="ghost" aria-label={t('to_top')} title={t('to_top')}
            onClick={() => window.scrollTo({
              top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
            })}>↑</button>
        </div>
      )}

      {tab !== 'dossier' && <header className="cs-head">
        <div className="cs-thumb imgbox">{photo(true)}</div>
        <div className="cs-name">
          {inSetup
            ? <>
                <input className="ss-line-in ss-name-in" value={name} placeholder={t('name_ph')}
                  onChange={ev => setTopKey('name', ev.target.value)} />
                <input className="ss-line-in cs-alias-in" value={alias} placeholder={t('alias_ph')}
                  onChange={ev => setTopKey('alias', ev.target.value)} />
              </>
            : <>
                <h2>{norm('name', savedTop.name) || e.name}</h2>
                {alias && <div className="cs-alias">{te('quoted', { s: alias })}</div>}
              </>}
          <div className="cs-pb">
            {locked('playbook')
              ? <b>?</b>
              : book
                ? <><b>{book.label}</b>{book.blurb && <span className="cs-blurb">{book.blurb}</span>}</>
                : <span className="ss-none">{String(fields.playbook || '') || t('pb_none')}</span>}
            {inSetup && book && !locked('playbook') && !repick && (
              <button className="ghost tiny cs-repick" onClick={() => setRepick(true)}>{t('pb_change')}</button>
            )}
            {e.archived && <span className="stamp">{te('page.archived')}</span>}
          </div>
          {tab === 'sheet' && <IdLine c={play} />}
          {(statusWord || (canEdit && !locked('status'))) && (def.statuses || []).length > 0 && (
            <div className="cs-status">
              {canEdit && !locked('status')
                ? <Select className={`cs-stat t-${statusTone(e.status)}`} value={e.status || ''}
                    options={def.statuses} title={te('status')} optionLabel={o => L(o) || o}
                    onChange={v => push({ status: v })} />
                : <span className={`cs-stat t-${statusTone(e.status)}`}>{statusWord}</span>}
            </div>
          )}
        </div>
        {inSetup && (
          <div className="cs-look">
            <Line label={t('look')} value={fields.look} edit={inSetup} area hint={t('look_ph')}
              onChange={v => set('look', v)} />
          </div>
        )}
        {tab === 'sheet' && <Reference sheet={sheet} inHead />}
      </header>}

      {tab === 'sheet' && <>
        {phone && <Reference sheet={sheet} />}
        {!book && canEdit && !locked('playbook') && (
          <div className="cs-steps">
            <span>{t('pb_none')}</span>
            <div className="spacer" />
            <button className="ghost tiny" onClick={() => switchTab('setup')}>{t('tabs.setup')}</button>
          </div>
        )}
        <div className="cs-play">
          <Rail c={play} parts={phone ? ['stress'] : undefined} />
          <div className="cs-main">
            <ActionsLane c={play} />
            {book && <AbilityCards c={play} adv={pbAdv} setAdv={setPbAdv} />}
            {phone && <Rail c={play} parts={['trauma', 'harm']} />}
            <GearLane c={play} />
            {phone && <Rail c={play} parts={['money']} />}
            <ContactsLane c={play} npcs={npcs} onAdd={n => void addContact(n)} />
          </div>
        </div>
      </>}

      {inSetup && <>
        {(!book || repick) && !locked('playbook') && (
          <PlaybookPick meta={meta} onPick={pickPlaybook} onCancel={book ? () => setRepick(false) : undefined} />
        )}
        {book && !fields.created && (
          <Steps c={pick} named={!!name.trim() && !!alias.trim() && !!String(fields.look || '').trim()}
            onDone={finish} />
        )}
        <Identity c={pick} />
        <ActionsLane c={pick} />
        {book && <AbilitiesLane c={pick} />}
        <TraumaPick c={pick} />
        <ContactsLane c={pick} npcs={npcs} onAdd={n => void addContact(n)} />
        {book && fields.created && (
          <div className="cs-done">
            <button className="ghost" onClick={() => switchTab('sheet')}>{t('setup_done')} →</button>
          </div>
        )}
      </>}

      {tab === 'dossier' && <>
        <DossierFile c={play} id={id} name={norm('name', savedTop.name) || e.name} alias={alias}
          photo={portrait('')} status={locked('status') ? '' : e.status || ''} npcs={npcs}
          rev={campaign?.world_day != null ? stamp(campaign.world_day) : ''}
          texts={<>
            <DosText label={t('dos.text.summary')} value={top.summary} edit={canEdit} locked={locked('summary')} lead
              eye={eye('summary')} onChange={v => setTopKey('summary', v)} />
            <DosText label={t('dos.text.look')} value={fields.look} edit={canEdit} locked={locked('look')}
              eye={eye('look')} onChange={v => set('look', v)} />
            <DosText label={t('dos.text.background')} value={fields.background}
              edit={canEdit} locked={locked('background')} eye={eye('background')}
              onChange={v => set('background', v)} />
          </>} />

        <Lane title={t('lane.links')} id="links">
          <section className="ss-p cs-box"><LinksPanel entityId={id} kind="character" name={e.name} skip={contactIds} /></section>
          <section className="ss-p cs-box"><EntityClocks entityId={id} /></section>
        </Lane>

        <Lane title={t('lane.files')} one id="files">
          <div className="ss-p-b ss-lane-plain">
            <EntityMedia entityId={id} bump={bump} readonly={readonly}
              tail={!readonly && <>
                <label className="att-add" title={te('page.add_file_tip')}>
                  <input type="file"
                    onChange={ev => { ev.target.files?.[0] && void upload(ev.target.files[0], false); ev.target.value = '' }} />
                  <IconPlus size={18} /><span>{te('page.file')}</span>
                </label>
                {canEdit && (
                  <button type="button" className="att-add" title={te('page.gen_media')} onClick={gen}>
                    <IconSpark size={18} /><span>{te('page.generate')}</span>
                  </button>
                )}
              </>}
              onChange={() => setBump(b => b + 1)}
              onBrush={a => {
                setBrushSrc({ id: a.id, url: a.url, title: a.caption || a.filename || te('page.attachment'), sub: '' })
                setGenOpen(true)
              }} />
          </div>
        </Lane>

        <RecordsPanel entityType="entity" entityId={id} title={te('page.records_char')} />
      </>}

      {genOpen && (
        <Studio entity={e} source={brushSrc} onClose={() => setGenOpen(false)}
          onChanged={how => { reload(); setBump(b => b + 1); if (how === 'avatar') setGenOpen(false) }} />
      )}
      {pickOpen && (
        <MediaPickModal entityId={id} current={e.image_url} onClose={() => setPickOpen(false)}
          onPick={async url => { await push({ image_url: url }); setPickOpen(false) }} />
      )}
      {cropOpen && e.image_url && (
        <CropModal attachmentId={e.image_url.split('/').pop() || ''} src={e.image_url} title={e.name} ratio={4 / 5}
          onClose={() => setCropOpen(false)}
          onDone={() => { setCropOpen(false); reload(); setBump(b => b + 1) }} />
      )}
      {fullPhoto && e.image_url && <Lightbox src={e.image_url} alt={e.name} onClose={() => setFullPhoto(false)} />}
    </div>
  )
}

/** Длинное поле досье: правится по щелчку, в чтении пустое не показывается. */
function DosText({ label, value, edit, locked, gm, lead, eye, onChange }: {
  label: string; value: any; edit: boolean; locked?: boolean; gm?: boolean; lead?: boolean
  eye?: ReactNode; onChange: (v: string) => void
}) {
  const { t } = useTranslation('entity')
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLTextAreaElement>(null)
  const v = String(value ?? '')
  useEffect(() => {
    const el = box.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight + 2}px`
  }, [open, v])
  if (!edit && !v && !locked) return null
  return (
    <div className={`cs-dos${gm ? ' gm' : ''}${lead ? ' lead' : ''}`}>
      <div className="ss-cap">{label}{eye}</div>
      {locked
        ? <span className="unknown">?</span>
        : edit && open
          ? <textarea ref={box} className="ss-line-in" rows={3} value={v} autoFocus
              onChange={ev => onChange(ev.target.value)} onBlur={() => setOpen(false)} />
          : <div className={`cs-prose${edit ? ' ed-able' : ''}`} title={edit ? t('page.click_to_edit') : undefined}
              onClick={edit ? () => setOpen(true) : undefined}>
              {v || <span className="ss-none">{edit ? t('page.click_to_edit') : '—'}</span>}
            </div>}
    </div>
  )
}
