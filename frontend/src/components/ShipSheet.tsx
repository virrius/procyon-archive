import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api, c, isPublicView, type Dict, thumb } from '../api'
import { useApp } from '../ctx'
import { Modal, Select } from '../ui'
import { RecordsPanel } from './RecordsPanel'
import { IconButton, IconClose, IconEdit, IconPlus, IconTrash } from './icons'
import { ImgActions, ImgFlags } from './ImageTools'
import Stub from './Stub'
import EntityPicker from './EntityPicker'
import PasteImage from '../paste'
import '../styles.ship.css'

type Entry = { key: string; name: string; text?: string; cost?: number; role?: string }
type ContactRef = { entity_id: string; state: string }
type Book = {
  slots: Dict; modules: Dict; talents: Entry[]; upgrades: Entry[]
  xp_triggers: string[]; sizes: string[]
}

const SYSTEMS: { sec: string; label: string; key: string; dmg: string }[] = [
  { sec: 'hull', label: 'system.hull', key: 'sys_hull', dmg: 'dmg_hull' },
  { sec: 'engines', label: 'system.engines', key: 'sys_engines', dmg: 'dmg_engines' },
  { sec: 'sensors', label: 'system.sensors', key: 'sys_sensors', dmg: 'dmg_sensors' },
  { sec: 'guns', label: 'system.guns', key: 'sys_guns', dmg: 'dmg_guns' },
]

const KITS: { sec: string; label: string }[] = [
  { sec: 'extra', label: 'kit.extra' },
  { sec: 'gear', label: 'kit.gear' },
  { sec: 'crew_gear', label: 'kit.crew_gear' },
  { sec: 'training', label: 'kit.training' },
]

const MOD_SECS = [...SYSTEMS.map(s => ({ sec: s.sec, label: s.label })), ...KITS]

const SYS_MAX = 3
const POWER_MAX = 8
const XP_MAX = 8
const RANK_MAX = 4
const CREDS_MAX = 4
const DEBT_MAX = 8
const MISS_MAX = 3
const EDIT_KEY = 'pa_ship_edit'
const AUTOSAVE_MS = 700

const STATES = ['neutral', 'friend', 'rival']
const FLAG: Dict = { friend: 'flag.friend', neutral: 'flag.neutral', rival: 'flag.rival' }

const num = (v: any): number => {
  const n = Number(v)
  return Number.isFinite(n) ? Math.max(0, Math.trunc(n)) : 0
}
const list = (v: any): string[] => (Array.isArray(v) ? v.filter(x => typeof x === 'string') : [])
const dict = (v: any): Dict => (v && typeof v === 'object' && !Array.isArray(v) ? v : {})
const entries = (v: any): Entry[] =>
  (Array.isArray(v) ? v : [])
    .filter(x => x && typeof x === 'object' && typeof x.key === 'string' && x.key)
    .map(x => ({
      key: String(x.key),
      name: String(x.name ?? x.key),
      text: x.text ? String(x.text) : undefined,
      cost: x.cost == null ? undefined : num(x.cost),
      role: x.role ? String(x.role) : undefined,
    }))

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v ?? null)) as T

/** На сервер уходят только ключи, тронутые на этом бланке; убранный ключ — null.
 *  Соседний бланк, открытый на другом устройстве, так не затирает чужую правку. */
const changedKeys = (next: Dict, base: Dict): Dict => {
  const out: Dict = {}
  for (const k of new Set([...Object.keys(base), ...Object.keys(next)])) {
    const v = next[k] === undefined ? null : next[k]
    if (JSON.stringify(v) !== JSON.stringify(base[k] ?? null)) out[k] = v
  }
  return out
}

const PHONE = '(max-width: 760px)'

/** Телефон: раскладка плотнее, длинные описания талантов по умолчанию свёрнуты. */
function usePhone() {
  const [on, setOn] = useState(() =>
    typeof window !== 'undefined' && !!window.matchMedia?.(PHONE).matches)
  useEffect(() => {
    const mq = window.matchMedia?.(PHONE)
    if (!mq) return
    const sync = () => setOn(mq.matches)
    sync()
    mq.addEventListener('change', sync)
    return () => mq.removeEventListener('change', sync)
  }, [])
  return on
}

let keySeq = 0
const newKey = () => `c${Date.now().toString(36)}${(keySeq++).toString(36)}`

const readContacts = (v: any): ContactRef[] =>
  (Array.isArray(v) ? v : [])
    .filter(x => x && typeof x === 'object' && typeof x.entity_id === 'string' && x.entity_id)
    .map(x => ({
      entity_id: String(x.entity_id),
      state: STATES.includes(x.state) ? String(x.state) : 'neutral',
    }))
const serContacts = (rows: ContactRef[]): Dict[] =>
  rows.map(r => ({ entity_id: r.entity_id, state: r.state }))

