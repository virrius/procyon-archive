import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api, c, store, thumb, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import { useLayer } from '../layers'
import EntityPage from './EntityPage'
import { NewEntityModal } from '../components/EntityGallery'
import { ClockForm, useClockKinds } from '../components/ClockForm'
import { NewClockModal } from '../components/ClockForm'
import NewsGenerator, { attachOfClock, attachOfEntity, type Attach } from '../components/NewsGenerator'
import Stub from '../components/Stub'
import EntityPicker from '../components/EntityPicker'
import {
  Chip, ClockDial, ColorPicker, Input, Modal, PALETTE, PALETTE_HEX, PALETTE_NAME, clockTitle,
  rankRoman, statusTone,
} from '../ui'
import '../styles.board.css'

/* Доска квеста: холст ГМа. Карточки записей (миниатюра, подпись, ключевые
   заметки), свободные стикеры и улики-кадры; между ними — нити, как на детективной
   доске. Кухня ГМа: столу не отдаётся, поэтому видимости у карточек нет. */

type V = { k: number; tx: number; ty: number }

const MIN_K = 0.1
const MAX_K = 2.5
const STEP = 1.15
const CARD_W = { text: 230, entity: 520, image: 260, clock: 230, sketch: 420, name: 260 }
/* две базы имён: колорит фронтира или мировая классика по странам */
const NAME_POOLS: [string, string][] = [
  ['setting', 'pool.setting'], ['world', 'pool.world'],
]
/* пол имени: ксеносам он безразличен, они приходят при любом выборе */
const NAME_GENDERS: [string, string][] = [
  ['any', 'gender.any'], ['m', 'gender.m'], ['f', 'gender.f'],
]
/* огранка имени: как его выкликают на доске — одним словом, с фамилией, с прозвищем */
const NAME_SHAPES: [string, string][] = [
  ['mix', 'shape.mix'], ['mono', 'shape.mono'], ['full', 'shape.full'],
  ['alias', 'shape.alias'], ['aliasfull', 'shape.aliasfull'], ['xeno', 'shape.xeno'],
]
/* набросок — единственная карточка со своей высотой: из содержимого её не вывести */
const SKETCH_H = 300
/* толщина линии: от пометки волоском до жирной обводки поверх схемы */
const INK_W: [number, string][] = [[1.5, 'ink.thin'], [3, 'ink.medium'], [7, 'ink.thick']]
/* палитра наброска — палитра приборов плюс чёрный: на наброске он нужен как тень
   и заливка, а счётчикам и отметкам карты чёрный цвет ни к чему */
const INK_COLORS = [...PALETTE, 'black']
/* «чёрный» на тёмном поле — графит: настоящий чёрный на нём просто не виден */
const INK_HEX: Dict = { ...PALETTE_HEX, black: '#3a332e' }
const inkHex = (color?: string) => INK_HEX[color || ''] || INK_HEX.amber
/* кегль подписи на наброске: ярлык у стрелки, имя узла, заголовок схемы */
const INK_SZ: [number, string][] = [[14, 'S'], [22, 'M'], [40, 'L']]
const INK_MODES: [string, string][] = [
  ['pen', 'ink.pen'], ['text', 'ink.text'], ['erase', 'ink.erase'],
]
/* что заводится прямо с доски. Корабля и игрового персонажа тут нет: их место в
   бланке экипажа, на доску они попадают готовыми */
const NEW_KINDS: [string, string][] = [
  ['npc', 'kind.npc'],
  ['item', 'kind.item'],
  ['faction', 'kind.faction'],
  ['location', 'kind.location'],
]
const KIND_TITLE: Dict = Object.fromEntries(NEW_KINDS)
/* разрез состава квеста: сперва живые лица, потом силы, места, вещи и корабли —
   тот же порядок, в котором доску пересказывают вслух */
const ROSTER_KINDS: [string, string][] = [
  ['npc', 'roster.npc'],
  ['character', 'roster.character'],
  ['faction', 'roster.faction'],
  ['location', 'roster.location'],
  ['item', 'roster.item'],
  ['ship', 'roster.ship'],
]
const TABS: [string, string][] = [['canvas', 'tab.canvas'], ['roster', 'tab.roster']]
const tabKey = () => `pa_board_tab:${store.campaign || ''}`
/* кегль текстового поля: от пометки на полях до вывески во всю доску. Шаг крупный —
   мелкие ступени на отдалённом холсте всё равно неразличимы */
const FONT_SIZES: [number, string][] = [
  [12, 'S'], [20, 'M'], [36, 'L'], [64, 'XL'], [110, 'XXL'], [180, '3XL'],
]
/* правка уходит по её концу: уход с поля, снятие карточки, смена доски. Таймер —
   только страховка на случай брошенной правки, поэтому он длинный */
const IDLE_SAVE = 4000
const lastKey = () => `pa_board_last:${store.campaign || ''}`

const hex = (color?: string) => PALETTE_HEX[color || ''] || PALETTE_HEX.amber

/** Файл в кампанию: возвращает адрес, годный и для карточки, и для миниатюр. */
async function uploadImage(f: File, boardId: string): Promise<string> {
  const fd = new FormData()
  // из буфера файл приходит без имени — расширение нужно хранилищу
  fd.append('file', f, f.name || 'clipboard.png')
  fd.append('target_type', 'board')
  fd.append('target_id', boardId)
  const r = await api.post(`${c()}/upload`, fd)
  return r.url as string
}

export default function BoardsPage() {
  const [boards, loading, reloadBoards, err] = useAsync<Dict[]>(
    () => api.get(`${c()}/boards`), [])
  const nav = useNavigate()
  const { t } = useTranslation('boards')
  const { pathname } = useLocation()
  // доска живёт в адресе: /gm/boards/<id>. Ссылку на квест можно отдать соседнему ГМу
  const routeId = pathname.split('/').filter(Boolean)[2] || ''
  const [newBoard, setNewBoard] = useState<Dict | null>(null)
  const [renaming, setRenaming] = useState(false)
  const [killing, setKilling] = useState(false)
  const [oops, setOops] = useState('')

  const list = boards || []
  const current = useMemo(() => {
    if (routeId) return list.find(b => b.id === routeId) || list[0] || null
    const last = localStorage.getItem(lastKey())
    return (last && list.find(b => b.id === last)) || list[0] || null
  }, [list, routeId])

  // адрес без доски (или с чужой) подтягивается к открытой: назад по истории не швыряет
  useEffect(() => {
    if (!current) return
    localStorage.setItem(lastKey(), current.id)
    if (routeId !== current.id) nav(`/gm/boards/${current.id}`, { replace: true })
  }, [current?.id, routeId])

  const create = async (form: Dict) => {
    try {
      const r = await api.post(`${c()}/boards`, { name: form.name, summary: form.summary })
      setNewBoard(null)
      nav(`/gm/boards/${r.id}`)
      reloadBoards()
    } catch (e: any) { setOops(e.message || t('err.create')) }
  }

  const rename = async (name: string) => {
    if (!current || !name || name === current.name) return
    try { await api.patch(`${c()}/boards/${current.id}`, { name }) }
    catch (e: any) { setOops(e.message || t('err.rename')) }
    reloadBoards()
  }

  const drop = async () => {
    if (!current) return
    try { await api.del(`${c()}/boards/${current.id}`) }
    catch (e: any) { setOops(e.message || t('err.delete')); return }
    localStorage.removeItem(lastKey())
    nav('/gm/boards', { replace: true })
    reloadBoards()
  }

  if (loading && !boards) return <div className="panel col dim">{t('loading')}</div>
  if (err) return <div className="panel col"><div className="eg-err">{err}</div></div>

  return (
    <div className="col">
      <div className="bd-bar">
        <span className="lb">{t('bar.board')}</span>
        {list.length > 0 && (
          <select className="bd-pick" value={current?.id || ''}
            onChange={e => nav(`/gm/boards/${e.target.value}`)}>
            {list.map(b => (
              <option key={b.id} value={b.id}>{b.name} · {b.card_count || 0}</option>
            ))}
          </select>
        )}
        <button className="tiny ghost"
          onClick={() => setNewBoard({ name: '', summary: '' })}>{t('bar.new')}</button>
        {current && <>
          <button className="tiny ghost" onClick={() => setRenaming(true)}>{t('bar.rename')}</button>
          <button className="tiny danger" onClick={() => setKilling(true)}>{t('bar.delete')}</button>
        </>}
      </div>

      {oops && <div className="bd-oops" role="alert">{oops}</div>}

      {!current
        ? <div className="empty">{t('empty')}</div>
        : <Board board={current} onCards={() => reloadBoards()} />}

      {renaming && current && (
        <AskText title={t('rename_title')} label={t('name')} value={current.name}
          onClose={() => setRenaming(false)} onSave={rename} />
      )}

      {killing && current && (
        <Ask yes={t('bar.delete')} onClose={() => setKilling(false)} onYes={drop}
          text={t('delete_confirm', { name: current.name })
            + (current.card_count ? ` ${t('delete_confirm_cards', { n: current.card_count })}` : '')} />
      )}

      {newBoard && (
        <Modal title={t('new.title')} onClose={() => setNewBoard(null)} watch={newBoard}
          dirtyAsk={t('new.dirty')}>
          <Input label={t('name')} value={newBoard.name}
            onChange={v => setNewBoard({ ...newBoard, name: v })} />
          <div className="field">
            <label>{t('new.about')}</label>
            <textarea rows={3} value={newBoard.summary}
              onChange={e => setNewBoard({ ...newBoard, summary: e.target.value })} />
          </div>
          <button className="primary" disabled={!newBoard.name.trim()}
            onClick={() => create(newBoard)}>{t('new.create')}</button>
        </Modal>
      )}
    </div>
  )
}


/* --- окошки вместо системных alert/confirm/prompt --------------------------- */

/** Да/нет своим окном: системный confirm выбивается из вида и блокирует страницу. */
function Ask({ text, yes, onYes, onClose }: {
  text: string; yes?: string; onYes: () => void; onClose: () => void
}) {
  const { t } = useTranslation('boards')
  return (
    <Modal title={t('ask.title')} onClose={onClose}>
      <div style={{ whiteSpace: 'pre-wrap' }}>{text}</div>
      <div className="row" style={{ marginTop: 12 }}>
        <button className="danger" onClick={() => { onClose(); onYes() }}>{yes || t('ask.yes')}</button>
        <button className="ghost" onClick={onClose}>{t('ask.no')}</button>
      </div>
    </Modal>
  )
}

