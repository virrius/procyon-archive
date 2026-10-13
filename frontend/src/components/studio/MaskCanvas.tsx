import { forwardRef, useImperativeHandle, useRef } from 'react'
import { useTranslation } from 'react-i18next'

const UNDO_DEPTH = 8

export type MaskApi = {
  undo: () => void
  clear: () => void
  hasPaint: () => boolean
  blob: () => Promise<Blob | null>
}

/** Mask canvas over the picture. Kept at the picture's natural size:
 *  the mask goes to the server one to one (white: redraw). */
const MaskCanvas = forwardRef<MaskApi, {
  src: string; brush: number; erase: boolean; locked?: boolean
  onPaint: (painted: boolean) => void
}>(function MaskCanvas({ src, brush, erase, locked, onPaint }, ref) {
  const { t } = useTranslation('studio')
  const canvas = useRef<HTMLCanvasElement | null>(null)
  const drawing = useRef(false)
  const last = useRef<{ x: number; y: number } | null>(null)
  const undoStack = useRef<ImageData[]>([])

  const hasPaint = () => {
    const cv = canvas.current
    if (!cv || !cv.width) return false
    // by the alpha of a scaled-down copy: a full megapixel pass on every stroke is slow
    const probe = document.createElement('canvas')
    probe.width = 96
    probe.height = 96
    const ctx = probe.getContext('2d')!
    ctx.drawImage(cv, 0, 0, 96, 96)
    const px = ctx.getImageData(0, 0, 96, 96).data
    for (let i = 3; i < px.length; i += 4) if (px[i] > 8) return true
    return false
  }

  useImperativeHandle(ref, () => ({
    undo: () => {
      const cv = canvas.current
      const prev = undoStack.current.pop()
      if (!cv || !prev) return
      cv.getContext('2d')!.putImageData(prev, 0, 0)
      onPaint(hasPaint())
    },
    clear: () => {
      const cv = canvas.current
      if (!cv) return
      cv.getContext('2d')!.clearRect(0, 0, cv.width, cv.height)
      undoStack.current = []
      onPaint(false)
    },
    hasPaint,
    blob: () => {
      const cv = canvas.current!
      const flat = document.createElement('canvas')
      flat.width = cv.width
      flat.height = cv.height
      const ctx = flat.getContext('2d')!
      ctx.fillStyle = '#000'
      ctx.fillRect(0, 0, flat.width, flat.height)
      ctx.drawImage(cv, 0, 0)
      return new Promise(res => flat.toBlob(b => res(b), 'image/png'))
    },
  }))

  const fit = (img: HTMLImageElement) => {
    const cv = canvas.current
    if (!cv) return
    cv.width = img.naturalWidth
    cv.height = img.naturalHeight
    undoStack.current = []
    onPaint(false)
  }

  const spot = (e: React.PointerEvent) => {
    const cv = canvas.current!
    const r = cv.getBoundingClientRect()
    return { x: ((e.clientX - r.left) / r.width) * cv.width, y: ((e.clientY - r.top) / r.height) * cv.height }
  }

  const stroke = (from: { x: number; y: number }, to: { x: number; y: number }) => {
    const ctx = canvas.current!.getContext('2d')!
    ctx.globalCompositeOperation = erase ? 'destination-out' : 'source-over'
    ctx.strokeStyle = '#fff'
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.lineWidth = brush
    ctx.beginPath()
    ctx.moveTo(from.x, from.y)
    ctx.lineTo(to.x, to.y)
    ctx.stroke()
  }

  const down = (e: React.PointerEvent) => {
    const cv = canvas.current
    if (locked || !cv) return
    undoStack.current.push(cv.getContext('2d')!.getImageData(0, 0, cv.width, cv.height))
    if (undoStack.current.length > UNDO_DEPTH) undoStack.current.shift()
    cv.setPointerCapture(e.pointerId)
    drawing.current = true
    const p = spot(e)
    last.current = p
    stroke(p, p)
    onPaint(true)
  }
  const move = (e: React.PointerEvent) => {
    if (!drawing.current) return
    const p = spot(e)
    stroke(last.current || p, p)
    last.current = p
  }
  const up = () => { drawing.current = false; last.current = null }

  return (
    <div className="st-cv-stage">
      <img src={src} alt={t('source_alt')} draggable={false} onLoad={e => fit(e.currentTarget)} />
      <canvas ref={canvas} className={locked ? 'locked' : ''}
        onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} />
    </div>
  )
})

export default MaskCanvas
