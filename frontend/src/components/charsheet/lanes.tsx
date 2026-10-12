import { Fragment, type ReactNode, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { type Dict } from '../../api'
import { asList } from '../../ui'
import { IconButton, IconPlus } from '../icons'
import {
  ContactNpc, dict, type Entry, Lane, list, NpcPicker, num, Panel, Picks, Pips, readContacts, serContacts,
  STATES, TextMore, Track,
} from '../sheet/parts'
import {
  ACT_MAX, ARMOR_KEYS, type Attr, ATTR_XP, type Book, bookOf, CREDS_MAX, effective, HARM_KEYS,
  HEAL_MAX, loadChoices, loadLimit, LOADS, loadUsed, PB_XP, pointsOf, STASH_MAX, talentKey, talentOf,
  TRAUMA_MAX, VET_MAX,
} from './model'

/** Что знает каждый свимлейн бланка: черновик полей и как его менять.
 *  `marks` — игровые отметки (вкладка «Бланк»), `pick` — разовые выборы (вкладка «Настройка»). */
export type Ctx = {
  f: Dict
  set: (k: string, v: any) => void
  patch: (part: Dict) => void
  marks: boolean
  pick: boolean
  isGM: boolean
  phone: boolean
  meta: Dict | null
  sheet: Dict
  book: Book | null
  pb: string
  eff: ReturnType<typeof effective>
  /** настройка бланков кампании */
  setup: Dict
  /** поле закрыто ГМом и этому зрителю пришло пустым */
  locked: (k: string) => boolean
  /** глаз ГМа «закрыть от стола» */
  eye: (k: string) => ReactNode
}

const optionsOf = (meta: Dict | null, key: string): string[] =>
  list((meta?.kinds?.character?.fields || []).find((x: Dict) => x.key === key)?.options)
const textOf = (rows: any, name: string): string =>
  String((Array.isArray(rows) ? rows : []).find((r: Dict) => r?.name === name)?.text || '')
const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s)

