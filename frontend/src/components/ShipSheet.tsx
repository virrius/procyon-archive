import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c, isPublicView, type Dict, thumb } from '../api'
import { useApp } from '../ctx'
import { Select } from '../ui'
import { RecordsPanel } from './RecordsPanel'
import { IconButton, IconPlus } from './icons'
import { ImgActions, ImgFlags } from './ImageTools'
import Stub from './Stub'
import PasteImage from '../paste'
import {
  changedKeys, ContactNpc, type ContactRef, dict, entries, type Entry, Lane, Line, list, NpcPicker, num, Panel,
  Picks, Pips, readContacts, serContacts, STATES, Track, usePhone,
} from './sheet/parts'
import { KITS, MOD_SECS, stockFields, SYSTEMS } from './sheet/ship'
import '../styles.ship.css'

const SYS_MAX = 3
const XP_MAX = 8
const RANK_MAX = 4
const CREDS_MAX = 4
const DEBT_MAX = 8
const MISS_MAX = 3
const EDIT_KEY = 'pa_ship_edit'
const AUTOSAVE_MS = 700

export function ShipSheet({ ship, loading }: { ship: Dict | null; loading?: boolean }) {
  const { meta, isGM, campaign } = useApp()
  const { t } = useTranslation('ship')
  const phone = usePhone()
  const canEdit = !isPublicView() && campaign?.my_role !== 'observer'
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

  useEffect(() => {
    setFields(ship?.fields || {})
    setSaved(ship?.fields || {})
    setName(ship?.name || '')
    setSavedName(ship?.name || '')
    setShot(ship?.image_url || '')
    setHid(ship?.hidden_fields || [])
    setPhase(''); setErr('')
    setAdding(false)
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
  const pickType = (k: string) => {
    const { patch, dropped } = stockFields(meta, fields, k)
    if (dropped && !confirm(t('stock_confirm', { n: dropped }))) return
    put({ ...fields, ...patch })
  }
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
            ? <textarea className="ss-line-in ss-blurb-in" rows={1} value={ownBlurb}
                placeholder={String(type.blurb || t('blurb_ph'))}
                onChange={e => setSoon('blurb', e.target.value)} />
            : blurb && <div className="ss-blurb">{blurb}</div>}
        </div>
        <Line label={t('reputation')} value={fields.reputation} edit={editing} area
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
            <div className="ss-strip-cell">
              <span className="ss-cap">{t('builder.type')}</span>
              {editing && isGM && typeKeys.length > 0
                ? <Select className="ss-size-sel" value={String(fields.ship_type || '')} options={typeKeys}
                    empty={t('builder.custom_ship')} optionLabel={k => dict(types[k]).label || k}
                    title={t('builder.type')} onChange={pickType} />
                : <span className="ss-size on">{String(type.label || '—')}</span>}
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
                <Picks items={items} taken={mods} edit={editing} compact={!editing} rest
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
              <Picks items={items} taken={mods} edit={editing} compact={!editing} rest
                cost open={!phone} onToggle={editing ? m => flip('modules', m) : undefined}
                empty={t('ref_empty')} />
            </Panel>
          )
        })}

        <Panel title={t('upgrades')}
          count={upgradeItems.length ? `${upgrades.length}/${upgradeItems.length}` : undefined}>
          <Picks items={upgradeItems} taken={upgrades} edit={editing} cost
            compact={!editing} rest open={!phone}
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
            compact={!editing} rest
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
    </div>
  )
}

export default ShipSheet

