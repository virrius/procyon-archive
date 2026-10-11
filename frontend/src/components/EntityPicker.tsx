import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import i18n from '../i18n'
import { api, c, type Dict, thumb } from '../api'
import { useApp, useAsync } from '../ctx'
import { Chip, ClockDial, clockTitle } from '../ui'
import { useLayer } from '../layers'
import { FieldEye } from './FieldEye'
import Stub from './Stub'
import '../styles.entity.css'

export function Thumb({ e }: { e: Dict }) {
  return e.image_url
    ? <img className="lnk-thumb" src={thumb(e.image_url, 240)} alt="" />
    : <Stub kind={e.kind} sub={e.fields?.job_type} className="lnk-thumb" />
}

/** Поиск для пикеров. Карточки ищет сервер и отдаёт лишь то, что видит смотрящий;
    пустой запрос — свежие карточки. С `clocks` в тот же список встают счётчики
    кампании, и всё вместе идёт свежим сверху; у находок тогда есть `type`. */
export function usePickHits({ q, on = true, kind, exclude, limit = 20, clocks }: {
  q: string
  /** искать, только пока список на экране */
  on?: boolean
  kind?: string
  exclude?: string | string[]
  limit?: number
  /** счётчики в том же списке: только идущие или все */
  clocks?: 'active' | 'all'
}) {
  const [ents, setEnts] = useState<Dict[]>([])
  const [asked, setAsked] = useState<string | null>(null)
  const [oops, setOops] = useState('')
  const [cls] = useAsync<Dict[]>(
    () => (clocks
      ? api.get(`${c()}/clocks?status=${clocks === 'active' ? 'active' : ''}`)
      : Promise.resolve([])),
    [clocks])
  const needle = q.trim()

  useEffect(() => {
    if (!on) return
    let alive = true
    const t = setTimeout(() => {
      const qs = [
        needle ? `q=${encodeURIComponent(needle)}` : '',
        kind ? `kind=${encodeURIComponent(kind)}` : '',
        'order=recent',
        `limit=${limit}`,
      ].filter(Boolean).join('&')
      api.get(`${c()}/entities?${qs}`)
        .then(r => {
          if (!alive) return
          setEnts(Array.isArray(r) ? r : []); setOops(''); setAsked(needle)
        })
        .catch(e => {
          if (!alive) return
          setEnts([]); setAsked(needle); setOops(e?.message || i18n.t('entity:picker.search_down'))
        })
    }, needle ? 250 : 0)  // список по фокусу открываем сразу, набор — с паузой
    return () => { alive = false; clearTimeout(t) }
  }, [needle, on, kind, limit])

  const skip = new Set(Array.isArray(exclude) ? exclude : exclude ? [exclude] : [])
  const free = ents.filter(e => !skip.has(e.id))
  if (!clocks) return { hits: free, ready: asked === needle, oops }
  const low = needle.toLowerCase()
  const stamp = (h: Dict) => Date.parse(h.created_at || '') || 0
  const hits = [
    ...free.map(e => ({ ...e, type: 'entity' })),
    ...(cls || [])
      .filter(cl => !skip.has(cl.id) && (!low || clockTitle(cl).toLowerCase().includes(low)))
      .map(cl => ({ ...cl, type: 'clock' })),
  ].sort((a, b) => stamp(b) - stamp(a))
  return { hits, ready: asked === needle, oops }
}

/** Выбор записи поиском. Пустая подпись — поле без своей подписи и отступа:
    их вместе с уже выбранным рисует тот, кто встроил пикер. */
