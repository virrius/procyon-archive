import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'
import { api, c, isPublicView, store, thumb, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import EntityPicker from '../components/EntityPicker'
import { Glyph, ICON_NAME, iconOf, MARKER_ICONS } from '../components/MapPin'
import Stub from '../components/Stub'
import RecordsPanel from '../components/RecordsPanel'
import VisibilityMenu from '../components/VisibilityMenu'
import {
  Chip, ColorPicker, Input, Modal, PALETTE, PALETTE_HEX, PALETTE_NAME,
  Select, statusTone, VisibilityPicker,
} from '../ui'
import '../styles.map.css'

type V = { k: number; tx: number; ty: number }

/* цвет отметки хранится в MapMarker.size как индекс палитры */
const COLORS = PALETTE
const HEX = PALETTE_HEX
const CNAME = PALETTE_NAME
const WIDTHS = [2, 4, 8]
const MAX_K = 8
const STEP = 1.15
const MAX_PTS = 500
const LABELS_KEY = 'pa_map_labels'
const lastKey = () => `pa_map_last:${store.campaign || ''}`

const colorIdx = (v: any) => {
  const i = Math.round(Number(v) || 0)
  return i >= 0 && i < COLORS.length ? i : 0
}
const colorOf = (m: Dict) => COLORS[colorIdx(m.size)]

function thin(pts: number[][]) {
  if (pts.length <= MAX_PTS) return pts
  const step = (pts.length - 1) / (MAX_PTS - 1)
  const out: number[][] = []
  for (let i = 0; i < MAX_PTS; i++) out.push(pts[Math.round(i * step)])
  return out
}

export default function MapPage() {
  const { isGM, campaign, memberName, L } = useApp()
  const { t } = useTranslation('map')
  const readonly = isPublicView()  // витрина для стола — только чтение
  const myId: string = campaign?.my_member_id || ''
  const nav = useNavigate()
  const loc = useLocation()

  /* активная карта — в пути (/map/:mapId), выбранная отметка — в ?m */
  const urlMapId = useMemo(() => {
    const m = /^\/map\/([^/?#]+)/.exec(loc.pathname)
    if (!m) return ''
    try { return decodeURIComponent(m[1]) } catch { return m[1] }
  }, [loc.pathname])
  const selId = useMemo(() => new URLSearchParams(loc.search).get('m') || '', [loc.search])

  const [maps, mapsLoading, reloadMaps] = useAsync<Dict[]>(() => api.get(`${c()}/maps`), [])
  /* без карты в пути открываем последнюю посещённую */
  const current = useMemo(() => {
    const list = maps || []
    if (urlMapId) return list.find(m => m.id === urlMapId) || list[0] || null
    const last = localStorage.getItem(lastKey())
    return (last && list.find(m => m.id === last)) || list[0] || null
  }, [maps, urlMapId])

  const [markers, markersLoading, reloadMarkers] = useAsync<Dict[]>(
    () => current ? api.get(`${c()}/maps/${current.id}/markers`) : Promise.resolve([]),
    [current?.id])
  const [strokes, , reloadStrokes] = useAsync<Dict[]>(
    () => current ? api.get(`${c()}/maps/${current.id}/strokes`) : Promise.resolve([]),
    [current?.id])

  const [tool, setTool] = useState('pan')
  const [color, setColor] = useState('amber')
  const [width, setWidth] = useState(4)
  const [labels, setLabels] = useState(() => localStorage.getItem(LABELS_KEY) !== '0')
  const [view, setView] = useState<V>({ k: 1, tx: 0, ty: 0 })
  const [box, setBox] = useState({ w: 1000, h: 562 })
  const [ar, setAr] = useState(16 / 9)
  const [draft, setDraft] = useState<number[][] | null>(null)
  const [placing, setPlacing] = useState<Dict | null>(null)
  const [dragPos, setDragPos] = useState<Dict | null>(null)
  const [newMap, setNewMap] = useState<Dict | null>(null)

  /* отмена действий: стек обратных операций, живёт в рамках открытой карты */
  const undoRef = useRef<{ label: string; run: () => Promise<void> }[]>([])
  const [undoTop, setUndoTop] = useState('')
  const pushUndo = (label: string, run: () => Promise<void>) => {
    undoRef.current = [...undoRef.current.slice(-19), { label, run }]
    setUndoTop(label)
  }
  const undo = async () => {
    const a = undoRef.current.pop()
    setUndoTop(undoRef.current[undoRef.current.length - 1]?.label || '')
    if (!a) return
    try { await a.run() }
    catch (e: any) { alert(e.message || t('err.undo')) }
  }

  const viewRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const ptsRef = useRef<number[][] | null>(null)
  const panRef = useRef<{ x: number; y: number } | null>(null)
  const ptrs = useRef(new Map<number, { x: number; y: number }>())
  const pinchRef = useRef<{ d: number; cx: number; cy: number } | null>(null)
  const spaceRef = useRef(false)
  const dragRef = useRef<{ id: string; sx: number; sy: number; moved: boolean } | null>(null)
  const skipClick = useRef(false)
  const wantMap = useRef('') /* только что созданная карта — ждём её в списке */

  const mode = readonly ? 'pan' : tool
  /* право правки отметки считает сервер; локальная проверка — тот же порядок */
  const canEdit = (m: Dict) =>
    m.can_edit ?? (isGM || (!!m.created_by && m.created_by === myId))
  const mapKey = current?.id || ''

  const pathOf = (mapId: string) => mapId ? `/map/${encodeURIComponent(mapId)}` : '/map'
  const go = (mapId: string, marker = '', replace = false) =>
    nav(`${pathOf(mapId)}${marker ? `?m=${encodeURIComponent(marker)}` : ''}`, { replace })
  const select = (id: string) => { if (current && id !== selId) go(current.id, id) }
  const clearSel = (replace = false) => { if (current && selId) go(current.id, '', replace) }

  const clampV = (v: V, w: number, h: number): V => {
    const k = Math.min(MAX_K, Math.max(1, v.k))
    return {
      k,
      tx: Math.min(0, Math.max(w * (1 - k), v.tx)),
      ty: Math.min(0, Math.max(h * (1 - k), v.ty)),
    }
  }
  const zoomAt = (cx: number, cy: number, f: number) => setView(v => {
    const el = viewRef.current
    if (!el) return v
    const r = el.getBoundingClientRect()
    const k = Math.min(MAX_K, Math.max(1, v.k * f))
    const s = k / v.k
    return clampV({ k, tx: cx - (cx - v.tx) * s, ty: cy - (cy - v.ty) * s }, r.width, r.height)
  })
  const panBy = (dx: number, dy: number) => setView(v => {
    const el = viewRef.current
    if (!el) return v
    const r = el.getBoundingClientRect()
    return clampV({ ...v, tx: v.tx + dx, ty: v.ty + dy }, r.width, r.height)
  })
  const zoomCenter = (f: number) => {
    const r = viewRef.current?.getBoundingClientRect()
    if (r) zoomAt(r.width / 2, r.height / 2, f)
  }
  /* подвести отметку в центр холста */
  const focusMarker = (m: Dict) => {
    const el = viewRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    setView(v => {
      const k = v.k > 1.05 ? v.k : 2
      return clampV({
        k,
        tx: r.width / 2 - k * m.x * r.width,
        ty: r.height / 2 - k * m.y * r.height,
      }, r.width, r.height)
    })
  }

  /* путь всегда указывает на реально открытую карту */
  useEffect(() => {
    if (!maps) return
    if (wantMap.current) {
      if (wantMap.current === urlMapId && !maps.some(m => m.id === wantMap.current)) return
      wantMap.current = ''
    }
    if (current && loc.pathname !== pathOf(current.id)) go(current.id, selId, true)
  }, [maps, loc.pathname, current?.id, selId])

  /* ?m на исчезнувшую отметку не держим */
  useEffect(() => {
    if (!current || markersLoading || !selId) return
    if (!(markers || []).some(m => m.id === selId)) go(current.id, '', true)
  }, [selId, markers, markersLoading, current?.id])

  useEffect(() => { if (mapKey) localStorage.setItem(lastKey(), mapKey) }, [mapKey])
  useEffect(() => { undoRef.current = []; setUndoTop('') }, [mapKey])
  useEffect(() => { setView({ k: 1, tx: 0, ty: 0 }) }, [mapKey])
  useEffect(() => { setDragPos(null) }, [markers])
  useEffect(() => { setAr(16 / 9) }, [current?.image_url])
  useEffect(() => { localStorage.setItem(LABELS_KEY, labels ? '1' : '0') }, [labels])

  useEffect(() => {
    const el = viewRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const r = el.getBoundingClientRect()
      const cx = e.clientX - r.left, cy = e.clientY - r.top
      if (e.ctrlKey) zoomAt(cx, cy, Math.exp(-e.deltaY / 120))
      else if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) panBy(-e.deltaX, -e.deltaY)
      else zoomAt(cx, cy, e.deltaY < 0 ? STEP : 1 / STEP)
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [mapKey])

  useEffect(() => {
    const el = viewRef.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect()
      if (!r.width) return
      setBox({ w: Math.round(r.width), h: Math.round(r.height) })
      setView(v => clampV(v, r.width, r.height))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [mapKey])

  /* code, а не key: на кириллической раскладке Ctrl+Z даёт «я» */
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.code !== 'KeyZ' || !(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey) return
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      if (readonly) return
      e.preventDefault()
      undo()
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [readonly])

  useEffect(() => {
    const down = (e: KeyboardEvent) => { if (e.code === 'Space') spaceRef.current = true }
    const up = (e: KeyboardEvent) => { if (e.code === 'Space') spaceRef.current = false }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up) }
  }, [])

  /* точка события в нормализованных координатах изображения */
  const norm = (e: { clientX: number; clientY: number }): number[] => {
    const el = viewRef.current
    if (!el) return [0.5, 0.5]
    const r = el.getBoundingClientRect()
    const x = (e.clientX - r.left - view.tx) / (r.width * view.k)
    const y = (e.clientY - r.top - view.ty) / (r.height * view.k)
    return [
      +Math.min(1, Math.max(0, x)).toFixed(4),
      +Math.min(1, Math.max(0, y)).toFixed(4),
    ]
  }

  const finishStroke = async () => {
    const p = ptsRef.current
    ptsRef.current = null
    setDraft(null)
    if (!p || p.length < 2 || !current) return
    try {
      const r = await api.post(`${c()}/strokes`, {
        map_id: current.id, points: thin(p), color, width,
        visibility: 'crew', visible_to: [],
      })
      pushUndo('undo_action.stroke', async () => {
        await api.del(`${c()}/strokes/${r.id}`)
        reloadStrokes()
      })
    } catch (e: any) { alert(e.message || t('err.stroke_save')) }
    reloadStrokes()
  }

  const stageDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button === 2) return
    const el = viewRef.current
    if (!el) return
    skipClick.current = false
    ptrs.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (ptrs.current.size === 2) {
      panRef.current = null
      ptsRef.current = null
      setDraft(null)
      const [a, b] = Array.from(ptrs.current.values())
      pinchRef.current = {
        d: Math.hypot(a.x - b.x, a.y - b.y), cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2,
      }
      return
    }
    if (ptrs.current.size > 2) return
    if (mode === 'pan' || e.button === 1 || spaceRef.current) {
      panRef.current = { x: e.clientX, y: e.clientY }
      el.setPointerCapture(e.pointerId)
      return
    }
    if (mode === 'draw' && e.button === 0) {
      const p = norm(e)
      ptsRef.current = [p]
      setDraft([p])
      el.setPointerCapture(e.pointerId)
    }
  }

  const stageMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (ptrs.current.has(e.pointerId)) ptrs.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    const el = viewRef.current
    if (!el) return
    if (pinchRef.current && ptrs.current.size >= 2) {
      const [a, b] = Array.from(ptrs.current.values())
      const d = Math.hypot(a.x - b.x, a.y - b.y)
      const cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2
      const prev = pinchRef.current
      const r = el.getBoundingClientRect()
      panBy(cx - prev.cx, cy - prev.cy)
      if (prev.d > 4 && d > 4) zoomAt(cx - r.left, cy - r.top, d / prev.d)
      pinchRef.current = { d, cx, cy }
      skipClick.current = true
      return
    }
    if (panRef.current) {
      const dx = e.clientX - panRef.current.x, dy = e.clientY - panRef.current.y
      if (dx || dy) skipClick.current = true
      panBy(dx, dy)
      panRef.current = { x: e.clientX, y: e.clientY }
      return
    }
    const p0 = ptsRef.current
    if (p0) {
      const p = norm(e)
      const last = p0[p0.length - 1]
      if (Math.hypot(p[0] - last[0], p[1] - last[1]) <= 0.0035 / view.k) return
      const next = [...p0, p]
      ptsRef.current = next
      setDraft(next)
    }
  }

  const stageUp = (e: React.PointerEvent<HTMLDivElement>) => {
    ptrs.current.delete(e.pointerId)
    if (ptrs.current.size < 2) pinchRef.current = null
    panRef.current = null
    if (ptsRef.current) finishStroke()
    const el = viewRef.current
    if (el?.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId)
  }

  const stageClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (skipClick.current) { skipClick.current = false; return }
    if (mode === 'pan' && selId) { clearSel(); return }
    if (readonly || mode !== 'mark' || !current) return
    const [x, y] = norm(e)
    setPlacing({
      x, y, label: '', color, kind: 'custom', icon: 'dot', entity: null,
      visibility: 'crew', visible_to: [],
    })
  }

  const addMarker = async () => {
    if (!placing || !current) return
    const link = placing.kind === 'location' ? placing.entity : null
    try {
      const r = await api.post(`${c()}/markers`, {
        map_id: current.id, x: placing.x, y: placing.y,
        marker_type: placing.kind === 'location' ? 'location' : 'custom', icon: placing.icon,
        label: placing.label || (link ? link.name : ''),
        size: COLORS.indexOf(placing.color),
        linked_type: link ? 'entity' : null, linked_id: link ? link.id : null,
        visibility: placing.visibility, visible_to: placing.visible_to,
      })
      pushUndo('undo_action.marker', async () => {
        await api.del(`${c()}/markers/${r.id}`)
        reloadMarkers()
      })
    } catch (e: any) { alert(e.message || t('err.marker_save')) }
    setPlacing(null)
    reloadMarkers()
  }

  const pinDown = (e: React.PointerEvent<Element>, m: Dict) => {
    if (mode !== 'pan' && mode !== 'mark') return
    /* нажатие на метку не отдаём холсту: иначе панорама помечает клик «сдвигом»
       и выбор отметки не срабатывает — в общем виде это ломало открытие карточки */
    e.stopPropagation()
    if (e.button !== 0 || readonly || !canEdit(m)) return
    e.currentTarget.setPointerCapture(e.pointerId)
    dragRef.current = { id: m.id, sx: e.clientX, sy: e.clientY, moved: false }
  }
  const pinMove = (e: React.PointerEvent<Element>) => {
    const d = dragRef.current
    if (!d) return
    e.stopPropagation()
    if (!d.moved && Math.hypot(e.clientX - d.sx, e.clientY - d.sy) < 4) return
    d.moved = true
    const [x, y] = norm(e)
    setDragPos({ id: d.id, x, y })
  }
  const pinUp = async (e: React.PointerEvent<Element>, m: Dict) => {
    const d = dragRef.current
    if (!d) return
    e.stopPropagation()
    dragRef.current = null
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId)
    const pos = dragPos
    if (!d.moved || !pos || pos.id !== d.id) { setDragPos(null); return }
    skipClick.current = true
    const was = { x: m.x, y: m.y }
    try {
      await api.patch(`${c()}/markers/${m.id}`, { x: pos.x, y: pos.y })
      pushUndo('undo_action.move', async () => {
        await api.patch(`${c()}/markers/${m.id}`, was)
        reloadMarkers()
      })
    } catch (err: any) { alert(err.message || t('err.position')) }
    reloadMarkers()
  }

  const dropMarker = async (m: Dict) => {
    if (!confirm(t('drop_marker_confirm'))) return false
    try {
      await api.del(`${c()}/markers/${m.id}`)
      /* Ctrl+Z вернёт саму отметку, но не её записи — они удалены на сервере */
      pushUndo('undo_action.drop', async () => {
        await api.post(`${c()}/markers`, {
          map_id: current!.id, x: m.x, y: m.y, marker_type: m.marker_type || 'custom',
          icon: iconOf(m.icon),
          label: m.label || '', size: colorIdx(m.size),
          visibility: m.visibility || 'crew', visible_to: m.visible_to || [],
          linked_type: m.linked_type, linked_id: m.linked_id,
        })
        reloadMarkers()
      })
    } catch (err: any) { alert(err.message || t('err.delete')) }
    if (selId === m.id) clearSel(true)
    reloadMarkers()
    return true
  }

  const saveMarker = async (m: Dict, patch: Dict) => {
    const was: Dict = {}
    for (const k of Object.keys(patch)) {
      was[k] = k === 'size' ? colorIdx(m.size)
        : k === 'icon' ? iconOf(m.icon)
          : m[k] ?? ''
    }
    await api.patch(`${c()}/markers/${m.id}`, patch)
    pushUndo('undo_action.edit', async () => {
      await api.patch(`${c()}/markers/${m.id}`, was)
      reloadMarkers()
    })
    reloadMarkers()
  }

  const strokeBody = (s: Dict) => ({
    map_id: current?.id, points: s.points, color: s.color, width: s.width,
    visibility: s.visibility || 'crew', visible_to: [],
  })
  const eraseStroke = async (s: Dict) => {
    try {
      await api.del(`${c()}/strokes/${s.id}`)
      pushUndo('undo_action.erase', async () => {
        await api.post(`${c()}/strokes`, strokeBody(s))
        reloadStrokes()
      })
    } catch (e: any) { alert(e.message || t('err.stroke_delete')) }
    reloadStrokes()
  }
  const clearStrokes = async () => {
    if (!current || !confirm(t('clear_strokes_confirm'))) return
    const mine = (strokes || []).filter(s => s.created_by === myId)
    try {
      await api.del(`${c()}/maps/${current.id}/strokes`)
      if (mine.length) pushUndo('undo_action.clear', async () => {
        for (const s of mine) await api.post(`${c()}/strokes`, strokeBody(s))
        reloadStrokes()
      })
    } catch (e: any) { alert(e.message || t('err.erase')) }
    reloadStrokes()
  }

  const setBackground = async (url: string) => {
    if (!current) return
    try {
      await api.patch(`${c()}/maps/${current.id}`, {
        name: current.name, level: current.level, image_url: url,
      })
      reloadMaps()
    } catch (e: any) { alert(e.message || t('err.bg_save')) }
  }
  const uploadBackground = async (f?: File | null) => {
    if (!f) return
    const fd = new FormData()
    fd.append('file', f)
    try {
      const r = await api.post(`${c()}/upload`, fd)
      await setBackground(r.url)
    } catch (e: any) { alert(e.message || t('err.bg_upload')) }
  }

  const dropMap = async () => {
    if (!current) return
    const n = (markers || []).length
    const tail = n ? ` ${t('drop_map_tail', { n })}` : ''
    if (!confirm(`${t('drop_map_confirm', { name: current.name })}${tail}`)) return
    try { await api.del(`${c()}/maps/${current.id}`) }
    catch (e: any) { alert(e.message || t('err.map_delete')); return }
    if (localStorage.getItem(lastKey()) === current.id) localStorage.removeItem(lastKey())
    wantMap.current = ''
    nav('/map', { replace: true })
    reloadMaps()
  }

  const createdMap = (id: string) => {
    wantMap.current = id
    setNewMap(null)
    reloadMaps()
    go(id)
  }

  if (mapsLoading && !maps) return <div className="dim">{t('loading')}</div>
  if (!current) {
    return (
      <div className="col">
        <div className="empty">{t('no_maps')}</div>
        {isGM && !readonly && (
          <div className="row">
            <button className="primary" onClick={() => setNewMap({ name: '', level: 'sector', image_url: '' })}>
              {t('create_map')}
            </button>
          </div>
        )}
        {newMap && <NewMapModal form={newMap} setForm={setNewMap} onDone={createdMap} />}
      </div>
    )
  }

  const list = markers || []
  const sel = list.find(m => m.id === selId) || null
  const pick = (m: Dict) => { select(m.id); focusMarker(m) }
  const hint = readonly ? t('hint.readonly')
    : mode === 'mark' ? t('hint.mark')
      : mode === 'draw' ? t('hint.draw')
        : mode === 'erase' ? t('hint.erase')
          : t('hint.pan')

  return (
    <div className="col">
      <div className="row wrap">
        <h1>{current.name}</h1>
        <Chip tone="cyan">{L(current.level)}</Chip>
        <div className="spacer" />
        {(maps || []).length > 1 && (
          <div style={{ maxWidth: 240 }}>
            <Select value={current.id} empty={null} title={t('map')}
              options={(maps || []).map((m: Dict) => m.id)}
              optionLabel={id => {
                const m = (maps || []).find((x: Dict) => x.id === id)
                return m ? `${L(m.level)} · ${m.name}` : id
              }}
              onChange={go} />
          </div>
        )}
        {isGM && !readonly && <>
          <button className="ghost" onClick={() => setNewMap({ name: '', level: 'system', image_url: '' })}>
            {t('add_map')}
          </button>
          <button className="danger" onClick={dropMap}>{t('drop_map')}</button>
        </>}
      </div>

      <div className="mp-bar">
        {!readonly && <>
          <span className="lb">{t('mode_label')}</span>
          {([['pan', 'mode.pan'], ['mark', 'mode.mark'], ['draw', 'mode.draw'], ['erase', 'mode.erase']] as [string, string][])
            .map(([k, lb]) => (
              <button key={k} className={`tiny ${tool === k ? '' : 'ghost'}`}
                onClick={() => setTool(k)}>{t(lb)}</button>
            ))}
          <span className="mp-sep" />
          <span className="lb">{t('color')}</span>
          {COLORS.map(k => (
            <button key={k} className={`sw ${color === k ? 'on' : ''}`} title={CNAME[k]}
              onClick={() => setColor(k)}>
              <i style={{ background: HEX[k] }} />
            </button>
          ))}
          <span className="mp-sep" />
          <span className="lb">{t('width')}</span>
          {WIDTHS.map(w => (
            <button key={w} className={`tiny ${width === w ? '' : 'ghost'}`}
              onClick={() => setWidth(w)}>{w}</button>
          ))}
          <span className="mp-sep" />
        </>}
        <button className={`tiny ${labels ? '' : 'ghost'}`} onClick={() => setLabels(!labels)}>
          {t('labels')}: {labels ? t('on') : t('off')}
        </button>
        <span className="mp-sep" />
        <button className="tiny ghost" onClick={() => zoomCenter(1 / STEP)}>−</button>
        <span className="mp-zoom">{Math.round(view.k * 100)}%</span>
        <button className="tiny ghost" onClick={() => zoomCenter(STEP)}>+</button>
        <button className="tiny ghost" onClick={() => setView({ k: 1, tx: 0, ty: 0 })}>{t('reset')}</button>
        {!readonly && <>
          <span className="mp-sep" />
          <button className="tiny ghost" disabled={!undoTop} onClick={undo}
            title={undoTop ? t('undo_title', { action: t(undoTop) }) : t('undo_none')}>
            ↶ {t('undo')}
          </button>
        </>}
        {isGM && !readonly && <>
          <span className="mp-sep" />
          <button className="tiny ghost" onClick={() => fileRef.current?.click()}>{t('bg')}</button>
          {current.image_url && (
            <button className="tiny ghost" onClick={() => setBackground('')}>{t('bg_remove')}</button>
          )}
          <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }}
            onChange={e => { uploadBackground(e.target.files?.[0]); e.target.value = '' }} />
        </>}
      </div>

      <div className="mp-split">
        <div className="mp-main">
          <div ref={viewRef} className={`mp-view t-${mode}`}
            style={{ aspectRatio: String(ar), maxWidth: `calc(88vh * ${ar})` }}
            onPointerDown={stageDown} onPointerMove={stageMove} onPointerUp={stageUp}
            onPointerCancel={stageUp} onClick={stageClick}
            onContextMenu={e => e.preventDefault()}>
            {!current.image_url && (
              <div className="mp-blank">
                <div>{t('bg_none')}</div>
                {isGM && !readonly
                  ? <button className="ghost" onClick={ev => { ev.stopPropagation(); fileRef.current?.click() }}>
                    {t('bg_upload')}
                  </button>
                  : <div>{t('bg_none_player')}</div>}
              </div>
            )}
            <div className="mp-layer"
              style={{ transform: `translate(${view.tx}px, ${view.ty}px) scale(${view.k})` }}>
              {current.image_url && (
                <img src={current.image_url} alt="" draggable={false}
                  onLoad={e => {
                    const im = e.currentTarget
                    if (im.naturalWidth && im.naturalHeight) setAr(im.naturalWidth / im.naturalHeight)
                  }} />
              )}


            </div>

            <svg className="mp-ink" viewBox={`0 0 ${box.w} ${box.h}`} preserveAspectRatio="none">
              {(strokes || []).map(s => {
                const pts = (s.points || [])
                  .map((p: number[]) => `${(view.tx + p[0] * box.w * view.k).toFixed(1)},`
                    + `${(view.ty + p[1] * box.h * view.k).toFixed(1)}`)
                  .join(' ')
                const w = s.width || 3
                return (
                  <g key={s.id}>
                    <polyline points={pts} fill="none" stroke={HEX[s.color] || HEX.amber}
                      strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" />
                    {mode === 'erase' && (
                      <polyline points={pts} fill="none" stroke="transparent" strokeWidth={w + 14}
                        strokeLinecap="round" strokeLinejoin="round"
                        style={{ pointerEvents: 'stroke', cursor: 'cell' }}
                        onClick={ev => { ev.stopPropagation(); eraseStroke(s) }} />
                    )}
                  </g>
                )
              })}
              {draft && draft.length > 1 && (
                <polyline fill="none" stroke={HEX[color]} strokeWidth={width}
                  strokeLinecap="round" strokeLinejoin="round"
                  points={draft.map(p => `${(view.tx + p[0] * box.w * view.k).toFixed(1)},`
                    + `${(view.ty + p[1] * box.h * view.k).toFixed(1)}`).join(' ')} />
              )}
            </svg>

            <div className="mp-pins">
              {list.map(m => {
                const pos = dragPos && dragPos.id === m.id ? dragPos : m
                return (
                  <div key={m.id} className={`mp-pin ${selId === m.id ? 'on' : ''}`}
                    style={{
                      left: `${view.tx + pos.x * box.w * view.k}px`,
                      top: `${view.ty + pos.y * box.h * view.k}px`,
                    }}>
                    <Glyph className="mp-dot" icon={m.icon} color={colorOf(m)} hit
                      on={selId === m.id}
                      style={{
                        cursor: mode === 'draw' || mode === 'erase' ? 'inherit' : 'pointer',
                        pointerEvents: mode === 'draw' || mode === 'erase' ? 'none' : 'auto',
                      }}
                      onPointerDown={ev => pinDown(ev, m)}
                      onPointerMove={pinMove}
                      onPointerUp={ev => pinUp(ev, m)}
                      onClick={ev => {
                        ev.stopPropagation()
                        if (skipClick.current) { skipClick.current = false; return }
                        select(m.id)
                      }}>
                      <title>{m.label || ''}</title>
                    </Glyph>
                    {m.note_count > 0 && <span className="mp-cnt">{m.note_count}</span>}
                    {labels && m.label && <span className="mp-lab">{m.label}</span>}
                  </div>
                )
              })}
            </div>
          </div>

          <div className="row wrap">
            <span className="mp-hint">{hint}</span>
            <div className="spacer" />
            {!readonly && (
              <button className="tiny ghost" onClick={clearStrokes}>{t('clear_strokes')}</button>
            )}
          </div>
        </div>

        <aside className="mp-side">
          <div className="mp-side-hd">
            <span className="mp-side-t">{t('markers_title')}</span>
            <div className="spacer" />
            <span className="mono dim2">{list.length}</span>
          </div>
          <div className="mp-side-body">
            {!list.length && (
              <div className="empty">
                {t('no_markers')}{!readonly && ` ${t('no_markers_hint')}`}
              </div>
            )}
            <div className="mp-mlist">
              {list.map(m => (
                <div key={m.id} className="mp-mrow" role="button" tabIndex={0}
                  onClick={() => pick(m)}
                  onKeyDown={ev => {
                    if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); pick(m) }
                  }}>
                  <Glyph className="mp-mdot" icon={m.icon} color={colorOf(m)} size={16} />
                  <span className="mp-mname">
                    {m.label || m.linked?.name || <span className="dim2">{t('no_label')}</span>}
                  </span>
                  <span className="mp-mby mono dim2">{memberName(m.created_by)}</span>
                  {m.note_count > 0 && <span className="mp-mcnt">{m.note_count}</span>}
                  {!readonly && canEdit(m) && (
                    <button className="tiny danger"
                      onClick={ev => { ev.stopPropagation(); dropMarker(m) }}>×</button>
                  )}
                </div>
              ))}
            </div>
            {list.length > 0 && (
              <div className="mp-hint" style={{ marginTop: 10 }}>
                {t('list_hint')}
              </div>
            )}
          </div>
        </aside>
      </div>

      {sel && (
        <MarkerModal marker={sel} readonly={readonly || !canEdit(sel)}
          author={memberName(sel.created_by)}
          onClose={() => clearSel()} onFocus={() => focusMarker(sel)}
          onOpen={id => nav(`/entity/${id}`)}
          onSave={patch => saveMarker(sel, patch)}
          onDelete={() => dropMarker(sel)} />
      )}

      {placing && (
        <Modal title={t('new_marker')} onClose={() => setPlacing(null)} watch={placing}
          dirtyAsk={t('new_marker_dirty')}>
          <TypePick value={placing.kind}
            onChange={k => setPlacing({
              ...placing,
              kind: k,
              icon: placing.icon === 'dot' && k === 'location' ? 'target' : placing.icon,
              entity: k === 'location' ? placing.entity : null,
            })} />
          {placing.kind === 'location' && (
            <EntityPicker label={t('location_entry')} kind="location" value={placing.entity}
              placeholder={t('location_placeholder')}
              onChange={e => setPlacing({
                ...placing,
                entity: e,
                label: placing.label && placing.label !== placing.entity?.name
                  ? placing.label : (e?.name || ''),
              })} />
          )}
          <Input label={t('label')} value={placing.label}
            onChange={v => setPlacing({ ...placing, label: v })} />
          <IconPick value={placing.icon} color={placing.color}
            onChange={v => setPlacing({ ...placing, icon: v })} />
          <ColorPicker value={placing.color}
            onChange={v => setPlacing({ ...placing, color: v })} />
          <VisibilityPicker visibility={placing.visibility} visibleTo={placing.visible_to}
            onChange={(v, to) => setPlacing({ ...placing, visibility: v, visible_to: to })} />
          <div className="mono dim2 small">x={placing.x} · y={placing.y}</div>
          <button className="primary" style={{ marginTop: 10 }}
            disabled={placing.kind === 'location' && !placing.entity && !placing.label.trim()}
            onClick={addMarker}>{t('place')}</button>
        </Modal>
      )}

      {newMap && <NewMapModal form={newMap} setForm={setNewMap} onDone={createdMap} />}
    </div>
  )
}

