import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import i18n from './i18n'
import { api, c, isPublicView, store, type Dict } from './api'
import { useApp, useAsync } from './ctx'
import { IconCheck, IconChevron } from './components/icons'
import VisibilityMenu from './components/VisibilityMenu'
import OwnerMenu from './components/OwnerMenu'
import PopLayer from './components/PopLayer'
import Foldable from './components/Foldable'
import { useLayer } from './layers'

function liveLabels(group: string, keys: string[]): Dict {
  const out: Dict = {}
  for (const k of keys) {
    Object.defineProperty(out, k, { enumerable: true, get: () => i18n.t(`common:${group}.${k}`) })
  }
  return out
}

export const VIS_CLASS: Dict = {
  crew: 'crew-block', selected: 'sel-block', owner: 'secret-block', gm: 'gm-block',
}
/* палитра приборов: отметки карты и счётчики красим одним набором */
export const PALETTE = ['amber', 'rust', 'steel', 'plum', 'olive', 'white']
export const PALETTE_HEX: Dict = {
  amber: '#d8a24a', rust: '#c05a3c', steel: '#6f9a94',
  plum: '#9a7bab', olive: '#86a05e', white: '#e7e1d5',
}
export const PALETTE_NAME: Dict = liveLabels('palette', PALETTE)

export function Chip({ children, tone = '' }: { children: ReactNode; tone?: string }) {
  return <span className={`chip ${tone}`}>{children}</span>
}

/* тон печати статуса: в деле · тревога · чёрная метка · конец · выбыл.
   ключи общие для всех типов — свои статусы у персонажа, контакта, корабля и артефакта */
const STATUS_TONE: Dict = {
  active: 'ok', 'with crew': 'ok', visited: 'ok', confirmed: 'ok',
  injured: 'warn', hidden: 'warn', impounded: 'warn',
  dormant: 'warn', rumored: 'warn', compromised: 'warn',
  blocked: 'black', captured: 'black',
  dead: 'dead', destroyed: 'dead', failed: 'dead',
  retired: 'end', sold: 'end', lost: 'end', frozen: 'end',
  stolen: 'end', 'left crew': 'end', 'handed over': 'end',
  unknown: 'none', inaccessible: 'none',
  offered: 'fresh', 'in progress': 'work', done: 'win', expired: 'grey',
}

/** Класс тона для печати статуса: t-ok · t-warn · t-black · t-dead · t-end · t-none;
    у работёнки свои: t-fresh · t-work · t-win · t-grey. */
export const statusTone = (v: any): string => STATUS_TONE[String(v ?? '')] || 'none'

const ROMAN = ['0', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']

/** Ранг храним цифрой, читаем римской: «3» → «III». Незнакомое значение отдаём как есть. */
export function rankRoman(v: any): string {
  const s = String(v ?? '').trim()
  const n = Number(s)
  return s !== '' && Number.isInteger(n) && n >= 0 && n < ROMAN.length ? ROMAN[n] : s
}

/** Видимость только для показа — тот же чип, что у меню «кто видит», без выбора. */
export function VisChip({ v }: { v?: string | null }) {
  if (!v) return null
  return <VisibilityMenu value={v} visibleTo={[]} disabled onChange={() => {}} />
}

/** Имя счётчика в списках: «привязанная запись: счётчик». Без привязки — как есть */
export function clockTitle(cl: { name?: string; owner_name?: string } | null | undefined): string {
  const name = String(cl?.name || '')
  const owner = String(cl?.owner_name || '')
  return owner ? `${owner}: ${name}` : name
}

export function ClockDial({ segments, filled, size = 46, hidden = false, color }:
  { segments: number; filled: number; size?: number; hidden?: boolean; color?: string }) {
  const fill = hidden ? undefined : PALETTE_HEX[String(color || '')]
  const n = Math.max(1, segments || 1)
  const r = size / 2 - 2
  const cx = size / 2, cy = size / 2
  const paths = []
  for (let i = 0; i < n; i++) {
    const a0 = (i / n) * 2 * Math.PI - Math.PI / 2
    const a1 = ((i + 1) / n) * 2 * Math.PI - Math.PI / 2
    const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0)
    const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1)
    const large = a1 - a0 > Math.PI ? 1 : 0
    paths.push(
      <path key={i} className={`seg ${i < filled ? (hidden ? 'hidden-on' : 'on') : ''}`}
        style={i < filled && fill ? { fill } : undefined}
        d={`M ${cx} ${cy} L ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1} Z`} />
    )
  }
  return <div className="clock"><svg width={size} height={size}>{paths}</svg></div>
}