export function ShipSheet({ ship, loading }: { ship: Dict | null; loading?: boolean }) {
  const { meta, isGM, campaign } = useApp()
  const { t } = useTranslation('ship')
  const phone = usePhone()
  const canEdit = !isPublicView() && campaign?.my_role !== 'observer'
  const canBuild = isGM && !isPublicView()
  const shipId: string = ship?.id || ''

  const [edit, setEdit] = useState(() => localStorage.getItem(EDIT_KEY) === '1')
  const [fields, setFields] = useState<Dict>(ship?.fields || {})
  const [saved, setSaved] = useState<Dict>(ship?.fields || {})
  const [name, setName] = useState<string>(ship?.name || '')
  const [savedName, setSavedName] = useState<string>(ship?.name || '')
  const [shot, setShot] = useState<string>(ship?.image_url || '')
  // поштучно закрытое ГМом: из него бланку нужен только снимок
  const [hid, setHid] = useState<string[]>(ship?.hidden_fields || [])
  const [phase, setPhase] = useState<'' | 'busy' | 'ok'>('')
  const [err, setErr] = useState('')
  const [npcs, setNpcs] = useState<Dict[]>([])
  const [adding, setAdding] = useState(false)
  const [builder, setBuilder] = useState(false)

  useEffect(() => {
    setFields(ship?.fields || {})
    setSaved(ship?.fields || {})
    setName(ship?.name || '')
    setSavedName(ship?.name || '')
    setShot(ship?.image_url || '')
    setHid(ship?.hidden_fields || [])
    setPhase(''); setErr('')
    setAdding(false); setBuilder(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shipId])

  useEffect(() => {
    if (!shipId) { setNpcs([]); return }
    let alive = true
    api.get(`${c()}/entities?kind=npc`)
      .then(r => { if (alive) setNpcs(Array.isArray(r) ? r : []) })
      .catch(() => { if (alive) setNpcs([]) })
    return () => { alive = false }
  }, [shipId])

  const dirty = JSON.stringify(fields) !== JSON.stringify(saved) || name.trim() !== savedName

  const save = useCallback(async (next: Dict) => {
    if (!shipId) return
    const title = name.trim()
    const rename = !!title && title !== savedName
    const diff = changedKeys(next, saved)
    if (!Object.keys(diff).length && !rename) { setSaved(next); return }
    setPhase('busy'); setErr('')
    try {
      await api.patch(`${c()}/entities/${shipId}`, {
        ...(Object.keys(diff).length ? { fields: diff } : {}), ...(rename ? { name: title } : {}),
      })
      setSaved(next)
      if (rename) { setName(title); setSavedName(title) }
      setPhase('ok')
    } catch (e: any) {
      setErr(e?.message || t('err.save')); setPhase('')
    }
  }, [shipId, name, savedName, saved, t])

  /* Правки уходят сами: пауза в наборе, выход из режима правки, уход со страницы.
     Отдельной кнопки «сохранить» на бланке нет — как в остальных формах. */
  const saveRef = useRef(save)
  saveRef.current = save
  const draft = useRef(fields)
  draft.current = fields
  const dirtyRef = useRef(dirty)
  dirtyRef.current = dirty

  useEffect(() => {
    if (!dirty) return
    const t = window.setTimeout(() => void saveRef.current(draft.current), AUTOSAVE_MS)
    return () => window.clearTimeout(t)
  }, [dirty, fields, name])

  useEffect(() => () => { if (dirtyRef.current) void saveRef.current(draft.current) }, [])

  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  if (loading) return <div className="dim">{t('common:loading')}</div>
  if (!ship) return <div className="empty">{t('no_ship')}</div>

  // правки живут в черновике, на сервер уходят автосейвом
  const put = (next: Dict) => { setFields(next); setPhase(''); setErr('') }
  const putSoon = put

  const editing = canEdit && edit
  const setMode = (v: boolean) => {
    if (!v && dirty) void save(fields)
    setEdit(v)
    localStorage.setItem(EDIT_KEY, v ? '1' : '0')
  }

  const set = (k: string, v: any) => put({ ...fields, [k]: v })
  const setSoon = (k: string, v: any) => putSoon({ ...fields, [k]: v })
  const flip = (k: string, key: string) => {
    const cur = list(fields[k])
    put({ ...fields, [k]: cur.includes(key) ? cur.filter(x => x !== key) : [...cur, key] })
  }

  /* --- справочник и шаблон этого корабля ------------------------------------ */

  const types = dict(meta?.ship_types)
  const typeKeys = Object.keys(types)
  const type = dict(types[String(fields.ship_type || '')])
  const modsMeta = dict(meta?.ship_modules)
  const bookSlots = dict(type.slots)
  const bookSizes = list(meta?.ship_sizes)

  const custom = dict(fields.custom)
  const cuMods = dict(custom.modules)
  const cuSlots = dict(custom.slots)
  const hasCuSlots = Object.keys(cuSlots).length > 0

  const secItems = (sec: string): Entry[] =>
    Array.isArray(cuMods[sec]) ? entries(cuMods[sec]) : entries(modsMeta[sec])
  const secPower = (sec: string): number =>
    hasCuSlots && cuSlots[sec] != null ? num(cuSlots[sec]) : num(bookSlots[sec])

  const sizes = Array.isArray(custom.sizes) ? list(custom.sizes) : bookSizes
  const talentItems = Array.isArray(custom.talents) ? entries(custom.talents) : entries(type.talents)
  const upgradeItems = Array.isArray(custom.upgrades) ? entries(custom.upgrades) : entries(type.upgrades)
  const xpTriggers = Array.isArray(custom.xp_triggers) ? list(custom.xp_triggers) : list(type.xp_triggers)

  const book: Book = {
    slots: bookSlots,
    modules: Object.fromEntries(MOD_SECS.map(s => [s.sec, entries(modsMeta[s.sec])] as [string, Entry[]])),
    talents: entries(type.talents),
    upgrades: entries(type.upgrades),
    xp_triggers: list(type.xp_triggers),
    sizes: bookSizes,
  }

  /** Смена типа ставит заводскую комплектацию нового корабля вместо прежних отметок:
   *  чужие модули на бланке путают сильнее, чем потеря пары галочек. */
  const pickType = (k: string) => {
    const stock = list(dict(types[k]).start_modules)
    const drop = list(fields.modules).filter(m => !stock.includes(m))
    if (drop.length && !confirm(t('stock_confirm', { n: drop.length }))) return
    const start = dict(dict(types[k]).systems)
    const quals = Object.fromEntries(
      SYSTEMS.filter(s => start[s.sec] != null).map(s => [s.key, String(num(start[s.sec]))]))
    put({ ...fields, ...quals, ship_type: k, modules: stock })
  }

  const mods = list(fields.modules)
  const talents = list(fields.talents)
  const upgrades = list(fields.upgrades)

  const rank = num(fields.crew_rank)
  const sysSum = SYSTEMS.reduce((s, x) => s + num(fields[x.key]), 0)
  const upkeep = Math.floor((sysSum + rank) / 4)

  const known = new Set<string>()
  new Set([...Object.keys(modsMeta), ...Object.keys(cuMods), ...MOD_SECS.map(s => s.sec)])
    .forEach(sec => secItems(sec).forEach(m => known.add(m.key)))
  const orphanMods = mods.filter(k => !known.has(k))
  const orphanTalents = talents.filter(k => !talentItems.some(x => x.key === k))
  const orphanUpgrades = upgrades.filter(k => !upgradeItems.some(x => x.key === k))

  /* --- знакомые экипажа: только карточки NPC -------------------------------- */

  const contactRows = readContacts(fields.contacts)
  const npcById: Dict = {}
  npcs.forEach(n => { if (n?.id) npcById[n.id] = n })
  const takenIds = contactRows.map(r => r.entity_id || '').filter(Boolean)

  const putContacts = (rows: ContactRef[]) => put({ ...fields, contacts: serContacts(rows) })
  const cycleContact = (i: number) => {
    const rows = contactRows.slice()
    const cur = rows[i]
    if (!cur) return
    rows[i] = { ...cur, state: STATES[(STATES.indexOf(cur.state) + 1) % STATES.length] }
    putContacts(rows)
  }
  const dropContact = (i: number) => {
    const rows = contactRows.slice()
    rows.splice(i, 1)
    putContacts(rows)
  }
  const linkNpc = async (npcId: string) => {
    try {
      await api.post(`${c()}/links`, {
        from_id: shipId, to_id: npcId, label: t('contact_link'), visibility: 'crew',
      })
    } catch { /* связь необязательна: знакомый уже записан в бланк */ }
  }
  const addContact = async (npc: Dict) => {
    setAdding(false)
    if (!npc?.id || takenIds.includes(npc.id)) return
    putContacts([...contactRows, { entity_id: npc.id, state: 'neutral' }])
    setNpcs(prev => (prev.some(n => n.id === npc.id) ? prev : [...prev, npc]))
    await linkNpc(npc.id)
  }

  /* --- прочее -------------------------------------------------------------- */

  const saveTemplate = (next: Dict) => {
    const f = { ...fields }
    if (Object.keys(next).length) f.custom = next
    else delete f.custom
    put(f)
    setBuilder(false)
  }

  const saveShot = async (url: string) => {
    setPhase('busy'); setErr('')
    try {
      await api.patch(`${c()}/entities/${shipId}`, { image_url: url })
      setShot(url); setPhase('ok')
    } catch (e: any) { setErr(e?.message || t('err.image')); setPhase('') }
  }
  const shotHidden = hid.includes('image_url')
  // закрытый снимок игрок не меняет: сервер такую правку не примет
  const shotLocked = !isGM && shotHidden
  const hideShot = async (hide: boolean) => {
    const next = [...hid.filter(k => k !== 'image_url'), ...(hide ? ['image_url'] : [])]
    setPhase('busy'); setErr('')
    try {
      const r = await api.patch(`${c()}/entities/${shipId}`, { hidden_fields: next })
      setHid(r?.hidden_fields || next); setPhase('ok')
    } catch (e: any) { setErr(e?.message || t('err.visibility')); setPhase('') }
  }
  const upload = async (f?: File | null) => {
    if (!f) return
    const fd = new FormData()
    fd.append('file', f)
    fd.append('target_type', 'entity')
    fd.append('target_id', shipId)
    setPhase('busy'); setErr('')
    try {
      const r = await api.post(`${c()}/upload`, fd)
      await saveShot(r.url)
    } catch (e: any) { setErr(e?.message || t('err.upload')); setPhase('') }
  }

  // подпись берём из бланка типа, но своя строка её перекрывает; пустая — возврат к книжной
  const ownBlurb = String(fields.blurb ?? '')
  const blurb = ownBlurb.trim() || String(type.blurb || '')

  return (
    <div className={`ss${editing ? ' edit' : ''}`}>
      {/* Ctrl+V на бланке — вставленный снимок становится снимком корабля */}
      <PasteImage enabled={editing && !shotLocked} onFiles={files => void upload(files[0])}
        question={shot ? t('paste.replace') : t('paste.set')} />
      <div className="ss-tools">
        {canBuild && (
          <button className="ghost tiny ss-build" onClick={() => setBuilder(true)}>{t('setup')}</button>
        )}
        <div className="spacer" />
        {err
          ? <span className="ss-state bad">{err}</span>
          : phase === 'busy' || dirty
            ? <span className="ss-state">{t('saving')}</span>
            : phase === 'ok' && <span className="ss-state">{t('saved')}</span>}
        {canEdit && (
          <button className={`ss-mode${edit ? ' on' : ''}`} aria-pressed={edit}
            onClick={() => setMode(!edit)}>
            <span className="ss-mode-box" />{t('edit')}
          </button>
        )}
      </div>

      {typeKeys.length === 0 && (
        <div className="ss-warn">
          {t('no_reference')}
        </div>
      )}

      {/* шапка: название с подписью, справа на том же уровне реноме.
          «класс корабля» и «цвет / вид» с бланка убраны — их держат тип и снимок */}
      <header className="ss-head">
        <div className="ss-name">
          {editing
            ? <input className="ss-line-in ss-name-in" value={name} placeholder={t('name_ph')}
                onChange={e => { setName(e.target.value); setPhase(''); setErr('') }} />
            : <h2>{savedName || ship.name}</h2>}
          {editing
            ? <textarea className="ss-line-in ss-blurb-in" rows={2} value={ownBlurb}
                placeholder={String(type.blurb || t('blurb_ph'))}
                onChange={e => setSoon('blurb', e.target.value)} />
            : blurb && <div className="ss-blurb">{blurb}</div>}
        </div>
        <Line label={t('reputation')} value={fields.reputation} edit={editing}
          onChange={v => setSoon('reputation', v)} />
      </header>

      {/* снимок и состояние экипажа: ранг с опытом, размер, ресурсы */}
      <div className="ss-top">
        <section className="ss-p ss-shot imgbox">
          {shot
            ? <img className="ss-shot-img" src={thumb(shot, 960)} alt={ship.name} />
            : <Stub kind="ship" className="ss-shot-none" caption={t('shot.none')} />}
          <ImgFlags hidden={isGM && shotHidden} />
          {editing && !shotLocked && (
            <ImgActions
              vis={isGM ? { hidden: shotHidden, onChange: hide => void hideShot(hide) } : undefined}
              upload={{
                title: shot ? t('shot.replace') : t('shot.upload'),
                onFile: file => void upload(file),
              }}
              remove={shot ? { title: t('shot.remove'), onClick: () => void saveShot('') } : undefined} />
          )}
        </section>

        <div className="ss-status">
          <div className="ss-strip">
            <div className="ss-strip-cell">
              <span className="ss-cap">{t('crew_quality')}</span>
              <Pips n={RANK_MAX} value={rank} onSet={editing ? v => set('crew_rank', v) : undefined} />
            </div>
            <div className="ss-strip-cell grow">
              <span className="ss-cap">{t('size')}</span>
              {editing && sizes.length > 0
                ? <Select className="ss-size-sel" value={String(fields.size || '')} options={sizes}
                    empty={t('size_unset')} onChange={v => set('size', v)} />
                : <span className="ss-size on">{String(fields.size || '—')}</span>}
            </div>
          </div>

          <Panel title={t('crew_xp')}
            count={`${Math.min(num(fields.crew_xp), XP_MAX)}/${XP_MAX}`}>
            <>
              <div className="ss-xp-bar">
                <Pips n={XP_MAX} value={num(fields.crew_xp)}
                  onSet={editing ? v => set('crew_xp', Math.min(v, XP_MAX)) : undefined} />
                <div className="spacer" />
                <span className="ss-track-n">{Math.min(num(fields.crew_xp), XP_MAX)} / {XP_MAX}</span>
              </div>
              <details className="ss-why">
                <summary>{t('xp_why')}</summary>
                <div className="ss-hint">
                  {t('xp_hint')}
                </div>
                {xpTriggers.length > 0
                  ? <ul className="ss-xp">{xpTriggers.map((x, i) => <li key={i}>{x}</li>)}</ul>
                  : <div className="ss-empty">{t('xp_empty')}</div>}
              </details>
            </>
          </Panel>

          <Panel title={t('res_title')}>
            <div className="ss-res">
              <Track label={t('cred')} n={CREDS_MAX} value={num(fields.creds)}
                onSet={editing ? v => set('creds', v) : undefined} />
              <Track label={t('debt')} n={DEBT_MAX} value={num(fields.debt)} tone="rust"
                onSet={editing ? v => set('debt', v) : undefined} />
              <div className="ss-upkeep">
                <div>
                  <div className="ss-cap">{t('upkeep')}</div>
                  <div className="ss-hint">{t('upkeep_formula')}</div>
                </div>
                <span className="ss-big">{upkeep}</span>
              </div>
              <div className="ss-hint">
                {t('upkeep_now', { sys: sysSum, rank })}
              </div>
              <Track label={t('skipped')} n={MISS_MAX} value={num(fields.upkeep_missed)} tone="rust"
                onSet={editing ? v => set('upkeep_missed', v) : undefined} />
            </div>
          </Panel>
        </div>
      </div>

      <Lane title={t('lane.systems')}>
        {SYSTEMS.map(s => {
            const items = secItems(s.sec)
            const power = secPower(s.sec)
            const pipN = power || SYS_MAX
            const used = items.filter(m => mods.includes(m.key)).length
            const q = num(fields[s.key])
            const d = num(fields[s.dmg])
            return (
              <Panel key={s.sec} title={t(s.label)}
                count={power > 0 ? `${used}/${power}` : undefined}
                head={
                  <span className="ss-meter">
                    <span className="ss-cap">{t('quality')}</span>
                    <Pips n={pipN} value={q} onSet={editing ? v => set(s.key, v) : undefined} />
                  </span>
                }
                sub={
                  <div className="ss-dmg">
                    <span className="ss-meter">
                      <span className="ss-cap">{t('damage')}</span>
                      <Pips n={pipN} value={d} tone="dmg"
                        onSet={editing ? v => set(s.dmg, Math.min(v, pipN)) : undefined} />
                    </span>
                    <div className="spacer" />
                    <span className="ss-eff" title={t('rating_title')}>
                      {t('rating')} <b className={d > 0 ? 'hurt' : ''}>{Math.max(0, q - d)}</b>
                    </span>
                  </div>
                }>
                <Picks items={items} taken={mods} edit={editing} compact={!editing}
                  open={!phone}
                  onToggle={editing ? k => flip('modules', k) : undefined}
                  empty={t('sys_empty')} />
              </Panel>
            )
          })}
      </Lane>

      <Lane title={t('lane.upgrades')}>
        {KITS.map(k => {
          const items = secItems(k.sec)
          const used = items.filter(m => mods.includes(m.key)).length
          return (
            <Panel key={k.sec} title={t(k.label)}
              count={items.length ? `${used}/${items.length}` : undefined}>
              <Picks items={items} taken={mods} edit={editing} compact={!editing}
                cost open={!phone} onToggle={editing ? m => flip('modules', m) : undefined}
                empty={t('ref_empty')} />
            </Panel>
          )
        })}

        <Panel title={t('upgrades')}
          count={upgradeItems.length ? `${upgrades.length}/${upgradeItems.length}` : undefined}>
          <Picks items={upgradeItems} taken={upgrades} edit={editing} cost
            compact={!editing} open={!phone}
            onToggle={editing ? k => flip('upgrades', k) : undefined}
            empty={t('upgrades_empty')} />
          {orphanUpgrades.length > 0 && (
            <div className="ss-sub">
              <div className="ss-cap">{t('unlisted')}</div>
              <Picks items={orphanUpgrades.map(k => ({ key: k, name: k }))} taken={upgrades}
                edit={editing} onToggle={editing ? k => flip('upgrades', k) : undefined} />
            </div>
          )}
        </Panel>

        {orphanMods.length > 0 && (
          <Panel title={t('unlisted_mods')} count={String(orphanMods.length)}>
            <Picks items={orphanMods.map(k => ({ key: k, name: k }))} taken={mods} edit={editing}
              onToggle={editing ? k => flip('modules', k) : undefined} />
          </Panel>
        )}
      </Lane>

      <Lane title={t('talents')} one
        count={talentItems.length ? `${talents.length}/${talentItems.length}` : undefined}>
        <div className="ss-p-b ss-lane-plain">
          <Picks items={talentItems} taken={talents} edit={editing} open={!phone}
            compact={!editing}
            onToggle={editing ? k => flip('talents', k) : undefined}
            empty={t('talents_empty')} />
          {orphanTalents.length > 0 && (
            <div className="ss-sub">
              <div className="ss-cap">{t('unlisted')}</div>
              <Picks items={orphanTalents.map(k => ({ key: k, name: k }))} taken={talents}
                edit={editing} onToggle={editing ? k => flip('talents', k) : undefined} />
            </div>
          )}
        </div>
      </Lane>

      <Lane title={t('contacts')} one
        head={editing && !adding && (
          <IconButton icon={<IconPlus />} title={t('contact_add')}
            onClick={() => setAdding(true)} />
        )}>
        <div className="ss-p-b ss-lane-plain">
          {contactRows.length === 0 && !adding && (
            editing
              ? <button className="ghost tiny" onClick={() => setAdding(true)}>{t('contact_add')}</button>
              : <div className="ss-empty">{t('contacts_empty')}</div>
          )}

          <div className="ss-contacts">
            {contactRows.map((r, i) => (
              <ContactNpc key={`e:${i}:${r.entity_id}`} id={r.entity_id!} npc={npcById[r.entity_id!]}
                state={r.state}
                onCycle={editing ? () => cycleContact(i) : undefined}
                onDrop={editing ? () => dropContact(i) : undefined} />
            ))}
          </div>

          {adding && (
            <NpcPicker exclude={takenIds} note={t('contact_pick')}
              onPick={n => { void addContact(n) }} onClose={() => setAdding(false)} />
          )}
        </div>
      </Lane>

      <RecordsPanel entityType="entity" entityId={ship.id} title={t('notes')} />

      {builder && (
        <SheetBuilder custom={custom} book={book} types={types} shipType={String(fields.ship_type || '')}
          onSave={saveTemplate} onPickType={pickType}
          onFactory={() => { if (fields.ship_type) pickType(String(fields.ship_type)) }}
          onClose={() => setBuilder(false)} />
      )}
    </div>
  )
}

export default ShipSheet

/* --- свимлейн бланка ------------------------------------------------------- */

/** Полоса раздела: подпись с чертой, под ней панели в два столбца
    (`one` — в один, когда внутри длинные описания). */
function Lane({ title, count, head, one, children }: {
  title: string; count?: string; head?: ReactNode; one?: boolean; children: ReactNode
}) {
  return (
    <section className={`ss-lane${one ? ' one' : ''}`}>
      <div className="ss-lane-hd">
        <span className="ss-lane-t">{title}</span>
        <span className="ss-lane-rule" />
        {count && <span className="ss-slots">{count}</span>}
        {head}
      </div>
      <div className="ss-lane-b">{children}</div>
    </section>
  )
}

/* --- панель бланка --------------------------------------------------------- */

/** Разделы бланка не складываются: на телефоне мельче шрифт и две колонки,
    так вся картина остаётся на виду. Справа в заголовке — счётчик отметок. */
function Panel({ title, head, sub, count, children }: {
  title: string; head?: ReactNode; sub?: ReactNode; count?: string; children: ReactNode
}) {
  const { t } = useTranslation('ship')
  return (
    <section className="ss-p">
      <div className="ss-p-hd">
        <span className="ss-p-t">{title}</span>
        {head}
        {count && (
          <>
            <div className="spacer" />
            <span className="ss-slots" title={t('marked_of')}>{count}</span>
          </>
        )}
      </div>
      {sub}
      <div className="ss-p-b">{children}</div>
    </section>
  )
}

/* --- строка бланка --------------------------------------------------------- */

function Line({ label, value, hint, edit, wide, area, onChange }: {
  label: string; value?: any; hint?: string; edit?: boolean
  wide?: boolean; area?: boolean; onChange: (v: string) => void
}) {
  const v = value == null ? '' : String(value)
  return (
    <div className={`ss-line${wide ? ' wide' : ''}`}>
      {edit
        ? (area
            ? <textarea className="ss-line-in" rows={2} value={v} placeholder={hint}
                onChange={e => onChange(e.target.value)} />
            : <input className="ss-line-in" value={v} placeholder={hint}
                onChange={e => onChange(e.target.value)} />)
        : <div className="ss-line-v">{v || <span className="ss-none">—</span>}</div>}
      <div className="ss-cap">{label}</div>
    </div>
  )
}

/* --- деления показателя ---------------------------------------------------- */

function Pips({ n, value, tone, onSet }: {
  n: number; value: number; tone?: string; onSet?: (v: number) => void
}) {
  const { t } = useTranslation('ship')
  const total = Math.max(n, value)
  return (
    <span className="ss-pips" title={t('of', { value, n })}>
      {Array.from({ length: total }, (_, i) => {
        const cls = `ss-pip${tone ? ' ' + tone : ''}${i < value ? ' on' : ''}`
        return onSet
          ? <button key={i} className={cls} aria-label={`${i + 1}`}
              onClick={() => onSet(value === i + 1 ? i : i + 1)} />
          : <span key={i} className={cls} />
      })}
    </span>
  )
}

/* --- ряд квадратиков: креды, долг, пропуски -------------------------------- */

function Track({ label, n, value, tone, onSet }: {
  label: string; n: number; value: number; tone?: string; onSet?: (v: number) => void
}) {
  const total = Math.max(n, value)
  return (
    <div className="ss-track">
      <div className="ss-cap">{label}</div>
      <div className="ss-sqs">
        {Array.from({ length: total }, (_, i) => {
          const cls = `ss-sq${i < value ? ' on' : ''}${tone ? ' ' + tone : ''}`
          return onSet
            ? <button key={i} className={cls} aria-label={`${i + 1}`}
                onClick={() => onSet(value === i + 1 ? i : i + 1)} />
            : <span key={i} className={cls} />
        })}
        <span className="ss-track-n">{value}</span>
      </div>
    </div>
  )
}

/* --- список с отметками: модули, таланты, улучшения ------------------------ */

function Picks({ items, taken, edit, onToggle, cost, open, empty, compact }: {
  items: Entry[]; taken: string[]; edit?: boolean; onToggle?: (key: string) => void
  cost?: boolean; open?: boolean; empty?: string; compact?: boolean
}) {
  const { t } = useTranslation('ship')
  // вне правки в списке остаётся только отмеченное — свободные строки не нужны
  if (items.length === 0) return compact ? null : <div className="ss-empty">{empty || '—'}</div>
  const shown = compact ? items.filter(it => taken.includes(it.key)) : items
  if (shown.length === 0) return null
  return (
    <ul className="ss-picks">
      {shown.map(it => {
        const on = taken.includes(it.key)
        const marks = (
          <>
            {cost && num(it.cost) > 1 && <span className="ss-cost">×{it.cost}</span>}
          </>
        )
        return (
          <li className={`ss-pick${on ? ' on' : ''}`} key={it.key}>
            {onToggle
              ? <button className={`ss-tick${on ? ' on' : ''}`} aria-pressed={on}
                  title={on ? t('untick') : t('tick')} onClick={() => onToggle(it.key)} />
              : <span className={`ss-tick${on ? ' on' : ''}`} />}
            {it.text
              ? open
                ? <div className="ss-fold plain">
                    <div className="ss-nm-row"><span className="ss-nm">{it.name}</span>{marks}</div>
                    <div className="ss-text">{it.text}</div>
                  </div>
                : <details className="ss-fold">
                    <summary><span className="ss-nm">{it.name}</span>{marks}</summary>
                    <div className="ss-text">{it.text}</div>
                  </details>
              : <div className="ss-fold flat"><span className="ss-nm">{it.name}</span>{marks}</div>}
          </li>
        )
      })}
    </ul>
  )
}

/* --- знакомые -------------------------------------------------------------- */

function Flag({ state, onCycle }: { state: string; onCycle?: () => void }) {
  const { t } = useTranslation('ship')
  const label = FLAG[state] ? t(FLAG[state]) : state
  return onCycle
    ? <button className={`ss-flag ${state}`} title={t('flag_cycle')}
        onClick={onCycle}>{label}</button>
    : <span className={`ss-flag ${state}`}>{label}</span>
}

function ContactNpc({ id, npc, state, onCycle, onDrop }: {
  id: string; npc?: Dict; state: string; onCycle?: () => void; onDrop?: () => void
}) {
  const { t } = useTranslation('ship')
  const role = npc ? String(npc.summary || '') : t('card_na')
  return (
    <div className="ss-contact">
      <div className="ss-contact-hd">
        {npc
          ? <Link className="ss-nm on" to={`/entity/${id}/profile`}>{npc.name}</Link>
          : <span className="ss-nm on">{t('npc_na')}</span>}
        <div className="spacer" />
        <Flag state={state} onCycle={onCycle} />
        {onDrop && <IconButton icon={<IconTrash />} title={t('contact_drop')} danger onClick={onDrop} />}
      </div>
      {role && <div className="ss-role">{role}</div>}
    </div>
  )
}

function NpcPicker({ exclude, note, onPick, onClose }: {
  exclude: string[]; note?: string; onPick: (npc: Dict) => void; onClose: () => void
}) {
  const { t } = useTranslation('ship')
  return (
    <div className="ss-npc">
      <div className="ss-npc-hd">
        <span className="ss-cap">{note}</span>
        <IconButton icon={<IconClose />} title={t('cancel')} onClick={onClose} />
      </div>
      <div className="ss-npc-pick">
        <EntityPicker label="" value={null} kind="npc" exclude={exclude} listed autoFocus
          placeholder={t('npc_search')} onChange={n => { if (n) onPick(n) }} />
      </div>
    </div>
  )
}

/* --- конструктор бланка (только настоящий ГМ) ------------------------------ */

function SheetBuilder({ custom, book, types, shipType, onSave, onPickType, onFactory, onClose }: {
  custom: Dict; book: Book; types: Dict; shipType: string
  onSave: (next: Dict) => void; onPickType: (k: string) => void
  onFactory: () => void; onClose: () => void
}) {
  const { t } = useTranslation('ship')
  const typeKeys = Object.keys(types)
  const [d, setD] = useState<Dict>(() => clone(dict(custom)))

  const patch = (k: string, v: any) => setD(prev => {
    const next = { ...prev }
    if (v === undefined) delete next[k]
    else next[k] = v
    return next
  })

  // мощность систем
  const cuSlots = dict(d.slots)
  const ownSlots = Object.keys(cuSlots).length > 0
  const powerOf = (sec: string) =>
    ownSlots && cuSlots[sec] != null ? num(cuSlots[sec]) : num(book.slots[sec])
  const forkSlots = () =>
    patch('slots', Object.fromEntries(SYSTEMS.map(s => [s.sec, num(book.slots[s.sec])] as [string, number])))
  const setPower = (sec: string, v: number) => {
    const base: Dict = Object.fromEntries(SYSTEMS.map(s => [s.sec, powerOf(s.sec)] as [string, number]))
    base[sec] = Math.max(0, Math.min(POWER_MAX, num(v)))
    patch('slots', base)
  }

  // модули по разделам
  const cuMods = dict(d.modules)
  const ownMods = (sec: string) => Array.isArray(cuMods[sec])
  const modsOf = (sec: string): Entry[] =>
    ownMods(sec) ? entries(cuMods[sec]) : (book.modules[sec] || [])
  const setMods = (sec: string, arr: Entry[]) => patch('modules', { ...cuMods, [sec]: arr })
  const resetMods = (sec: string) => {
    const rest = { ...cuMods }
    delete rest[sec]
    patch('modules', Object.keys(rest).length ? rest : undefined)
  }

  // таланты / улучшения / триггеры / размеры
  const ownTalents = Array.isArray(d.talents)
  const talents = ownTalents ? entries(d.talents) : book.talents
  const ownUpgrades = Array.isArray(d.upgrades)
  const upgrades = ownUpgrades ? entries(d.upgrades) : book.upgrades
  const ownXp = Array.isArray(d.xp_triggers)
  const xp = ownXp ? list(d.xp_triggers) : book.xp_triggers
  const ownSizes = Array.isArray(d.sizes)
  const sizes = ownSizes ? list(d.sizes) : book.sizes

  /** Пустые строки, набранные и брошенные, в шаблон не уезжают. */
  const clean = (): Dict => {
    const out: Dict = {}
    if (Object.keys(dict(d.slots)).length) out.slots = dict(d.slots)
    const m: Dict = {}
    Object.keys(dict(d.modules)).forEach(sec => {
      if (Array.isArray(dict(d.modules)[sec])) {
        m[sec] = entries(dict(d.modules)[sec]).filter(x => x.name.trim())
      }
    })
    if (Object.keys(m).length) out.modules = m
    if (ownTalents) out.talents = talents.filter(x => x.name.trim())
    if (ownUpgrades) out.upgrades = upgrades.filter(x => x.name.trim())
    if (ownXp) out.xp_triggers = xp.map(x => x.trim()).filter(Boolean)
    if (ownSizes) out.sizes = sizes.map(x => x.trim()).filter(Boolean)
    return out
  }

  return (
    <Modal title={t('builder.title')} wide onClose={onClose}>
      <div className="sb">
        <div className="sb-note">
          {t('builder.note')}
        </div>

        {typeKeys.length > 0 && (
          <div className="sb-sect">
            <div className="sb-hd">
              <span className="sb-t">{t('builder.reference')}</span>
              <span className="sb-src">{t('builder.preset')}</span>
            </div>
            <div className="col" style={{ gap: 7 }}>
              <label className="ss-sel">
                <span className="ss-cap">{t('builder.type')}</span>
                <Select value={shipType} options={typeKeys} empty={t('builder.custom_ship')}
                  optionLabel={k => dict(types[k]).label || k}
                  title={t('builder.type')} onChange={onPickType} />
              </label>
              <div className="sb-flat">
                {t('builder.type_hint')}
              </div>
            </div>
          </div>
        )}

        <Sect label={t('builder.power')} own={ownSlots}
          onFork={forkSlots} onReset={() => patch('slots', undefined)}>
          {ownSlots
            ? <div className="sb-powers">
                {SYSTEMS.map(s => (
                  <label className="sb-power" key={s.sec}>
                    <span className="ss-cap">{t(s.label)}</span>
                    <input type="number" min={0} max={POWER_MAX} value={powerOf(s.sec)}
                      onChange={e => setPower(s.sec, num(e.target.value))} />
                  </label>
                ))}
              </div>
            : <div className="sb-flat">
                {SYSTEMS.map(s => `${t(s.label).toLowerCase()} ${num(book.slots[s.sec])}`).join(' · ')}
              </div>}
          <div className="ss-hint">{t('builder.power_hint')}</div>
        </Sect>

        <details className="sb-group">
          <summary>{t('builder.mods')}</summary>
          {MOD_SECS.map(s => (
            <Sect key={s.sec} label={t(s.label)} own={ownMods(s.sec)}
              onFork={() => setMods(s.sec, clone(book.modules[s.sec] || []))}
              onReset={() => resetMods(s.sec)}
              onAdd={() => setMods(s.sec, [...modsOf(s.sec), { key: newKey(), name: '' }])}>
              {ownMods(s.sec)
                ? <EntryRows items={modsOf(s.sec)} onChange={arr => setMods(s.sec, arr)} />
                : <Flat items={modsOf(s.sec)} />}
            </Sect>
          ))}
        </details>

        <Sect label={t('talents')} own={ownTalents}
          onFork={() => patch('talents', clone(book.talents))}
          onReset={() => patch('talents', undefined)}
          onAdd={() => patch('talents', [...talents, { key: newKey(), name: '' }])}>
          {ownTalents
            ? <EntryRows items={talents} onChange={arr => patch('talents', arr)} />
            : <Flat items={talents} />}
        </Sect>

        <Sect label={t('upgrades')} own={ownUpgrades}
          onFork={() => patch('upgrades', clone(book.upgrades))}
          onReset={() => patch('upgrades', undefined)}
          onAdd={() => patch('upgrades', [...upgrades, { key: newKey(), name: '', cost: 1 }])}>
          {ownUpgrades
            ? <EntryRows items={upgrades} cost onChange={arr => patch('upgrades', arr)} />
            : <Flat items={upgrades} />}
        </Sect>

        <Sect label={t('builder.xp')} own={ownXp}
          onFork={() => patch('xp_triggers', clone(book.xp_triggers))}
          onReset={() => patch('xp_triggers', undefined)}
          onAdd={() => patch('xp_triggers', [...xp, ''])}>
          {ownXp
            ? <TextRows items={xp} placeholder={t('builder.xp_ph')}
                onChange={arr => patch('xp_triggers', arr)} />
            : <div className="sb-flat">{xp.join(' · ') || '—'}</div>}
        </Sect>

        <Sect label={t('builder.sizes')} own={ownSizes}
          onFork={() => patch('sizes', clone(book.sizes))}
          onReset={() => patch('sizes', undefined)}
          onAdd={() => patch('sizes', [...sizes, ''])}>
          {ownSizes
            ? <TextRows items={sizes} placeholder={t('builder.size_ph')}
                onChange={arr => patch('sizes', arr)} />
            : <div className="sb-flat">{sizes.join(' · ') || '—'}</div>}
        </Sect>

        <div className="sb-foot">
          <button className="ghost" onClick={() => { setD({}); onFactory() }}
            title={t('builder.reset_all_title')}>
            {t('builder.reset_all')}
          </button>
          <div className="spacer" />
          <button className="ghost" onClick={onClose}>{t('cancel')}</button>
          <button className="primary" onClick={() => onSave(clean())}>{t('common:save')}</button>
        </div>
      </div>
    </Modal>
  )
}

function Sect({ label, own, onFork, onReset, onAdd, children }: {
  label: string; own: boolean; onFork: () => void; onReset: () => void
  onAdd?: () => void; children: ReactNode
}) {
  const { t } = useTranslation('ship')
  return (
    <section className="sb-sect">
      <div className="sb-hd">
        <span className="sb-t">{label}</span>
        <span className={`sb-src${own ? ' own' : ''}`}>{own ? t('builder.own') : t('builder.default')}</span>
        <div className="spacer" />
        {own
          ? <>
              {onAdd && <IconButton icon={<IconPlus />} title={t('builder.add_row')} onClick={onAdd} />}
              <button className="ghost tiny" title={t('builder.reset_title')}
                onClick={onReset}>{t('builder.reset')}</button>
            </>
          : <IconButton icon={<IconEdit />} title={t('builder.edit_sect')} onClick={onFork} />}
      </div>
      {children}
    </section>
  )
}

function Flat({ items }: { items: Entry[] }) {
  return <div className="sb-flat">{items.map(i => i.name).join(' · ') || '—'}</div>
}

function EntryRows({ items, cost, onChange }: {
  items: Entry[]; cost?: boolean; onChange: (v: Entry[]) => void
}) {
  const { t } = useTranslation('ship')
  const upd = (i: number, part: Partial<Entry>) =>
    onChange(items.map((it, j) => (j === i ? { ...it, ...part } : it)))
  return (
    <div className="sb-rows">
      {items.length === 0 && <div className="ss-empty">{t('builder.empty')}</div>}
      {items.map((it, i) => (
        <div className="sb-row" key={it.key}>
          <input className="sb-name" value={it.name} placeholder={t('builder.name_ph')}
            onChange={e => upd(i, { name: e.target.value })} />
          {cost && (
            <input className="sb-cost" type="number" min={1} max={9} value={it.cost ?? 1}
              title={t('builder.cost_title')}
              onChange={e => upd(i, { cost: Math.max(1, num(e.target.value)) })} />
          )}
          <input className="sb-text" value={it.text || ''} placeholder={t('builder.text_ph')}
            onChange={e => upd(i, { text: e.target.value })} />
          <IconButton icon={<IconTrash />} title={t('builder.del_row')} danger
            onClick={() => onChange(items.filter((_, j) => j !== i))} />
        </div>
      ))}
    </div>
  )
}

function TextRows({ items, placeholder, onChange }: {
  items: string[]; placeholder?: string; onChange: (v: string[]) => void
}) {
  const { t } = useTranslation('ship')
  return (
    <div className="sb-rows">
      {items.length === 0 && <div className="ss-empty">{t('builder.empty')}</div>}
      {items.map((v, i) => (
        <div className="sb-row" key={i}>
          <input className="sb-text" value={v} placeholder={placeholder}
            onChange={e => onChange(items.map((x, j) => (j === i ? e.target.value : x)))} />
          <IconButton icon={<IconTrash />} title={t('builder.del_row')} danger
            onClick={() => onChange(items.filter((_, j) => j !== i))} />
        </div>
      ))}
    </div>
  )
}