function TypePick({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const { t } = useTranslation('map')
  return (
    <div className="field">
      <label>{t('marker_type')}</label>
      <div className="row wrap">
        {([['custom', 'type.custom'], ['location', 'type.location']] as [string, string][]).map(([k, lb]) => (
          <button key={k} className={`tiny ${value === k ? '' : 'ghost'}`}
            onClick={() => onChange(k)}>{t(lb)}</button>
        ))}
      </div>
    </div>
  )
}

function IconPick({ value, color, onChange }: {
  value: string; color: string; onChange: (v: string) => void
}) {
  const { t } = useTranslation('map')
  return (
    <div className="field">
      <label>{t('icon_label')}</label>
      <div className="row wrap">
        {MARKER_ICONS.map(k => (
          <button key={k} className={`mp-icon ${iconOf(value) === k ? 'on' : ''}`}
            title={t(ICON_NAME[k])} onClick={() => onChange(k)}>
            <Glyph icon={k} color={color} size={22} />
          </button>
        ))}
      </div>
    </div>
  )
}

/** Карточка привязанной записи: картинка и описание, вся карточка — ссылка. */
function LinkedCard({ e, onOpen }: { e: Dict; onOpen: (id: string) => void }) {
  const { L } = useApp()
  const { t } = useTranslation('map')
  return (
    <div className="mp-loc" role="button" tabIndex={0}
      title={t('open_entry')}
      onClick={() => onOpen(e.id)}
      onKeyDown={ev => {
        if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); onOpen(e.id) }
      }}>
      {e.image_url
        ? <img className="mp-loc-img" src={thumb(e.image_url, 240)} alt="" />
        : <Stub kind={e.kind} className="mp-loc-img" />}
      <div className="mp-loc-main">
        <div className="row wrap">
          <span className="mp-loc-name">{e.name}</span>
          <Chip tone="cyan">{L(e.kind)}</Chip>
          {e.status && <Chip tone={statusTone(e.status)}>{L(e.status)}</Chip>}
        </div>
        {e.alias && <div className="dim2">{e.alias}</div>}
        {e.summary && <div className="mp-loc-sum">{e.summary}</div>}
        <span className="mp-loc-go">{t('open_card')} →</span>
      </div>
    </div>
  )
}

