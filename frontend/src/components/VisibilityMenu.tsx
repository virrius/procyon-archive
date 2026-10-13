/* Unified "who can see this" menu, the same in all panels. */

import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { Dict } from '../api'
import { useApp } from '../ctx'
import { IconCheck, IconChevron, IconEyeOff, IconLock, IconUser, IconUsers } from './icons'
import PopLayer from './PopLayer'
import '../styles.vis.css'

const ALL_SCOPES = ['crew', 'selected', 'owner', 'gm']

function scopeIcon(s: string, size = 13) {
  if (s === 'selected') return <IconUser size={size} />
  if (s === 'owner') return <IconLock size={size} />
  if (s === 'gm') return <IconEyeOff size={size} />
  return <IconUsers size={size} />
}

export type VisibilityMenuProps = {
  value: string
  visibleTo: string[]
  onChange: (v: string, to: string[]) => void
  disabled?: boolean
  allowGM?: boolean
  compact?: boolean
  hint?: string
}

export function VisibilityMenu({
  value, visibleTo, onChange, disabled, allowGM, compact, hint,
}: VisibilityMenuProps) {
  const { campaign, isGM, meta } = useApp()
  const { t } = useTranslation('entity')
  const wrap = useRef<HTMLDivElement | null>(null)
  const pop = useRef<HTMLDivElement | null>(null)
  const btn = useRef<HTMLButtonElement | null>(null)
  const opts = useRef<(HTMLButtonElement | null)[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)

  const gmOk = allowGM ?? isGM
  const scopes: string[] = ((meta?.visibility_scopes as string[]) || ALL_SCOPES)
    .filter(s => gmOk || s !== 'gm')
  const cur = value || 'crew'
  const to = visibleTo || []
  const people = ((campaign?.members || []) as Dict[]).filter(m => m.role !== 'gm')
  const known = (s: string) => ALL_SCOPES.includes(s)
  // for the GM "only me" would read as "GM only"
  const wordOf = (s: string) => (isGM && s === 'owner' ? t('vis.owner_gm') : known(s) ? t(`vis.${s}`) : s)
  const noteOf = (s: string) => (isGM && s === 'owner' ? t('vis.owner_gm_note') : known(s) ? t(`vis.${s}_note`) : '')
  const word = wordOf(cur)
  const label = t('vis.label', { word })

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

  useEffect(() => { if (open) opts.current[active]?.focus() }, [open, active])

  useEffect(() => { if (disabled) setOpen(false) }, [disabled])

  const raise = (idx: number) => {
    setActive(idx)
    setOpen(true)
  }

  const toggle = () => {
    if (open) { setOpen(false); return }
    raise(Math.max(0, scopes.indexOf(cur)))
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
    raise(e.key === 'ArrowDown' ? 0 : scopes.length - 1)
  }

  const menuKey = (e: ReactKeyboardEvent) => {
    const n = scopes.length
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(i => (i + 1) % n) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(i => (i - 1 + n) % n) }
    else if (e.key === 'Home') { e.preventDefault(); setActive(0) }
    else if (e.key === 'End') { e.preventDefault(); setActive(n - 1) }
    else if (e.key === 'Tab') setOpen(false)
  }

  const pick = (s: string, i: number) => {
    setActive(i)
    onChange(s, s === 'selected' ? to : [])
    if (s !== 'selected') { setOpen(false); btn.current?.focus() }
  }

  const flip = (id: string, on: boolean) =>
    onChange('selected', on ? [...to, id] : to.filter(x => x !== id))

  const tip = hint ? `${label} — ${hint}` : label
  const chip = `vis-chip vis-${cur}${compact ? ' compact' : ''}`
  const face = (
    <>
      {scopeIcon(cur)}
      {!compact && <span className="vis-w">{word}</span>}
    </>
  )

  if (disabled) {
    return (
      <span className="vis-wrap">
        <span className={`${chip} static`} role="img" aria-label={tip} title={tip}>{face}</span>
      </span>
    )
  }

  return (
    <div className="vis-wrap" ref={wrap} onKeyDown={onKey}>
      <button ref={btn} type="button"
        className={`${chip}${open ? ' open' : ''}`}
        title={tip} aria-label={tip} aria-haspopup="menu" aria-expanded={open}
        onClick={toggle} onKeyDown={btnKey}>
        {face}
        <IconChevron size={11} className="vis-caret" />
      </button>

      {open && (
        <PopLayer anchor={btn} popRef={pop} className="vis-pop" onClose={() => setOpen(false)}>
          <div className="vis-opts" role="menu" aria-label={t('vis.menu')} onKeyDown={menuKey}>
            {scopes.map((s, i) => (
              <button key={s} type="button" role="menuitemradio" aria-checked={s === cur}
                ref={el => { opts.current[i] = el }} tabIndex={i === active ? 0 : -1}
                className={`vis-opt${s === cur ? ' on' : ''}`} onClick={() => pick(s, i)}>
                {scopeIcon(s, 14)}
                <span className="vis-txt">
                  <span className="vis-h">{wordOf(s)}</span>
                  <span className="vis-d">{noteOf(s)}</span>
                </span>
                {s === cur && <IconCheck size={13} className="vis-mark" />}
              </button>
            ))}
          </div>

          {cur === 'selected' && (
            <div className="vis-people" role="group" aria-label={t('vis.people')}>
              <span className="vis-cap">{t('vis.pick_people')}</span>
              {people.length === 0
                ? <span className="vis-none">{t('vis.no_players')}</span>
                : people.map(m => (
                  <label key={m.id} className="vis-who">
                    <input type="checkbox" checked={to.includes(m.id)}
                      onChange={e => flip(m.id, e.target.checked)} />
                    {m.display_name}
                  </label>
                ))}
            </div>
          )}
        </PopLayer>
      )}
    </div>
  )
}

export default VisibilityMenu