export default function EntityPicker({
  value, onChange, label: labelProp, placeholder: placeholderProp,
  kind, exclude, autoFocus, limit = 20, vis, clocks, listed, initialQ = '', onEmpty,
}: {
  value: Dict | null
  onChange: (e: Dict | null) => void
  label?: string
  placeholder?: string
  /** сузить до одного или нескольких видов: `npc` или `npc,faction` */
  kind?: string
  /** id записей, которые нельзя выбрать: та, из которой выбираем, или уже выбранные */
  exclude?: string | string[]
  autoFocus?: boolean
  limit?: number
  /** видимость выбранной записи столу — глаз за подписью, как у полей карточки */
  vis?: { hidden: boolean; onChange: (hide: boolean) => void }
  /** и счётчики кампании тем же списком */
  clocks?: 'active' | 'all'
  /** список раскрыт всегда: выбор в своём окне, а не выпадашкой у поля */
  listed?: boolean
  /** с чего начинается строка поиска — например, нынешний выбор */
  initialQ?: string
  /** строку стёрли и подтвердили (Enter или уход из поля) — значит, выбор снят */
  onEmpty?: () => void
}) {
  const { L } = useApp()
  const { t } = useTranslation('entity')
  const label = labelProp ?? t('picker.label')
  const placeholder = placeholderProp ?? t('picker.placeholder')
  const [q, setQ] = useState(initialQ)
  const [open, setOpen] = useState(false)
  const shown = (listed || open) && !value
  const { hits, ready, oops } = usePickHits({ q, on: shown, kind, exclude, limit, clocks })
  // раскрытая выпадашка — верхний слой: Escape снимает её, следующий — окно под ней
  useLayer(open && !listed && !value, () => setOpen(false))

  const pick = (e: Dict) => { onChange(e); setQ(''); setOpen(false) }
  const clear = () => { onChange(null); setQ(''); setOpen(true) }

  if (value) {
    return (
      <div className="field">
        {vis
          ? <div className={`fld-lbl${vis.hidden ? ' off' : ''}`}>
              {label}<FieldEye hidden={vis.hidden} onChange={vis.onChange} />
            </div>
          : <label>{label}</label>}
        <div className="lnk-pick">
          <Thumb e={value} />
          <div className="lnk-main">
            <div className="lnk-head">
              <span className="lnk-name">{value.name}</span>
              <Chip tone="cyan">{L(value.kind)}</Chip>
            </div>
            {value.summary && <div className="lnk-sub">{value.summary}</div>}
          </div>
          <button className="tiny ghost" onClick={clear}>{t('picker.change')}</button>
        </div>
      </div>
    )
  }

  return (
    <div className={label ? 'field' : undefined}
      onFocus={() => setOpen(true)}
      onBlur={ev => {
        if (ev.currentTarget.contains(ev.relatedTarget as Node | null)) return
        setOpen(false)
        if (onEmpty && initialQ && !q.trim()) onEmpty()
      }}>
      {label && <label>{label}</label>}
      <input type="text" autoFocus={autoFocus} placeholder={placeholder}
        value={q} onChange={e => { setQ(e.target.value); setOpen(true) }}
        onClick={() => setOpen(true)}
        onKeyDown={ev => { if (ev.key === 'Enter' && onEmpty && !q.trim()) onEmpty() }} />
      {oops && <div className="lnk-err">{oops}</div>}
      {shown && !oops && ready && hits.length === 0 && (
        <div className="tag-note">{t('picker.nothing')}</div>
      )}
      {shown && hits.length > 0 && (
        <div className="lnk-hits" style={{ marginTop: 6 }}>
          {hits.map(h => {
            const clock = h.type === 'clock'
            // у выпадашки mousedown, а не click: blur убрал бы список раньше клика; фокус остаётся в поле
            const take = listed
              ? { onClick: () => pick(h) }
              : { onMouseDown: (ev: React.MouseEvent) => { ev.preventDefault(); pick(h) } }
            return (
              <button key={`${h.type || 'entity'}:${h.id}`} className="lnk-hit" {...take}>
                {clock
                  ? <ClockDial segments={h.segments} filled={h.filled} size={28} color={h.color} />
                  : <Thumb e={h} />}
                <span style={{ flex: 1, minWidth: 0 }}>
                  {clock ? clockTitle(h) : h.name}
                  {clock
                    ? <span className="lnk-sub"> · {h.filled}/{h.segments}</span>
                    : h.summary && <span className="lnk-sub"> · {h.summary}</span>}
                </span>
                <Chip tone={clock ? 'amber' : 'cyan'}>{clock ? t('picker.clock') : L(h.kind)}</Chip>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
