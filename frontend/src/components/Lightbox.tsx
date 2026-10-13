import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useLayer } from '../layers'

/** Full-size photo view: dark backdrop, the whole picture without cropping/stretching.
 *  If onPrev/onNext are passed, arrows and buttons page through the set of pictures. */
export default function Lightbox({ src, alt, caption, onClose, onPrev, onNext }: {
  src: string
  alt?: string
  caption?: string
  onClose: () => void
  onPrev?: () => void
  onNext?: () => void
}) {
  const { t } = useTranslation('media')
  // the viewer can open over a card window too: Escape closes only the viewer
  useLayer(true, onClose)

  useEffect(() => {
    const h = (ev: KeyboardEvent) => {
      if (ev.key === 'ArrowLeft') onPrev?.()
      if (ev.key === 'ArrowRight') onNext?.()
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onPrev, onNext])

  const step = (fn?: () => void) => (ev: React.MouseEvent) => {
    ev.stopPropagation()
    fn?.()
  }

  // close only if both press and release were on the backdrop: otherwise selecting
  // the caption and dragging the mouse past the picture would slam the viewer shut
  const downOnBd = useRef(false)

  return (
    <div className="lightbox-bd"
      onMouseDown={ev => { downOnBd.current = ev.target === ev.currentTarget }}
      onClick={ev => { if (ev.target === ev.currentTarget && downOnBd.current) onClose() }}>
      <img className="lightbox-img" src={src} alt={alt || ''} onClick={ev => ev.stopPropagation()} />
      {caption && <div className="lightbox-cap" onClick={ev => ev.stopPropagation()}>{caption}</div>}
      {onPrev && (
        <button type="button" className="lightbox-nav prev" aria-label={t('lightbox.prev')}
          onClick={step(onPrev)}>‹</button>
      )}
      {onNext && (
        <button type="button" className="lightbox-nav next" aria-label={t('lightbox.next')}
          onClick={step(onNext)}>›</button>
      )}
      <button type="button" className="lightbox-x" aria-label={t('common:close')} onClick={onClose}>×</button>
    </div>
  )
}
