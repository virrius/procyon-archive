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

/* Story board: the GM's canvas. Entry cards (thumbnail, caption, key
   notes), free sticky notes and frame clues; threads between them, like on a detective's
   board. GM-only: never sent to the table, so cards have no visibility. */

type V = { k: number; tx: number; ty: number }

const MIN_K = 0.1
const MAX_K = 2.5
const STEP = 1.15
const CARD_W = { text: 230, entity: 520, image: 260, clock: 230, sketch: 420, name: 260 }
/* two name pools: frontier flavor or world classics by country */
const NAME_POOLS: [string, string][] = [
  ['setting', 'pool.setting'], ['world', 'pool.world'],
]
/* name gender: xenos don't care, they come up with any choice */
const NAME_GENDERS: [string, string][] = [
  ['any', 'gender.any'], ['m', 'gender.m'], ['f', 'gender.f'],
]
/* name form: how it's called out on the board — one word, with surname, with alias */
const NAME_SHAPES: [string, string][] = [
  ['mix', 'shape.mix'], ['mono', 'shape.mono'], ['full', 'shape.full'],
  ['alias', 'shape.alias'], ['aliasfull', 'shape.aliasfull'], ['xeno', 'shape.xeno'],
]
/* the sketch is the only card with its own height: it can't be derived from the content */
const SKETCH_H = 300
/* line width: from a hairline mark to a bold outline over a diagram */
const INK_W: [number, string][] = [[1.5, 'ink.thin'], [3, 'ink.medium'], [7, 'ink.thick']]
/* sketch palette = the shared palette plus black: a sketch needs it for shadow
   and fill, while clocks and map markers have no use for black */
const INK_COLORS = [...PALETTE, 'black']
/* "black" on a dark field is graphite: true black is simply invisible on it */
const INK_HEX: Dict = { ...PALETTE_HEX, black: '#3a332e' }
const inkHex = (color?: string) => INK_HEX[color || ''] || INK_HEX.amber
/* sketch label font size: a tag by an arrow, a node name, a diagram title */
const INK_SZ: [number, string][] = [[14, 'S'], [22, 'M'], [40, 'L']]
const INK_MODES: [string, string][] = [
  ['pen', 'ink.pen'], ['text', 'ink.text'], ['erase', 'ink.erase'],
]
/* what can be created right from the board. No ship or player character here: they belong
   on the crew sheet and arrive on the board ready-made */
const NEW_KINDS: [string, string][] = [
  ['npc', 'kind.npc'],
  ['item', 'kind.item'],
  ['faction', 'kind.faction'],
  ['location', 'kind.location'],
]
const KIND_TITLE: Dict = Object.fromEntries(NEW_KINDS)
/* story roster order: living people first, then powers, places, items and ships —
   the same order in which the board is retold out loud */
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
/* text field font size: from a margin note to a sign across the whole board. Big steps —
   small ones are indistinguishable on a zoomed-out canvas anyway */
const FONT_SIZES: [number, string][] = [
  [12, 'S'], [20, 'M'], [36, 'L'], [64, 'XL'], [110, 'XXL'], [180, '3XL'],
]
/* an edit goes out when it ends: leaving the field, deselecting the card, switching boards. The timer
   is only a safety net for an abandoned edit, so it's long */
const IDLE_SAVE = 4000
const lastKey = () => `pa_board_last:${store.campaign || ''}`

const hex = (color?: string) => PALETTE_HEX[color || ''] || PALETTE_HEX.amber

