import { useRef } from 'react'
import '../styles.tabs.css'

export function Tabs({ tabs, value, onChange }: {
  tabs: [string, string][]
  value: string
  onChange: (k: string) => void
}) {
  const box = useRef<HTMLDivElement>(null)
  const idx = tabs.findIndex(([k]) => k === value)

  const go = (n: number) => {
    if (!tabs.length) return
    const i = (n + tabs.length) % tabs.length
    onChange(tabs[i][0])
    box.current?.querySelectorAll<HTMLButtonElement>('button')[i]?.focus()
  }

  return (
    <div className="tabs" role="tablist" ref={box} onKeyDown={e => {
      if (e.key === 'ArrowRight') { e.preventDefault(); go((idx < 0 ? -1 : idx) + 1) }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); go((idx < 0 ? tabs.length : idx) - 1) }
      else if (e.key === 'Home') { e.preventDefault(); go(0) }
      else if (e.key === 'End') { e.preventDefault(); go(tabs.length - 1) }
    }}>
      {tabs.map(([k, label], i) => (
        <button key={k} type="button" role="tab" aria-selected={k === value}
          tabIndex={i === (idx < 0 ? 0 : idx) ? 0 : -1}
          className={k === value ? 'on' : ''} onClick={() => onChange(k)}>
          {label}
        </button>
      ))}
    </div>
  )
}

export default Tabs
