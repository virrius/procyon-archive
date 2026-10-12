import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { type Dict } from '../../api'
import { IconButton, IconClose, IconPlus, IconTrash } from '../icons'
import EntityPicker, { Thumb } from '../EntityPicker'
import Stub from '../Stub'
import '../../styles.ship.css'

/* Общее у бланков корабля и персонажа: панели, деления, списки с отметками, знакомые,
   строки конструктора. Подписи — в разделе sheet. */

export type Entry = {
  key: string; name: string; text?: string; more?: string; cost?: number; role?: string
  armor?: boolean; fine?: boolean; load?: number | number[]
}
export type ContactRef = { entity_id: string; state: string }

export const STATES = ['neutral', 'friend', 'rival']
const FLAG: Dict = { friend: 'flag.friend', neutral: 'flag.neutral', rival: 'flag.rival' }

export const num = (v: any): number => {
  const n = Number(v)
  return Number.isFinite(n) ? Math.max(0, Math.trunc(n)) : 0
}
export const list = (v: any): string[] => (Array.isArray(v) ? v.filter(x => typeof x === 'string') : [])
export const dict = (v: any): Dict => (v && typeof v === 'object' && !Array.isArray(v) ? v : {})
const loadOf = (v: any): number | number[] | undefined =>
  Array.isArray(v) ? v.map(num) : v == null ? undefined : num(v)
export const entries = (v: any): Entry[] =>
  (Array.isArray(v) ? v : [])
    .filter(x => x && typeof x === 'object' && typeof x.key === 'string' && x.key)
    .map(x => ({
      key: String(x.key),
      name: String(x.name ?? x.key),
      text: x.text ? String(x.text) : undefined,
      more: x.more ? String(x.more) : undefined,
      cost: x.cost == null ? undefined : num(x.cost),
      role: x.role ? String(x.role) : undefined,
      armor: x.armor ? true : undefined,
      fine: x.fine ? true : undefined,
      load: loadOf(x.load),
    }))

export const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v ?? null)) as T

/** На сервер уходят только ключи, тронутые на этом бланке; убранный ключ — null.
 *  Соседний бланк, открытый на другом устройстве, так не затирает чужую правку. */
export const changedKeys = (next: Dict, base: Dict): Dict => {
  const out: Dict = {}
  for (const k of new Set([...Object.keys(base), ...Object.keys(next)])) {
    const v = next[k] === undefined ? null : next[k]
    if (JSON.stringify(v) !== JSON.stringify(base[k] ?? null)) out[k] = v
  }
  return out
}

const PHONE = '(max-width: 760px)'

