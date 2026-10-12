import { useEffect, useMemo, useState, type MutableRefObject, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, c, isPublicView, thumb, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import { asList, Input, Modal, MultiPick, OwnerPicker, rankRoman, statusTone } from '../ui'
import { IconPlus } from './icons'
import VisibilityMenu from './VisibilityMenu'
import OwnerMenu from './OwnerMenu'
import { AffiliationPicker, useKindIndex } from './AffiliationPicker'
import { ImgFlags } from './ImageTools'
import Stub from './Stub'
import EntityPicker from './EntityPicker'
import EntityPage from '../pages/EntityPage'
import '../styles.gallery.css'

export type GalleryField = {
  key: string
  label: string
  type?: 'text' | 'textarea' | 'select' | 'multi' | 'ref'
  /** у ref — из каких видов карточек выбирать */
  kinds?: string
  options?: string[]
  /** потолок выбора у поля-множества */
  max?: number
  /** подпись-полоска под именем — чем карточка является, а не что о ней известно */
  badge?: boolean
  /** строка у описания, а не тег описи: свободный текст, который читают целиком */
  note?: boolean
}

export type EntityGalleryProps = {
  kind: string
  title: string
  /** куда ведёт карточка; по умолчанию — полная страница сущности */
  linkTo?: (e: Dict) => string
  /** карточка без списка полей: только снимок, имя, краткое описание */
  hideFacts?: boolean
  /** поиск по имени и описанию и «N из M» — у больших галерей */
  search?: boolean
  /** ГМу — ряд «кто видит», когда в нём больше одной корзины */
  visRow?: boolean
  /** постоянные заголовки по своему select-полю типа: категория у фракций, система у мест */
  sectionBy?: string
  /** порядок карточек; по умолчанию свежие сверху */
  sort?: (a: Dict, b: Dict) => number
  /** итоговые статусы: такие карточки идут бледным хвостом в конце */
  closed?: string[]
  /** ручка обновления списка для родителя: тихий refetch без перемонтажа галереи */
  reloadRef?: MutableRefObject<((silent?: boolean) => void) | null>
  /** раскладка по группам от родителя: каждая группа — отдельный блок с заголовком;
   *  пустые группы родителя тоже рисуются */
  groupBy?: (list: Dict[]) => Group[]
  /** блок под плиткой, вне ссылки: своё у вида (состояние персонажа ГМу) */
  extra?: (e: Dict) => ReactNode
  /** свои кнопки сразу за заголовком */
  beside?: ReactNode
}

/** idle — группа бледная (никем не занята); add — в пустой группе своя кнопка добавления */
export type Group = [key: string, label: string, items: Dict[], look?: { idle?: boolean; add?: boolean }]

const NO_SECTION = ' nosection'

const ru = (a: string, b: string) => String(a).localeCompare(String(b), 'ru')

/** порядок ряда «кто видит»: сначала открытое столу */
const VIS_ORDER = ['crew', 'some', 'gm']

/** подписи ГМ-фильтра по видимости */
const VIS_FILTER: Dict = {
  crew: 'gallery.vis_crew', some: 'gallery.vis_some', gm: 'gallery.vis_gm',
}

const idsOf = (e: Dict, key: string): string[] =>
  Array.isArray(e[key]) ? e[key].filter(Boolean) : []


const UNKNOWN = '?'  // ГМ закрыл поле: значение есть, стол его не знает

const orderOf = (value: any, order: string[]) => {
  const i = order.indexOf(String(value || ''))
  return i < 0 ? order.length + 1 : i
}

const freshFirst = (a: Dict, b: Dict) =>
  String(b.created_at || '').localeCompare(String(a.created_at || ''))
  || ru(a.name || '', b.name || '')

export function EntityGallery({
  kind, title, linkTo, hideFacts, search, visRow, sectionBy, sort, closed, extra, beside,
  reloadRef, groupBy,
}: EntityGalleryProps) {
  const nav = useNavigate()
  const { meta, isGM, L, campaign } = useApp()
  const { t } = useTranslation('entity')
  const [rows, loading, reload, loadErr] = useAsync<Dict[]>(
    () => api.get(`${c()}/entities?kind=${kind}`), [kind])
  // архив нужен только ГМу: вернуть карточку можно с её страницы
  const [archRows, , reloadArch] = useAsync<Dict[]>(
    () => (isGM ? api.get(`${c()}/entities?kind=${kind}&archived=true`) : Promise.resolve([])),
    [kind, isGM])
  const [inArch, setInArch] = useState(false)
  const { byId: facById } = useKindIndex('faction')
  const { byId: locById } = useKindIndex('location')
  const [q, setQ] = useState('')
  // ГМ-фильтр: что стол уже видит, а что лежит закрытым
  const [visF, setVisF] = useState<string[]>([])
  const [creating, setCreating] = useState(false)
  // карточку открываем окном поверх галереи: поиск и фильтр остаются на месте
  // открытая карточка живёт в адресе (?card=id): ссылкой можно поделиться, «назад» закрывает окно
  const [sp, setSp] = useSearchParams()
  const cardId = sp.get('card')
  const [freshId, setFreshId] = useState<string | null>(null)
  const openEnt: Dict | null = cardId ? { id: cardId, fresh: freshId === cardId } : null
  const setOpenEnt = (x: Dict | null) => {
    const next = new URLSearchParams(sp)
    if (x) next.set('card', x.id)
    else next.delete('card')
    if (x?.fresh) setFreshId(x.id)
    setSp(next)
  }

  // «добавить» заводит пустую карточку и сразу открывает её окном — поля вписываются на месте
  const create = async () => {
    if (creating) return
    setCreating(true)
    try {
      const made = await api.post(`${c()}/entities`, {
        kind, name: '',
        ...(kind === 'job' ? { fields: { job_type: 'job' } } : {}),
        ...(!isGM && kind === 'character' ? { owner_member_id: campaign?.my_member_id } : {}),
      })
      refresh(true)
      if (linkTo) nav(linkTo({ id: made.id }))
      else setOpenEnt({ id: made.id, fresh: true })
    } catch (ex: any) { alert(ex?.message || t('gallery.create_failed')) }
    setCreating(false)
  }
  // новая карточка без имени не сохраняется: уходя, спрашиваем и убираем её
  const closeEnt = async () => {
    const was = openEnt
    if (was?.fresh) {
      let named = true
      try { named = !!String((await api.get(`${c()}/entities/${was.id}`))?.name || '').trim() } catch { /* нет — закрываем */ }
      if (!named) {
        if (!confirm(t('gallery.unnamed_leave'))) return
        try { await api.del(`${c()}/entities/${was.id}?discard=1`) } catch { /* осталась — не беда */ }
      }
    }
    setOpenEnt(null)
    refresh()
  }

  const refresh = (silent?: boolean) => { reload(silent); reloadArch(silent) }

  useEffect(() => {
    if (!reloadRef) return
    reloadRef.current = refresh
    return () => { reloadRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadRef])

  const readonly = isPublicView()
  const canCreate = !readonly
  const def: Dict = meta?.kinds?.[kind] || {}
  const statuses: string[] = Array.isArray(def.statuses) ? def.statuses : []
  // свои поля типа: их же показываем в форме создания.
  // gm_-поля — рабочая кухня ГМа (внешность под генерацию), в галерее им не место
  const extraFields: GalleryField[] = (def.fields || [])
    .filter((f: Dict) => !String(f.key).startsWith('gm_'))
  const archived = archRows || []
  const showArch = isGM && inArch
  const all = (showArch ? archived : rows) || []

  // «скрыто» — карточка целиком у ГМа; «частично» — открыта только выбранным или владельцу
  const visKey = (e: Dict) =>
    e.visibility === 'gm' ? 'gm' : e.visibility === 'crew' || !e.visibility ? 'crew' : 'some'

  const visCounts = useMemo<[string, number][]>(() => {
    if (!isGM || !visRow) return []
    const m = new Map<string, number>()
    for (const e of all) m.set(visKey(e), (m.get(visKey(e)) || 0) + 1)
    return VIS_ORDER.filter(k => m.has(k)).map(k => [k, m.get(k) as number])
  }, [all, isGM, visRow])
  // ряд из одной корзины ничего не делит; спрятанный ряд и не фильтрует
  const visShown = visCounts.length > 1
  const visOn = visShown ? visF : []

  const list = useMemo(() => {
    const needle = search ? q.trim().toLowerCase() : ''
    const out = all.filter(e => {
      if (visOn.length && !visOn.includes(visKey(e))) return false
      if (!needle) return true
      const hay = `${e.name || ''} ${e.alias || ''} ${e.summary || ''}`
      return hay.toLowerCase().includes(needle)
    })
    out.sort(sort || freshFirst)
    if (!closed?.length) return out
    const done = (e: Dict) => closed.includes(String(e.status || ''))
    return [...out.filter(e => !done(e)), ...out.filter(done)]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [all, q, search, visOn.join('|'), sort, closed?.join('|')])

  const sectionDef = sectionBy ? extraFields.find(f => f.key === sectionBy) : undefined
  // значение раздела уже стоит в заголовке группы — на карточке его не повторяем
  const cardFields = sectionBy ? extraFields.filter(f => f.key !== sectionBy) : extraFields

  const groups = useMemo<Group[]>(() => {
    // пустые группы родителя рисуются — но не раньше, чем пришёл список
    if (groupBy) return rows ? groupBy(list) : []
    if (!sectionBy && closed?.length) {
      const done = (e: Dict) => closed.includes(String(e.status || ''))
      return [['on', t('gallery.open_group'), list.filter(e => !done(e))],
        ['off', t('gallery.closed_group'), list.filter(done)]] as Group[]
    }
    if (!sectionBy) return [['', '', list] as Group]
    const map = new Map<string, Dict[]>()
    for (const e of list) {
      const k = String(e.fields?.[sectionBy] ?? '').trim() || NO_SECTION
      const arr = map.get(k)
      arr ? arr.push(e) : map.set(k, [e])
    }
    const opts = sectionDef?.options || []
    return Array.from(map.entries())
      .sort((a, b) => Number(a[0] === NO_SECTION) - Number(b[0] === NO_SECTION)
        || orderOf(a[0], opts) - orderOf(b[0], opts) || ru(L(a[0]), L(b[0])))
      .map(([k, items]) => [
        k,
        k === NO_SECTION ? t('gallery.no_section', { label: (sectionDef?.label || '').toLowerCase() }) : (L(k) || k),
        items,
      ] as Group)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, list, sectionBy, sectionDef, meta, groupBy, closed?.join("|"), t])

  const toggle = (setter: (fn: (cur: string[]) => string[]) => void, id: string) =>
    setter(cur => cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id])

  const setVis = async (id: string, v: string, to: string[]) => {
    try {
      await api.patch(`${c()}/entities/${id}`, { visibility: v, visible_to: to })
      refresh()
    } catch (err: any) {
      alert(err?.message || t('gallery.vis_failed'))
    }
  }

  const setOwner = async (id: string, v: string | null) => {
    try {
      await api.patch(`${c()}/entities/${id}`, { owner_member_id: v })
      refresh()
    } catch (err: any) {
      alert(err?.message || t('gallery.owner_failed'))
    }
  }

  const isClosed = (e: Dict) => !!closed?.includes(String(e.status || ''))

  return (
    <div className="col">
      <div className="eg-bar">
        <div className="eg-line">
          <h1 className="eg-title">{title}</h1>
          {beside}
          {search && (
            <input type="text" placeholder={t('gallery.search_ph')} value={q}
              onChange={e => setQ(e.target.value)} />
          )}
          <div className="spacer" />
          {search && <span className="eg-count">{t('gallery.count', { shown: list.length, total: all.length })}</span>}
          {isGM && (
            <button className={`eg-tog ${showArch ? 'on' : ''}`} disabled={!archived.length && !showArch}
              onClick={() => setInArch(v => !v)}>
              {t('gallery.archive')}<span className="n">{archived.length}</span>
            </button>
          )}
          {canCreate && (
            <button className="primary btn-ico" title={t('gallery.add_tip')}
              onClick={create} disabled={creating}>
              <IconPlus size={13} />{t('gallery.add')}
            </button>
          )}
        </div>

        {visShown && (
          <div className="eg-line">
            <span className="eg-lbl">{t('gallery.who_sees')}</span>
            {visCounts.map(([k, n]) => (
              <button key={k} className={`eg-tog ${visF.includes(k) ? 'on' : ''}`}
                onClick={() => toggle(setVisF, k)}>
                {t(VIS_FILTER[k])}<span className="n">{n}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {loading && <div className="dim">{t('common:loading')}</div>}
      {!loading && loadErr && <div className="eg-err">{loadErr}</div>}

      {!loading && !loadErr && all.length === 0 && (showArch
        ? <div className="eg-hint">{t('gallery.archive_empty')}</div>
        : (
          <div className="eg-hint">
            {t('gallery.empty')}{' '}
            {canCreate
              ? t('gallery.empty_can')
              : t('gallery.empty_wait')}
          </div>
        ))}
      {!loading && all.length > 0 && list.length === 0 && (
        <div className="eg-hint">
          {visOn.length ? t('gallery.nothing_filter') : t('gallery.nothing')}
        </div>
      )}

      <div className={groupBy ? 'eg-groups boxed' : 'eg-groups'}>
        {groups.filter(([, , items]) => items.length > 0 || !!groupBy).map(([key, label, items, look]) => (
          <div key={key || '_'} className={look?.idle ? 'eg-group idle' : 'eg-group'}
            style={groupBy ? { ['--eg-n' as string]: Math.max(1, items.length) } : undefined}>
            {(!!sectionBy || !!groupBy || !!closed?.length) && (
              <div className="eg-group-hd">
                <span className="t">{label}</span>
                <span className="n">{items.length}</span>
              </div>
            )}
            {look?.add && canCreate && items.length === 0 && (
              <div className="eg-group-add">
                <button className="ghost btn-ico" onClick={create} disabled={creating}>
                  <IconPlus size={13} />{(def.label || title).toLowerCase()}
                </button>
              </div>
            )}
            {items.length > 0 && <div className="eg-grid">
              {items.map(e => (
                <Card key={e.id} e={e} kind={kind} isGM={isGM} L={L}
                  fieldDefs={cardFields} defaultStatus={statuses[0]}
                  facById={facById} locById={locById}
                  hideFacts={hideFacts} faded={isClosed(e)}
                  href={linkTo ? linkTo(e) : `/entity/${e.id}`}
                  onOpen={linkTo ? undefined : () => setOpenEnt(e)}
                  readonly={readonly} onVis={(v, to) => setVis(e.id, v, to)}
                  onOwner={v => setOwner(e.id, v)} extra={extra?.(e)} />
              ))}
            </div>}
          </div>
        ))}
      </div>

      {openEnt && (
        <Modal wide title={def.label || title} onClose={closeEnt}>
          <EntityPage id={openEnt.id} fresh={!!openEnt.fresh} onClose={closeEnt} />
        </Modal>
      )}
    </div>
  )
}

/** Заведение записи вне галереи — с той же формой и теми же полями типа.
    Схему типа берём из меты кампании, как это делает сама галерея. */
export function NewEntityModal({ kind, onDone, onClose }: {
  kind: string; onDone: (id: string) => void; onClose: () => void
}) {
  const { meta } = useApp()
  const def: Dict = meta?.kinds?.[kind] || {}
  const statuses: string[] = Array.isArray(def.statuses) ? def.statuses : []
  const extraFields: GalleryField[] = (def.fields || [])
    .filter((f: Dict) => !String(f.key).startsWith('gm_'))
  return (
    <CreateForm kind={kind} label={def.label || kind} statuses={statuses}
      createExtra={extraFields} onClose={onClose} onDone={onDone} />
  )
}

export default EntityGallery

/* --- карточка --------------------------------------------------------------- */

function Card({ e, kind, isGM, L, fieldDefs, defaultStatus, facById, locById, href, onOpen, readonly, onVis, onOwner, hideFacts, faded, extra }: {
  e: Dict
  kind: string
  isGM: boolean
  L: (k?: string | null) => string
  fieldDefs: GalleryField[]
  /** обычное состояние вида («в деле»): его на плитке не пишем, читается только отличие */
  defaultStatus?: string
  facById: Map<string, Dict>
  locById: Map<string, Dict>
  href: string
  hideFacts?: boolean
  /** дело закрыто: карточка бледнее открытых */
  faded?: boolean
  /** открыть карточку окном; ссылка остаётся рабочей для «в новой вкладке» */
  onOpen?: () => void
  readonly: boolean
  onVis: (v: string, to: string[]) => void
  onOwner: (v: string | null) => void
  extra?: ReactNode
}) {
  const { t } = useTranslation('entity')
  const [open, setOpen] = useState(false)
  const hidden = new Set<string>((e.hidden_fields || []) as string[])
  const locWord = kind === 'faction' ? t('hq') : t('place')
  // закрытое поле: ГМ читает значение с рустовой меткой, стол — только «?»
  const shutKey = (key: string) => hidden.has(key)
  const seen = (key: string, values: string[]) =>
    (shutKey(key) && !isGM ? [UNKNOWN] : values)

  const facts: [string, string[], string][] = []
  const put = (key: string, label: string, values: string[]) => {
    const vals = seen(key, values)
    if (vals.length) facts.push([label, vals, key])
  }
  // привязка на закрытую карточку: имя приходит с сервера, ссылки на неё нет
  const names = (ids: string[], by: Map<string, Dict>) =>
    ids.map(id => String(by.get(id)?.name || e.peer_names?.[id] || '')).filter(Boolean)
  if (kind !== 'faction') put('faction_ids', t('faction'), names(idsOf(e, 'faction_ids'), facById))
  if (kind !== 'location') put('location_ids', locWord, names(idsOf(e, 'location_ids'), locById))
  for (const f of fieldDefs) {
    if (f.key === 'rank' || f.key === 'playbook' || f.badge || f.note) continue
    if (f.type === 'multi') { put(f.key, f.label, asList(e.fields?.[f.key])); continue }
    if (f.type === 'ref') { put(f.key, f.label, names(asList(e.fields?.[f.key]), new Map())); continue }
    const v = String(e.fields?.[f.key] ?? '').trim()
    put(f.key, f.label, v ? [f.type === 'select' ? (L(v) || v) : v] : [])
  }
  const shown = hideFacts ? [] : open ? facts : facts.slice(0, 3)
  const rest = hideFacts ? 0 : facts.length - shown.length

  const caption = shutKey('summary') && !isGM ? UNKNOWN : String(e.summary || '')
  const hasRank = isGM ? !!e.fields?.rank : !!e.fields?.rank || shutKey('rank')
  const rankVal = shutKey('rank') && !isGM ? UNKNOWN : rankRoman(e.fields?.rank)
  const status = String(e.status || '')
  const tone = statusTone(status)
  const showStatus = !!status
  const statusWord = L(status) || status
  // мёртвый, выбывший, чёрная метка — кадр выцветает: состояние видно без подписи
  const gone = (tone === 'dead' || tone === 'end' || tone === 'black')

  // роль — одна строка: класс персонажа, тип работёнки
  const badgeKey = fieldDefs.find(f => f.badge)?.key || ''
  const badgeRaw = String(e.fields?.[badgeKey] ?? '').trim()
  const roleKey = e.fields?.playbook || shutKey('playbook') ? 'playbook' : badgeKey
  const roleRaw = roleKey === 'playbook' ? String(e.fields?.playbook || '') : badgeRaw
  const role = roleKey && shutKey(roleKey) && !isGM ? UNKNOWN : roleRaw && (L(roleRaw) || roleRaw)
  const notes = hideFacts ? [] : fieldDefs.filter(f => f.note).flatMap(f => {
    const raw = String(e.fields?.[f.key] ?? '').trim()
    const val = shutKey(f.key) && !isGM ? UNKNOWN : raw
    return val ? [[f, val] as const] : []
  })
  const showAlias = (kind === 'character' || kind === 'npc') && !!e.alias && !!e.name

  const cls = ['tile']
  if (isGM && e.visibility === 'gm') cls.push('tile-gm')
  if (faded) cls.push('tile-faded')
  if (gone) cls.push('tile-gone')
  if (kind === 'character' || kind === 'npc') cls.push('tile-person')

  return (
    <article className={cls.join(' ')}>
      <Link to={href} className="tile-link" onClick={onOpen && (ev => {
        // Ctrl/Cmd/Shift и средняя кнопка оставляем браузеру — карточка откроется отдельной страницей
        if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.button !== 0) return
        ev.preventDefault(); onOpen()
      })}>
        <div className="tile-shot">
          {e.image_url
            ? <>
                <img className="tile-bg" src={thumb(e.image_url, 480)} alt="" aria-hidden="true" loading="lazy" />
                <img src={thumb(e.image_url, 480)} alt={e.name} loading="lazy" />
              </>
            : <Stub kind={e.kind} sub={badgeRaw} className="tile-stub" />}
          <ImgFlags hidden={isGM && shutKey('image_url')} />
          {hasRank && (
            <span className={`tile-rank${shutKey('rank') ? ' hid' : ''}`} title={t('rank')}>
              <span className="tr-num">{rankVal}</span>
            </span>
          )}
          {showStatus && (
            <span className={`tile-status t-${tone}`}>
              {statusWord}
            </span>
          )}
        </div>
        <div className="tile-body">
          {!!role && <div className={`tile-type${shutKey(roleKey) ? ' hid' : ''}`}>{role}</div>}
          <div className="tile-id">
            <h3 className="tile-name">
              {e.name || (e.alias ? t('quoted', { s: e.alias }) : t('no_name'))}
              {showAlias && <span className="tile-alias">{t('quoted', { s: e.alias })}</span>}
            </h3>
          </div>
          {caption && (
            <p className={`tile-sum${hideFacts ? ' long' : ''}${shutKey('summary') ? ' hid' : ''}`}>
              {caption}
            </p>
          )}
          {(shown.length > 0 || notes.length > 0) && (
            <dl className="tile-facts">
              {notes.map(([f, val]) => (
                <div key={f.key} className={shutKey(f.key) ? 'hid' : undefined}
                  title={`${f.label}: ${val}`}>
                  <dt>{f.label}</dt><dd>{val}</dd>
                </div>
              ))}
              {shown.map(([k, vals, key]) => (
                <div key={k} className={shutKey(key) ? 'hid' : undefined}
                  title={`${k}: ${vals.join(', ')}`}>
                  <dt>{k}</dt><dd>{vals.join(', ')}</dd>
                </div>
              ))}
              {rest > 0 && (
                <button type="button" className="tile-more"
                  onClick={ev => { ev.preventDefault(); ev.stopPropagation(); setOpen(true) }}>
                  {t('gallery.more', { count: rest })}
                </button>
              )}
            </dl>
          )}
        </div>
      </Link>
      {extra && <div className="tile-extra">{extra}</div>}
      {isGM && (
        <div className="tile-svc">
          {kind !== 'ship' && (
            <OwnerMenu value={e.owner_member_id} disabled={readonly} compact onChange={onOwner} />
          )}
          <VisibilityMenu value={e.visibility || 'crew'} visibleTo={e.visible_to || []}
            disabled={readonly} compact onChange={onVis} />
        </div>
      )}
    </article>
  )
}

/* --- создание карточки: форма перед сохранением ----------------------------- */

export function CreateForm({ kind, label, statuses, createExtra, autoOwn, onClose, onDone }: {
  kind: string
  label: string
  statuses: string[]
  createExtra?: GalleryField[]
  autoOwn?: string
  onClose: () => void
  onDone: (id: string) => void
}) {
  const { isGM } = useApp()
  const { t } = useTranslation('entity')
  const [refs, setRefs] = useState<Record<string, Dict | null>>({})
  const [form, setForm] = useState<Dict>({
    name: '', summary: '', status: statuses[0] || 'active', owner_member_id: '',
    faction_ids: [], location_ids: [], visible_to: [], fields: {},
    visibility: isGM ? 'gm' : 'crew',
  })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const set = (k: string, v: any) => setForm(f => ({ ...f, [k]: v }))
  const setField = (key: string, v: string | string[]) =>
    setForm(f => ({ ...f, fields: { ...f.fields, [key]: v } }))

  const save = async () => {
    const name = form.name.trim()
    if (!name) { setErr(t('create.need_name')); return }
    setBusy(true); setErr('')
    try {
      const made = await api.post(`${c()}/entities`, {
        kind, name, summary: form.summary, status: form.status,
        faction_ids: form.faction_ids, location_ids: form.location_ids,
        fields: form.fields, visibility: form.visibility, visible_to: form.visible_to,
        owner_member_id: form.owner_member_id || autoOwn || null,
      })
      onDone(String(made?.id || ''))
    } catch (e: any) {
      setErr(e?.message || t('create.save_failed'))
      setBusy(false)
    }
  }

  return (
    <Modal title={t('create.title', { label })} onClose={onClose} watch={form}>
      <Input label={t('create.name')} value={form.name} onChange={v => set('name', v)} />
      <Input label={t('summary')} type="textarea" rows={3} value={form.summary}
        onChange={v => set('summary', v)} />
      {statuses.length > 0 && (
        <Input label={t('status')} value={form.status} options={statuses}
          onChange={v => set('status', v)} />
      )}
      {(createExtra || []).map(f => f.type === 'ref'
        ? (
          <EntityPicker key={f.key} label={f.label} kind={f.kinds} placeholder={t('start_typing')}
            value={refs[f.key] || null}
            onChange={x => { setRefs(r => ({ ...r, [f.key]: x })); setField(f.key, x?.id || '') }} />
        )
        : f.type === 'multi'
        ? (
          <div key={f.key} className="field">
            <label>{f.label}</label>
            <MultiPick options={f.options || []} value={form.fields[f.key]} max={f.max}
              onChange={v => setField(f.key, v)} />
          </div>
        )
        : (
          <Input key={f.key} label={f.label} value={form.fields[f.key] || ''}
            type={f.type === 'textarea' ? 'textarea' : 'text'}
            options={f.type === 'select' ? (f.options || []) : undefined}
            optionLabel={f.key === 'rank' ? rankRoman : undefined}
            onChange={v => setField(f.key, v)} />
        ))}
      {kind !== 'faction' && (
        <div className="field">
          <label>{t('factions')}</label>
          <AffiliationPicker ids={form.faction_ids} kind="faction"
            onChange={(ids: string[]) => set('faction_ids', ids)} />
        </div>
      )}
      {kind !== 'location' && (
        <div className="field">
          <label>{kind === 'faction' ? t('hq') : t('place')}</label>
          <AffiliationPicker ids={form.location_ids} kind="location"
            onChange={(ids: string[]) => set('location_ids', ids)} />
        </div>
      )}
      {isGM && (
        <OwnerPicker value={form.owner_member_id}
          onChange={v => set('owner_member_id', v || '')} />
      )}
      <div className="field">
        <label>{t('who_sees')}</label>
        <div className="row wrap">
          <VisibilityMenu value={form.visibility} visibleTo={form.visible_to}
            onChange={(v, to) => setForm(f => ({ ...f, visibility: v, visible_to: to }))} />
        </div>
      </div>
      {err && <div className="eg-err">{err}</div>}
      <button className="primary eg-save-btn" disabled={busy || !form.name.trim()}
        onClick={save}>{busy ? t('create.saving') : t('common:save')}</button>
    </Modal>
  )
}
