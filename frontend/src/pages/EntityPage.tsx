import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { api, c, isPublicView, type Dict, thumb, thumbFull } from '../api'
import { useApp, useAsync } from '../ctx'
import {
  asList, Chip, ClockDial, ColorPicker, Modal, MultiPick, Select, VisChip, rankRoman, statusTone,
} from '../ui'
import { IconImage, IconPlus, IconSpark } from '../components/icons'
import { ClockMoves, useClockMoves } from '../components/ClockMoves'
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
import { RecordsPanel } from '../components/RecordsPanel'

// маршрут ещё умеет /profile,/records,/links,/media — подвкладок больше нет,
// весь контент рисуется одной страницей, редирект оставлен ради старых ссылок
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

// портрет — главный знак карточки: кадр во всю ширину колонки, высота по самому кадру.
// без заданных пропорций: любой кадр садится в поле впритык, без пустых полей по краям
const PHOTO: Dict = { width: '100%', height: 'auto', display: 'block' }
// заглушки кадра нет — держим под неё вертикальное поле
const NOIMG: Dict = {
  width: '100%', aspectRatio: '3 / 4', display: 'grid', placeItems: 'center',
  fontFamily: 'var(--util)', fontSize: 26, letterSpacing: '.12em', color: 'var(--dim2)',
}
const ERR: Dict = {
  color: '#e08a70', background: '#251712', border: '1px solid #5c3327', padding: '5px 8px',
}

// закрытое ГМом поле: значение есть, стол его не знает
function Unknown() {
  const { t } = useTranslation('entity')
  return <span className="unknown" title={t('unknown_tip')}>?</span>
}
const UNKNOWN = <Unknown />

const text = (v: any): string =>
  v === null || v === undefined ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v)

/** Карточка сущности: своим маршрутом /entity/:id и окном поверх галереи (id + onClose).
 *  В окне галерея остаётся смонтированной — поиск, фильтры и группировка не сбрасываются. */
