/* Кому отдана правка карточки — тот же чип с меню, что и «кто это видит». */

import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { Dict } from '../api'
import { useApp } from '../ctx'
import { IconCheck, IconChevron, IconEdit, IconLock, IconUser, IconUsers } from './icons'
import PopLayer from './PopLayer'
import '../styles.vis.css'

export const ANY_PLAYER = '*'

const GM_ONLY = ''

function ownerIcon(id: string, size = 13) {
  if (id === ANY_PLAYER) return <IconUsers size={size} />
  if (id === GM_ONLY) return <IconLock size={size} />
  return <IconUser size={size} />
}

function ownerTone(id: string): string {
  return id === ANY_PLAYER ? 'own-all' : id === GM_ONLY ? 'own-gm' : 'own-one'
}

export function OwnerMenu({ value, onChange, disabled, compact }: {
  value?: string | null
  onChange: (v: string | null) => void
  disabled?: boolean
  compact?: boolean
}) {
  const { campaign, memberName } = useApp()
  const { t } = useTranslation('entity')
  const wrap = useRef<HTMLDivElement | null>(null)
  const pop = useRef<HTMLDivElement | null>(null)
  const btn = useRef<HTMLButtonElement | null>(null)
  const items = useRef<(HTMLButtonElement | null)[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)

  const players = ((campaign?.members || []) as Dict[]).filter(m => m.role !== 'gm')
  const opts: { id: string; word: string; note: string }[] = [
    { id: GM_ONLY, word: t('owner.gm_only'), note: t('owner.gm_only_note') },
    { id: ANY_PLAYER, word: t('owner.all'), note: t('owner.all_note') },
    ...players.map(m => ({
      id: String(m.id), word: String(m.display_name || ''), note: t('owner.one_note'),
    })),
  ]
  const cur = value || GM_ONLY
  const word = opts.find(o => o.id === cur)?.word || memberName(cur) || t('owner.player')
  const label = t('owner.label', { who: word })

  useEffect(() => {
    if (!open) return
    const away = (e: MouseEvent) => {
      const t = e.target as Node
      if (wrap.current?.contains(t) || pop.current?.contains(t)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', away)
    return () => document.removeEventListener('mousedown', away)
  }, [open])

  useEffect(() => { if (open) items.current[active]?.focus() }, [open, active])
  useEffect(() => { if (disabled) setOpen(false) }, [disabled])

  const raise = (idx: number) => {
    setActive(idx)
    setOpen(true)
  }

  const toggle = () => {
    if (open) { setOpen(false); return }
    raise(Math.max(0, opts.findIndex(o => o.id === cur)))
  }

  const onKey = (e: ReactKeyboardEvent) => {
    if (e.key !== 'Escape' || !open) return
    e.stopPropagation()
    setOpen(false)
    btn.current?.focus()
  }

  const btnKey = (e: ReactKeyboardEvent) => {
    if (open || (e.key !== 'ArrowDown' && e.key !== 'ArrowUp')) return
    e.preventDefault()
    raise(e.key === 'ArrowDown' ? 0 : opts.length - 1)
  }

  const menuKey = (e: ReactKeyboardEvent) => {
    const n = opts.length
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(i => (i + 1) % n) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(i => (i - 1 + n) % n) }
    else if (e.key === 'Home') { e.preventDefault(); setActive(0) }
    else if (e.key === 'End') { e.preventDefault(); setActive(n - 1) }
    else if (e.key === 'Tab') setOpen(false)
  }

  const pick = (id: string, i: number) => {
    setActive(i)
    onChange(id === GM_ONLY ? null : id)
    setOpen(false)
    btn.current?.focus()
  }

  const chip = `vis-chip own-chip ${ownerTone(cur)}${compact ? ' compact' : ''}`
  // карандаш на лице чипа: рядом с глазом видимости сразу читается «это про правку»
  const face = <><IconEdit size={12} />{!compact && <span className="vis-w">{word}</span>}</>

  if (disabled) {
    return (
      <span className="vis-wrap">
        <span className={`${chip} static`} role="img" aria-label={label} title={label}>{face}</span>
      </span>
    )
  }

  return (
    <div className="vis-wrap" ref={wrap} onKeyDown={onKey}>
      <button ref={btn} type="button" className={`${chip}${open ? ' open' : ''}`}
        title={label} aria-label={label} aria-haspopup="menu" aria-expanded={open}
        onClick={toggle} onKeyDown={btnKey}>
        {face}
        <IconChevron size={11} className="vis-caret" />
      </button>

      {open && (
        <PopLayer anchor={btn} popRef={pop} className="vis-pop" onClose={() => setOpen(false)}>
          <div className="vis-opts" role="menu" aria-label={t('owner.menu')} onKeyDown={menuKey}>
            {opts.map((o, i) => (
              <button key={o.id || 'gm'} type="button" role="menuitemradio" aria-checked={o.id === cur}
                ref={el => { items.current[i] = el }} tabIndex={i === active ? 0 : -1}
                className={`vis-opt${o.id === cur ? ' on' : ''}`} onClick={() => pick(o.id, i)}>
                {ownerIcon(o.id, 14)}
                <span className="vis-txt">
                  <span className="vis-h">{o.word}</span>
                  <span className="vis-d">{o.note}</span>
                </span>
                {o.id === cur && <IconCheck size={13} className="vis-mark" />}
              </button>
            ))}
          </div>
        </PopLayer>
      )}
    </div>
  )
}

export default OwnerMenu
