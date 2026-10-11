import { useRef, useState, type PointerEvent } from 'react'
import { useTranslation } from 'react-i18next'
import '../styles.crop.css'

/** рамка в долях картинки: 0..1, независимо от того, как её показали на экране */
export type Box = { x: number; y: number; w: number; h: number }

const clamp = (v: number, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, v))
/** меньше этого рамка считается случайным кликом, а не выделением */
const MIN = 0.05

/** Рамка в пикселях исходника — то, что уходит на сервер. */
export const cropParam = (box: Box | null, w: number, h: number) =>
  box ? `${Math.round(box.x * w)},${Math.round(box.y * h)},${Math.round(box.w * w)},${Math.round(box.h * h)}` : ''

/** Размер обрезка в пикселях — подписью рядом с рамкой. */
export const cropSize = (box: Box, w: number, h: number) =>
  `${Math.round(box.w * w)}×${Math.round(box.h * h)}`

type Drag =
  | { kind: 'new'; ax: number; ay: number }
  | { kind: 'move'; dx: number; dy: number }
  | { kind: 'size'; ax: number; ay: number }

/** Кадрирование: тянешь рамку по картинке, отпускаешь — рамка готова. Внутри рамки
 *  курсор её двигает, за угол — тянет размер. Пропорции можно запереть. */
export default function CropBox({ src, ratio, lock, box, onBox }: {
  src: string
  /** aspect-ratio картинки строкой CSS — держит место до загрузки файла */
  ratio: string
  /** ширина/высота рамки, null — свободная */
  lock: number | null
  box: Box | null
  onBox: (b: Box | null) => void
}) {
  const { t } = useTranslation('media')
  const wrap = useRef<HTMLDivElement>(null)
  const [drag, setDrag] = useState<Drag | null>(null)

  /** точка события в долях картинки */
  const at = (e: PointerEvent) => {
    const r = wrap.current!.getBoundingClientRect()
    return { px: clamp((e.clientX - r.left) / r.width), py: clamp((e.clientY - r.top) / r.height),
      aspect: r.width / r.height }
  }

  /** рамка от закреплённого угла до курсора, с учётом запертых пропорций */
  const fromCorner = (ax: number, ay: number, px: number, py: number, aspect: number): Box => {
    let w = Math.abs(px - ax)
    let h = Math.abs(py - ay)
    if (lock) {
      // lock — отношение сторон картинки, а не долей: доли считаем через её аспект
      const wantW = (h * lock) / aspect
      if (wantW <= w) w = wantW
      else h = (w * aspect) / lock
      // за край рамка не выходит: сжимаем ту сторону, которая упёрлась
      const capW = px >= ax ? 1 - ax : ax
      const capH = py >= ay ? 1 - ay : ay
      if (w > capW) { w = capW; h = (w * aspect) / lock }
      if (h > capH) { h = capH; w = (h * lock) / aspect }
    }
    return {
      x: px >= ax ? ax : ax - w,
      y: py >= ay ? ay : ay - h,
      w, h,
    }
  }

  const down = (e: PointerEvent, kind: Drag['kind']) => {
    e.preventDefault()
    e.stopPropagation()
    const { px, py } = at(e)
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    if (kind === 'move' && box) setDrag({ kind: 'move', dx: px - box.x, dy: py - box.y })
    // за угол тянем от противоположного: он и остаётся на месте
    else if (kind === 'size' && box) setDrag({ kind: 'size', ax: box.x, ay: box.y })
    else setDrag({ kind: 'new', ax: px, ay: py })
  }

  const move = (e: PointerEvent) => {
    if (!drag) return
    const { px, py, aspect } = at(e)
    if (drag.kind === 'move') {
      if (box) onBox({ ...box, x: clamp(px - drag.dx, 0, 1 - box.w), y: clamp(py - drag.dy, 0, 1 - box.h) })
      return
    }
    onBox(fromCorner(drag.ax, drag.ay, px, py, aspect))
  }

  const up = () => {
    if (drag && drag.kind !== 'move' && box && (box.w < MIN || box.h < MIN)) onBox(null)
    setDrag(null)
  }

  return (
    <div ref={wrap} className="crop-wrap" style={{ aspectRatio: ratio }}
      onPointerDown={e => down(e, 'new')} onPointerMove={move}
      onPointerUp={up} onPointerCancel={up}>
      <img src={src} alt={t('crop.alt')} draggable={false} />
      {box && (
        <>
          <div className="crop-veil crop-top" style={{ height: `${box.y * 100}%` }} />
          <div className="crop-veil crop-bottom" style={{ top: `${(box.y + box.h) * 100}%` }} />
          <div className="crop-veil crop-left"
            style={{ top: `${box.y * 100}%`, height: `${box.h * 100}%`, width: `${box.x * 100}%` }} />
          <div className="crop-veil crop-right"
            style={{ top: `${box.y * 100}%`, height: `${box.h * 100}%`,
              left: `${(box.x + box.w) * 100}%` }} />
          <div className="crop-rect"
            style={{ left: `${box.x * 100}%`, top: `${box.y * 100}%`,
              width: `${box.w * 100}%`, height: `${box.h * 100}%` }}
            onPointerDown={e => down(e, 'move')}>
            <span className="crop-grip" onPointerDown={e => down(e, 'size')} />
          </div>
        </>
      )}
      {!box && <span className="crop-hint">{t('crop.hint')}</span>}
    </div>
  )
}