export default function EntityPage({ id: idProp, onClose, fresh }: {
  id?: string; onClose?: () => void
  /** только что заведённая карточка: сразу открыть имя на правку */
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
  // досье правится на месте: клик по значению открывает одно поле, клик мимо или Esc — закрывает
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
    // клик, который открыл поле, ещё всплывает до документа — его не считаем
    const since = performance.now()
    const away = (ev: MouseEvent) => {
      if (ev.timeStamp < since) return
      const t = ev.target as HTMLElement
      // кнопка внутри поля могла уже исчезнуть после своего же клика — это не «мимо»
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

  const readonly = isPublicView()  // витрина для стола — только чтение

  // права на правку: ГМ — всегда; корабль/экипаж — общий ресурс, правит любой игрок;
  // всё остальное — только владелец карточки (его назначает ГМ).
  // Генерация меняет карточку, поэтому доступна на тех же правах — не только ГМу
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

  const def: Dict = meta?.kinds?.[e.kind] || {}
  const kindLabel = def.label || L(e.kind) || e.kind
  const [backTo, backLabel] = BACK[e.kind] || ['/database', 'back.database']
  const own: Dict = e.fields || {}

  const isChar = e.kind === 'character'  // отличается только набором полей, не вёрсткой
  // своя принадлежность бессмысленна: локация не стоит в локации, фракция не входит в себя
  const showLoc = e.kind !== 'location'
  const showFac = e.kind !== 'faction'
  const locLabel = e.kind === 'faction' ? t('hq') : t('place')

  // поштучная видимость: ключ в hidden_fields = поле у ГМа есть, столу не отдаётся
  const hidden = new Set<string>((e.hidden_fields || []) as string[])

  // ранг — общее поле всех типов, читается в шапке, поэтому из своих полей его убираем
  const rankDef: Dict | undefined = (def.fields || []).find((f: Dict) => f.key === 'rank')
  const rankVal = text(own.rank)
  // ранг — в шапке справа: у правящего всегда (пустой бледно), у стола — только заданный
  const showRank = !!rankDef && (rankVal !== '' || hidden.has('rank') || (canEdit && (isGM || !hidden.has('rank'))))

  const showAlias = isChar || e.kind === 'npc'
  const hasStatuses = (def.statuses || []).length > 0

  const classDef: Dict | undefined = (def.fields || []).find((f: Dict) => f.key === 'playbook')
  const classVal = text(own.playbook)
  const showClass = !!classDef && (act === 'playbook' || classVal !== '' || hidden.has('playbook'))

  // ключ на gm_ сервер вообще не отдаёт столу (strip_gm_fields) — и подписи ему не рисуем
  const defs: Dict[] = (def.fields || [])
    .filter((f: Dict) => f.key !== 'rank' && f.key !== 'playbook')
    .filter((f: Dict) => isGM || !String(f.key).startsWith('gm_'))
  // пустой список text() отдаёт как «[]» — множество меряем длиной
  const filled = (f: Dict) => (f.type === 'multi' ? asList(own[f.key]).length > 0
    : f.type === 'ref' ? !!e.peer_names?.[text(own[f.key])]
    : text(own[f.key]) !== '')
  const shown = defs.filter(f => filled(f) || hidden.has(f.key) || act === f.key)


  const showVis = canEdit || (isGM && !!e.visibility)

  // в режиме чтения пустое поле — сиротливая подпись, поэтому показываем только заполненное
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
  // уходит один ключ: поля, которые в это время правит кто-то другой, не затираются
  const setOwn = (key: string, v: any) => push({ fields: { [key]: v } })

  // рустовая метка «закрыто» — рабочий сигнал ГМа, в режиме отображения её нет
  const shut = (key: string) => (isGM && hidden.has(key) ? ' shut' : '')
  // закрытое поле игрок не правит: значение у него пустое, и сервер такую правку не примет
  const locked = (key: string) => !isGM && hidden.has(key)
  // поле открыто для правки на месте
  const on = (key: string) => canEdit && act === key && !locked(key)
  // значение, по которому можно щёлкнуть, чтобы править
  const able = (key: string) => (canEdit && !locked(key)
    ? { className: 'ed-able', title: t('page.click_to_edit'), onClick: () => setAct(key) }
    : {})
  const setHidden = (key: string, hide: boolean) => {
    const next = new Set(hidden)
    if (hide) next.add(key)
    else next.delete(key)
    push({ hidden_fields: [...next] })
  }
  // gm_-поле столу не уходит никогда — глазок «закрыть» тут нечего переключать
  const eye = (key: string) => isGM && !key.startsWith('gm_')
    && !(e.kind === 'faction' && key === 'stance') && (
    <FieldEye hidden={hidden.has(key)} onChange={hide => setHidden(key, hide)} />
  )
  // подпись поля: глаз сразу за словом, у закрытого поля подпись рустовая
  const fieldLabel = (key: string, label: string) => (
    <div className={`fld-lbl${shut(key) ? ' off' : ''}`}>{label}{eye(key)}</div>
  )

  // обычное состояние («активен») не пишем — метка появляется, только когда есть отличие
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
      // сразу поиск с нынешним именем: выбор заменяет, стёртая строка (Enter или уход) — очищает
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
  // пустые поля в чтении не видны — добавить их можно отсюда, поле откроется на месте
  const blanks: [string, string][] = [
    ...(showFac && !showFacField ? [['faction_ids', t('factions')] as [string, string]] : []),
    ...(showLoc && !showLocField ? [['location_ids', locLabel] as [string, string]] : []),
    ...(classDef && !showClass ? [['playbook', classDef.label] as [string, string]] : []),
    ...defs.filter(f => !shown.includes(f) && !locked(f.key)).map(f => [f.key, f.label] as [string, string]),
  ]
  const short = shown.filter(f => f.type !== 'textarea')
  const long = shown.filter(f => f.type === 'textarea')
  const summaryLocked = locked('summary')
  // длинное описание читается свёрнутым — разворачивается по кнопке
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
      {/* Ctrl+V прямо на карточке — вставленный снимок становится портретом */}
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

              {showClass && (
                <div className={`dos-role${shut('playbook')}`} data-act="playbook">
                  {canEdit && !locked('playbook')
                    ? <Select className="ent-class-pick" value={classVal} empty={t('page.playbook_empty')}
                        options={classDef!.options || []} title={classDef!.label}
                        optionLabel={o => o} onChange={v => setOwn('playbook', v)} />
                    : <b>{locked('playbook') ? '?' : classVal || '—'}</b>}
                  {eye('playbook')}
                </div>
              )}
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
              <h4 className="dos-sec-t">{isChar ? t('page.sheet') : t('page.details')}</h4>
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

          {/* обвязка стоит той же колонкой, что и разбор — портрету остаётся весь левый край */}
          <div className="ent-aside">
            <div className="ent-aside-col">
              <div className="ent-sub col">
                <LinksPanel entityId={id} kind={e.kind} name={e.name} />
              </div>
              <div className="ent-sub col">
                <Clocks entityId={id} />
              </div>
            </div>
            <div className="ent-sub col">
              <h3>{t('page.media')}</h3>
              <Media entityId={id} bump={bump} readonly={readonly}
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
          title={isChar ? t('page.records_char') : t('page.records')} />
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

/* --- правка на месте: сохраняем по уходу из поля ---------------------------- */

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
  // поле растёт под текст: правка не сжимает описание до трёх строк со скроллом
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

/* --- вложения --------------------------------------------------------------- */

/** Вложения карточки: миниатюры плиткой, снимок разворачивается на весь экран,
 *  свой файл убирает загрузивший, чужой — ГМ. */
function Media({ entityId, bump, readonly, onChange, onBrush, tail }: {
  entityId: string; bump: number; readonly: boolean; onChange: () => void
  onBrush: (a: Dict) => void
  /** плитки «добавить» в конце сетки, на месте следующего снимка */
  tail?: ReactNode
}) {
  const { isGM, campaign } = useApp()
  const { t } = useTranslation('entity')
  const [rows, loading, reload, err] = useAsync<Dict[]>(
    () => api.get(`${c()}/attachments?target_type=entity&target_id=${entityId}`), [entityId, bump])
  const [shot, setShot] = useState(-1)
  const [oops, setOops] = useState('')
  const atts = rows || []
  const isImage = (a: Dict) => String(a.mime || '').startsWith('image/')
  const shots = atts.filter(isImage)
  const myMemberId = campaign?.my_member_id

  const drop = async (a: Dict) => {
    const name = a.caption || a.filename || t('page.file')
    if (!confirm(t('media.delete_confirm', { name }))) return
    setOops('')
    try {
      await api.del(`${c()}/attachments/${a.id}`)
      reload(); onChange()
    } catch (ex: any) { setOops(ex?.message || t('media.delete_failed')) }
  }

  // видимость поштучная: файл остаётся у ГМа, стол его просто не получает
  const setVis = async (a: Dict, hide: boolean) => {
    setOops('')
    try {
      await api.patch(`${c()}/attachments/${a.id}`, { visibility: hide ? 'gm' : 'crew' })
      reload(); onChange()
    } catch (ex: any) { setOops(ex?.message || t('media.vis_failed')) }
  }

  if (loading && !rows) return <div className="dim">{t('common:loading')}</div>
  if (err) return <div className="empty">{t('media.unavailable')}</div>
  if (!atts.length && !tail) return <div className="empty">{t('media.empty')}</div>

  return (
    <>
      {oops && <div className="lnk-err">{oops}</div>}
      <div className="att-grid">
        {atts.map(a => {
          const label = a.caption || a.filename || t('page.file')
          const mine = isGM || (!!myMemberId && a.uploaded_by === myMemberId)
          const i = shots.indexOf(a)
          const shut = isGM && a.visibility === 'gm'
          return (
            <div key={a.id} className={`att${shut ? ' att-shut' : ''}`} title={label}>
              <div className="att-box imgbox">
                {isImage(a)
                  ? <button type="button" className="att-shot" onClick={() => setShot(i)}
                      aria-label={t('media.open', { name: label })}>
                      <img src={thumbFull(a.url, 240, bump)} alt={label} loading="lazy" />
                    </button>
                  : <a className="att-shot att-file" href={a.url} target="_blank" rel="noreferrer">
                      <span className="att-ext">
                        {String(a.filename || '').split('.').pop()?.slice(0, 4) || t('page.file')}
                      </span>
                    </a>}
                <ImgFlags hidden={shut} />
                {!readonly && (
                  <ImgActions small
                    vis={isGM ? { hidden: shut, onChange: hide => setVis(a, hide) } : undefined}
                    inpaint={isGM && isImage(a) ? {
                      title: t('media.inpaint'), onClick: () => onBrush(a),
                    } : undefined}
                    remove={mine ? { title: t('media.delete_tip'), onClick: () => drop(a) } : undefined} />
                )}
              </div>
              <span className="att-cap">{label}</span>
            </div>
          )
        })}
        {tail}
      </div>

      {shot >= 0 && shots[shot] && (
        <Lightbox src={shots[shot].url} alt={shots[shot].filename}
          caption={shots.length > 1
            ? `${shots[shot].caption || shots[shot].filename} · ${shot + 1}/${shots.length}`
            : shots[shot].caption || shots[shot].filename}
          onClose={() => setShot(-1)}
          onPrev={shots.length > 1 ? () => setShot((shot - 1 + shots.length) % shots.length) : undefined}
          onNext={shots.length > 1 ? () => setShot((shot + 1) % shots.length) : undefined} />
      )}

    </>
  )
}

/* --- счётчики сущности ------------------------------------------------------ */
/* --- счётчики сущности ------------------------------------------------------ */

/** Счётчики записи двигаются прямо с карточки, как в базе кампании;
 *  описание, история и правка — в базе. */
function Clocks({ entityId }: { entityId: string }) {
  const { L, isGM } = useApp()
  const { t } = useTranslation('entity')
  const [rows, loading, reload, err] = useAsync<Dict[]>(
    () => api.get(`${c()}/clocks?status=&owner_id=${entityId}`), [entityId])
  const moves = useClockMoves(rows, reload)
  const list = (rows || [])
    .filter(cl => cl.owner_type === 'entity' && cl.owner_id === entityId).map(moves.view)

  return (
    <div className="col">
      <div className="row">
        <h3>{t('clocks.title')}</h3>
      </div>

      {err && <div className="empty">{t('clocks.unavailable')}</div>}
      {!err && loading && !rows && <div className="dim">{t('common:loading')}</div>}
      {!err && !loading && list.length === 0 && <div className="empty">{t('clocks.empty')}</div>}

      {!err && list.length > 0 && (
        <div className="lnk-list clocks-list">
          {list.map(cl => (
            <div key={cl.id} className="lnk">
              <ClockDial segments={cl.segments} filled={cl.filled} size={34}
                hidden={cl.visibility === 'gm'} color={cl.color} />
              <div className="lnk-main">
                <div className="lnk-head">
                  <Link className="lnk-name" to={`/database/clocks?open=${cl.id}`}
                    title={t('clocks.open_tip')}>{cl.name}</Link>
                  {cl.kind && <Chip tone="cyan">{cl.kind}</Chip>}
                  {cl.status === 'abandoned' && <Chip tone="black">{L(cl.status)}</Chip>}
                  {cl.status === 'completed' && <Chip tone="green">{L(cl.status)}</Chip>}
                  {cl.status === 'active' && cl.filled >= cl.segments &&
                    <Chip tone="amber">{t('clocks.filled')}</Chip>}
                  {isGM && <VisChip v={cl.visibility} />}
                </div>
                <div className="clock-line">
                  <span className="lnk-sub">{cl.filled}/{cl.segments}</span>
                  <div className="spacer" />
                  <ClockMoves cl={cl} moves={moves} />
                </div>
                {moves.oops(cl) && <div className="clock-err">{moves.oops(cl)}</div>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