const SAVE_DELAY = 250

function MarkerModal({
  marker, readonly, author, onClose, onFocus, onOpen, onSave, onDelete,
}: {
  marker: Dict; readonly: boolean; author: string
  onClose: () => void; onFocus: () => void; onOpen: (id: string) => void
  onSave: (patch: Dict) => Promise<void>; onDelete: () => Promise<boolean>
}) {
  const { t } = useTranslation('map')
  const kindOf = (m: Dict) => (m.linked_type === 'entity' || m.marker_type === 'location' ? 'location' : 'custom')
  const [label, setLabel] = useState(marker.label || '')
  const [color, setColor] = useState(colorOf(marker))
  const [icon, setIcon] = useState(iconOf(marker.icon))
  const [kind, setKind] = useState(kindOf(marker))
  const [entity, setEntity] = useState<Dict | null>(marker.linked || null)
  const [vis, setVis] = useState({
    visibility: marker.visibility || 'crew', visible_to: marker.visible_to || [],
  })
  const [swap, setSwap] = useState(false)
  const [phase, setPhase] = useState('')
  useEffect(() => {
    setLabel(marker.label || '')
    setColor(colorOf(marker))
    setIcon(iconOf(marker.icon))
    setKind(kindOf(marker))
    setEntity(marker.linked || null)
    setVis({ visibility: marker.visibility || 'crew', visible_to: marker.visible_to || [] })
    setSwap(false)
    setPhase('')
  }, [marker.id])

  const link = kind === 'location' ? entity : null
  const patch: Dict = {
    label,
    size: COLORS.indexOf(color),
    icon,
    marker_type: kind === 'location' ? 'location' : 'custom',
    linked_type: link ? 'entity' : '',
    linked_id: link ? link.id : '',
    visibility: vis.visibility,
    visible_to: vis.visible_to,
  }
  const dirty = label !== (marker.label || '')
    || color !== colorOf(marker)
    || icon !== iconOf(marker.icon)
    || (link?.id || '') !== (marker.linked_id || '')
    || kind !== kindOf(marker)
    || vis.visibility !== (marker.visibility || 'crew')
    || vis.visible_to.join(',') !== (marker.visible_to || []).join(',')

  /* автосохранение: правка уезжает сама. Запросы не наслаиваются — пока один в
     полёте, следующий ждёт в очереди; при закрытии окна недосохранённое дошлётся */
  const flying = useRef({ busy: false, next: null as Dict | null, gone: false })
  const flush = async (p: Dict) => {
    if (flying.current.gone) return
    if (flying.current.busy) { flying.current.next = p; return }
    flying.current.busy = true
    setPhase('busy')
    try { await onSave(p); setPhase('ok') }
    catch { setPhase('err') }
    flying.current.busy = false
    const next = flying.current.next
    flying.current.next = null
    if (next) flush(next)
  }

  const pending = useRef<Dict | null>(null)
  pending.current = !readonly && dirty ? patch : null

  useEffect(() => {
    const p = pending.current
    if (!p) return
    const t = setTimeout(() => flush(p), SAVE_DELAY)
    return () => clearTimeout(t)
  }, [readonly, dirty, JSON.stringify(patch)])

  /* закрыли окно раньше, чем сработал таймер, — дошлём правку вдогонку */
  useEffect(() => () => { if (pending.current) flush(pending.current) }, [])

  /* удаление гасит дошлю правок; отказ от подтверждения — возвращает как было */
  const kill = async () => {
    flying.current.gone = true
    pending.current = null
    if (!await onDelete()) flying.current.gone = false
  }

  const title = label || marker.label || marker.linked?.name || t('marker')
  return (
    <Modal title={title} onClose={onClose}>
      <div className="col">
        <div className="row wrap">
          <Glyph icon={icon} color={color} size={18} />
          <Chip tone="cyan">{kindOf(marker) === 'location' ? t('type.location') : t('type.custom')}</Chip>
          {author && <span className="mono dim2">{author}</span>}
          <div className="spacer" />
          {marker.visibility && (
            <VisibilityMenu value={vis.visibility} visibleTo={vis.visible_to} disabled={readonly}
              onChange={(v, to) => setVis({ visibility: v, visible_to: to })} />
          )}
          <button className="tiny ghost" onClick={() => { onFocus(); onClose() }}>{t('show_on_map')}</button>
        </div>

        {marker.linked && <LinkedCard e={marker.linked} onOpen={onOpen} />}
        {marker.linked_id && !marker.linked && (
          <div className="mp-hint">{t('linked_hidden')}</div>
        )}

        {readonly
          ? <div className="mp-hint">
            {marker.can_edit === false ? t('foreign_marker') : t('readonly_edit')}
          </div>
          : <div>
            <TypePick value={kind} onChange={k => {
              setKind(k)
              if (k === 'custom') setEntity(null)
              else if (icon === 'dot') setIcon('target')
            }} />
            {kind === 'location' && (entity && !swap
              ? <div className="field">
                <label>{t('location')}</label>
                <div className="row wrap">
                  <span>{entity.name}</span>
                  <div className="spacer" />
                  <button className="tiny ghost" onClick={() => setSwap(true)}>{t('change')}</button>
                  <button className="tiny ghost" onClick={() => setEntity(null)}>{t('unlink')}</button>
                </div>
              </div>
              : <EntityPicker label={t('location_entry')} kind="location" value={null} autoFocus={swap}
                placeholder={t('location_placeholder')}
                onChange={e => {
                  setSwap(false)
                  setEntity(e)
                  if (e && (!label || label === entity?.name)) setLabel(e.name)
                }} />)}
            <Input label={t('label')} value={label} onChange={setLabel} />
            <IconPick value={icon} color={color} onChange={setIcon} />
            <ColorPicker value={color} onChange={setColor} />
            <div className="row wrap">
              <span className={`mp-save${phase === 'err' ? ' bad' : ''}`}>
                {phase === 'busy' ? t('save.busy')
                  : phase === 'err' ? t('save.err')
                      : dirty ? t('save.pending') : phase === 'ok' ? t('save.ok') : t('save.auto')}
              </span>
              <div className="spacer" />
              <button className="danger" onClick={kill}>{t('common:delete')}</button>
            </div>
          </div>}

        <RecordsPanel entityType="marker" entityId={marker.id} title={t('records')} />
      </div>
    </Modal>
  )
}

