import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

/* Текст длиннее пары строк прячется под «развернуть» и по умолчанию свёрнут. */
export default function Foldable({ children, className = '', lines = 2, style }: {
  children: ReactNode
  className?: string
  lines?: number
  style?: React.CSSProperties
}) {
  const { t } = useTranslation('common')
  const ref = useRef<HTMLDivElement>(null)
  const [long, setLong] = useState(false)
  const [open, setOpen] = useState(false)

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const measure = () => {
      const cs = getComputedStyle(el)
      const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.4
      el.style.maxHeight = `${lh * lines}px`
      const over = el.scrollHeight - el.clientHeight > 2
      setLong(over)
      if (open || !over) el.style.maxHeight = ''
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [children, lines, open])

  useEffect(() => { setOpen(false) }, [children])

  return (
    <>
      <div ref={ref} className={`fold ${className} ${open || !long ? '' : 'clip'}`} style={style}>
        {children}
      </div>
      {long && (
        <button type="button" className="fold-btn" onClick={() => setOpen(o => !o)}>
          {open ? t('fold.less') : t('fold.more')}
        </button>
      )}
    </>
  )
}