/** Телефон: раскладка плотнее, длинные описания по умолчанию свёрнуты. */
export function usePhone() {
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
export const newKey = () => `c${Date.now().toString(36)}${(keySeq++).toString(36)}`

export const readContacts = (v: any): ContactRef[] =>
  (Array.isArray(v) ? v : [])
    .filter(x => x && typeof x === 'object' && typeof x.entity_id === 'string' && x.entity_id)
    .map(x => ({
      entity_id: String(x.entity_id),
      state: STATES.includes(x.state) ? String(x.state) : 'neutral',
    }))
export const serContacts = (rows: ContactRef[]): Dict[] =>
  rows.map(r => ({ entity_id: r.entity_id, state: r.state }))

/* --- свимлейн бланка ------------------------------------------------------- */

/** Полоса раздела: подпись с чертой, под ней панели в два столбца
    (`one` — в один, когда внутри длинные описания). */
/** `beside` — сразу за названием, до линейки; `head` — справа, после счётчика. */
export function Lane({ title, count, head, beside, one, cols, id, children }: {
  title?: string; count?: string; head?: ReactNode; beside?: ReactNode; one?: boolean; cols?: number; id?: string
  children: ReactNode
}) {
  return (
    <section className={`ss-lane${one ? ' one' : ''}${cols ? ` c${cols}` : ''}`} data-sec={id}>
      {(title || count || head) && (
        <div className="ss-lane-hd">
          <span className="ss-lane-t">{title}</span>
          {beside}
          <span className="ss-lane-rule" />
          {count && <span className="ss-slots">{count}</span>}
          {head}
        </div>
      )}
      <div className="ss-lane-b">{children}</div>
    </section>
  )
}

/* --- панель бланка --------------------------------------------------------- */

/** Разделы бланка не складываются: на телефоне мельче шрифт, вся картина остаётся на виду.
    Справа в заголовке — счётчик отметок. */
export function Panel({ title, head, sub, count, children }: {
  title: string; head?: ReactNode; sub?: ReactNode; count?: string; children: ReactNode
}) {
  const { t } = useTranslation('sheet')
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

export function Line({ label, value, hint, edit, wide, area, onChange }: {
  label: string; value?: any; hint?: string; edit?: boolean
  wide?: boolean; area?: boolean; onChange: (v: string) => void
}) {
  const v = value == null ? '' : String(value)
  return (
    <div className={`ss-line${wide ? ' wide' : ''}`}>
      {edit
        ? (area
            ? <textarea className="ss-line-in" rows={1} value={v} placeholder={hint}
                onChange={e => onChange(e.target.value)} />
            : <input className="ss-line-in" value={v} placeholder={hint}
                onChange={e => onChange(e.target.value)} />)
        : <div className="ss-line-v">{v || <span className="ss-none">—</span>}</div>}
      <div className="ss-cap">{label}</div>
    </div>
  )
}

/* --- деления показателя ---------------------------------------------------- */

/** `split` — щель после первых делений (навык: первое деление даёт показатель характеристики). */
export function Pips({ n, value, tone, split, onSet }: {
  n: number; value: number; tone?: string; split?: number; onSet?: (v: number) => void
}) {
  const { t } = useTranslation('sheet')
  const total = Math.max(n, value)
  return (
    <span className="ss-pips" title={t('of', { value, n })}>
      {Array.from({ length: total }, (_, i) => {
        const cls = `ss-pip${tone ? ' ' + tone : ''}${i < value ? ' on' : ''}${split && i === split ? ' gap' : ''}`
        return onSet
          ? <button key={i} className={cls} aria-label={`${i + 1}`}
              onClick={() => onSet(value === i + 1 ? i : i + 1)} />
          : <span key={i} className={cls} />
      })}
    </span>
  )
}

/* --- ряд квадратиков: креды, долг, пропуски -------------------------------- */

export function Track({ label, n, value, tone, cls, onSet }: {
  label: string; n: number; value: number; tone?: string; cls?: string; onSet?: (v: number) => void
}) {
  const total = Math.max(n, value)
  return (
    <div className={`ss-track${cls ? ' ' + cls : ''}`}>
      <div className="ss-cap">{label}</div>
      <div className="ss-sqs">
        {Array.from({ length: total }, (_, i) => {
          const c = `ss-sq${i < value ? ' on' : ''}${tone ? ' ' + tone : ''}`
          return onSet
            ? <button key={i} className={c} aria-label={`${i + 1}`}
                onClick={() => onSet(value === i + 1 ? i : i + 1)} />
            : <span key={i} className={c} />
        })}
        <span className="ss-track-n">{value}</span>
      </div>
    </div>
  )
}

/* --- список с отметками: модули, таланты, улучшения ------------------------ */

export function Picks({ items, taken, edit, onToggle, cost, open, empty, compact, rest, tag, hot, lock }: {
  items: Entry[]; taken: string[]; edit?: boolean; onToggle?: (key: string) => void
  cost?: boolean; open?: boolean; empty?: string; compact?: boolean
  /** вне правки — неотмеченное одной строкой под списком */
  rest?: boolean
  /** метка справа от имени (источник ветеранского таланта) */
  tag?: (it: Entry) => ReactNode
  /** подсветить строку — её сейчас предлагают выбрать */
  hot?: (it: Entry) => boolean
  /** отметку не снять и не поставить — галочка без кнопки */
  lock?: (it: Entry) => boolean
}) {
  const { t } = useTranslation('sheet')
  // вне правки в списке остаётся только отмеченное — свободные строки не нужны
  if (items.length === 0) return compact ? null : <div className="ss-empty">{empty || '—'}</div>
  const shown = compact ? items.filter(it => taken.includes(it.key)) : items
  const left = compact && rest ? items.filter(it => !taken.includes(it.key)) : []
  const restLine = left.length > 0 && (
    <div className="ss-rest">
      {t('rest')}{' '}
      {left.map((it, i) => <span key={it.key} title={it.text || undefined}>{i > 0 && ' · '}{it.name}</span>)}
    </div>
  )
  if (shown.length === 0) return restLine || null
  return (
    <>
      <ul className="ss-picks">
        {shown.map(it => {
          const on = taken.includes(it.key)
          const marks = (
            <>
              {cost && num(it.cost) > 1 && <span className="ss-cost">×{it.cost}</span>}
              {tag?.(it)}
            </>
          )
          return (
            <li className={`ss-pick${on ? ' on' : ''}${hot?.(it) ? ' hot' : ''}`} key={it.key}>
              {onToggle && !lock?.(it)
                ? <button className={`ss-tick${on ? ' on' : ''}`} aria-pressed={on}
                    title={on ? t('untick') : t('tick')} onClick={() => onToggle(it.key)} />
                : <span className={`ss-tick${on ? ' on' : ''}`} />}
              {it.text
                ? open
                  ? <div className="ss-fold plain">
                      <div className="ss-nm-row"><span className="ss-nm">{it.name}</span>{marks}</div>
                      <TextMore text={it.text} more={it.more} />
                    </div>
                  : <details className="ss-fold">
                      <summary><span className="ss-nm">{it.name}</span>{marks}</summary>
                      <TextMore text={it.text} more={it.more} />
                    </details>
                : <div className="ss-fold flat"><span className="ss-nm">{it.name}</span>{marks}</div>}
            </li>
          )
        })}
      </ul>
      {restLine}
    </>
  )
}

/** Описание с «подробнее ±» в его последней строке справа; подробности — под ним. */
export function TextMore({ text, more }: { text: ReactNode; more?: string }) {
  const { t } = useTranslation('sheet')
  const [open, setOpen] = useState(false)
  return (
    <>
      <div className="ss-tmore">
        <div className="ss-text">{text}</div>
        {more && (
          <button type="button" className="ss-more-b" aria-expanded={open} onClick={() => setOpen(!open)}>
            {t('more')} {open ? '−' : '+'}
          </button>
        )}
      </div>
      {more && open && <div className="ss-text dim">{more}</div>}
    </>
  )
}

/* --- знакомые -------------------------------------------------------------- */

export function Flag({ state, onCycle }: { state: string; onCycle?: () => void }) {
  const { t } = useTranslation('sheet')
  const label = FLAG[state] ? t(FLAG[state]) : state
  return onCycle
    ? <button className={`ss-flag ${state}`} title={t('flag_cycle')}
        onClick={onCycle}>{label}</button>
    : <span className={`ss-flag ${state}`}>{label}</span>
}

export function ContactNpc({ id, npc, state, onCycle, onDrop }: {
  id: string; npc?: Dict; state: string; onCycle?: () => void; onDrop?: () => void
}) {
  const { t } = useTranslation('sheet')
  const role = npc ? String(npc.summary || '') : t('card_na')
  return (
    <div className="ss-contact">
      {npc
        ? <Link className="ss-contact-img" to={`/entity/${id}/profile`} tabIndex={-1} aria-hidden="true"><Thumb e={npc} /></Link>
        : <Stub kind="npc" className="lnk-thumb" />}
      <div className="ss-contact-b">
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
    </div>
  )
}

export function NpcPicker({ exclude, note, onPick, onClose }: {
  exclude: string[]; note?: string; onPick: (npc: Dict) => void; onClose: () => void
}) {
  const { t } = useTranslation('sheet')
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

/* --- настройка бланков (GM space) ------------------------------------------ */

/** Настройка сохраняется сама: пауза в наборе, смена раздела, уход со страницы.
 *  `mark` — принять тело за уже сохранённое (после записи в обход автосейва). */
export function useAutosave(body: Dict, put: (b: Dict) => Promise<unknown>, errText: string) {
  const json = JSON.stringify(body)
  const saved = useRef(json)
  const [phase, setPhase] = useState<'' | 'busy' | 'ok'>('')
  const [err, setErr] = useState('')
  const flush = useRef(() => {})
  flush.current = () => {
    if (json === saved.current) return
    const sent = json
    setPhase('busy'); setErr('')
    put(JSON.parse(sent))
      .then(() => { saved.current = sent; setPhase('ok') })
      .catch((e: any) => { setErr(e?.message || errText); setPhase('') })
  }
  const dirty = json !== saved.current
  useEffect(() => {
    if (!dirty) return
    const h = window.setTimeout(() => flush.current(), 700)
    return () => window.clearTimeout(h)
  }, [json])  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => flush.current(), [])
  useEffect(() => {
    if (!dirty) return
    const warn = (ev: BeforeUnloadEvent) => { ev.preventDefault(); ev.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  return { phase: dirty && phase === 'ok' ? '' as const : phase, err, mark: (b: Dict) => { saved.current = JSON.stringify(b) } }
}

/** Раздел настройки всегда открыт для правки: первая правка делает его своим,
 *  «к книге» возвращает книжный. */
export function Sect({ label, own, count, onReset, children }: {
  label: string; own: boolean; count?: number; onReset: () => void; children: ReactNode
}) {
  const { t } = useTranslation('sheet')
  return (
    <section className={`sb-sect${own ? ' own' : ''}`}>
      <div className="sb-hd">
        <span className="sb-t">{label}</span>
        {count != null && <span className="sb-n">{count}</span>}
        <span className={`sb-src${own ? ' own' : ''}`}>{own ? t('builder.own') : t('builder.default')}</span>
        <div className="spacer" />
        {own && (
          <button className="ghost tiny sb-back" title={t('builder.reset_title')}
            onClick={() => { if (confirm(t('builder.reset_ask', { name: label }))) onReset() }}>{t('builder.reset')}</button>
        )}
      </div>
      {children}
    </section>
  )
}

/** Многострочное поле, растущее под текст. */
export function GrowText({ value, placeholder, onChange }: {
  value: string; placeholder?: string; onChange: (v: string) => void
}) {
  const box = useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight + 2}px`
  }, [value])
  return (
    <textarea ref={box} className="sb-desc" rows={1} value={value} placeholder={placeholder}
      onChange={e => onChange(e.target.value)} />
  )
}

/** Карточки «название · деления · описание». `num` — что считают деления:
 *  стоимость улучшения корабля или нагрузку предмета. */
export function EntryRows({ items, cost, num: numKey, onChange, onAdd }: {
  items: Entry[]; cost?: boolean; num?: { key: 'cost' | 'load'; label: string; min: number; max: number }
  onChange: (v: Entry[]) => void; onAdd?: () => void
}) {
  const { t } = useTranslation('sheet')
  const field = numKey || (cost ? { key: 'cost' as const, label: t('builder.cost'), min: 1, max: 3 } : null)
  const upd = (i: number, part: Partial<Entry>) =>
    onChange(items.map((it, j) => (j === i ? { ...it, ...part } : it)))
  const read = (it: Entry): number => {
    const v = it[field?.key || 'cost']
    return Array.isArray(v) ? num(v[v.length - 1]) : v == null ? field?.min ?? 0 : num(v)
  }
  return (
    <div className="sb-cards">
      {items.map((it, i) => (
        <div className="sb-entry" key={it.key}>
          <input className="sb-name" value={it.name} placeholder={t('builder.name_ph')}
            onChange={e => upd(i, { name: e.target.value })} />
          {field && (
            <span className="sb-num">
              <span className="sb-num-t">{field.label}</span>
              <Pips n={field.max} value={read(it)}
                onSet={v => upd(i, { [field.key]: Math.max(field.min, v) })} />
            </span>
          )}
          <IconButton icon={<IconTrash />} title={t('builder.del_row')} danger
            onClick={() => onChange(items.filter((_, j) => j !== i))} />
          <GrowText value={it.text || ''} placeholder={t('builder.text_ph')} onChange={v => upd(i, { text: v })} />
        </div>
      ))}
      {onAdd && (
        <button className="sb-addcard" onClick={onAdd}><IconPlus /> {t('builder.add_row')}</button>
      )}
    </div>
  )
}

export function TextRows({ items, placeholder, onChange, onAdd }: {
  items: string[]; placeholder?: string; onChange: (v: string[]) => void; onAdd?: () => void
}) {
  const { t } = useTranslation('sheet')
  return (
    <div className="sb-rows">
      {items.map((v, i) => (
        <div className="sb-row" key={i}>
          <input className="sb-text" value={v} placeholder={placeholder}
            onChange={e => onChange(items.map((x, j) => (j === i ? e.target.value : x)))} />
          <IconButton icon={<IconTrash />} title={t('builder.del_row')} danger
            onClick={() => onChange(items.filter((_, j) => j !== i))} />
        </div>
      ))}
      {onAdd && (
        <button className="sb-addrow" onClick={onAdd}><IconPlus /> {t('builder.add_row')}</button>
      )}
    </div>
  )
}
