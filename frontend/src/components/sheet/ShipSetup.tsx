import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c, type Dict } from '../../api'
import { useApp } from '../../ctx'
import { clone, dict, entries, type Entry, EntryRows, list, newKey, num, Pips, Sect, TextRows, useAutosave } from './parts'
import { MOD_SECS, shipBook, stockFields, SYSTEMS } from './ship'
import '../../styles.ship.css'

const POWER_MAX = 4

/** Ship setup (GM space): own rows on top of its type's book. Writes straight into the ship
 *  card, `fields.custom`; the type itself is picked on the ship sheet. */
export default function ShipSetup({ ship, onSaved }: { ship: Dict; onSaved: (e: Dict) => void }) {
  const { meta } = useApp()
  const { t } = useTranslation('ship')
  const fields: Dict = ship.fields || {}
  const { type, book } = shipBook(meta, fields)
  const [d, setD] = useState<Dict>(() => clone(dict(fields.custom)))
  const [phase, setPhase] = useState<'' | 'busy' | 'ok'>('')
  const [err, setErr] = useState('')

  /** A reset is written at once, bypassing autosave. */
  const write = async (part: Dict) => {
    setPhase('busy'); setErr('')
    try {
      onSaved(await api.patch(`${c()}/entities/${ship.id}`, { fields: part }))
      setPhase('ok')
    } catch (e: any) { setErr(e?.message || t('err.save')); setPhase('') }
  }

  const patch = (k: string, v: any) => {
    setD(prev => {
      const next = { ...prev }
      if (v === undefined) delete next[k]
      else next[k] = v
      return next
    })
  }

  const cuSlots = dict(d.slots)
  const ownSlots = Object.keys(cuSlots).length > 0
  const powerOf = (sec: string) =>
    ownSlots && cuSlots[sec] != null ? num(cuSlots[sec]) : num(book.slots[sec])
  const setPower = (sec: string, v: number) => {
    const base: Dict = Object.fromEntries(SYSTEMS.map(s => [s.sec, powerOf(s.sec)] as [string, number]))
    base[sec] = Math.max(0, Math.min(POWER_MAX, num(v)))
    patch('slots', base)
  }

  const cuMods = dict(d.modules)
  const ownMods = (sec: string) => Array.isArray(cuMods[sec])
  const modsOf = (sec: string): Entry[] => (ownMods(sec) ? entries(cuMods[sec]) : (book.modules[sec] || []))
  const setMods = (sec: string, arr: Entry[]) => patch('modules', { ...cuMods, [sec]: arr })
  const resetMods = (sec: string) => {
    const rest = { ...cuMods }
    delete rest[sec]
    patch('modules', Object.keys(rest).length ? rest : undefined)
  }

  const ownTalents = Array.isArray(d.talents)
  const talents = ownTalents ? entries(d.talents) : book.talents
  const ownUpgrades = Array.isArray(d.upgrades)
  const upgrades = ownUpgrades ? entries(d.upgrades) : book.upgrades
  const ownXp = Array.isArray(d.xp_triggers)
  const xp = ownXp ? list(d.xp_triggers) : book.xp_triggers
  const ownSizes = Array.isArray(d.sizes)
  const sizes = ownSizes ? list(d.sizes) : book.sizes

  /** Empty rows, typed and abandoned, don't go into the template. */
  const clean = (): Dict => {
    const out: Dict = {}
    if (Object.keys(dict(d.slots)).length) out.slots = dict(d.slots)
    const m: Dict = {}
    Object.keys(dict(d.modules)).forEach(sec => {
      if (Array.isArray(dict(d.modules)[sec])) m[sec] = entries(dict(d.modules)[sec]).filter(x => x.name.trim())
    })
    if (Object.keys(m).length) out.modules = m
    if (ownTalents) out.talents = talents.filter(x => x.name.trim())
    if (ownUpgrades) out.upgrades = upgrades.filter(x => x.name.trim())
    if (ownXp) out.xp_triggers = xp.map(x => x.trim()).filter(Boolean)
    if (ownSizes) out.sizes = sizes.map(x => x.trim()).filter(Boolean)
    return out
  }
  const next = clean()
  const auto = useAutosave({ custom: Object.keys(next).length ? next : null }, async b => {
    onSaved(await api.patch(`${c()}/entities/${ship.id}`, { fields: b }))
  }, t('err.save'))

  const shown = auto.err || err
  const busy = auto.phase === 'busy' || phase === 'busy'
  const ok = auto.phase === 'ok' || phase === 'ok'

  return (
    <div className="sb">
      <div className="sb-note">
        {type.label ? t('builder.note', { type: type.label }) : t('builder.note_custom')}
      </div>

      <Sect label={t('builder.power')} own={ownSlots} onReset={() => patch('slots', undefined)}>
        <div className="sb-powers">
          {SYSTEMS.map(s => (
            <div className="sb-power" key={s.sec}>
              <span className="ss-cap">{t(s.label)}</span>
              <Pips n={POWER_MAX} value={powerOf(s.sec)} onSet={v => setPower(s.sec, v)} />
              <span className="sb-meter-n">{powerOf(s.sec)}</span>
            </div>
          ))}
        </div>
        <div className="ss-hint">{t('builder.power_hint')}</div>
      </Sect>

      <div className="sb-group">
        <div className="sb-group-t">{t('builder.mods')}</div>
        {MOD_SECS.map(s => (
          <Sect key={s.sec} label={t(s.label)} own={ownMods(s.sec)} count={modsOf(s.sec).length}
            onReset={() => resetMods(s.sec)}>
            <EntryRows items={modsOf(s.sec)} onChange={arr => setMods(s.sec, arr)}
              onAdd={() => setMods(s.sec, [...modsOf(s.sec), { key: newKey(), name: '' }])} />
          </Sect>
        ))}
      </div>

      <Sect label={t('talents')} own={ownTalents} count={talents.length} onReset={() => patch('talents', undefined)}>
        <EntryRows items={talents} onChange={arr => patch('talents', arr)}
          onAdd={() => patch('talents', [...talents, { key: newKey(), name: '' }])} />
      </Sect>

      <Sect label={t('upgrades')} own={ownUpgrades} count={upgrades.length} onReset={() => patch('upgrades', undefined)}>
        <EntryRows items={upgrades} cost onChange={arr => patch('upgrades', arr)}
          onAdd={() => patch('upgrades', [...upgrades, { key: newKey(), name: '', cost: 1 }])} />
      </Sect>

      <div className="sb-pair">
        <Sect label={t('builder.xp')} own={ownXp} count={xp.length} onReset={() => patch('xp_triggers', undefined)}>
          <TextRows items={xp} placeholder={t('builder.xp_ph')} onChange={arr => patch('xp_triggers', arr)}
            onAdd={() => patch('xp_triggers', [...xp, ''])} />
        </Sect>
        <Sect label={t('builder.sizes')} own={ownSizes} count={sizes.length} onReset={() => patch('sizes', undefined)}>
          <TextRows items={sizes} placeholder={t('builder.size_ph')} onChange={arr => patch('sizes', arr)}
            onAdd={() => patch('sizes', [...sizes, ''])} />
        </Sect>
      </div>

      {(Object.keys(d).length > 0 || shown || busy || ok) && <div className="sb-foot">
        {Object.keys(d).length > 0 && (
          <button className="ghost" title={t('builder.reset_all_title')} onClick={() => {
            const stock = fields.ship_type ? stockFields(meta, fields, String(fields.ship_type)) : null
            if (!confirm(stock?.dropped ? t('stock_confirm', { n: stock.dropped }) : t('builder.reset_all_ask'))) return
            setD({})
            auto.mark({ custom: null })
            void write({ custom: null, ...(stock?.patch || {}) })
          }}>{t('builder.reset_all')}</button>
        )}
        <div className="spacer" />
        {shown ? <span className="ss-state bad">{shown}</span>
          : busy ? <span className="ss-state">{t('saving')}</span>
          : ok && <span className="ss-state">{t('saved')}</span>}
      </div>}
    </div>
  )
}