function NewMapModal({ form, setForm, onDone }: {
  form: Dict; setForm: (v: Dict | null) => void; onDone: (id: string) => void
}) {
  const { t } = useTranslation('map')
  return (
    <Modal title={t('new_map')} onClose={() => setForm(null)} watch={form}
      dirtyAsk={t('new_map_dirty')}>
      <Input label={t('name')} value={form.name} onChange={v => setForm({ ...form, name: v })} />
      <div className="field">
        <label>{t('level')}</label>
        <Select value={form.level} empty={null} title={t('level')}
          options={['sector', 'system', 'local']}
          onChange={v => setForm({ ...form, level: v })} />
      </div>
      <div className="field">
        <label>{t('image')}</label>
        <input type="file" accept="image/*" onChange={async e => {
          const f = e.target.files?.[0]
          if (!f) return
          const fd = new FormData()
          fd.append('file', f)
          try {
            const r = await api.post(`${c()}/upload`, fd)
            setForm({ ...form, image_url: r.url })
          } catch (err: any) { alert(err.message || t('err.file_upload')) }
        }} />
        {form.image_url && <div className="mono dim2 small">{t('uploaded')}</div>}
      </div>
      <button className="primary" disabled={!form.name.trim()} onClick={async () => {
        try {
          const r = await api.post(`${c()}/maps`, {
            name: form.name, level: form.level, image_url: form.image_url,
            visibility: 'crew', visible_to: [],
          })
          onDone(r.id)
        } catch (e: any) { alert(e.message || t('err.map_create')) }
      }}>{t('create')}</button>
    </Modal>
  )
}