/** Тронута ли форма: сравнение с состоянием на момент открытия.
 *  Несколько полей отдавать массивом — [name, status, …]. */
export function useDirty(v: any): boolean {
  const first = useRef<string | null>(null)
  const now = JSON.stringify(v)
  if (first.current === null) first.current = now
  return now !== first.current
}

export function Modal({ title, onClose, children, wide, watch, dirty, dirtyAsk }:
  {
    title: ReactNode; onClose: () => void; children: ReactNode; wide?: boolean
    /** черновик формы: окно само сравнит его с состоянием на момент открытия
     *  и спросит подтверждение, если закрывают с несохранённым */
    watch?: any
    /** признак «есть несохранённое» вручную — когда форма считает его сама */
    dirty?: boolean
    dirtyAsk?: string
  }) {
  const { t } = useTranslation('common')
  const [ask, setAsk] = useState(false)

  const touched = useDirty(watch)
  const unsaved = dirty ?? (watch !== undefined && touched)

  // с пустой формы уходить нечему — снятый признак снимает и вопрос
  useEffect(() => { if (!unsaved) setAsk(false) }, [unsaved])

  const tryClose = () => { if (unsaved) setAsk(true); else onClose() }

  // окна вкладываются друг в друга (карточка → генерация снимка): Escape снимает верхнее,
  // а в нём вопрос о несохранённом гасится первым
  useLayer(true, () => (ask ? setAsk(false) : tryClose()))

  // закрываем, только если и нажатие, и отпускание были на фоне:
  // иначе выделение текста, вылезшее мышкой за карточку, захлопывает окно
  const downOnBackdrop = useRef(false)

  return (
    <div className="backdrop"
      onMouseDown={e => { downOnBackdrop.current = e.target === e.currentTarget }}
      onClick={e => { if (e.target === e.currentTarget && downOnBackdrop.current) tryClose() }}>
      <div className="modal" style={wide ? { width: 'min(1400px,100%)' } : undefined}>
        <div className="hd"><h2>{title}</h2><div className="spacer" />
          <button className="ghost" onClick={tryClose}>{t('close')}</button></div>
        {children}
        {ask && (
          <div className="ask" onMouseDown={e => e.stopPropagation()} onClick={e => e.stopPropagation()}>
            <div className="ask-box">
              <strong>{t('modal.unsaved_title')}</strong>
              <p>{dirtyAsk || t('modal.unsaved_text')}</p>
              <div className="row">
                <div className="spacer" />
                <button className="ghost" onClick={() => setAsk(false)}>{t('modal.back')}</button>
                <button className="danger" onClick={() => { setAsk(false); onClose() }}>
                  {t('modal.close_unsaved')}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/** Выбор из списка. Нативный select отдаёт раскрытый список системе —
 *  он рисуется мимо темы, поэтому меню своё, как у «кто видит» и «чей лист». */
export function Select({
  value, options, onChange, optionLabel, empty = '—', title, className, disabled, popCenter,
}: {
  value: any
  options: string[]
  onChange: (v: string) => void
  /** своя подпись варианта, если словарь не подходит (ранг читаем римской) */
  optionLabel?: (o: string) => string
  /** подпись пустого значения; null — пустой вариант не предлагаем */
  empty?: string | null
  title?: string
  className?: string
  disabled?: boolean
  /** список серединой под кнопкой — для узких значений вроде ранга */
  popCenter?: boolean
}) {
  const { L } = useApp()
  const wrap = useRef<HTMLDivElement | null>(null)
  const pop = useRef<HTMLDivElement | null>(null)
  const btn = useRef<HTMLButtonElement | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    const away = (ev: MouseEvent) => {
      const t = ev.target as Node
      if (wrap.current?.contains(t) || pop.current?.contains(t)) return
      setOpen(false)
    }
    window.addEventListener('mousedown', away)
    return () => window.removeEventListener('mousedown', away)
  }, [open])

  const lab = (o: string) => (optionLabel ? optionLabel(o) : L(o) || o)
  const cur = String(value ?? '')
  const list = empty === null ? options : ['', ...options]

  const toggle = () => {
    if (disabled) return
    setOpen(o => !o)
  }

  return (
    <div className={`drop${open ? ' open' : ''}${className ? ` ${className}` : ''}`} ref={wrap}>
      <button ref={btn} type="button" className="drop-btn" title={title} disabled={disabled}
        aria-haspopup="listbox" aria-expanded={open} onClick={toggle}>
        <span className={`drop-val${cur ? '' : ' none'}`}>
          {cur ? lab(cur) : empty ?? '—'}
        </span>
        <IconChevron size={11} />
      </button>

      {open && (
        <PopLayer anchor={btn} popRef={pop} center={popCenter} onClose={() => setOpen(false)}
          className={`drop-pop${className ? ` ${className}` : ''}`} role="listbox">
          {list.map(o => (
            <button type="button" key={o || '_'} role="option" aria-selected={o === cur}
              className={`drop-opt${o === cur ? ' on' : ''}${o ? '' : ' none'}`}
              onClick={() => { onChange(o); setOpen(false) }}>
              <span className="t">{o ? lab(o) : empty ?? '—'}</span>
              {o === cur && <IconCheck size={12} />}
            </button>
          ))}
        </PopLayer>
      )}
    </div>
  )
}

export function Input({
  label, value, onChange, type = 'text', options, rows, optionLabel, suggest, placeholder,
}: {
  label: string; value: any; onChange: (v: string) => void; type?: string
  options?: string[]; rows?: number
  /** своя подпись варианта, если словарь не подходит (ранг читаем римской) */
  optionLabel?: (o: string) => string
  /** подсказки к свободному вводу: выбрать из уже встречавшихся или вписать своё */
  suggest?: string[]
  placeholder?: string
}) {
  const { L } = useApp()
  const listId = suggest?.length ? `sg-${label.replace(/\s+/g, '-')}` : undefined
  return (
    <div className="field">
      <label>{label}</label>
      {options
        ? <Select value={value} options={options} onChange={onChange}
            optionLabel={optionLabel} title={label} />
        : type === 'textarea'
          ? <textarea value={value ?? ''} rows={rows} placeholder={placeholder}
              onChange={e => onChange(e.target.value)} />
          : <input type={type} value={value ?? ''} list={listId} placeholder={placeholder}
              onChange={e => onChange(e.target.value)} />}
      {listId && (
        <datalist id={listId}>
          {suggest!.map(s => <option key={s} value={s} />)}
        </datalist>
      )}
    </div>
  )
}

/** Значение поля-множества: массив строк; старые карточки могли хранить строку. */
export const asList = (v: any): string[] =>
  Array.isArray(v)
    ? v.map(x => String(x).trim()).filter(Boolean)
    : String(v ?? '').split(',').map(x => x.trim()).filter(Boolean)

/** max — потолок выбора из описания поля: набрав его, остальные варианты бледнеют */
export function MultiPick({ options, value, onChange, max }: {
  options: string[]; value: any; onChange: (v: string[]) => void; max?: number
}) {
  const { t } = useTranslation('common')
  const picked = asList(value)
  const full = !!max && picked.length >= max
  const toggle = (o: string) =>
    onChange(picked.includes(o) ? picked.filter(x => x !== o) : [...picked, o])
  return (
    <div className="row wrap" style={{ gap: 5 }}>
      {options.map(o => {
        const on = picked.includes(o)
        return (
          <button key={o} type="button" className={`pick${on ? ' on' : ''}`}
            disabled={full && !on} title={full && !on ? t('pick_max', { max }) : undefined}
            onClick={() => toggle(o)}>{o}</button>
        )
      })}
    </div>
  )
}

export function ColorPicker({ value, onChange, label }: {
  value?: string | null; onChange: (v: string) => void; label?: string
}) {
  const { t } = useTranslation('common')
  return (
    <div className="field">
      <label>{label ?? t('color')}</label>
      <div className="row wrap">
        {PALETTE.map(k => (
          <button key={k} type="button" className={`sw ${value === k ? 'on' : ''}`}
            title={PALETTE_NAME[k]} onClick={() => onChange(k)}>
            <i style={{ background: PALETTE_HEX[k] }} />
          </button>
        ))}
      </div>
    </div>
  )
}

export function VisibilityPicker({ visibility, visibleTo, onChange }: {
  visibility: string; visibleTo: string[]; onChange: (v: string, to: string[]) => void
}) {
  const { t } = useTranslation('common')
  return (
    <div className="field">
      <label>{t('who_sees')}</label>
      <div className="row wrap">
        <VisibilityMenu value={visibility || 'crew'} visibleTo={visibleTo || []} onChange={onChange} />
      </div>
    </div>
  )
}

export function OwnerPicker({ value, onChange, label }: {
  value?: string | null; onChange: (v: string | null) => void; label?: string
}) {
  const { t } = useTranslation('common')
  return (
    <div className="field">
      <label>{label || t('who_edits')}</label>
      <div className="row wrap">
        <OwnerMenu value={value} onChange={onChange} />
      </div>
    </div>
  )
}