/** File into the campaign: returns a URL usable both for the card and for thumbnails. */
async function uploadImage(f: File, boardId: string): Promise<string> {
  const fd = new FormData()
  // a clipboard file comes without a name — storage needs an extension
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
  // the board lives in the URL: /gm/boards/<id>. A story link can be handed to a fellow GM
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

  // a URL without a board (or with an unknown one) snaps to the open board: Back in history doesn't bounce
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


/* --- in-app dialogs instead of system alert/confirm/prompt ------------------ */

/** Yes/no in our own dialog: the system confirm clashes with the look and blocks the page. */
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

/** Single-line input in our own dialog — instead of prompt. */
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

/* --- canvas of a single board --------------------------------------------- */

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
  // canvas or roster: the choice persists across boards — the GM's habit is the same
  const [tab, setTab] = useState(() => localStorage.getItem(tabKey()) || 'canvas')
  useEffect(() => { localStorage.setItem(tabKey(), tab) }, [tab])

  const viewRef = useRef<HTMLDivElement>(null)
  const skipClick = useRef(false)
  /* two-finger pinch: while it lasts, canvas and card dragging stay idle */
  const pinch = useRef<Dict | null>(null)
  const viewNow = useRef<V>(view)
  /* fresh cards for blind edits: two note fields are edited almost at once,
     and the second edit, built from props, would overwrite the first */
  const cardsRef = useRef<Dict[]>([])
  // last pointer point on the canvas: pasted clipboard content lands there
  const lastPt = useRef<Dict | null>(null)
  const fitted = useRef('')

  /* the previous board's cards must not linger on the new one: while loading or if
     the request failed, the canvas is empty rather than showing another board */
  const list = cardsErr || cardsLoading ? [] : cards || []
  const threads = cardsErr || cardsLoading ? [] : edges || []

  useEffect(() => { viewNow.current = view }, [view])
  useEffect(() => { cardsRef.current = cards || [] }, [cards])
  useEffect(() => { setDragPos(null) }, [cards])
  useEffect(() => {
    setLinkFrom(''); setGhost(null); setSelEdge(''); setSel([])
    fitted.current = ''   // enter a new board with the fitted view, not the previous one
  }, [board.id])

  /* the canvas takes the full height down to the bottom of the window: below it is only the hint line,
     and a fixed height left half the screen empty */
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

  /* event point in board coordinates */
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
  /* fit the whole board in the window: cards drift apart, no need to hunt for them by hand */
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
    // fit only by shrinking: otherwise fitting a single card blows it up to the whole canvas
    const k = Math.max(MIN_K, Math.min(1,
      (r.width - pad * 2) / (box.x2 - box.x1 || 1),
      (r.height - pad * 2) / (box.y2 - box.y1 || 1)))
    setView({
      k,
      tx: r.width / 2 - k * (box.x1 + box.x2) / 2,
      ty: r.height / 2 - k * (box.y1 + box.y2) / 2,
    })
  }

  /* a board opens fitted: cards drift far apart, and without this the GM
     starts every time from an empty corner of the canvas and hunts for them. Once per board —
     after that the view belongs to whoever moved it */
  useEffect(() => {
    // until this board's cards arrive, the previous board's set is in hand — can't fit by it
    const mine = !!cards && (!cards.length || cards[0].board_id === board.id)
    if (!mine || cardsLoading || fitted.current === board.id) return
    // card height is known only after measuring: before that the content frame
    // is computed from the placeholder and the view drifts off
    if (list.some(cd => !sizes[cd.id])) return
    if (!viewRef.current?.getBoundingClientRect().width) return
    fitted.current = board.id
    fitView()
  }, [board.id, cards, cardsLoading, list, sizes])

  /* two-finger zoom: on a tablet or phone this is the only way
     to zoom the board out — there is no wheel, and the zoom buttons step too finely */
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
      // the pinch point stays under the fingers: the midpoint also pans the canvas
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

  /* Del on selected cards. Input fields are left alone: Del there is a normal edit */
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

  /* Ctrl+V: a clipboard image lands on the canvas under the pointer. Input fields are
     left alone — pasting there is normal; dialogs over the board take the clipboard too */
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
      // the image is centered under the pointer, not placed by its corner
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

  /* card sizes are measured as rendered: height depends on the text, and threads attach to centers */
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

  /* both panning and card dragging listen on the window: the pointer leaves the element it
     started on, and pointer capture on a scaled layer behaves unevenly */
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
  /* Shift + box: everything it touches joins the selection — then the batch is dragged
     and removed as one. Ctrl/Meta adds to the current selection */
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
    /* grabbing a card also selects it: borderless cards are all text field,
       so there is no "empty spot" on the card to click */
    setSel(cur => (e.ctrlKey || e.metaKey || e.shiftKey
      ? (cur.includes(card.id) ? cur.filter(x => x !== card.id) : [...cur, card.id])
      : (cur.includes(card.id) ? cur : [card.id])))
    const [sx, sy] = at(e)
    /* dragging one of the selected cards moves the whole batch, otherwise only this card */
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

  /* a click draws a thread if one is started, otherwise selects; Ctrl/Shift builds a batch */
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

  /* where a new card goes: the menu point, otherwise the center of the visible canvas */
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

  /* where bold/italic from the menu apply: the field with a selection inside the card, or for a
     text field, its whole text */
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

  /* Text and notes are edited by the GM, who sees the result in the field: no need to re-read
     the board after them — keep a fresh snapshot in cardsRef and do with one request.
     Everything else (color, font size, clock tick) changes the card's look — re-read there. */
  const saveCard = async (card: Dict, patch: Dict, refresh = true) => {
    if (!refresh) {
      cardsRef.current = cardsRef.current.map(
        x => (x.id === card.id ? { ...x, ...patch } : x))
    }
    try { await api.patch(`${c()}/board-cards/${card.id}`, patch) }
    catch (e: any) { setOops(e.message || t('err.edit')); return }
    if (refresh) reloadCards()
  }


  /* notes are edited from the last known state, not from the props snapshot */
  const saveNotes = (card: Dict, fn: (notes: Dict[]) => Dict[], refresh = false) => {
    const cur = cardsRef.current.find(x => x.id === card.id)?.notes || []
    return saveCard(card, { notes: fn(cur) }, refresh)
  }

  /* always ask before removing: a batch is easy to wipe by accident. Entries, clocks
     and files stay in the campaign — only their spot on the board and their threads go */
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

  /* a clock on the board is the same campaign clock: edits go to /clocks;
     while a tick is in flight, a repeat click on the same clock isn't sent */
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

  /* hovering a thread keeps the whole tangle it reaches on the board:
     a link reads together with its chain, not as two cards from the middle */
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
              /* the string sags under its own weight: the longer it is, the deeper the arc */
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
              // several cards selected — news about all entries and clocks in the selection
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

