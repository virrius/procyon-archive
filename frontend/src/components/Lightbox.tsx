import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useLayer } from '../layers'

/** Просмотр фото в полную величину: тёмная подложка, картинка целиком без обрезки/растяжения.
 *  Если переданы onPrev/onNext — стрелками и кнопками листаем набор снимков. */
export default function Lightbox({ src, alt, caption, onClose, onPrev, onNext }: {
  src: string
  alt?: string
  caption?: string
  onClose: () => void
  onPrev?: () => void
  onNext?: () => void
}) {
  const { t } = useTranslation('media')
  // просмотр открывают и поверх окна карточки: Escape снимает только его
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

  // закрываем, только если и нажатие, и отпускание были на подложке: иначе выделение
  // подписи, вылезшее мышкой за картинку, захлопывает просмотр
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