/** Однострочный ввод своим окном — вместо prompt. */
function AskText({ title, label, value, onSave, onClose }: {
  title: string; label: string; value: string
  onSave: (v: string) => void; onClose: () => void
}) {
  const { t } = useTranslation('boards')
  const [v, setV] = useState(value)
  const save = () => { onClose(); onSave(v.trim()) }
  return (
    <Modal title={title} onClose={onClose}>
      <div className="field">
        <label>{label}</label>
        <input autoFocus value={v} onChange={e => setV(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') save() }} />
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <button className="primary" onClick={save}>{t('common:save')}</button>
        <button className="ghost" onClick={onClose}>{t('ask.cancel')}</button>
      </div>
    </Modal>
  )
}

/* --- холст одной доски ---------------------------------------------------- */

function Board({ board, onCards }: { board: Dict; onCards: () => void }) {
  const { t } = useTranslation('boards')
  const [cards, cardsLoading, reloadCards, cardsErr] = useAsync<Dict[]>(
    () => api.get(`${c()}/boards/${board.id}/cards`), [board.id])
  const [edges, , reloadEdges] = useAsync<Dict[]>(
    () => api.get(`${c()}/boards/${board.id}/edges`), [board.id])

  const [view, setView] = useState<V>({ k: 1, tx: 40, ty: 40 })
  const [linkFrom, setLinkFrom] = useState('')
  const [ghost, setGhost] = useState<number[] | null>(null)
  const [selEdge, setSelEdge] = useState('')
  const [hotEdge, setHotEdge] = useState('')
  const [dragPos, setDragPos] = useState<Dict | null>(null)
  const [band, setBand] = useState<Dict | null>(null)
  const [killAsk, setKillAsk] = useState<Dict | null>(null)
  const [sizes, setSizes] = useState<Dict>({})
  const [adding, setAdding] = useState<Dict | null>(null)
  const [entityId, setEntityId] = useState('')
  const [clockFor, setClockFor] = useState<Dict | null>(null)
  const [newsFor, setNewsFor] = useState<Attach[] | null>(null)
  const [menu, setMenu] = useState<Dict | null>(null)
  const [oops, setOops] = useState('')
  const [labelFor, setLabelFor] = useState<Dict | null>(null)
  const [sel, setSel] = useState<string[]>([])
  const [pasting, setPasting] = useState(0)
  // холст или состав: выбор держится между досками — привычка ГМа общая
  const [tab, setTab] = useState(() => localStorage.getItem(tabKey()) || 'canvas')
  useEffect(() => { localStorage.setItem(tabKey(), tab) }, [tab])

  const viewRef = useRef<HTMLDivElement>(null)
  const skipClick = useRef(false)
  /* щипок двумя пальцами: пока он идёт, тяга холста и карточек молчит */
  const pinch = useRef<Dict | null>(null)
  const viewNow = useRef<V>(view)
  /* свежие карточки для правок вслепую: два поля записки правятся почти одновременно,
     и вторая правка, собранная из пропсов, затирала бы первую */
  const cardsRef = useRef<Dict[]>([])
  // последняя точка указателя на холсте: туда ложится вставленное из буфера
  const lastPt = useRef<Dict | null>(null)
  const fitted = useRef('')

  /* карточки прошлой доски не должны висеть на новой: пока грузим или если
     запрос упал — холст пустой, а не чужой */
  const list = cardsErr || cardsLoading ? [] : cards || []
  const threads = cardsErr || cardsLoading ? [] : edges || []

  useEffect(() => { viewNow.current = view }, [view])
  useEffect(() => { cardsRef.current = cards || [] }, [cards])
  useEffect(() => { setDragPos(null) }, [cards])
  useEffect(() => {
    setLinkFrom(''); setGhost(null); setSelEdge(''); setSel([])
    fitted.current = ''   // на новую доску заходим сведённым видом, а не чужим
  }, [board.id])

  /* холст добирает всю высоту до низа окна: под ним живёт только строка подсказок,
     а фиксированная высота оставляла полэкрана пустоты */
  useEffect(() => {
    const fit = () => {
      const el = viewRef.current
      if (!el) return
      const r = el.getBoundingClientRect()
      const wrap = el.parentElement?.getBoundingClientRect()
      const below = wrap ? Math.max(0, wrap.bottom - r.bottom) : 0
      el.style.height = `${Math.max(360, window.innerHeight - r.top - below - 22)}px`
    }
    fit()
    window.addEventListener('resize', fit)
    return () => window.removeEventListener('resize', fit)
  }, [board.id, board.summary, oops, cardsErr, tab])

  /* точка события в координатах доски */
  const at = (e: { clientX: number; clientY: number }): number[] => {
    const r = viewRef.current?.getBoundingClientRect()
    if (!r) return [0, 0]
    return [
      Math.round((e.clientX - r.left - view.tx) / view.k),
      Math.round((e.clientY - r.top - view.ty) / view.k),
    ]
  }

  const zoomAt = (cx: number, cy: number, f: number) => setView(v => {
    const k = Math.min(MAX_K, Math.max(MIN_K, v.k * f))
    const s = k / v.k
    return { k, tx: cx - (cx - v.tx) * s, ty: cy - (cy - v.ty) * s }
  })
  const zoomCenter = (f: number) => {
    const r = viewRef.current?.getBoundingClientRect()
    if (r) zoomAt(r.width / 2, r.height / 2, f)
  }
  /* свести всю доску в окно: карточки разъезжаются, искать их руками незачем */
  const fitView = () => {
    const r = viewRef.current?.getBoundingClientRect()
    const items = cardsRef.current
    if (!r || !items.length) { setView({ k: 1, tx: 40, ty: 40 }); return }
    const box = items.reduce((acc, card) => {
      const s = sizes[card.id] || { w: card.w || 240, h: 160 }
      return {
        x1: Math.min(acc.x1, card.x), y1: Math.min(acc.y1, card.y),
        x2: Math.max(acc.x2, card.x + s.w), y2: Math.max(acc.y2, card.y + s.h),
      }
    }, { x1: Infinity, y1: Infinity, x2: -Infinity, y2: -Infinity })
    const pad = 40
    // сводим только уменьшением: на одной карточке подгонка иначе раздувает её во весь холст
    const k = Math.max(MIN_K, Math.min(1,
      (r.width - pad * 2) / (box.x2 - box.x1 || 1),
      (r.height - pad * 2) / (box.y2 - box.y1 || 1)))
    setView({
      k,
      tx: r.width / 2 - k * (box.x1 + box.x2) / 2,
      ty: r.height / 2 - k * (box.y1 + box.y2) / 2,
    })
  }

  /* доска открывается сведённой: карточки разъезжаются далеко, и без этого ГМ
     каждый раз начинает с пустого угла холста и ищет их руками. Один раз на доску —
     дальше вид принадлежит тому, кто его сдвинул */
  useEffect(() => {
    // пока не пришли карточки этой доски, в руках набор прошлой — сводить по нему нельзя
    const mine = !!cards && (!cards.length || cards[0].board_id === board.id)
    if (!mine || cardsLoading || fitted.current === board.id) return
    // высота карточки известна только после обмера: до него рамка контента
    // считается по заглушке и вид уезжает мимо
    if (list.some(cd => !sizes[cd.id])) return
    if (!viewRef.current?.getBoundingClientRect().width) return
    fitted.current = board.id
    fitView()
  }, [board.id, cards, cardsLoading, list, sizes])

  /* масштаб двумя пальцами: на планшете и телефоне это единственный способ
     отдалить доску — колеса там нет, а кнопки зума слишком мелкий шаг */
  useEffect(() => {
    const el = viewRef.current
    if (!el) return
    const span = (t: TouchList) =>
      Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY)
    const mid = (t: TouchList, r: DOMRect) => [
      (t[0].clientX + t[1].clientX) / 2 - r.left,
      (t[0].clientY + t[1].clientY) / 2 - r.top,
    ]
    const start = (e: TouchEvent) => {
      if (e.touches.length !== 2) return
      const r = el.getBoundingClientRect()
      const [cx, cy] = mid(e.touches, r)
      const v = viewNow.current
      pinch.current = { d: span(e.touches) || 1, k: v.k, tx: v.tx, ty: v.ty, cx, cy }
    }
    const move = (e: TouchEvent) => {
      const p = pinch.current
      if (!p || e.touches.length !== 2) return
      e.preventDefault()
      const k = Math.min(MAX_K, Math.max(MIN_K, p.k * (span(e.touches) / p.d)))
      const s = k / p.k
      const r = el.getBoundingClientRect()
      const [cx, cy] = mid(e.touches, r)
      // точка щипка держится под пальцами: середина заодно тянет холст
      setView({ k, tx: cx - (p.cx - p.tx) * s, ty: cy - (p.cy - p.ty) * s })
    }
    const end = (e: TouchEvent) => { if (e.touches.length < 2) pinch.current = null }
    el.addEventListener('touchstart', start, { passive: false })
    el.addEventListener('touchmove', move, { passive: false })
    el.addEventListener('touchend', end)
    el.addEventListener('touchcancel', end)
    return () => {
      el.removeEventListener('touchstart', start)
      el.removeEventListener('touchmove', move)
      el.removeEventListener('touchend', end)
      el.removeEventListener('touchcancel', end)
    }
  }, [board.id])

  useEffect(() => {
    const el = viewRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const r = el.getBoundingClientRect()
      const cx = e.clientX - r.left, cy = e.clientY - r.top
      if (e.shiftKey) setView(v => ({ ...v, tx: v.tx - e.deltaY, ty: v.ty - e.deltaX }))
      else zoomAt(cx, cy, Math.exp(-e.deltaY / 400))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [board.id, view.k])

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (linkFrom) { setLinkFrom(''); setGhost(null) }
      else if (selEdge) setSelEdge('')
      else setSel([])
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [linkFrom, selEdge])

  /* Del по выделенным карточкам. Поля ввода не трогаем: там Del — обычная правка */
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key !== 'Delete' || !sel.length) return
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      e.preventDefault()
      askDropCards(sel)
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [sel, list])

  /* Ctrl+V: картинка из буфера ложится на холст под указателем. Поля ввода не
     трогаем — там вставка обычная; окна поверх доски тоже забирают буфер себе */
  useEffect(() => {
    const h = async (e: ClipboardEvent) => {
      const tg = e.target as HTMLElement | null
      if (tg && (tg.tagName === 'INPUT' || tg.tagName === 'TEXTAREA' || tg.isContentEditable)) return
      if (adding || killAsk || clockFor || entityId || labelFor) return
      const files = Array.from(e.clipboardData?.items || [])
        .filter(i => i.kind === 'file' && i.type.startsWith('image/'))
        .map(i => i.getAsFile())
        .filter((f): f is File => !!f)
      if (!files.length) return
      e.preventDefault()
      const p = lastPt.current
      // картинка встаёт серединой под указатель, а не углом
      const base = p ? { x: p.x - CARD_W.image / 2, y: p.y - CARD_W.image / 2 } : spot()
      setPasting(files.length)
      for (const [i, f] of files.entries()) {
        try {
          const url = await uploadImage(f, board.id)
          await addCard({ kind: 'image', image_url: url, w: CARD_W.image },
            { x: base.x + i * 24, y: base.y + i * 24 })
        } catch (err: any) { setOops(err.message || t('err.paste')) }
      }
      setPasting(0)
    }
    window.addEventListener('paste', h)
    return () => window.removeEventListener('paste', h)
  }, [board.id, view, adding, killAsk, clockFor, entityId, labelFor])

  /* размеры карточек меряем по факту: высота зависит от текста, а нити тянутся к центрам */
  const measure = (id: string, el: HTMLElement | null) => {
    if (!el) return
    const w = el.offsetWidth, h = el.offsetHeight
    setSizes(s => (s[id]?.w === w && s[id]?.h === h ? s : { ...s, [id]: { w, h } }))
  }

  const posOf = (card: Dict) =>
    dragPos && dragPos.ids.includes(card.id)
      ? { x: card.x + dragPos.dx, y: card.y + dragPos.dy }
      : { x: card.x, y: card.y }

  const boxOf = (card: Dict) => {
    const s = sizes[card.id] || { w: card.w || 240, h: 120 }
    return { x: card.x, y: card.y, w: s.w, h: s.h }
  }
  const centerOf = (card: Dict) => {
    const p = posOf(card)
    const s = sizes[card.id] || { w: card.w || 240, h: 120 }
    return [p.x + s.w / 2, p.y + s.h / 2]
  }

  /* и панорама, и перенос карточки слушают окно: указатель уходит с элемента, под
     которым начали, а pointer capture на масштабированном слое ведёт себя неровно */
  const stageDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return
    setMenu(null)
    skipClick.current = false
    if (e.shiftKey) { bandDown(e); return }
    let last = { x: e.clientX, y: e.clientY }
    const move = (m: PointerEvent) => {
      if (pinch.current) return
      const dx = m.clientX - last.x, dy = m.clientY - last.y
      if (!dx && !dy) return
      skipClick.current = true
      last = { x: m.clientX, y: m.clientY }
      setView(v => ({ ...v, tx: v.tx + dx, ty: v.ty + dy }))
    }
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }
  /* Shift + рамка: всё, что она задела, идёт в выделение — дальше пачку тянут
     и убирают целиком. Ctrl/Meta добавляет к уже выделенному */
  const bandDown = (e: React.PointerEvent<HTMLDivElement>) => {
    const [sx, sy] = at(e)
    const keep = e.ctrlKey || e.metaKey
    let box = { x1: sx, y1: sy, x2: sx, y2: sy }
    setBand(box)
    const move = (m: PointerEvent) => {
      const [x, y] = at(m)
      box = { x1: sx, y1: sy, x2: x, y2: y }
      skipClick.current = true
      setBand(box)
    }
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      setBand(null)
      const x1 = Math.min(box.x1, box.x2), x2 = Math.max(box.x1, box.x2)
      const y1 = Math.min(box.y1, box.y2), y2 = Math.max(box.y1, box.y2)
      if (x2 - x1 < 4 && y2 - y1 < 4) return
      const hit = cardsRef.current.filter(card => {
        const b = boxOf(card)
        return b.x < x2 && b.x + b.w > x1 && b.y < y2 && b.y + b.h > y1
      }).map(card => card.id)
      setSel(cur => (keep ? [...new Set([...cur, ...hit])] : hit))
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  const stageMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const [x, y] = at(e)
    lastPt.current = { x, y }
    if (linkFrom) setGhost([x, y])
  }
  const stageClick = () => {
    if (skipClick.current) { skipClick.current = false; return }
    if (linkFrom) { setLinkFrom(''); setGhost(null); return }
    if (selEdge) setSelEdge('')
    setSel([])
    setMenu(null)
  }

  const cardDown = (e: React.PointerEvent<Element>, card: Dict) => {
    if (e.button !== 0) return
    e.stopPropagation()
    setMenu(null)
    if (linkFrom) return
    /* взялись за карточку — она же и выделена: у безрамочных всё тело занимает
       текстовое поле, и клика по «пустому месту» карточки там просто нет */
    setSel(cur => (e.ctrlKey || e.metaKey || e.shiftKey
      ? (cur.includes(card.id) ? cur.filter(x => x !== card.id) : [...cur, card.id])
      : (cur.includes(card.id) ? cur : [card.id])))
    const [sx, sy] = at(e)
    /* тянут за одну из выделенных — едет вся пачка, иначе только эта карточка */
    const group = sel.includes(card.id) && sel.length > 1 ? [...sel] : [card.id]
    let moved = false
    let shift = { dx: 0, dy: 0 }
    const move = (m: PointerEvent) => {
      if (pinch.current) return
      const [x, y] = at(m)
      if (!moved && Math.hypot(x - sx, y - sy) * view.k < 4) return
      moved = true
      shift = { dx: Math.round(x - sx), dy: Math.round(y - sy) }
      setDragPos({ ids: group, ...shift })
    }
    const up = async () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      if (!moved) return
      skipClick.current = true
      for (const id of group) {
        const it = cardsRef.current.find(x => x.id === id)
        if (!it) continue
        try {
          await api.patch(`${c()}/board-cards/${id}`,
            { x: it.x + shift.dx, y: it.y + shift.dy })
        } catch (err: any) { setOops(err.message || t('err.position')) }
      }
      reloadCards()
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    raise(card)
  }

  const raise = async (card: Dict) => {
    const top = Math.max(0, ...list.map(x => x.z || 0))
    if ((card.z || 0) >= top) return
    try { await api.patch(`${c()}/board-cards/${card.id}`, { z: top + 1 }) } catch { /* noop */ }
  }

  /* клик тянет нить, если она начата, иначе выделяет; Ctrl/Shift набирает пачку */
  const clickCard = (card: Dict, add: boolean) => {
    if (linkFrom) {
      if (linkFrom === card.id) { setLinkFrom(''); setGhost(null); return }
      link(linkFrom, card.id)
      return
    }
    setSelEdge('')
    setSel(cur => add
      ? (cur.includes(card.id) ? cur.filter(x => x !== card.id) : [...cur, card.id])
      : [card.id])
  }

  const link = async (from: string, to: string) => {
    setLinkFrom('')
    setGhost(null)
    try {
      await api.post(`${c()}/board-edges`, {
        board_id: board.id, from_card_id: from, to_card_id: to, color: 'rust', style: 'thread',
      })
    } catch (e: any) { setOops(e.message || t('err.thread')) }
    reloadEdges()
  }

  /* куда лечь новой карточке: точка вызова меню, иначе центр видимой части холста */
  const spot = (): Dict => {
    if (adding?.at) return adding.at
    if (menu && !menu.card) return { x: menu.bx, y: menu.by }
    const r = viewRef.current?.getBoundingClientRect()
    return {
      x: r ? Math.round((r.width / 2 - view.tx) / view.k) - 120 : 40,
      y: r ? Math.round((r.height / 2 - view.ty) / view.k) - 80 : 40,
    }
  }

  const addCard = async (body: Dict, at?: Dict) => {
    const p = at || spot()
    try {
      await api.post(`${c()}/board-cards`, { board_id: board.id, x: p.x, y: p.y, ...body })
    } catch (e: any) { setOops(e.message || t('err.card')) }
    setAdding(null)
    setMenu(null)
    reloadCards()
    onCards()
  }

  const openMenu = (e: React.MouseEvent, card?: Dict) => {
    e.preventDefault()
    e.stopPropagation()
    const r = viewRef.current?.getBoundingClientRect()
    if (!r) return
    const [bx, by] = at(e)
    if (card) setSel(cur => (cur.includes(card.id) ? cur : [card.id]))
    setMenu({ sx: e.clientX - r.left, sy: e.clientY - r.top, bx, by, card, ...markTarget(e, card) })
  }

  /* куда лягут жирный/курсив из меню: поле с выделением внутри карточки, а у
     текстового поля — его текст целиком */
  const markTarget = (e: React.MouseEvent, card?: Dict) => {
    const host = e.currentTarget as HTMLElement
    if (!card || !host?.querySelector) return {}
    const s = window.getSelection()
    const range = s && s.rangeCount && !s.isCollapsed ? s.getRangeAt(0) : null
    const node = range?.commonAncestorContainer
    const inSel = node && (node.nodeType === Node.ELEMENT_NODE ? node as Element : node.parentElement)
      ?.closest('.bd-rich')
    const field = (inSel && host.contains(inSel) ? inSel : null)
      || (card.kind === 'text' ? host.querySelector('.bd-rich') : null)
    if (!field) return {}
    return { markField: field, markRange: field === inSel ? range!.cloneRange() : null }
  }

  /* Текст и записки правит сам ГМ и видит результат в поле: перечитывать за ними
     доску незачем — держим свежий слепок в cardsRef и обходимся одним запросом.
     Всё остальное (цвет, кегль, тик счётчика) меняет вид карточки — там перечитываем. */
  const saveCard = async (card: Dict, patch: Dict, refresh = true) => {
    if (!refresh) {
      cardsRef.current = cardsRef.current.map(
        x => (x.id === card.id ? { ...x, ...patch } : x))
    }
    try { await api.patch(`${c()}/board-cards/${card.id}`, patch) }
    catch (e: any) { setOops(e.message || t('err.edit')); return }
    if (refresh) reloadCards()
  }


  /* записки правим от последнего известного состояния, а не от снимка в пропсах */
  const saveNotes = (card: Dict, fn: (notes: Dict[]) => Dict[], refresh = false) => {
    const cur = cardsRef.current.find(x => x.id === card.id)?.notes || []
    return saveCard(card, { notes: fn(cur) }, refresh)
  }

  /* убрать спрашиваем всегда: пачку легко снести случайно. Сами записи, счётчики
     и файлы остаются в кампании — пропадают только место на доске и нити к ним */
  const askDropCards = (ids: string[]) => {
    if (!ids.length) return
    const one = ids.length === 1
      ? cardsRef.current.find(x => x.id === ids[0]) : null
    const text = one
      ? t('drop.one', { name: one.entity?.name || one.clock?.name || one.title || t('drop.card') })
      : t('drop.many', { count: ids.length })
    setKillAsk({ text, yes: t('drop.yes'), run: () => dropCards(ids) })
  }

  const dropCards = async (ids: string[]) => {
    for (const id of ids) {
      try { await api.del(`${c()}/board-cards/${id}`) }
      catch (e: any) { setOops(e.message || t('err.drop')) }
    }
    setSel(cur => cur.filter(id => !ids.includes(id)))
    reloadCards()
    reloadEdges()
    onCards()
  }
  const dropCard = (card: Dict) => askDropCards([card.id])

  /* счётчик на доске — тот же счётчик кампании: правка уходит в /clocks;
     пока тик в пути, повторный клик по тому же счётчику не уходит */
  const ticking = useRef(new Set<string>())
  const tickClock = async (clockId: string, delta: number, comment = '') => {
    if (ticking.current.has(clockId)) return
    ticking.current.add(clockId)
    try { await api.post(`${c()}/clocks/${clockId}/tick`, { delta, comment }) }
    catch (e: any) { setOops(e.message || t('err.tick')) }
    ticking.current.delete(clockId)
    reloadCards()
  }

  const askDropEdge = (id: string) =>
    setKillAsk({ text: t('drop.thread'), yes: t('drop.yes'),
      run: () => dropEdge(id) })

  const dropEdge = async (id: string) => {
    setSelEdge('')
    try { await api.del(`${c()}/board-edges/${id}`) }
    catch (e: any) { setOops(e.message || t('err.thread_drop')) }
    reloadEdges()
  }
  const labelEdge = async (edge: Dict, label: string) => {
    try { await api.patch(`${c()}/board-edges/${edge.id}`, { label }) }
    catch (e: any) { setOops(e.message || t('err.label')) }
    reloadEdges()
  }

  /* навели на нить — на доске остаётся весь клубок, до которого она дотягивается:
     связь читается вместе со своей цепочкой, а не двумя карточками из середины */
  const web = useMemo(() => {
    const t0 = hotEdge ? threads.find(t => t.id === hotEdge) : null
    if (!t0) return null
    const cards = new Set<string>([t0.from_card_id, t0.to_card_id])
    const edges = new Set<string>([t0.id])
    for (let grew = true; grew;) {
      grew = false
      for (const t of threads) {
        if (edges.has(t.id)) continue
        if (!cards.has(t.from_card_id) && !cards.has(t.to_card_id)) continue
        edges.add(t.id)
        cards.add(t.from_card_id)
        cards.add(t.to_card_id)
        grew = true
      }
    }
    return { cards, edges }
  }, [hotEdge, threads])

  const byId: Dict = Object.fromEntries(list.map(x => [x.id, x]))
  const fromCard = linkFrom ? byId[linkFrom] : null

  return (
    <div className="col bd-wrap">
      {board.summary && <div className="bd-sum">{board.summary}</div>}
      {cardsErr && (
        <div className="bd-oops" role="alert">{t('err.cards_load', { err: cardsErr })}</div>
      )}
      {oops && (
        <div className="bd-oops" role="alert" onClick={() => setOops('')}>
          {oops}<span className="dim2 small"> · {t('dismiss')}</span>
        </div>
      )}

      <div className="bd-tabs">
        {TABS.map(([k, lb]) => (
          <button key={k} className={`tiny ghost${tab === k ? ' on' : ''}`}
            onClick={() => setTab(k)}>{t(lb)}</button>
        ))}
        <span className="dim2 small">{t('on_board', { count: list.length })}</span>
      </div>

      {tab === 'roster' ? (
        <BoardRoster cards={list} onOpenEntity={setEntityId} onOpenClock={setClockFor}
          onTick={(id, d) => tickClock(id, d)} />
      ) : (<>
      <div ref={viewRef} className={`bd-view${linkFrom ? ' linking' : ''}`}
        onPointerDown={stageDown} onPointerMove={stageMove} onClick={stageClick}
        onContextMenu={e => openMenu(e)}>
        <div className="bd-layer"
          style={{ transform: `translate(${view.tx}px, ${view.ty}px) scale(${view.k})` }}>
          <svg className="bd-ink">
            {threads.map(t => {
              const a = byId[t.from_card_id], b = byId[t.to_card_id]
              if (!a || !b) return null
              const [x1, y1] = centerOf(a)
              const [x2, y2] = centerOf(b)
              const mx = (x1 + x2) / 2, my = (y1 + y2) / 2
              const on = selEdge === t.id
              /* верёвка провисает под своим весом: чем длиннее, тем глубже дуга */
              const sag = Math.min(60, Math.hypot(x2 - x1, y2 - y1) * 0.12)
              const d = `M ${x1} ${y1} Q ${mx} ${my + sag * 2} ${x2} ${y2}`
              return (
                <g key={t.id}
                  className={`bd-thread${on ? ' on' : ''}`
                    + (web && !web.edges.has(t.id) ? ' faded' : '')}>
                  <path d={d} fill="none" stroke={hex(t.color)} strokeWidth={on ? 2.4 : 1.6}
                    strokeLinecap="round"
                    strokeDasharray={t.style === 'dashed' ? '7 6' : undefined} />
                  <circle cx={x1} cy={y1} r={3.5} className="bd-pin" fill={hex(t.color)} />
                  <circle cx={x2} cy={y2} r={3.5} className="bd-pin" fill={hex(t.color)} />
                  <path d={d} fill="none" stroke="transparent" strokeWidth={16}
                    style={{ pointerEvents: 'stroke', cursor: 'pointer' }}
                    onPointerEnter={() => setHotEdge(t.id)}
                    onPointerLeave={() => setHotEdge(cur => (cur === t.id ? '' : cur))}
                    onClick={ev => { ev.stopPropagation(); skipClick.current = true; setSelEdge(t.id) }} />
                  {t.label && (
                    <text x={mx} y={my + sag} className="bd-thread-lab" textAnchor="middle">
                      {t.label}
                    </text>
                  )}
                </g>
              )
            })}
            {fromCard && ghost && (
              <line x1={centerOf(fromCard)[0]} y1={centerOf(fromCard)[1]}
                x2={ghost[0]} y2={ghost[1]} stroke={hex('rust')} strokeWidth={2}
                strokeDasharray="6 6" />
            )}
          </svg>

          {band && (
            <div className="bd-band" style={{
              left: Math.min(band.x1, band.x2), top: Math.min(band.y1, band.y2),
              width: Math.abs(band.x2 - band.x1), height: Math.abs(band.y2 - band.y1),
            }} />
          )}

          {list.map(card => {
            const p = posOf(card)
            return (
              <BoardCard key={card.id} card={card} x={p.x} y={p.y} k={view.k}
                linking={linkFrom === card.id} threading={!!linkFrom}
                onMeasure={el => measure(card.id, el)}
                onPointerDown={e => cardDown(e, card)}
                selected={sel.includes(card.id)}
                faded={!!web && !web.cards.has(card.id)}
                onClick={add => clickCard(card, add)}
                onMenu={e => openMenu(e, card)}
                onSave={(patch, quiet) => saveCard(card, patch, !quiet)}
                onOpenEntity={() => card.entity && setEntityId(card.entity.id)}
                onNotes={(fn, quiet) => saveNotes(card, fn, !quiet)}
                onTick={(d, cm) => tickClock(card.clock_id, d, cm)}
                onOpenClock={() => setClockFor(card)}
                onDrop={() => dropCard(card)} />
            )
          })}

          {selEdge && (() => {
            const th = threads.find(x => x.id === selEdge)
            if (!th) return null
            const a = byId[th.from_card_id], b = byId[th.to_card_id]
            if (!a || !b) return null
            const [x1, y1] = centerOf(a)
            const [x2, y2] = centerOf(b)
            return (
              <div className="bd-thread-menu"
                style={{ left: (x1 + x2) / 2, top: (y1 + y2) / 2 }}
                onPointerDown={e => e.stopPropagation()}
                onClick={e => e.stopPropagation()}>
                <button className="tiny ghost" onClick={() => setLabelFor(th)}>{t('thread.label')}</button>
                {PALETTE.map(k => (
                  <button key={k} className={`sw ${th.color === k ? 'on' : ''}`} title={PALETTE_NAME[k]}
                    onClick={async () => {
                      await api.patch(`${c()}/board-edges/${th.id}`, { color: k })
                      reloadEdges()
                    }}>
                    <i style={{ background: PALETTE_HEX[k] }} />
                  </button>
                ))}
                <button className="tiny ghost" onClick={async () => {
                  await api.patch(`${c()}/board-edges/${th.id}`, {
                    style: th.style === 'dashed' ? 'thread' : 'dashed',
                  })
                  reloadEdges()
                }}>{th.style === 'dashed' ? t('thread.solid') : t('thread.dashed')}</button>
                <button className="tiny danger" onClick={() => askDropEdge(th.id)}>{t('thread.drop')}</button>
              </div>
            )
          })()}
        </div>

        {menu && (
          <BoardMenu menu={menu} onClose={() => setMenu(null)}
            onCreate={kind => { setAdding({ kind: 'new-entity', entityKind: kind, name: '',
              alias: '', summary: '', at: { x: menu.bx, y: menu.by } }); setMenu(null) }}
            onImport={() => { setAdding({ kind: 'entity', tab: 'entity', entity: null,
              at: { x: menu.bx, y: menu.by } }); setMenu(null) }}
            onNote={() => addCard({ kind: 'text', title: '', body: '', w: CARD_W.text },
              { x: menu.bx, y: menu.by })}
            onShot={() => { setAdding({ kind: 'image', title: '', image_url: '',
              at: { x: menu.bx, y: menu.by } }); setMenu(null) }}
            onSketch={() => addCard(
              { kind: 'sketch', w: CARD_W.sketch, h: SKETCH_H, ink: [] },
              { x: menu.bx, y: menu.by })}
            onName={() => { setAdding({ kind: 'name', at: { x: menu.bx, y: menu.by } })
              setMenu(null) }}
            onClock={() => { setAdding({ kind: 'clock', name: '', color: 'amber',
              segments: 6, at: { x: menu.bx, y: menu.by } }); setMenu(null) }}
            onThread={card => { setLinkFrom(card.id); setMenu(null) }}
            onOpenEntity={card => { setEntityId(card.entity.id); setMenu(null) }}
            onOpenClock={card => { setClockFor(card); setMenu(null) }}
            onNews={card => {
              // выделено несколько карточек — новость обо всех записях и счётчиках в выделении
              const cards = sel.includes(card.id) && sel.length > 1 ? sel.map(id => byId[id]).filter(Boolean) : [card]
              setNewsFor(cards.flatMap((cd: Dict) => (cd.kind === 'entity' && cd.entity ? [attachOfEntity(cd.entity)]
                : cd.kind === 'clock' && cd.clock ? [attachOfClock(cd.clock)] : [])))
              setMenu(null)
            }}
            onColor={(card, color) => { saveCard(card, { color }); setMenu(null) }}
            onDropCard={card => {
              setMenu(null)
              dropCards(sel.includes(card.id) && sel.length > 1 ? sel : [card.id])
            }}
            selCount={sel.includes(menu.card?.id) ? sel.length : 1}
            onFont={(card, size) => { saveCard(card, { font_size: size }); setMenu(null) }} />
        )}

        <div className="bd-zoombar" onPointerDown={e => e.stopPropagation()}
          onClick={e => e.stopPropagation()} onContextMenu={e => e.stopPropagation()}>
          <button className="tiny ghost" title={t('zoom.out')}
            onClick={() => zoomCenter(1 / STEP)}>−</button>
          <span className="bd-zoom">{Math.round(view.k * 100)}%</span>
          <button className="tiny ghost" title={t('zoom.in')}
            onClick={() => zoomCenter(STEP)}>+</button>
          <button className="tiny ghost" title={t('zoom.fit_tip')}
            onClick={fitView}>{t('zoom.fit')}</button>
        </div>

        {!list.length && (
          <div className="bd-blank">{t('blank')}</div>
        )}
      </div>

      <div className="bd-hint">
        {pasting
          ? (pasting > 1 ? t('hint.paste_images') : t('hint.paste_image'))
          : linkFrom
            ? t('hint.linking')
            : t('hint.idle')}
      </div>
      </>)}

      {entityId && (() => {
        const close = () => { setEntityId(''); reloadCards() }
        const name = list.find(x => x.entity?.id === entityId)?.entity?.name || t('entry_title')
        return (
          <Modal wide title={name} onClose={close}>
            <EntityPage id={entityId} onClose={close} />
          </Modal>
        )
      })()}

      {adding?.kind === 'new-entity' && (
        <NewEntityModal kind={adding.entityKind} onClose={() => setAdding(null)}
          onDone={id => addCard(
            { kind: 'entity', entity_id: id, w: CARD_W.entity }, adding.at)} />
      )}

      {adding?.kind === 'entity' && (
        <Modal title={t('pick_title')} onClose={() => setAdding(null)}>
          <BoardPick onPick={item => addCard(
            item.type === 'clock'
              ? { kind: 'clock', clock_id: item.id, w: CARD_W.clock }
              : { kind: 'entity', entity_id: item.id, w: CARD_W.entity },
            adding.at,
          )} />
        </Modal>
      )}

      {adding?.kind === 'image' && (
        <Modal title={t('image_title')} onClose={() => setAdding(null)}>
          <PickImage value={adding.image_url} boardId={board.id}
            onPick={url => setAdding({ ...adding, image_url: url })} />
          <button className="primary" disabled={!adding.image_url} onClick={() => addCard({
            kind: 'image', image_url: adding.image_url, w: CARD_W.image,
          }, adding.at)}>{t('place')}</button>
        </Modal>
      )}

      {adding?.kind === 'name' && (
        <NameRoll onClose={() => setAdding(null)}
          onDone={(title, body) => addCard(
            { kind: 'name', title, body, w: CARD_W.name }, adding.at)} />
      )}

      {adding?.kind === 'clock' && (
        <NewClockModal onClose={() => setAdding(null)}
          onDone={id => addCard({ kind: 'clock', clock_id: id, w: CARD_W.clock }, adding.at)} />
      )}

      {labelFor && (
        <AskText title={t('thread.label_title')} label={t('thread.label_field')} value={labelFor.label || ''}
          onClose={() => setLabelFor(null)} onSave={v => labelEdge(labelFor, v)} />
      )}

      {killAsk && (
        <Ask text={killAsk.text} yes={killAsk.yes} onClose={() => setKillAsk(null)}
          onYes={killAsk.run} />
      )}

      {clockFor && (
        <ClockEdit card={clockFor} onClose={() => setClockFor(null)}
          onDone={() => { setClockFor(null); reloadCards() }} />
      )}

      {newsFor && <NewsGenerator attach={newsFor} toFeed onClose={() => setNewsFor(null)} />}

    </div>
  )
}