/* --- story roster --------------------------------------------------------- */

/** Board roster: the same cards, but sorted like a card index — characters first, then
    factions, locations, clocks. The canvas answers "who is connected to whom", the roster
    "who is in this story at all", and it is read without moving a single card. */
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
      /* extras come right after characters, but on their own shelf: they are not reused
         and mustn't be confused with campaign entries */
      const names = cards.filter(cd => cd.kind === 'name')
      if (names.length) out.push({ key: 'name', label: 'roster.extras', items: names })
    }
    // the entry was deleted from the campaign but the card stayed — it mustn't get lost on the board
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

/** Roster tile: an entry as a snapshot with a caption, a clock as a dial, a note as
    its text or frame. Board notes go as chips: they were created for the story. */
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

/** Card notes in the roster are read-only: they are edited on the canvas, where the context is visible. */
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

/* --- context menu ---------------------------------------------------------- */

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

/* --- card ----------------------------------------------------------------- */

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
  /* quiet — the edit doesn't change the card's look (text, note): don't re-read the board */
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
  /* the header only marks the card kind: the entry name is shown large in the body */
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
        /* text and image sit on the board as is: dragged by themselves, removed via the right-click menu */
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
          {/* photo and description come from the entry itself: the board only shows them,
              editing happens in the full card window (click it) */}
          <button type="button" className="bd-ent" title={t('open_entry')}
            onClick={ev => { ev.stopPropagation(); onOpenEntity() }}>
            {e?.image_url
              ? <img className="bd-thumb" src={thumb(e.image_url, 240)} alt="" />
              : <Stub kind={e?.kind || 'npc'} className="bd-thumb" />}
            <span className="bd-ent-main">
              {e ? <>
                <span className="bd-ent-name">
                  {e.name}
                  {/* the number goes inline, not in its own column: the column took
                      width from the name and broke long names letter by letter */}
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
          {/* an extra is a name and one line about them: that is all they need, and if
              more is needed, a real entry is created from them */}
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

      {/* width is dragged by the vertical edges — right or left; the left one also
          shifts the card so the opposite edge stays put */}
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

      {/* a sketch has its own height: drag the bottom edge, like the side edges for width,
          and the corner for both at once */}
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

/** Drawing pad: the GM sketches freehand over the board — a heist plan, a deck
    layout, arrows on a map — and labels what is drawn. Everything lives in card
    coordinates, so it moves with the card on drag and zoom. Edits go out at the
    end of a stroke or label: no requests while a line is being drawn. */
/* A frame on the canvas picks a thumbnail by how many screen pixels it covers:
   card width × zoom × device pixel ratio. The step only grows — zoom the board out
   and the sharpness stays; the next one is preloaded and swaps in without flicker */
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
  /* a label is edited over the pad with a plain input: at is its index in the list, -1 for a new one */
  const [edit, setEdit] = useState<Dict | null>(null)
  const box = useRef<SVGSVGElement>(null)
  const dirty = useRef(false)

  /* accept outside edits until we have our own: the sketch is edited by the same GM
     who looks at it, so no need to re-read the board after every stroke */
  useEffect(() => { if (!dirty.current) setMarks(ink) }, [ink])
  // the card was deselected — the tools are gone, and with them the mode and any unfinished label
  useEffect(() => { if (!tools) { setMode('pen'); setEdit(null) } }, [tools])

  const put = (next: Dict[]) => {
    dirty.current = true
    setMarks(next)
    onSave(next)
  }

  /* point in card coordinates: the frame on the canvas is already scaled by zoom */
  const at = (e: PointerEvent | React.PointerEvent): number[] => {
    const r = box.current?.getBoundingClientRect()
    if (!r) return [0, 0]
    const s = k || 1
    return [
      Math.round(((e.clientX - r.left) / s) * 10) / 10,
      Math.round(((e.clientY - r.top) / s) * 10) / 10,
    ]
  }

  /* the eraser removes a whole stroke or label: half-lines read worse on the board
     than a line drawn again */
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

  /* a label is dragged by itself: a short move edits the text, a long one moves it */
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
    /* without this the browser moves focus to the pad itself on press — the label input
       that just appeared immediately loses it and closes empty */
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
      // points closer than 1.5 units apart don't change the line but bloat the JSON
      if (Math.hypot(x - pts[n - 2], y - pts[n - 1]) < 1.5) return
      pts.push(x, y)
      setLive([...pts])
    }
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      setLive(null)
      // a tap without movement is a dot: a short line into itself
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