/** Заметка к происхождению, прошлому, страсти: поле растёт по тексту. */
function NoteBox({ value, placeholder, onChange }: { value: string; placeholder: string; onChange: (v: string) => void }) {
  const box = useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight + 1}px`
  }, [value])
  return (
    <textarea ref={box} className="cs-idnote" rows={1} value={value} placeholder={placeholder}
      onChange={e => onChange(e.target.value)} />
  )
}

/* --- происхождение, прошлое, страсть, креды ------------------------------- */

function IdRow({ c, label, field, refKey, multi, ph }: {
  c: Ctx; label: string; field: string; refKey: string; multi?: boolean; ph: string
}) {
  const opts = optionsOf(c.meta, field)
  const val = multi ? asList(c.f[field]) : String(c.f[field] || '')
  const picked = multi ? (val as string[]) : val ? [val as string] : []
  const note = String(c.f[`${field}_note`] || '')
  const shut = c.locked(field)
  const toggle = (o: string) => {
    if (!multi) return c.set(field, val === o ? '' : o)
    const cur = val as string[]
    c.set(field, cur.includes(o) ? cur.filter(x => x !== o) : [...cur, o].slice(0, 2))
  }
  if (c.pick) {
    const hint = picked.map(o => [o, textOf(c.sheet[refKey], o)]).filter(([, x]) => x)
    return (
      <section className="ss-p cs-idcard">
        <div className="ss-p-hd"><span className="ss-p-t">{label}</span>{c.eye(field)}</div>
        <div className="ss-p-b">
          {shut
            ? <span className="unknown">?</span>
            : <>
                <div className="cs-chips">
                  {[...opts, ...picked.filter(o => !opts.includes(o))].map(o => {
                    const on = picked.includes(o)
                    return (
                      <button key={o} className={`cs-chip${on ? ' on' : ''}`} title={textOf(c.sheet[refKey], o)}
                        disabled={multi && !on && picked.length >= 2} onClick={() => toggle(o)}>{o}</button>
                    )
                  })}
                </div>
                {hint.length > 0 && (
                  <div className="cs-idhint">{hint.map(([o, x]) => <div key={o}><b>{o}.</b> {x}</div>)}</div>
                )}
                <NoteBox value={note} placeholder={ph} onChange={v => c.set(`${field}_note`, v)} />
              </>}
        </div>
      </section>
    )
  }
  return (
    <div className="cs-idrow">
      <span className="ss-cap">{label}{c.eye(field)}</span>
      <div className="cs-idv">
        {shut
          ? <span className="unknown">?</span>
          : picked.length
            ? <><b>{picked.join(', ')}</b>{note && <span className="cs-note"> — {note}</span>}</>
            : <span className="ss-none">—</span>}
      </div>
    </div>
  )
}

export function Identity({ c }: { c: Ctx }) {
  const { t } = useTranslation('char')
  return (
    <Lane cols={3} id="identity">
      <IdRow c={c} label={t('id.heritage')} field="heritage" refKey="heritages" ph={t('id.ph_heritage')} />
      <IdRow c={c} label={t('id.past')} field="past" refKey="pasts" ph={t('id.ph_past')} />
      <IdRow c={c} label={t('id.vice')} field="vice" refKey="vices" multi ph={t('id.ph_vice')} />
    </Lane>
  )
}

/** Происхождение, прошлое и страсть одной строкой под именем — на «Бланке». */
export function IdLine({ c }: { c: Ctx }) {
  const { t } = useTranslation('char')
  const part = (field: string, label: string) => {
    if (c.locked(field)) return <span key={field} title={label}>?</span>
    const v = asList(c.f[field]).join(', ') || String(c.f[field] || '')
    if (!v) return null
    return <span key={field} title={label}><b>{v}</b></span>
  }
  const parts = [part('heritage', t('id.heritage')), part('past', t('id.past')), part('vice', t('id.vice'))]
    .filter(Boolean)
  return parts.length ? <div className="cs-idline">{parts}</div> : null
}

/** Подпись с правилом из книги: нажатие раскрывает две-три строки под ней. */
function HelpHead({ k, tip, setTip, label, children }: {
  k: string; tip: string; setTip: (k: string) => void; label: string; children?: ReactNode
}) {
  return (
    <div className="cs-rl">
      <button className={`cs-hl${tip === k ? ' on' : ''}`} aria-expanded={tip === k}
        onClick={() => setTip(tip === k ? '' : k)}>{label}</button>
      {children}
    </div>
  )
}

/* --- колонка состояния: всё, что меняется по ходу дела ---------------------- */

type RailPart = 'stress' | 'trauma' | 'harm' | 'load' | 'money'
const RAIL_ALL: RailPart[] = ['stress', 'trauma', 'harm', 'load', 'money']

/** `parts` — какие блоки показать: на телефоне колонка режется на куски между разделами бланка. */
export function Rail({ c, parts = RAIL_ALL }: { c: Ctx; parts?: RailPart[] }) {
  const { t } = useTranslation('char')
  const has = (k: RailPart) => parts.includes(k)
  const [tip, setTip] = useState('')
  const [menu, setMenu] = useState(false)
  const stress = num(c.f.stress)
  const max = c.eff.stressMax
  const traumas = asList(c.f.trauma)
  const harm = dict(c.f.harm)
  const healing = num(c.f.healing)
  const armor = dict(c.f.armor)
  const stash = num(c.f.stash)
  // ступени судьбы из книги, по строке заначки на ступень: ступень взята, когда её строка заполнена
  const tiers: any[][] = Array.isArray(c.sheet.stash) ? c.sheet.stash : []
  const tierName = (r?: any[]) => String(r?.[2] || '').split(':')[0].trim()
  const fateName = tierName(tiers[Math.max(Math.min(Math.floor(stash / 10), tiers.length) - 1, 0)]).toLowerCase()
  const effs = dict(c.sheet.harm)
  const head = (k: string, label: string, right?: ReactNode) => (
    <HelpHead k={k} tip={tip} setTip={setTip} label={label}>{right}</HelpHead>
  )
  const tipBox = (k: string, body: ReactNode) => tip === k && <div className="cs-tip">{body}</div>
  const setHarm = (k: string, v: string) => c.set('harm', { ...harm, [k]: v })
  const slot = (k: string) => (c.marks
    ? <input key={k} className="cs-hslot" value={String(harm[k] || '')} aria-label={k}
        onChange={e => setHarm(k, e.target.value)} />
    : <span key={k} className="cs-hslot">{String(harm[k] || '')}</span>)
  const setStash = (i: number) => c.set('stash', stash === i + 1 ? i : i + 1)

  return (
    <aside className="cs-rail" data-sec="state">
      {has('stress') && (
        <div className="cs-rb">
          {head('stress', t('stress.stress'), <span className={`cs-rn${stress >= max - 2 ? ' hot' : ''}`}>{stress}/{max}</span>)}
          {tipBox('stress', t('help.stress'))}
          <div className="cs-stress">
            <Pips n={max} value={stress} tone="stress" onSet={c.marks ? v => c.set('stress', v) : undefined} />
          </div>
          {c.marks && stress >= max && traumas.length < TRAUMA_MAX && (
            menu
              ? <div className="cs-tmenu" role="menu">
                  <div className="cs-tmenu-hd">
                    <span>{t('stress.pick')}</span>
                    <button className="ghost tiny" onClick={() => setMenu(false)}>{t('cancel')}</button>
                  </div>
                  {optionsOf(c.meta, 'trauma').filter(o => !traumas.includes(o)).map(o => (
                    <button key={o} className="cs-topt" role="menuitem"
                      onClick={() => { c.patch({ trauma: [...traumas, o], stress: 0 }); setMenu(false) }}>
                      <b>{o}</b>{textOf(c.sheet.traumas, o) && <span>{textOf(c.sheet.traumas, o)}</span>}
                    </button>
                  ))}
                </div>
              : <div className="cs-call">
                  <span>{t('stress.full')}</span>
                  <button className="ghost tiny rust" onClick={() => setMenu(true)}>{t('stress.take')}</button>
                </div>
          )}
        </div>
      )}

      {has('trauma') && (
        <div className="cs-rb">
          {head('trauma', t('stress.trauma'), <span className="cs-rn">{traumas.length}/{TRAUMA_MAX}</span>)}
          {tipBox('trauma', t('help.trauma'))}
          <div className="cs-trauma">
            <Pips n={TRAUMA_MAX} value={traumas.length} tone="dmg" />
            {traumas.length > 0 && (
              <span className="cs-trs">
                {traumas.map(o => <span key={o} className="cs-tr" title={textOf(c.sheet.traumas, o)}>{o}</span>)}
              </span>
            )}
          </div>
          {traumas.length >= TRAUMA_MAX && (
            <div className="cs-call">{t('stress.retire')}{fateName && ` ${t('stress.fate', { fate: fateName })}`}</div>
          )}
        </div>
      )}

      {has('harm') && (
        <div className="cs-rb">
          {head('harm', t('harm.title'))}
          {tipBox('harm', t('help.harm'))}
          <div className="cs-harm">
            {([['3', ['h3']], ['2', ['h2a', 'h2b']], ['1', ['h1a', 'h1b']]] as [string, string[]][]).map(([lv, ks]) => (
              <div key={lv} className="cs-hrow">
                <span className="cs-hlv">{lv}</span>
                <span className="cs-hslots">{ks.map(slot)}</span>
                <span className={`cs-heff${ks.some(k => harm[k]) ? ' hot' : ''}`}>{String(effs[lv] || '')}</span>
              </div>
            ))}
          </div>
          <div className="cs-heal">
            <Clock n={HEAL_MAX} value={healing} onSet={c.marks ? v => c.set('healing', v) : undefined} />
            <span className="cs-rv">{t('harm.healing')} <b>{healing}/{HEAL_MAX}</b></span>
            {c.marks && healing >= HEAL_MAX && (
              <button className="ghost tiny" onClick={() => c.patch({
                harm: Object.fromEntries(HARM_KEYS.map(k => [k, ''])), healing: 0,
              })}>{t('harm.clear')}</button>
            )}
          </div>
          <div className="cs-armor">
            {ARMOR_KEYS.map(k => (
              <button key={k} className={`cs-arm${armor[k] ? ' on' : ''}`} disabled={!c.marks}
                aria-pressed={!!armor[k]} onClick={() => c.set('armor', { ...armor, [k]: !armor[k] })}>
                <i />{cap(t(`armor.${k}`))}
              </button>
            ))}
          </div>
        </div>
      )}

      {has('load') && <div className="cs-rb" data-sec="load"><LoadBlock c={c} /></div>}

      {has('money') && (
        <div className="cs-rb">
          <div className="cs-rl"><span className="cs-rt">{t('creds')}</span><span className="cs-rn">{num(c.f.creds)}/{CREDS_MAX}</span></div>
          <Track label="" n={CREDS_MAX} value={num(c.f.creds)} cls="bare"
            onSet={c.marks ? v => c.set('creds', v) : undefined} />
          <div className="cs-rl"><span className="cs-rt">{t('stash')}</span><span className="cs-rn">{stash}/{STASH_MAX}</span></div>
          <div className="cs-stash">
            {Array.from({ length: STASH_MAX / 10 }, (_, g) => (
              <div key={g} className={`cs-srow${stash >= (g + 1) * 10 ? ' on' : ''}`}>
                <span className="cs-sg">
                  {Array.from({ length: 10 }, (_, j) => {
                    const i = g * 10 + j
                    const cls = `ss-sq${i < stash ? ' on' : ''}`
                    return c.marks
                      ? <button key={j} className={cls} aria-label={`${i + 1}`} onClick={() => setStash(i)} />
                      : <span key={j} className={cls} />
                  })}
                </span>
                <span className="cs-slv" title={String(tiers[g]?.[2] || '')}>{tierName(tiers[g])}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </aside>
  )
}

/** Нагрузка: уровень и занятое. На ПК — в колонке состояния, на телефоне — в «Снаряжении». */
function LoadBlock({ c }: { c: Ctx }) {
  const { t } = useTranslation('char')
  const [tip, setTip] = useState('')
  const level = String(c.f.load || 'normal')
  const used = loadUsed(dict(c.f.items))
  const lim = loadLimit(level)
  const loads = dict(c.sheet.load)
  return (
    <>
      <HelpHead k="load" tip={tip} setTip={setTip} label={t('gear.load_title')}>
        <span className={`cs-rn${used > lim ? ' hot' : ''}`}>{used}/{lim}</span>
      </HelpHead>
      {tip === 'load' && (
        <div className="cs-tip">
          {LOADS.map(([k, n]) => <div key={k}><b>{cap(t(`gear.load.${k}`))} {n}.</b> {String(loads[k] || '')}</div>)}
          <div>{t('help.load')}</div>
        </div>
      )}
      {c.marks
        ? <span className="cs-seg">
            {LOADS.map(([k, n]) => (
              <button key={k} className={level === k ? 'on' : ''} title={String(loads[k] || '')}
                onClick={() => c.set('load', k)}>{cap(t(`gear.load.${k}`))} <b>{n}</b></button>
            ))}
          </span>
        : <span className="cs-rv">{cap(t(`gear.load.${level}`))}</span>}
      <div className="cs-loadbar">
        {Array.from({ length: Math.max(lim, used) }, (_, i) => (
          <i key={i} className={`${i < used ? 'on' : ''}${i >= lim ? ' over' : ''}`} />
        ))}
      </div>
    </>
  )
}

/* --- травмы выбирают на «Настройке»; на «Бланке» — только взятые ------------- */

export function TraumaPick({ c }: { c: Ctx }) {
  const { t } = useTranslation('char')
  const traumas = asList(c.f.trauma)
  const toggle = (name: string) =>
    c.set('trauma', traumas.includes(name) ? traumas.filter(x => x !== name) : [...traumas, name])
  const hint = traumas.map(o => [o, textOf(c.sheet.traumas, o)]).filter(([, x]) => x)
  return (
    <Lane title={t('stress.trauma')} one id="traumas" count={`${traumas.length}/${TRAUMA_MAX}`}>
      <div className="ss-p-b ss-lane-plain">
        <div className="cs-chips cs-traumas">
          {optionsOf(c.meta, 'trauma').map(o => {
            const on = traumas.includes(o)
            return (
              <button key={o} className={`cs-chip rust${on ? ' on' : ''}`}
                title={textOf(c.sheet.traumas, o)} disabled={!on && traumas.length >= TRAUMA_MAX}
                onClick={() => toggle(o)}>{o}</button>
            )
          })}
        </div>
        {hint.length > 0 && (
          <div className="cs-idhint cs-trhint">
            {hint.map(([o, x]) => <div key={o}><b>{o}.</b> {x}</div>)}
          </div>
        )}
      </div>
    </Lane>
  )
}

/** Счётчик лечения — круг на `n` делений, как на бумажном бланке. */
function Clock({ n, value, onSet }: { n: number; value: number; onSet?: (v: number) => void }) {
  const r = 20, o = 22
  return (
    <svg className={`cs-clock${onSet ? ' edit' : ''}`} viewBox="0 0 44 44">
      {Array.from({ length: n }, (_, i) => {
        const a0 = (i / n) * 2 * Math.PI - Math.PI / 2
        const a1 = ((i + 1) / n) * 2 * Math.PI - Math.PI / 2
        const d = `M${o},${o} L${(o + r * Math.cos(a0)).toFixed(2)},${(o + r * Math.sin(a0)).toFixed(2)} `
          + `A${r},${r} 0 0 1 ${(o + r * Math.cos(a1)).toFixed(2)},${(o + r * Math.sin(a1)).toFixed(2)} Z`
        return <path key={i} d={d} className={i < value ? 'on' : ''}
          onClick={onSet ? () => onSet(value === i + 1 ? i : i + 1) : undefined} />
      })}
    </svg>
  )
}

/* --- навыки и опыт характеристик ------------------------------------------- */

export function ActionsLane({ c }: { c: Ctx }) {
  const { t } = useTranslation('char')
  const [adv, setAdv] = useState('')
  const [open, setOpen, box] = useOneOpen()
  const attrs: Attr[] = Array.isArray(c.sheet.attributes) ? c.sheet.attributes : []
  const acts = dict(c.f.actions)
  const xp = dict(c.f.xp)
  // стартовые навыки бланка не снимаются — ниже них не опустить
  const start = dict(c.book?.start)
  const setAct = (k: string, v: number) =>
    c.set('actions', { ...acts, [k]: Math.max(num(start[k]), Math.min(ACT_MAX, v)) })
  const advance = (attr: string, k: string) => {
    c.patch({ actions: { ...acts, [k]: Math.min(ACT_MAX, num(acts[k]) + 1) }, xp: { ...xp, [attr]: 0 } })
    setAdv('')
  }
  return (
    <Lane title={t('lane.actions')} cols={3} id="actions">
      <div className="cs-acts-box" ref={box}>
        {attrs.map(a => {
          const x = num(xp[a.key])
          const on = adv === a.key
          const canAdv = c.marks && x >= ATTR_XP && !on
          return (
            <Panel key={a.key} title={a.name}
              head={<>
                <div className="spacer" />
                {!c.pick && (
                  <span title={t('xp.attr', { n: x, max: ATTR_XP })}>
                    <Pips n={ATTR_XP} value={x} onSet={c.marks ? v => c.set('xp', { ...xp, [a.key]: v }) : undefined} />
                  </span>
                )}
              </>}
              sub={(canAdv || on) && (
                <div className="ss-dmg">
                  {canAdv && <button className="ghost tiny amber" onClick={() => setAdv(a.key)}>{t('xp.advance')}</button>}
                  {on && <button className="ghost tiny" onClick={() => setAdv('')}>{t('cancel')}</button>}
                </div>
              )}>
              {on && <div className="cs-adv">{t('xp.adv_attr')}</div>}
              <div className="cs-acts">
                {a.actions.map(x2 => {
                  const v = num(acts[x2.key])
                  return (
                    <div key={x2.key} className={`cs-act${v ? ' has' : ''}${on ? ' adv' : ''}${on && v >= ACT_MAX ? ' max' : ''}`}>
                      <span className="cs-act-n">
                        {x2.text
                          ? <button type="button" className={`cs-help${open === x2.key ? ' open' : ''}`}
                              aria-expanded={open === x2.key} onClick={() => setOpen(open === x2.key ? '' : x2.key)}>
                              {x2.name}
                              <span className="cs-pop" role="tooltip">
                                <b>{x2.name}</b>{x2.text}{x2.more && <span className="more">{x2.more}</span>}
                              </span>
                            </button>
                          : x2.name}
                      </span>
                      {on
                        ? <button className="ghost tiny amber" disabled={v >= ACT_MAX}
                            onClick={() => advance(a.key, x2.key)}>+1</button>
                        : <Pips n={ACT_MAX} value={v} split={1}
                            onSet={c.pick ? n => setAct(x2.key, n) : undefined} />}
                    </div>
                  )
                })}
              </div>
            </Panel>
          )
        })}
      </div>
    </Lane>
  )
}

/* --- способность, таланты, опыт бланка ------------------------------------- */

/** Таланты списком с отметками: выбор на «Настройке» и развитие по опыту бланка на «Бланке». */
export function AbilitiesLane({ c, adv = false, setAdv, beside }: {
  c: Ctx; adv?: boolean; setAdv?: (v: boolean) => void; beside?: ReactNode
}) {
  const { t } = useTranslation('char')
  const book = c.book!
  const taken = list(c.f.talents)
  const xp = dict(c.f.xp)
  const own = c.eff.talents.map(x => ({ ...x, key: talentKey(c.pb, x.key) }))
  const ownKeys = new Set(own.map(x => x.key))
  const others = taken.filter(k => !ownKeys.has(k))
  const vets = others.map(k => talentOf(c.meta, c.setup, k)).filter(Boolean) as (Entry & { pbLabel: string })[]
  const orphans = others.filter(k => !talentOf(c.meta, c.setup, k))
  const pbs = Object.keys(dict(c.meta?.playbooks)).filter(k => k !== c.pb)

  const toggle = (k: string) => {
    // в развитии только берут новый: взятое не снимается
    if (adv) {
      if (taken.includes(k)) return
      c.patch({ talents: [...taken, k], xp: { ...xp, playbook: 0 } })
      setAdv?.(false)
      return
    }
    c.set('talents', taken.includes(k) ? taken.filter(x => x !== k) : [...taken, k])
  }
  const xeno = !!c.f.xeno
  const uniqueText = xeno ? String(c.f.xeno_text || '') : book.unique.text || ''

  return (
    <Lane title={t('lane.abilities')} one id="abilities" beside={beside}
      count={own.length && !(adv && c.phone) ? `${own.filter(x => taken.includes(x.key)).length}/${own.length}` : undefined}>
      <div className="ss-p-b ss-lane-plain">
        <div className={c.pick ? undefined : 'ss-sub'}>
          {adv && <div className="cs-adv">{t('xp.adv_playbook')}</div>}
          <div className="cs-unique">
            <div className="ss-nm on">
              {xeno ? t('unique.xeno') : book.unique.name}
              <span className="ss-cap cs-uniq-cap">{t('unique.cap')}</span>
            </div>
            {xeno && c.pick
              ? <textarea className="ss-line-in" rows={2} value={String(c.f.xeno_text || '')}
                  placeholder={cap(String(c.sheet.xeno || ''))} onChange={e => c.set('xeno_text', e.target.value)} />
              : <TextMore text={uniqueText || cap(String(c.sheet.xeno || ''))} more={xeno ? undefined : book.unique.more} />}
            {c.pick && (
              <button className="ghost tiny cs-xeno" onClick={() => c.set('xeno', !xeno)}>
                {xeno ? t('unique.back') : t('unique.to_xeno')}
              </button>
            )}
          </div>
          <Picks items={own} taken={taken} edit={c.pick || adv} open={!c.phone}
            compact={!c.pick && !adv} onToggle={c.pick || adv ? toggle : undefined}
            hot={adv ? it => !taken.includes(it.key) : undefined}
            lock={adv ? it => taken.includes(it.key) : undefined}
            empty={t('talents_empty')} />
        </div>

        {(vets.length > 0 || orphans.length > 0 || c.pick || adv) && (
          <div className="ss-sub">
            <div className="cs-subhd">
              <span className="ss-cap">{t('vet.title')}</span>
              <div className="spacer" />
              <span className="ss-slots">{vets.length + orphans.length}/{VET_MAX}</span>
            </div>
            <Picks items={vets} taken={taken} edit={c.pick} open={!c.phone} compact={!c.pick}
              onToggle={c.pick ? toggle : undefined}
              tag={it => <span className="cs-src">{(it as any).pbLabel}</span>} />
            {orphans.length > 0 && (
              <Picks items={orphans.map(k => ({ key: k, name: k }))} taken={taken} edit={c.pick}
                onToggle={c.pick ? toggle : undefined} />
            )}
            {(c.pick || adv) && vets.length + orphans.length < VET_MAX && (
              <select className="cs-vet" value="" onChange={e => { if (e.target.value) toggle(e.target.value) }}>
                <option value="">{t('vet.add')}</option>
                {pbs.map(k => {
                  const b = bookOf(c.meta, k)
                  return b && (
                    <optgroup key={k} label={b.label}>
                      {effective(b, {}, c.setup).talents.map(x => (
                        <option key={x.key} value={`${k}:${x.key}`} disabled={taken.includes(`${k}:${x.key}`)}>
                          {x.name}
                        </option>
                      ))}
                    </optgroup>
                  )
                })}
              </select>
            )}
          </div>
        )}
      </div>
    </Lane>
  )
}

/** Способности на «Бланке»: уникальная и взятые — карточками с текстом, невзятые — строкой.
 *  Развитие по опыту бланка разворачивает полный список с отметками. */
export function AbilityCards({ c, adv, setAdv }: { c: Ctx; adv: boolean; setAdv: (v: boolean) => void }) {
  const { t } = useTranslation('char')
  const [why, setWhy] = useState(false)
  if (adv) {
    return <AbilitiesLane c={c} adv setAdv={setAdv}
      beside={<XpHead c={c} why={false} setWhy={setWhy} adv setAdv={setAdv} />} />
  }
  const book = c.book!
  const taken = list(c.f.talents)
  const own = c.eff.talents.map(x => ({ ...x, key: talentKey(c.pb, x.key) }))
  const ownKeys = new Set(own.map(x => x.key))
  const mine = own.filter(x => taken.includes(x.key))
  const rest = own.filter(x => !taken.includes(x.key))
  const vets = taken.filter(k => !ownKeys.has(k))
    .map(k => talentOf(c.meta, c.setup, k) || ({ key: k, name: k, pbLabel: '' } as Entry & { pbLabel: string }))
  const xeno = !!c.f.xeno
  const card = (key: string, name: string, text: string, more?: string, src?: string, u?: boolean) => (
    <AbilityCard key={key} name={name} text={text} more={more} src={src} u={u} />
  )
  return (
    <Lane title={t('lane.abilities')} id="abilities"
      count={own.length && !c.phone ? `${mine.length}/${own.length}` : undefined}
      beside={<XpHead c={c} why={why} setWhy={setWhy} adv={false} setAdv={setAdv} />}>
      {why && <XpWhy c={c} />}
      <div className="cs-cards">
        {card('unique', xeno ? t('unique.xeno') : book.unique.name,
          xeno ? String(c.f.xeno_text || '') || cap(String(c.sheet.xeno || '')) : book.unique.text || '',
          xeno ? '' : book.unique.more, '', true)}
        {mine.map(x => card(x.key, x.name, x.text || '', x.more))}
        {vets.map(x => card(x.key, x.name, x.text || '', x.more, x.pbLabel))}
      </div>
      {rest.length > 0 && <RestLine label={t('rest')} items={rest} />}
    </Lane>
  )
}

/** Карточка способности: «подробнее» справа в строке описания — не съедает строку под текстом. */
function AbilityCard({ name, text, more, src, u }: { name: string; text: string; more?: string; src?: string; u?: boolean }) {
  const { t } = useTranslation('char')
  const [open, setOpen] = useState(false)
  return (
    <div className={`ss-p cs-card${u ? ' u' : ''}`}>
      <div className="cs-card-n">{name}{src && <span className="cs-src">{src}</span>}</div>
      {(text || more) && (
        <div className="cs-card-tr">
          <div className="cs-card-t">{text}</div>
          {more && (
            <button type="button" className="cs-more" aria-expanded={open} onClick={() => setOpen(!open)}>
              {t('sheet:more')} {open ? '−' : '+'}
            </button>
          )}
        </div>
      )}
      {more && open && <div className="ss-text dim">{more}</div>}
    </div>
  )
}

/** Одна раскрытая карточка на блок: по нажатию, закрывается кликом мимо или Esc (на ПК ещё и по наведению — в CSS). */
function useOneOpen() {
  const [open, setOpen] = useState('')
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const shut = (e: MouseEvent) => {
      // кнопки-подсказки блока переключают себя сами; всё остальное — клик мимо
      const at = e.target as Element
      if (box.current?.contains(at) && at.closest('[aria-expanded]')) return
      setOpen('')
    }
    const esc = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      setOpen('')
      const f = document.activeElement
      if (f instanceof HTMLElement && box.current?.contains(f)) f.blur()
    }
    document.addEventListener('click', shut)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('click', shut); document.removeEventListener('keydown', esc) }
  }, [open])
  return [open, setOpen, box] as const
}

/** Невзятые способности строкой; полный текст — карточкой под строкой по наведению, на телефоне по нажатию. */
function RestLine({ label, items }: { label: string; items: Entry[] }) {
  const [open, setOpen, box] = useOneOpen()
  return (
    <div className="cs-rest" ref={box}>
      {label}{' '}
      {items.map((x, i) => (
        <Fragment key={x.key}>
          {i > 0 && ' · '}
          <button type="button" className={`cs-rest-b${open === x.key ? ' open' : ''}`} aria-expanded={open === x.key}
            onClick={() => setOpen(open === x.key ? '' : x.key)}>
            {x.name}
            {(x.text || x.more) && (
              <span className="cs-pop" role="tooltip">
                <b>{x.name}</b>{x.text}{x.more && <span className="more">{x.more}</span>}
              </span>
            )}
          </button>
        </Fragment>
      ))}
    </div>
  )
}

/** Опыт бланка в заголовке «Способностей»: шкала, развитие при полной, плюсик раскрывает, за что даётся. */
function XpHead({ c, why, setWhy, adv, setAdv }: {
  c: Ctx; why: boolean; setWhy: (v: boolean) => void; adv: boolean; setAdv: (v: boolean) => void
}) {
  const { t } = useTranslation('char')
  const xp = dict(c.f.xp)
  const px = num(xp.playbook)
  return (
    <span className="cs-xph" title={t('xp.playbook')}>
      <Pips n={PB_XP} value={px} onSet={c.marks ? v => c.set('xp', { ...xp, playbook: v }) : undefined} />
      <span className="ss-track-n">{px}/{PB_XP}</span>
      {adv
        ? <button className="ghost tiny" onClick={() => setAdv(false)}>{t('cancel')}</button>
        : c.marks && px >= PB_XP && (
            <button className="ghost tiny amber" onClick={() => setAdv(true)}>{t('xp.advance')}</button>
          )}
      {!adv && (
        <button type="button" className="cs-xpq" aria-expanded={why} aria-label={t('xp.why')} title={t('xp.why')}
          onClick={() => setWhy(!why)}>{why ? '−' : '+'}</button>
      )}
    </span>
  )
}

/** За что даётся опыт — раскрывается плюсиком из заголовка. */
function XpWhy({ c }: { c: Ctx }) {
  const sx = dict(c.sheet.xp)
  return (
    <div className="ss-p cs-xp">
      <ul className="ss-xp">
        {c.eff.xpTrigger && <li className="own">{c.eff.xpTrigger}</li>}
        {list(sx.common).map((x, i) => <li key={i}>{x}</li>)}
        {sx.desperate && <li>{String(sx.desperate)}</li>}
      </ul>
      {sx.note && <div className="ss-hint">{String(sx.note)}</div>}
    </div>
  )
}

/* --- снаряжение и нагрузка ------------------------------------------------- */

function ItemRow({ it, scope, c }: { it: Entry; scope: string; c: Ctx }) {
  const { t } = useTranslation('char')
  const key = `${scope}:${it.key}`
  const items = dict(c.f.items)
  const on = key in items
  const choices = loadChoices(it.load)
  const n = on ? num(items[key]) : choices[choices.length - 1]
  const flip = () => {
    const next = { ...items }
    if (on) delete next[key]
    else next[key] = choices[choices.length - 1]
    c.set('items', next)
  }
  const cycle = () => c.set('items', { ...items, [key]: choices[(choices.indexOf(n) + 1) % choices.length] })
  const nm = (
    <span className={`ss-nm${Math.min(...choices) === 0 && choices.length === 1 ? ' free' : ''}${it.fine ? ' fine' : ''}`}>
      {it.name}
    </span>
  )
  return (
    <li className={`cs-item${on ? ' on' : ''}`}>
      {c.marks
        ? <button className={`ss-tick${on ? ' on' : ''}`} aria-pressed={on} onClick={flip} />
        : <span className={`ss-tick${on ? ' on' : ''}`} />}
      {it.text
        ? <details className="ss-fold"><summary>{nm}</summary><div className="ss-text">{it.text}</div></details>
        : <div className="ss-fold flat">{nm}</div>}
      {on && choices.length > 1 && c.marks && (
        <button className="cs-vload" title={t('gear.load_choice')} onClick={cycle}>{n}</button>
      )}
      {n > 0 && <span className="cs-lbox">{Array.from({ length: n }, (_, i) => <i key={i} />)}</span>}
    </li>
  )
}

export function GearLane({ c }: { c: Ctx }) {
  const { t } = useTranslation('char')
  const items = dict(c.f.items)
  const level = String(c.f.load || 'normal')
  const used = loadUsed(items)
  const lim = loadLimit(level)
  const shown = (rows: Entry[], scope: string) =>
    rows.filter(it => c.marks || `${scope}:${it.key}` in items)
  const pbRows = shown(c.eff.items, 'pb')
  const cRows = shown(c.eff.common, 'c')
  const newJob = () => {
    if (!confirm(t('gear.new_job_confirm'))) return
    c.patch({ items: {}, armor: {} })
  }
  const group = (cls: string, label: string, rows: Entry[], scope: string) => rows.length > 0 && (
    <div className={cls}>
      <div className="cs-igrp">{label}</div>
      <ul className="cs-items cols">
        {rows.map(it => <ItemRow key={`${scope}:${it.key}`} it={it} scope={scope} c={c} />)}
      </ul>
    </div>
  )
  return (
    <Lane title={t('lane.gear')} one id="gear" count={c.phone ? undefined : `${used}/${lim} · ${t(`gear.load.${level}`)}`}
      head={c.marks && (
        <button className="ghost tiny" title={t('gear.new_job_title')} onClick={newJob}>{t('gear.new_job')}</button>
      )}>
      <div className="ss-p-b ss-lane-plain">
        {c.phone && <div className="cs-gload"><LoadBlock c={c} /></div>}
        {pbRows.length + cRows.length > 0
          ? <div className={`cs-gear${pbRows.length && cRows.length ? ' both' : ''}`}>
              {group('cs-gear-pb', c.book ? c.book.label : t('gear.pb_none'), pbRows, 'pb')}
              {group('cs-gear-c', t('gear.common'), cRows, 'c')}
            </div>
          : <div className="ss-empty">{t('gear.none')}</div>}
      </div>
    </Lane>
  )
}

/* --- знакомые: карточки NPC, как у корабля --------------------------------- */

export function ContactsLane({ c, npcs, onAdd }: {
  c: Ctx; npcs: Dict[]; onAdd: (npc: Dict) => void
}) {
  const { t } = useTranslation('char')
  const [adding, setAdding] = useState(false)
  const rows = readContacts(c.f.contacts)
  const byId: Dict = {}
  npcs.forEach(n => { if (n?.id) byId[n.id] = n })
  const put = (next: typeof rows) => c.set('contacts', serContacts(next))
  if (!c.pick && rows.length === 0) return null
  return (
    <Lane title={t('lane.contacts')} one id="contacts" head={c.pick && !adding && rows.length > 0 && (
      <IconButton icon={<IconPlus />} title={t('contacts.add')} onClick={() => setAdding(true)} />
    )}>
      <div className="ss-p-b ss-lane-plain">
        {rows.length === 0 && !adding && (
          c.pick
            ? <button className="sb-addrow" onClick={() => setAdding(true)}><IconPlus /> {t('contacts.add')}</button>
            : <div className="ss-empty">{t('contacts.empty')}</div>
        )}
        <div className="ss-contacts">
          {rows.map((r, i) => (
            <ContactNpc key={`${i}:${r.entity_id}`} id={r.entity_id} npc={byId[r.entity_id]} state={r.state}
              onCycle={c.pick ? () => put(rows.map((x, j) => (j === i
                ? { ...x, state: STATES[(STATES.indexOf(x.state) + 1) % STATES.length] } : x))) : undefined}
              onDrop={c.pick ? () => put(rows.filter((_, j) => j !== i)) : undefined} />
          ))}
        </div>
        {adding && (
          <NpcPicker exclude={rows.map(r => r.entity_id)} note={t('contacts.pick')}
            onPick={n => { setAdding(false); if (!rows.some(r => r.entity_id === n.id)) onAdd(n) }}
            onClose={() => setAdding(false)} />
        )}
      </div>
    </Lane>
  )
}

/* --- создание: выбор бланка и шаги памятки --------------------------------- */

export function PlaybookPick({ meta, onPick, onCancel }: {
  meta: Dict | null; onPick: (key: string) => void; onCancel?: () => void
}) {
  const { t } = useTranslation('char')
  const attrs: Attr[] = meta?.char_sheet?.attributes || []
  const actName = (k: string) => attrs.flatMap(a => a.actions).find(a => a.key === k)?.name || k
  return (
    <Lane title={t('pick.title')} one id="pick"
      head={onCancel && <button className="ghost tiny" onClick={onCancel}>{t('pick.keep')}</button>}>
      <div className="ss-p-b ss-lane-plain">
        <div className="cs-pbgrid">
          {Object.keys(dict(meta?.playbooks)).map(k => {
            const b = bookOf(meta, k)!
            return (
              <button key={k} className="cs-pbcard" onClick={() => onPick(k)}>
                <b>{b.label}</b>
                <span className="cs-pbsub">{b.blurb}</span>
                <span className="cs-pbu"><b>{/[.!?…]$/.test(b.unique.name) ? b.unique.name : `${b.unique.name}.`}</b> {b.unique.text}</span>
                <span className="cs-pbsub">
                  {t('pick.start', { acts: Object.entries(b.start).map(([a, n]) => `${actName(a)} ${n}`).join(', ') })}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </Lane>
  )
}

export function Steps({ c, named, onDone }: { c: Ctx; named: boolean; onDone: () => void }) {
  const { t } = useTranslation('char')
  const start = pointsOf(dict(c.book?.start))
  const spent = Math.max(0, pointsOf(dict(c.f.actions)) - start)
  const states = readContacts(c.f.contacts).map(r => r.state)
  // [подпись, сделано, перебор] — перебор подсвечен, но «персонаж готов» не держит
  const steps: [string, boolean, boolean?][] = [
    [t('steps.playbook'), !!c.pb],
    [t('steps.talent'), list(c.f.talents).length > 0],
    [t('steps.heritage'), !!c.f.heritage],
    [t('steps.past'), !!c.f.past],
    [t('steps.points', { n: spent }), spent === 4, spent > 4],
    [t('steps.friends'), states.includes('friend') && states.includes('rival')],
    [t('steps.vice'), asList(c.f.vice).length > 0],
    [t('steps.name'), named],
  ]
  return (
    <div className="cs-steps">
      {steps.map(([l, ok, over]) => <span key={l} className={`cs-step${ok ? ' ok' : ''}${over ? ' over' : ''}`}>{l}</span>)}
      <div className="spacer" />
      <button className="ghost tiny" onClick={onDone}>{t('steps.done')}</button>
    </div>
  )
}

/* --- памятка с нижней части листа ------------------------------------------ */

const MEMO_COL = 190
const MEMO_GAP = 16
const MEMO_POP = 340

/** Группы памятки по колонкам подряд, чтобы самая высокая колонка была как можно ниже (высота — по длине строк). */
function memoColumns(rows: Dict[], n: number): [number, number][] {
  const h = rows.map(r => 2 + (Array.isArray(r.lines) ? r.lines : [])
    .reduce((s: number, l: any) => s + Math.ceil(String(typeof l === 'object' && l ? l.text : l).length / 27), 0))
  let best: [number, number][] = [[0, rows.length]]
  let bestH = Infinity
  const walk = (from: number, left: number, acc: [number, number][], top: number) => {
    if (left === 1) {
      const all = [...acc, [from, rows.length] as [number, number]]
      const m = Math.max(top, h.slice(from).reduce((s, x) => s + x, 0))
      if (m < bestH) { bestH = m; best = all }
      return
    }
    for (let to = from + 1; to <= rows.length - left + 1; to++) {
      walk(to, left - 1, [...acc, [from, to]], Math.max(top, h.slice(from, to).reduce((s, x) => s + x, 0)))
    }
  }
  walk(0, Math.min(n, rows.length), [], 0)
  return best
}

/** `inHead` — открытой колонкой в шапке «Бланка» (видна только на широком экране).
 *  Строка памятки — текст или `{text, more}`: пояснение из книги карточкой по клику. */
export function Reference({ sheet, inHead }: { sheet: Dict; inHead?: boolean }) {
  const { t } = useTranslation('char')
  const [open, setOpen, box] = useOneOpen()
  const [width, setWidth] = useState(0)
  const [at, setAt] = useState<{ top: number; left: number } | null>(null)
  useLayoutEffect(() => {
    const el = box.current
    if (!inHead || !el) return
    const ro = new ResizeObserver(() => setWidth(el.clientWidth))
    ro.observe(el)
    return () => ro.disconnect()
  }, [inHead, box])
  useEffect(() => {
    if (!inHead || !open) return
    const shut = () => setOpen('')
    window.addEventListener('scroll', shut, true)
    window.addEventListener('resize', shut)
    return () => { window.removeEventListener('scroll', shut, true); window.removeEventListener('resize', shut) }
  }, [inHead, open, setOpen])
  const rows: Dict[] = Array.isArray(sheet.reference) ? sheet.reference : []
  if (!rows.length) return null
  const line = (l: any, key: string) => {
    if (typeof l !== 'object' || !l) return <li key={key}>{String(l)}</li>
    const text = String(l.text || '')
    if (!l.more) return <li key={key}>{text}</li>
    return (
      <li key={key}>
        <button type="button" className={`cs-help${open === key ? ' open' : ''}`} aria-expanded={open === key}
          onClick={e => {
            if (open === key) { setOpen(''); return }
            const r = e.currentTarget.getBoundingClientRect()
            const w = Math.min(MEMO_POP, window.innerWidth * 0.8)
            setAt({ top: r.bottom + 6, left: Math.max(8, Math.min(r.left, window.innerWidth - w - 8)) })
            setOpen(key)
          }}>
          {text}
          <span className="cs-pop" role="tooltip"
            style={inHead && open === key && at ? { position: 'fixed', top: at.top, left: at.left, right: 'auto' } : undefined}>
            <b>{text}</b>{String(l.more)}
          </span>
        </button>
      </li>
    )
  }
  const body = rows.map((r, ri) => (
    <div key={r.title}>
      <h4>{r.title}</h4>
      <ul>{(Array.isArray(r.lines) ? r.lines : []).map((l: any, i: number) => line(l, `${ri}:${i}`))}</ul>
    </div>
  ))
  if (inHead) {
    const fit = Math.floor((width + MEMO_GAP) / (MEMO_COL + MEMO_GAP))
    const n = Math.min(rows.length, Math.max(2, fit))
    return (
      <div className="cs-memo" ref={box}>
        {memoColumns(rows, n).map(([a, b]) => <div key={a} className="cs-memo-col">{body.slice(a, b)}</div>)}
      </div>
    )
  }
  return (
    <details className="cs-ref">
      <summary>{t('reference')}</summary>
      <div className="cs-ref-b" ref={box}>{body}</div>
    </details>
  )
}