/* --- состав квеста -------------------------------------------------------- */

/** Состав доски: те же карточки, но разрезом картотеки — сперва персонажи, потом
    фракции, локации, счётчики. Холст отвечает на «кто с кем связан», состав — на
    «кто вообще в этом квесте», и его читают не двигая ни одной карточки. */
function BoardRoster({ cards, onOpenEntity, onOpenClock, onTick }: {
  cards: Dict[]
  onOpenEntity: (id: string) => void
  onOpenClock: (card: Dict) => void
  onTick: (clockId: string, delta: number) => void
}) {
  const { L } = useApp()
  const { t } = useTranslation('boards')

  const groups = useMemo(() => {
    const out: { key: string; label: string; items: Dict[] }[] = []
    for (const [kind, label] of ROSTER_KINDS) {
      const items = cards.filter(cd => cd.kind === 'entity' && cd.entity?.kind === kind)
      if (items.length) out.push({ key: kind, label, items })
      if (kind !== 'npc') continue
      /* статисты идут сразу за персонажами, но своей полкой: их не переиспользуют
         и с записями кампании путать нельзя */
      const names = cards.filter(cd => cd.kind === 'name')
      if (names.length) out.push({ key: 'name', label: 'roster.extras', items: names })
    }
    // запись удалили из кампании, а карточка осталась — теряться ей на доске нельзя
    const orphans = cards.filter(cd => cd.kind === 'entity' && !cd.entity)
    if (orphans.length) out.push({ key: 'gone', label: 'roster.gone', items: orphans })
    const clocks = cards.filter(cd => cd.kind === 'clock')
    if (clocks.length) out.push({ key: 'clock', label: 'roster.clocks', items: clocks })
    const notes = cards.filter(cd => ['text', 'image', 'sketch'].includes(cd.kind))
    if (notes.length) out.push({ key: 'notes', label: 'roster.notes', items: notes })
    return out
  }, [cards])

  if (!cards.length) {
    return (
      <div className="empty">{t('roster.empty')}</div>
    )
  }

  return (
    <div className="eg-groups bd-ros">
      {groups.map(g => (
        <div className="eg-group" key={g.key}>
          <div className="eg-group-hd">
            <span className="t">{t(g.label)}</span>
            <span className="n">{g.items.length}</span>
          </div>
          <div className="eg-grid">
            {g.items.map(cd => (
              <RosterTile key={cd.id} card={cd} L={L}
                onOpenEntity={onOpenEntity} onOpenClock={onOpenClock} onTick={onTick} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

/** Плитка состава: запись — снимком и подписью, счётчик — циферблатом, заметка —
    своим текстом или кадром. Записки с доски идут чипами: на квест они и заводились. */
function RosterTile({ card, L, onOpenEntity, onOpenClock, onTick }: {
  card: Dict
  L: (k?: string | null) => string
  onOpenEntity: (id: string) => void
  onOpenClock: (card: Dict) => void
  onTick: (clockId: string, delta: number) => void
}) {
  const { t } = useTranslation('boards')
  const e = card.entity
  const cl = card.clock
  const notes: Dict[] = (card.notes || []).filter((n: Dict) => String(n.text || '').trim())

  if (card.kind === 'clock') {
    return (
      <div className="eg-card bd-ros-card">
        {!cl ? <div className="eg-body dim2 small">{t('clock_gone')}</div> : (
          <div className="eg-body">
            <div className="bd-ros-clock">
              <button type="button" className="bd-ros-dial" title={t('edit_clock')}
                onClick={() => onOpenClock(card)}>
                <ClockDial segments={cl.segments} filled={cl.filled} size={52} color={cl.color} />
              </button>
              <div className="col" style={{ gap: 4, minWidth: 0 }}>
                <button type="button" className="bd-ros-name" onClick={() => onOpenClock(card)}>
                  {clockTitle(cl)}
                </button>
                <div className="row wrap">
                  <span className="mono dim2 small">{cl.filled}/{cl.segments}</span>
                  {cl.kind && <Chip tone="cyan">{cl.kind}</Chip>}
                  {cl.status !== 'active' && (
                    <Chip tone={cl.status === 'completed' ? 'green' : 'black'}>{L(cl.status)}</Chip>
                  )}
                </div>
              </div>
            </div>
            {cl.description && <div className="eg-sub">{cl.description}</div>}
            {card.body && <div className="eg-sub"><Marked text={card.body} /></div>}
            {cl.status === 'active' && (
              <div className="row">
                <button className="tiny ghost" disabled={cl.filled <= 0}
                  onClick={() => onTick(cl.id, -1)}>−1</button>
                <button className="tiny" disabled={cl.filled >= cl.segments}
                  onClick={() => onTick(cl.id, 1)}>+1</button>
              </div>
            )}
            <RosterNotes notes={notes} />
          </div>
        )}
      </div>
    )
  }

  if (card.kind === 'name') {
    return (
      <div className="eg-card bd-ros-card">
        <div className="eg-body">
          <div className="eg-name"><span>{card.title || t('roster.no_name')}</span></div>
          {card.body && <div className="eg-sub full"><Marked text={card.body} /></div>}
          <RosterNotes notes={notes} />
        </div>
      </div>
    )
  }

  if (card.kind === 'text' || card.kind === 'image' || card.kind === 'sketch') {
    return (
      <div className="eg-card bd-ros-card">
        {card.kind === 'image' && card.image_url && (
          <img className="eg-photo" src={thumb(card.image_url, 480)} alt="" loading="lazy" />
        )}
        <div className="eg-body">
          <div className="eg-name">
            <span>{card.title || (card.kind === 'sketch' ? t('noun.sketch')
              : card.kind === 'image' ? t('noun.frame') : t('noun.note'))}</span>
          </div>
          {card.kind === 'sketch' && (
            <div className="dim2 small">
              {t('roster.lines', { count: (card.ink || []).filter((m: Dict) => m.kind !== 'text').length })}
              {(card.ink || []).some((m: Dict) => m.kind === 'text')
                ? t('roster.labels', { list: (card.ink || [])
                  .filter((m: Dict) => m.kind === 'text').map((m: Dict) => m.text).join(', ') })
                : ''}
            </div>
          )}
          {card.body && <div className="eg-sub full"><Marked text={card.body} /></div>}
        </div>
      </div>
    )
  }

  if (!e) {
    return (
      <div className="eg-card bd-ros-card">
        <div className="eg-body">
          <div className="eg-name"><span>{card.title || card.key || t('noun.card')}</span></div>
          <div className="dim2 small">{t('entry_gone')}</div>
          <RosterNotes notes={notes} />
        </div>
      </div>
    )
  }

  return (
    <div className="eg-card bd-ros-card">
      <button type="button" className="bd-ros-open" onClick={() => onOpenEntity(e.id)}
        title={t('open_entry')}>
        <div className="eg-shot-box">
          {e.image_url
            ? <img className="eg-photo" src={thumb(e.image_url, 480)} alt={e.name} loading="lazy" />
            : <Stub kind={e.kind} className="eg-photo" />}
          {e.status && (
            <span className={`eg-badge eg-status t-${statusTone(e.status)}`}>{L(e.status)}</span>
          )}
          {e.kind === 'faction' && rankRoman(e.rank) && (
            <span className="eg-badge eg-rank" title={t('tier')}>{rankRoman(e.rank)}</span>
          )}
        </div>
        <div className="eg-body">
          <div className="eg-name">
            <span>{e.name}{e.alias ? <span className="dim"> {t('roster.alias', { alias: e.alias })}</span> : null}</span>
          </div>
          {e.summary && <div className="eg-sub">{e.summary}</div>}
        </div>
      </button>
      {notes.length > 0 && <div className="eg-body bd-ros-notes"><RosterNotes notes={notes} /></div>}
    </div>
  )
}

/** Записки карточки в составе только читаются: правят их на холсте, где виден контекст. */
function RosterNotes({ notes }: { notes: Dict[] }) {
  if (!notes.length) return null
  return (
    <div className="eg-chips">
      {notes.map(n => (
        <span className="chip eg-tag" key={n.id}>
          {n.tag ? <i>{n.tag}:</i> : null} <Marked text={n.text} />
        </span>
      ))}
    </div>
  )
}

/* --- контекстное меню ------------------------------------------------------ */

function BoardMenu({
  menu, onClose, onCreate, onImport, onNote, onShot, onSketch, onName, onClock,
  onThread, onOpenEntity, onOpenClock, onNews, onColor, onDropCard, onFont, selCount,
}: {
  menu: Dict; onClose: () => void
  onCreate: (kind: string) => void
  onImport: () => void; onNote: () => void; onShot: () => void
  onSketch: () => void; onName: () => void
  onClock: (mode: string) => void
  onThread: (card: Dict) => void
  onOpenEntity: (card: Dict) => void
  onOpenClock: (card: Dict) => void
  onNews: (card: Dict) => void
  onColor: (card: Dict, color: string) => void
  onDropCard: (card: Dict) => void
  onFont: (card: Dict, size: number) => void
  selCount: number
}) {
  const { t } = useTranslation('boards')
  const card: Dict | undefined = menu.card
  const stop = (e: React.SyntheticEvent) => e.stopPropagation()
  useLayer(true, onClose)

  return (
    <div className="bd-menu" style={{ left: menu.sx, top: menu.sy }}
      onPointerDown={stop} onClick={stop} onContextMenu={e => { e.preventDefault(); onClose() }}>
      {card ? (
        <>
          <div className="bd-menu-lb">{card.entity?.name || clockTitle(card.clock)
            || (card.kind === 'text' ? t('noun.text_field')
              : card.kind === 'image' ? t('noun.image')
                : card.kind === 'sketch' ? t('noun.sketch')
                  : card.kind === 'name' ? t('noun.extra') : t('noun.card'))}</div>
          <button onClick={() => onThread(card)}>{t('menu.thread_from')}</button>
          {card.kind === 'entity' && card.entity && (
            <button onClick={() => onOpenEntity(card)}>{t('open_entry')}</button>
          )}
          {card.kind === 'clock' && card.clock && (
            <button onClick={() => onOpenClock(card)}>{t('edit_clock')}</button>
          )}
          {((card.kind === 'entity' && card.entity) || (card.kind === 'clock' && card.clock)) && (
            <button onClick={() => onNews(card)}>
              {selCount > 1 ? t('menu.news_sel', { n: selCount }) : t('menu.news_this')}
            </button>
          )}
          {menu.markField && (
            <div className="bd-menu-row">
              <span className="bd-menu-kind">{menu.markRange ? t('menu.mark_sel') : t('menu.mark_all')}</span>
              {MARKS.map(([cmd, lb, tip]) => (
                <button key={cmd} className={`bd-mark-${cmd}`} title={t(tip)}
                  onClick={() => { applyMark(menu.markField, cmd, menu.markRange); onClose() }}>
                  {t(lb)}
                </button>
              ))}
            </div>
          )}
          {card.kind === 'text' && (
            <div className="bd-menu-row">
              <span className="bd-menu-kind">{t('menu.font')}</span>
              {FONT_SIZES.map(([size, lb]) => (
                <button key={size} className={(card.font_size || 14) === size ? 'on' : ''}
                  title={`${size}px`} onClick={() => onFont(card, size)}>{lb}</button>
              ))}
            </div>
          )}
          <div className="bd-menu-colors">
            {PALETTE.map(k => (
              <button key={k} className={`sw ${card.color === k ? 'on' : ''}`}
                title={PALETTE_NAME[k]} onClick={() => onColor(card, k)}>
                <i style={{ background: PALETTE_HEX[k] }} />
              </button>
            ))}
          </div>
          <button className="bad" onClick={() => onDropCard(card)}>
            {selCount > 1 ? t('menu.drop_n', { n: selCount }) : t('drop_from_board')}
          </button>
        </>
      ) : (
        <>
          <button className="bd-menu-main" onClick={onImport}>{t('menu.take')}</button>
          <div className="bd-menu-lb">{t('menu.create_new')}</div>
          {NEW_KINDS.map(([k, lb]) => (
            <button key={k} onClick={() => onCreate(k)}>{t(lb)}</button>
          ))}
          <button onClick={() => onClock('new')}>{t('menu.clock')}</button>
          <div className="bd-menu-lb">{t('menu.place')}</div>
          <button onClick={onNote}>{t('menu.text_field')}</button>
          <button onClick={onShot}>{t('menu.image')}</button>
          <button onClick={onSketch}>{t('menu.sketch')}</button>
          <button onClick={onName}>{t('menu.extra')}</button>
        </>
      )}
    </div>
  )
}

/* --- карточка ------------------------------------------------------------- */

function BoardCard({
  card, x, y, k, linking, threading, selected, faded, onMeasure, onPointerDown, onClick, onMenu,
  onSave, onOpenEntity, onNotes, onTick, onOpenClock, onDrop,
}: {
  card: Dict; x: number; y: number; k: number
  linking: boolean; threading: boolean; selected: boolean; faded: boolean
  onMeasure: (el: HTMLElement | null) => void
  onPointerDown: (e: React.PointerEvent<Element>) => void
  onClick: (add: boolean) => void
  onMenu: (e: React.MouseEvent) => void
  /* quiet — правка не меняет вид карточки (текст, записка): доску не перечитываем */
  onSave: (patch: Dict, quiet?: boolean) => void
  onOpenEntity: () => void
  onNotes: (fn: (notes: Dict[]) => Dict[], quiet?: boolean) => void
  onTick: (delta: number, comment?: string) => void
  onOpenClock: () => void
  onDrop: () => void
}) {
  const { L } = useApp()
  const { t } = useTranslation('boards')
  const ref = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const e = card.entity

  useEffect(() => {
    const el = ref.current
    if (!el) return
    onMeasure(el)
    const ro = new ResizeObserver(() => onMeasure(el))
    ro.observe(el)
    return () => ro.disconnect()
  }, [card.id, card.w, card.collapsed])

  const cl = card.clock
  const bare = card.kind === 'text' || card.kind === 'image'
  /* в шапке — только пометка о роде карточки: имя записи живёт крупно в теле */
  const head = card.kind === 'entity' ? L(e?.kind) || t('noun.entry')
    : card.kind === 'clock' ? t('noun.clock')
      : card.kind === 'image' ? (card.title || t('noun.frame'))
        : card.kind === 'sketch' ? t('noun.sketch')
          : card.kind === 'name' ? t('noun.extra')
            : t('noun.text')

  return (
    <div ref={ref}
      className={`bd-card k-${card.kind}${bare ? ' bare' : ''}${linking ? ' linking' : ''}`
        + (selected ? ' sel' : '') + (faded ? ' faded' : '')}
      style={{ left: x, top: y, width: card.w || 240, borderTopColor: hex(card.color) }}
      onClick={ev => { ev.stopPropagation(); onClick(ev.ctrlKey || ev.metaKey || ev.shiftKey) }}
      onContextMenu={onMenu}>
      {bare
        /* текст и картинка ложатся на доску как есть: тянутся за себя, убираются из ПКМ */
        ? <div className="bd-bare-grab" onPointerDown={onPointerDown}
            style={{ cursor: threading ? 'crosshair' : 'grab' }} />
        : (
          <div className="bd-card-hd" onPointerDown={onPointerDown}
            style={{ cursor: threading ? 'crosshair' : 'grab' }}>
            <span className="bd-card-t" title={head}>{head}</span>
            <button className="bd-x" title={t('drop_from_board')}
              onPointerDown={ev => ev.stopPropagation()}
              onClick={ev => { ev.stopPropagation(); onDrop() }}>×</button>
          </div>
        )}

      {card.kind === 'entity' && (
        <div className="bd-card-body">
          {/* фото и описание — из самой записи: на доске они только показываются,
              правка идёт в полном окне карточки (клик по ней) */}
          <button type="button" className="bd-ent" title={t('open_entry')}
            onClick={ev => { ev.stopPropagation(); onOpenEntity() }}>
            {e?.image_url
              ? <img className="bd-thumb" src={thumb(e.image_url, 240)} alt="" />
              : <Stub kind={e?.kind || 'npc'} className="bd-thumb" />}
            <span className="bd-ent-main">
              {e ? <>
                <span className="bd-ent-name">
                  {e.name}
                  {/* цифра идёт строкой, а не отдельной колонкой: колонка отъедала
                      ширину у имени и рвала длинные названия по буквам */}
                  {e.kind === 'faction' && rankRoman(e.rank) &&
                    <span className="bd-ent-rank" title={t('card.tier', { tier: rankRoman(e.rank) })}>
                      {rankRoman(e.rank)}
                    </span>}
                </span>
                {e.summary && <span className="bd-ent-sum">{e.summary}</span>}
              </> : <span className="dim2 small">{t('card.entry_deleted')}</span>}
            </span>
          </button>
          <NoteStack notes={card.notes || []} onChange={onNotes} />
        </div>
      )}

      {card.kind === 'text' && (
        <div className="bd-card-body">
          <CardText value={card.body} placeholder={t('card.text_ph')}
            fontSize={card.font_size || 14} onSave={v => onSave({ body: v }, true)} />
        </div>
      )}

      {card.kind === 'name' && (
        <div className="bd-card-body">
          {/* статист — это имя и одна строка о нём: больше ему не нужно, а
              понадобится больше — из него заводят настоящую запись */}
          <CardText value={card.title} single placeholder={t('card.name_ph')} fontSize={17}
            onSave={v => onSave({ title: v }, true)} />
          <CardText value={card.body} placeholder={t('card.who_ph')}
            onSave={v => onSave({ body: v }, true)} />
          <NoteStack notes={card.notes || []} onChange={onNotes} />
        </div>
      )}

      {card.kind === 'clock' && (
        <div className="bd-card-body">
          {!cl ? <div className="dim2 small">{t('clock_gone')}</div> : (
            <div className="bd-clock" onPointerDown={ev => ev.stopPropagation()}>
              <button type="button" className="bd-clock-dial" title={t('edit_clock')}
                onClick={ev => { ev.stopPropagation(); onOpenClock() }}>
                <ClockDial segments={cl.segments} filled={cl.filled} size={54} color={cl.color} />
              </button>
              <div className="bd-clock-main">
                <button type="button" className="bd-clock-name" title={t('edit_clock')}
                  onClick={ev => { ev.stopPropagation(); onOpenClock() }}>{clockTitle(cl)}</button>
                <div className="row wrap">
                  <span className="mono dim2 small">{cl.filled}/{cl.segments}</span>
                  {cl.kind && <Chip tone="cyan">{cl.kind}</Chip>}
                  {cl.status !== 'active' && (
                    <Chip tone={cl.status === 'completed' ? 'green' : 'black'}>{L(cl.status)}</Chip>
                  )}
                </div>
                {cl.status === 'active' && (
                  <div className="row">
                    <button className="tiny ghost" disabled={cl.filled <= 0}
                      onClick={ev => { ev.stopPropagation(); onTick(-1) }}>−1</button>
                    <button className="tiny" disabled={cl.filled >= cl.segments}
                      onClick={ev => { ev.stopPropagation(); onTick(1) }}>+1</button>
                  </div>
                )}
              </div>
            </div>
          )}
          <CardText value={card.body} placeholder={t('card.clock_ph')}
            onSave={v => onSave({ body: v }, true)} />
          <NoteStack notes={card.notes || []} onChange={onNotes} />
        </div>
      )}

      {card.kind === 'image' && (
        <BoardShot url={card.image_url} k={k}
          onPointerDown={onPointerDown}
          onDoubleClick={ev => { ev.stopPropagation(); setOpen(true) }} />
      )}

      {card.kind === 'sketch' && (
        <SketchPad ink={card.ink || []} h={card.h || SKETCH_H}
          k={k} color={card.color} tools={selected}
          onSave={ink => onSave({ ink }, true)} />
      )}

      {/* ширину тянут за вертикальные кромки — и вправо, и влево; левая заодно
          сдвигает карточку, чтобы противоположный край стоял на месте */}
      {([-1, 1] as const).map(side => (
        <div key={side} className={`bd-edge ${side < 0 ? 'left' : 'right'}`}
          title={t('card.width')}
          onPointerDown={ev => {
            ev.stopPropagation()
            const startX = ev.clientX
            const startW = card.w || 240
            let w = startW
            const move = (m: PointerEvent) => {
              const d = (m.clientX - startX) / (k || 1)
              w = Math.round(Math.max(140, Math.min(1600, startW + side * d)))
              if (!ref.current) return
              ref.current.style.width = `${w}px`
              if (side < 0) ref.current.style.left = `${x + startW - w}px`
            }
            const up = () => {
              window.removeEventListener('pointermove', move)
              window.removeEventListener('pointerup', up)
              if (w === startW) return
              onSave(side < 0 ? { w, x: Math.round(x + startW - w) } : { w })
            }
            window.addEventListener('pointermove', move)
            window.addEventListener('pointerup', up)
          }} />
      ))}

      {/* у наброска высота своя: тянут за нижнюю кромку, как ширину — за боковые,
          а за уголок — обе сразу */}
      {card.kind === 'sketch' && (
        <div className="bd-corner" title={t('card.size')}
          onPointerDown={ev => {
            ev.stopPropagation()
            const startX = ev.clientX, startY = ev.clientY
            const startW = card.w || CARD_W.sketch, startH = card.h || SKETCH_H
            let w = startW, h = startH
            const move = (m: PointerEvent) => {
              const s = k || 1
              w = Math.round(Math.max(140, Math.min(1600, startW + (m.clientX - startX) / s)))
              h = Math.round(Math.max(120, Math.min(2000, startH + (m.clientY - startY) / s)))
              if (ref.current) ref.current.style.width = `${w}px`
              const pad = ref.current?.querySelector<HTMLElement>('.bd-sketch')
              if (pad) pad.style.height = `${h}px`
            }
            const up = () => {
              window.removeEventListener('pointermove', move)
              window.removeEventListener('pointerup', up)
              if (w !== startW || h !== startH) onSave({ w, h })
            }
            window.addEventListener('pointermove', move)
            window.addEventListener('pointerup', up)
          }} />
      )}

      {card.kind === 'sketch' && (
        <div className="bd-edge bottom" title={t('card.height')}
          onPointerDown={ev => {
            ev.stopPropagation()
            const startY = ev.clientY
            const startH = card.h || SKETCH_H
            let h = startH
            const move = (m: PointerEvent) => {
              const d = (m.clientY - startY) / (k || 1)
              h = Math.round(Math.max(120, Math.min(2000, startH + d)))
              const pad = ref.current?.querySelector<HTMLElement>('.bd-sketch')
              if (pad) pad.style.height = `${h}px`
            }
            const up = () => {
              window.removeEventListener('pointermove', move)
              window.removeEventListener('pointerup', up)
              if (h !== startH) onSave({ h })
            }
            window.addEventListener('pointermove', move)
            window.addEventListener('pointerup', up)
          }} />
      )}

      {open && (
        <Modal title={head} onClose={() => setOpen(false)} wide>
          <img style={{ width: '100%' }} src={card.image_url} alt="" />
        </Modal>
      )}
    </div>
  )
}

/** Поле для рисования: ГМ чертит поверх доски от руки — схема налёта, план
    палубы, стрелки по карте — и подписывает начерченное. Всё живёт в координатах
    карточки, поэтому едет вместе с ней при переносе и зуме. Правка уезжает по
    концу росчерка или подписи: пока ведут линию, запросов нет. */
/* Кадр на холсте берёт миниатюру по тому, сколько экранных пикселей он занимает:
   ширина карточки × зум × плотность экрана. Ступень только растёт — отдалил доску,
   а резкость осталась; следующая подгружается заранее и подменяет текущую без мигания */
const SHOT_STEPS = [240, 480, 960] as const
const shotStep = (px: number) => SHOT_STEPS.findIndex(w => px <= w)

function BoardShot({ url, k, onPointerDown, onDoubleClick }: {
  url: string; k: number
  onPointerDown: (e: React.PointerEvent<Element>) => void
  onDoubleClick: (e: React.MouseEvent) => void
}) {
  const ref = useRef<HTMLImageElement>(null)
  const [w, setW] = useState(0)
  const [step, setStep] = useState(-1)
  const need = w ? shotStep(w * k * (window.devicePixelRatio || 1)) : 1
  const want = need < 0 ? SHOT_STEPS.length : need
  const src = (i: number) => i >= SHOT_STEPS.length ? url : thumb(url, SHOT_STEPS[i])

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(() => setW(el.offsetWidth))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => { setStep(-1) }, [url])

  useEffect(() => {
    if (want <= step) return
    if (step < 0) { setStep(want); return }
    const im = new Image()
    im.onload = () => setStep(s => Math.max(s, want))
    im.src = src(want)
  }, [want, step, url])

  return (
    <img ref={ref} className="bd-shot" src={src(step < 0 ? want : step)} alt=""
      onPointerDown={onPointerDown} onDoubleClick={onDoubleClick} />
  )
}

function SketchPad({ ink, h, k, color, tools, onSave }: {
  ink: Dict[]; h: number; k: number; color?: string; tools: boolean
  onSave: (ink: Dict[]) => void
}) {
  const { t } = useTranslation('boards')
  const [marks, setMarks] = useState<Dict[]>(ink)
  const [live, setLive] = useState<number[] | null>(null)
  const [pen, setPen] = useState(color || 'amber')
  const [width, setWidth] = useState(3)
  const [size, setSize] = useState(22)
  const [mode, setMode] = useState('pen')
  /* подпись правится поверх поля обычным input: at — её место в списке, у новой -1 */
  const [edit, setEdit] = useState<Dict | null>(null)
  const box = useRef<SVGSVGElement>(null)
  const dirty = useRef(false)

  /* чужую правку принимаем, пока своей не было: набросок правит тот же ГМ, что
     на него смотрит, и перечитывать доску за каждым росчерком незачем */
  useEffect(() => { if (!dirty.current) setMarks(ink) }, [ink])
  // карточку сняли с выделения — приборы ушли, вместе с ними режим и недописанное
  useEffect(() => { if (!tools) { setMode('pen'); setEdit(null) } }, [tools])

  const put = (next: Dict[]) => {
    dirty.current = true
    setMarks(next)
    onSave(next)
  }

  /* точка в координатах карточки: рамка на холсте уже масштабирована зумом */
  const at = (e: PointerEvent | React.PointerEvent): number[] => {
    const r = box.current?.getBoundingClientRect()
    if (!r) return [0, 0]
    const s = k || 1
    return [
      Math.round(((e.clientX - r.left) / s) * 10) / 10,
      Math.round(((e.clientY - r.top) / s) * 10) / 10,
    ]
  }

  /* ластик снимает росчерк или подпись целиком: половинки линии на доске читаются
     хуже, чем перечёркнутая заново */
  const rub = (all: Dict[], x: number, y: number): Dict[] => all.filter(m => {
    if (m.kind === 'text') {
      const reach = Math.max(14, (m.size || 16) * 0.8)
      return Math.hypot((m.x || 0) - x, (m.y || 0) - y) > reach
    }
    const reach = Math.max(9, (m.width || 3) * 1.5)
    const p: number[] = m.pts || []
    for (let i = 0; i < p.length; i += 2) {
      if (Math.hypot(p[i] - x, p[i + 1] - y) <= reach) return false
    }
    return true
  })

  const commitEdit = (text: string) => {
    const body = text.trim()
    const cur = edit
    setEdit(null)
    if (!cur) return
    if (cur.at < 0) {
      if (!body) return
      put([...marks, {
        kind: 'text', text: body, x: cur.x, y: cur.y, color: cur.color, size: cur.size,
      }])
      return
    }
    const old = marks[cur.at]
    if (!old || old.kind !== 'text') return
    if (!body) { put(marks.filter((_, i) => i !== cur.at)); return }
    if (body === old.text) return
    put(marks.map((m, i) => (i === cur.at ? { ...m, text: body } : m)))
  }

  /* подпись тянут за неё саму: короткое движение — правка текста, длинное — перенос */
  const grabLabel = (e: React.PointerEvent, i: number) => {
    e.stopPropagation()
    e.preventDefault()
    const m = marks[i]
    const [sx, sy] = at(e)
    let moved = false
    let pos = [m.x || 0, m.y || 0]
    const move = (ev: PointerEvent) => {
      const [x, y] = at(ev)
      if (!moved && Math.hypot(x - sx, y - sy) < 3) return
      moved = true
      pos = [Math.round((m.x || 0) + (x - sx)), Math.round((m.y || 0) + (y - sy))]
      setMarks(cur => cur.map((c, j) => (j === i ? { ...c, x: pos[0], y: pos[1] } : c)))
      dirty.current = true
    }
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      if (moved) {
        put(marks.map((c, j) => (j === i ? { ...c, x: pos[0], y: pos[1] } : c)))
      } else {
        setEdit({
          at: i, x: m.x || 0, y: m.y || 0, text: m.text || '',
          color: m.color || pen, size: m.size || size,
        })
      }
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  const down = (e: React.PointerEvent) => {
    if (e.button !== 0) return
    e.stopPropagation()
    /* без этого браузер по нажатию уводит фокус на само поле — только что
       появившийся input подписи сразу теряет его и закрывается пустым */
    e.preventDefault()
    if (edit) return
    const [x0, y0] = at(e)

    if (mode === 'text') {
      setEdit({ at: -1, x: x0, y: y0, text: '', color: pen, size })
      return
    }

    if (mode === 'erase') {
      let left = rub(marks, x0, y0)
      const move = (m: PointerEvent) => {
        const [mx, my] = at(m)
        const next = rub(left, mx, my)
        if (next.length !== left.length) { left = next; setMarks(next); dirty.current = true }
      }
      const up = () => {
        window.removeEventListener('pointermove', move)
        window.removeEventListener('pointerup', up)
        if (left.length !== marks.length) put(left)
      }
      if (left.length !== marks.length) { setMarks(left); dirty.current = true }
      window.addEventListener('pointermove', move)
      window.addEventListener('pointerup', up)
      return
    }

    const pts = [x0, y0]
    setLive(pts)
    const move = (m: PointerEvent) => {
      const [x, y] = at(m)
      const n = pts.length
      // точки ближе полутора единиц друг к другу линию не меняют, а вес JSON растят
      if (Math.hypot(x - pts[n - 2], y - pts[n - 1]) < 1.5) return
      pts.push(x, y)
      setLive([...pts])
    }
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      setLive(null)
      // тычок без движения — точка: короткая линия сама в себя
      const line = pts.length >= 4 ? pts : [...pts, pts[0] + 0.6, pts[1] + 0.6]
      put([...marks, { color: pen, width, pts: line }])
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  const path = (pts: number[]) => {
    const out: string[] = []
    for (let i = 0; i < pts.length; i += 2) out.push(`${i ? 'L' : 'M'} ${pts[i]} ${pts[i + 1]}`)
    return out.join(' ')
  }

  const stop = (e: React.SyntheticEvent) => e.stopPropagation()

  return (
    <div className="bd-sketch-wrap">
      <svg ref={box} className={`bd-sketch m-${mode}`} style={{ height: h }}
        onPointerDown={down} onContextMenu={stop}>
        {marks.map((m, i) => (m.kind === 'text' ? (
          <text key={i} className="bd-sketch-lab" x={m.x || 0} y={m.y || 0}
            fill={inkHex(m.color)} fontSize={m.size || 16}
            style={{ pointerEvents: tools ? 'auto' : 'none' }}
            onPointerDown={ev => grabLabel(ev, i)}>{m.text}</text>
        ) : (
          <path key={i} d={path(m.pts || [])} fill="none" stroke={inkHex(m.color)}
            strokeWidth={m.width || 3} strokeLinecap="round" strokeLinejoin="round" />
        )))}
        {live && (
          <path d={path(live)} fill="none" stroke={inkHex(pen)} strokeWidth={width}
            strokeLinecap="round" strokeLinejoin="round" />
        )}
      </svg>

      {edit && (
        <input className="bd-sketch-in" autoFocus key={`${edit.at}:${edit.x}:${edit.y}`}
          defaultValue={edit.text}
          placeholder={t('ink.label_ph')}
          style={{
            left: edit.x, top: (edit.y || 0) - (edit.size || 16),
            fontSize: edit.size || 16, color: inkHex(edit.color),
          }}
          onPointerDown={stop} onClick={stop}
          onKeyDown={ev => {
            if (ev.key === 'Enter') { ev.preventDefault(); commitEdit(ev.currentTarget.value) }
            if (ev.key === 'Escape') { ev.preventDefault(); setEdit(null) }
          }}
          onBlur={ev => commitEdit(ev.currentTarget.value)} />
      )}

      {tools && (
        <div className="bd-ink-bar" onPointerDown={stop} onClick={stop}>
          {INK_MODES.map(([m, lb]) => (
            <button key={m} className={`tiny ghost${mode === m ? ' on' : ''}`}
              onClick={() => setMode(m)}>{t(lb)}</button>
          ))}
          {INK_COLORS.map(kk => (
            <button key={kk} className={`sw ${pen === kk ? 'on' : ''}`}
              title={kk === 'black' ? t('ink.graphite') : PALETTE_NAME[kk]} onClick={() => setPen(kk)}>
              <i style={{ background: INK_HEX[kk] }} />
            </button>
          ))}
          {mode === 'text'
            ? INK_SZ.map(([px, lb]) => (
              <button key={px} className={`tiny ghost${size === px ? ' on' : ''}`}
                title={`${px}px`} onClick={() => setSize(px)}>{lb}</button>
            ))
            : INK_W.map(([px, lb]) => (
              <button key={px} className={`tiny ghost${width === px ? ' on' : ''}`} title={t(lb)}
                onClick={() => setWidth(px)}>
                <i className="bd-ink-w" style={{ height: Math.max(2, px), background: inkHex(pen) }} />
              </button>
            ))}
          <button className="tiny ghost" disabled={!marks.length} title={t('ink.undo_tip')}
            onClick={() => put(marks.slice(0, -1))}>{t('ink.undo')}</button>
          <button className="tiny ghost" disabled={!marks.length} title={t('ink.clear_tip')}
            onClick={() => put([])}>{t('ink.clear')}</button>
        </div>
      )}
    </div>
  )
}

/** Статист на доску: npc-эпизодник — имя из генератора (списки корника плюс
    расширение) и одна строка о том, кто это. В базу кампании такая карточка не
    идёт: живёт ровно столько, сколько квест. */
function NameRoll({ onClose, onDone }: {
  onClose: () => void; onDone: (title: string, body: string) => void
}) {
  const { t } = useTranslation('boards')
  const [shape, setShape] = useState('mix')
  const [pool, setPool] = useState('setting')
  const [region, setRegion] = useState('any')
  const [gender, setGender] = useState('any')
  const [regions, setRegions] = useState<[string, string][]>([])
  const [rolls, setRolls] = useState<Dict[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [name, setName] = useState('')
  const [body, setBody] = useState('')

  const spin = async (s = shape, p = pool, reg = region, g = gender) => {
    setBusy(true)
    try {
      const r = await api.get(
        `${c()}/name-roll?n=9&shape=${s}&pool=${p}&region=${reg}&gender=${g}`)
      setRolls(Array.isArray(r?.names) ? r.names : [])
      if (Array.isArray(r?.regions)) setRegions(r.regions)
      setErr('')
    } catch (e: any) { setErr(e.message || t('roll.err')) } finally { setBusy(false) }
  }

  useEffect(() => { spin() }, [])

  return (
    <Modal title={t('roll.title')} onClose={onClose}>
      <div className="field">
        <label>{t('roll.pool')}</label>
        <div className="row wrap">
          {NAME_POOLS.map(([k, lb]) => (
            <button key={k} className={`tiny ghost${pool === k ? ' on' : ''}`}
              onClick={() => {
                /* ксенос живёт только в сеттинге: в мировой базе такой огранки нет */
                const sh = k === 'world' && shape === 'xeno' ? 'mix' : shape
                setPool(k); setShape(sh); spin(sh, k)
              }}>{t(lb)}</button>
          ))}
        </div>
      </div>

      {pool === 'world' && (
        <div className="field">
          <label>{t('roll.country')}</label>
          <div className="row wrap">
            <button className={`tiny ghost${region === 'any' ? ' on' : ''}`}
              onClick={() => { setRegion('any'); spin(shape, pool, 'any') }}>{t('roll.any_country')}</button>
            {regions.map(([k, lb]) => (
              <button key={k} className={`tiny ghost${region === k ? ' on' : ''}`}
                onClick={() => { setRegion(k); spin(shape, pool, k) }}>{lb}</button>
            ))}
          </div>
        </div>
      )}

      <div className="field">
        <label>{t('roll.gender')}</label>
        <div className="row wrap">
          {NAME_GENDERS.map(([k, lb]) => (
            <button key={k} className={`tiny ghost${gender === k ? ' on' : ''}`}
              onClick={() => { setGender(k); spin(shape, pool, region, k) }}>{t(lb)}</button>
          ))}
        </div>
      </div>

      <div className="field">
        <label>{t('roll.shape')}</label>
        <div className="row wrap">
          {NAME_SHAPES.filter(([k]) => k !== 'xeno' || pool !== 'world').map(([k, lb]) => (
            <button key={k} className={`tiny ghost${shape === k ? ' on' : ''}`}
              onClick={() => { setShape(k); spin(k) }}>{t(lb)}</button>
          ))}
        </div>
      </div>

      {err && <div className="bd-oops">{err}</div>}

      <div className="field">
        <label>{t('roll.pick')}</label>
        <div className="bd-roll">
          {rolls.map((r, i) => (
            <button key={`${r.name}:${i}`} className={`bd-roll-i${name === r.name ? ' on' : ''}`}
              onClick={() => setName(r.name)}>{r.name}</button>
          ))}
        </div>
        <button className="ghost" disabled={busy} onClick={() => spin()}>
          {busy ? t('roll.busy') : t('roll.more')}
        </button>
      </div>

      <Input label={t('roll.name')} value={name} onChange={setName} />
      <div className="field">
        <label>{t('roll.who')}</label>
        <textarea rows={2} value={body} placeholder={t('roll.who_ph')}
          onChange={e => setBody(e.target.value)} />
      </div>
      <button className="primary" disabled={!name.trim()}
        onClick={() => onDone(name.trim(), body.trim())}>{t('place')}</button>
    </Modal>
  )
}

/** Выбор картинки: кнопка вместо голого file input — по нему тяжело попасть. */
function PickImage({ value, boardId, onPick }: {
  value: string; boardId: string; onPick: (url: string) => void
}) {
  const { t } = useTranslation('boards')
  const ref = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const upload = async (f?: File | null) => {
    if (!f) return
    setBusy(true)
    try {
      onPick(await uploadImage(f, boardId))
    } catch (e: any) { setErr(e.message || t('img.err')) } finally { setBusy(false) }
  }

  return (
    <div className="field">
      <label>{t('img.label')}</label>
      <div className="row wrap">
        <button className="ghost" disabled={busy} onClick={() => ref.current?.click()}>
          {busy ? t('img.busy') : value ? t('img.other') : t('img.choose')}
        </button>
        {value && <span className="dim2 small">{t('img.done')}</span>}
      </div>
      <input ref={ref} type="file" accept="image/*" style={{ display: 'none' }}
        onChange={e => { upload(e.target.files?.[0]); e.target.value = '' }} />
      {err && <div className="bd-oops">{err}</div>}
      {value && <img className="bd-prev" src={thumb(value, 240)} alt="" />}
    </div>
  )
}

/** Записки карточки: плюсик добавляет новую. В запись кампании уходят одним блоком. */
function NoteStack({ notes, onChange }: {
  notes: Dict[]; onChange: (fn: (n: Dict[]) => Dict[], quiet?: boolean) => void
}) {
  const { t } = useTranslation('boards')
  const stop = (e: React.SyntheticEvent) => e.stopPropagation()
  const put = (id: string, patch: Dict) =>
    onChange(cur => cur.map(n => (n.id === id ? { ...n, ...patch } : n)), true)
  const add = () => onChange(cur => [...cur, { id: `${Date.now()}`, text: '' }])
  const drop = (id: string) => onChange(cur => cur.filter(n => n.id !== id))

  return (
    <div className="bd-notes" onPointerDown={stop} onClick={stop}>
      {notes.map(n => (
        <div className="bd-note" key={n.id}>
          <div className="bd-note-hd">
            <button className="bd-x" title={t('note.drop')} onClick={() => drop(n.id)}>×</button>
          </div>
          <CardText value={n.text || ''} placeholder={t('note.ph')}
            onSave={v => put(n.id, { text: v })} />
        </div>
      ))}
      <button type="button" className="bd-add" title={t('note.add_tip')} onClick={add}>
        {t('note.add')}
      </button>
    </div>
  )
}

/* Выделение в тексте доски: **жирный**, *курсив*, __подчёркнутый__. Хранится
   разметкой в той же строке — дамп для агента и записи кампании остаются текстом. */
const MARKS: [string, string, string][] = [
  ['bold', 'marks.bold', 'marks.bold_tip'], ['italic', 'marks.italic', 'marks.italic_tip'],
  ['underline', 'marks.underline', 'marks.underline_tip'],
]

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

function markHtml(src: string): string {
  const html = esc(src)
    .replace(/\*\*(?!\s)(.+?)(?<!\s)\*\*(?!\*)/g, '<b>$1</b>')
    .replace(/__(?!\s)(.+?)(?<!\s)__(?!_)/g, '<u>$1</u>')
    .replace(/(^|[^*])\*(?![\s*])([^*\n]*?[^\s*]|[^\s*])\*(?!\*)/gm, '$1<i>$2</i>')
    .replace(/\n/g, '<br>')
  // хвостовой перенос в редактируемом поле виден только со вторым <br>
  return src.endsWith('\n') ? `${html}<br>` : html
}

function markText(root: HTMLElement): string {
  const wrap = (s: string, m: string) => s.split('\n').map(line => {
    const [, a, core, z] = line.match(/^(\s*)([\s\S]*?)(\s*)$/) as string[]
    return core ? a + m + core + m + z : line
  }).join('\n')
  const walk = (n: Node): string => {
    if (n.nodeType === Node.TEXT_NODE) return (n.nodeValue || '').replace(/ /g, ' ')
    if (n.nodeType !== Node.ELEMENT_NODE) return ''
    const el = n as HTMLElement
    if (el.tagName === 'BR') return '\n'
    let out = Array.from(el.childNodes).map(walk).join('')
    const st = el.style
    if (el.tagName === 'U' || st.textDecorationLine.includes('underline')) out = wrap(out, '__')
    if (el.tagName === 'I' || el.tagName === 'EM' || st.fontStyle === 'italic') out = wrap(out, '*')
    if (el.tagName === 'B' || el.tagName === 'STRONG' || st.fontWeight === 'bold'
      || Number(st.fontWeight) >= 600) out = wrap(out, '**')
    if ((el.tagName === 'DIV' || el.tagName === 'P') && el.previousSibling) out = `\n${out}`
    return out
  }
  let out = Array.from(root.childNodes).map(walk).join('')
    .replace(/\*\*\*\*/g, '').replace(/____/g, '')
  if (root.lastChild?.nodeName === 'BR') out = out.replace(/\n$/, '')
  return out
}

/** Текст с разметкой — только для чтения (состав доски). */
function Marked({ text, className }: { text: string; className?: string }) {
  return <span className={className} dangerouslySetInnerHTML={{ __html: markHtml(text) }} />
}

/** Выделение в поле под кареткой; без выделения — во всём поле. */
function applyMark(el: HTMLElement, cmd: string, range?: Range | null) {
  el.focus()
  const s = window.getSelection()
  if (!s) return
  if (range) { s.removeAllRanges(); s.addRange(range) }
  if (s.isCollapsed || !s.rangeCount || !el.contains(s.getRangeAt(0).commonAncestorContainer)) {
    s.selectAllChildren(el)
  }
  document.execCommand(cmd)
}

const MARK_KEYS: Record<string, string> = { KeyB: 'bold', KeyI: 'italic', KeyU: 'underline' }

/** Текст карточки правится прямо на доске; правка уезжает сама, с паузой. */
function CardText({ value, onSave, placeholder, single, fontSize }: {
  value: string; onSave: (v: string) => void; placeholder?: string; single?: boolean
  fontSize?: number
}) {
  const area = useRef<HTMLDivElement>(null)
  const [text, setText] = useState(value || '')
  const dirty = useRef(false)
  /* правку уносим по её концу, а не по ходу набора: свежий текст и свежий
     обработчик держим в ref — иначе уход с поля сохранит то, что было в первом рендере */
  const last = useRef(text)
  const save = useRef(onSave)
  last.current = text
  save.current = onSave

  const flush = () => {
    if (!dirty.current) return
    dirty.current = false
    save.current(last.current)
  }

  useEffect(() => {
    if (dirty.current) return
    setText(value || '')
    const el = area.current
    if (el && markText(el) !== (value || '')) el.innerHTML = markHtml(value || '')
  }, [value])
  /* страховка: правку бросили, не уходя из поля (ушли во вкладку, закрыли ноут) */
  useEffect(() => {
    if (!dirty.current || text === (value || '')) return
    const t = setTimeout(flush, IDLE_SAVE)
    return () => clearTimeout(t)
  }, [text])
  // карточка ушла с доски или доску сменили — недописанное не теряем
  useEffect(() => flush, [])

  const set = (v: string) => { dirty.current = true; setText(v) }
  const stop = (ev: React.SyntheticEvent) => ev.stopPropagation()

  const input = () => {
    const el = area.current
    if (!el) return
    const v = markText(el)
    // стёртое поле браузер оставляет с <br> — без очистки не покажется подсказка
    if (!v) el.innerHTML = ''
    set(v)
  }
  const key = (ev: React.KeyboardEvent<HTMLDivElement>) => {
    const cmd = (ev.ctrlKey || ev.metaKey) && !ev.altKey && MARK_KEYS[ev.code]
    if (cmd) {
      ev.preventDefault()
      document.execCommand(cmd)
    } else if (ev.key === 'Enter') {
      // перенос строки, а не новый <div>: иначе разметка расползается по блокам
      ev.preventDefault()
      document.execCommand('insertLineBreak')
    }
  }
  const paste = (ev: React.ClipboardEvent<HTMLDivElement>) => {
    ev.preventDefault()
    document.execCommand('insertText', false, ev.clipboardData.getData('text/plain'))
  }

  const style = fontSize ? { fontSize, lineHeight: 1.3 } : undefined
  return single
    ? <input className="bd-in" value={text} placeholder={placeholder} style={style}
        onPointerDown={stop} onClick={stop} onChange={ev => set(ev.target.value)}
        onBlur={flush} />
    : <div ref={area} className="bd-in bd-area bd-rich" contentEditable
        suppressContentEditableWarning data-ph={placeholder} style={style}
        onPointerDown={stop} onClick={stop} onInput={input} onKeyDown={key} onPaste={paste}
        onBlur={flush} />
}

/* --- счётчик на доске ------------------------------------------------------ */

/** Записи и счётчики одним списком: на доске это одинаковые карточки, и делить
    их выбор на две вкладки было лишним. */
function BoardPick({ onPick }: { onPick: (item: Dict) => void }) {
  const { t } = useTranslation('boards')
  return (
    <div className="col">
      <EntityPicker label={t('pick.label')} value={null} clocks="active" listed autoFocus
        placeholder={t('pick.ph')} onChange={h => { if (h) onPick(h) }} />
      <div className="small dim2">{t('pick.hint')}</div>
    </div>
  )
}

/** Правка счётчика с доски — той же формой, что в базе кампании. */
function ClockEdit({ card, onClose, onDone }: {
  card: Dict; onClose: () => void; onDone: () => void
}) {
  const cl = card.clock || {}
  const [form, setForm] = useState<Dict>({
    id: cl.id, name: cl.name || '', description: cl.description || '', outcome: cl.outcome || '',
    kind: cl.kind || '', color: cl.color || 'amber', segments: cl.segments || 6,
  })
  const [owner, setOwner] = useState<Dict | null>(
    cl.owner_id ? { id: cl.owner_id, name: cl.owner_name || '', kind: '' } : null)
  const kinds = useClockKinds(null)
  if (!cl.id) return null
  return (
    <ClockForm form={form} setForm={setForm} owner={owner} setOwner={setOwner} kinds={kinds}
      onClose={onClose} onDone={onDone} />
  )
}