/** Extra onto the board: a one-scene NPC — a name from the generator (rulebook lists plus
    an extension) and one line about who they are. Such a card doesn't go into the campaign
    database: it lives exactly as long as the story. */
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
                /* xeno exists only in the setting pool: the world pool has no such name form */
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

/** Image picker: a button instead of a bare file input, which is hard to hit. */
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

/** Card notes: the plus adds a new one. They go into the campaign entry as one block. */
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

/* Formatting in board text: **bold**, *italic*, __underline__. Stored
   as markup in the same string — the agent dump and campaign entries stay plain text. */
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
  // a trailing line break in an editable field only shows with a second <br>
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

/** Formatted text, read-only (board roster). */
function Marked({ text, className }: { text: string; className?: string }) {
  return <span className={className} dangerouslySetInnerHTML={{ __html: markHtml(text) }} />
}

/** Selection in the field under the caret; without a selection, the whole field. */
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

/** Card text is edited right on the board; the edit goes out on its own, after a pause. */
function CardText({ value, onSave, placeholder, single, fontSize }: {
  value: string; onSave: (v: string) => void; placeholder?: string; single?: boolean
  fontSize?: number
}) {
  const area = useRef<HTMLDivElement>(null)
  const [text, setText] = useState(value || '')
  const dirty = useRef(false)
  /* the edit is sent when it ends, not while typing: the fresh text and fresh
     handler are kept in a ref — otherwise leaving the field would save what was in the first render */
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
  /* safety net: the edit was abandoned without leaving the field (switched tabs, closed the laptop) */
  useEffect(() => {
    if (!dirty.current || text === (value || '')) return
    const t = setTimeout(flush, IDLE_SAVE)
    return () => clearTimeout(t)
  }, [text])
  // the card left the board or the board changed — don't lose the unfinished text
  useEffect(() => flush, [])

  const set = (v: string) => { dirty.current = true; setText(v) }
  const stop = (ev: React.SyntheticEvent) => ev.stopPropagation()

  const input = () => {
    const el = area.current
    if (!el) return
    const v = markText(el)
    // the browser leaves a cleared field with a <br> — without clearing it, the placeholder won't show
    if (!v) el.innerHTML = ''
    set(v)
  }
  const key = (ev: React.KeyboardEvent<HTMLDivElement>) => {
    const cmd = (ev.ctrlKey || ev.metaKey) && !ev.altKey && MARK_KEYS[ev.code]
    if (cmd) {
      ev.preventDefault()
      document.execCommand(cmd)
    } else if (ev.key === 'Enter') {
      // a line break, not a new <div>: otherwise the markup spreads across blocks
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

/* --- clock on the board ---------------------------------------------------- */

/** Entries and clocks in one list: on the board they are the same kind of card, and
    splitting their picker into two tabs was unnecessary. */
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

/** Clock editing from the board — the same form as in the campaign database. */
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
