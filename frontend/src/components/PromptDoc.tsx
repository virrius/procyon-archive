import { useLayoutEffect, useMemo, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { type Dict } from '../api'
import { locale } from '../i18n'

// строка входа шаблона — на языке экземпляра, понимаем обе
const INPUT_LINE = /^[ \t]*=== (?:ВХОД|INPUT) ===[ \t]*$/
const SLOT = /\{\{\s*([^{}]+?)\s*\}\}|\{(view)\}/g

type Head = { at: number; len: number; text: string; input?: boolean }

/** Оглавление: абзацы, начатые фразой капсом до точки, и строка входа шаблона. */
function headings(text: string): Head[] {
  const out: Head[] = []
  let at = 0
  for (const line of text.split('\n')) {
    if (INPUT_LINE.test(line)) {
      out.push({ at, len: line.length, text: line.trim(), input: true })
    } else {
      const m = line.match(/^\s*([^.!?:\n]{4,90}?)[.:]/)
      const lead = m?.[1] || ''
      if (/\p{Lu}.*\p{Lu}/u.test(lead) && lead === lead.toUpperCase()) {
        out.push({ at: at + line.indexOf(lead), len: lead.length, text: lead })
      }
    }
    at += line.length + 1
  }
  return out
}

/** Высота строки offset внутри textarea: зеркальный блок с тем же шрифтом и шириной. */
function offsetY(ta: HTMLTextAreaElement, offset: number): number {
  const cs = getComputedStyle(ta)
  const m = document.createElement('div')
  for (const p of ['font', 'letterSpacing', 'lineHeight', 'padding', 'border', 'boxSizing', 'tabSize'] as const) {
    (m.style as any)[p] = (cs as any)[p]
  }
  Object.assign(m.style, {
    position: 'absolute', visibility: 'hidden', whiteSpace: 'pre-wrap', overflowWrap: 'break-word',
    width: `${ta.clientWidth}px`, top: '0', left: '-9999px',
  })
  m.textContent = ta.value.slice(0, offset)
  const mark = document.createElement('span')
  mark.textContent = '|'
  m.appendChild(mark)
  document.body.appendChild(m)
  const y = mark.offsetTop
  m.remove()
  return y
}

export function PromptDoc({ title, value, onChange, changed, onReset, inserts }: {
  title: string
  value: string
  onChange: (v: string) => void
  changed: boolean
  onReset: () => void
  /** вставка → что код подставит на её место */
  inserts?: Dict
}) {
  const { t } = useTranslation('media')
  const ta = useRef<HTMLTextAreaElement>(null)
  const caret = useRef<number | null>(null)

  useLayoutEffect(() => {
    const el = ta.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight + 2}px`
  }, [value])

  const toc = useMemo(() => headings(value), [value])
  const used = useMemo(() => new Set([...value.matchAll(SLOT)].map(m => m[1] || m[2])), [value])
  const unknown = inserts ? [...used].filter(s => !(s in inserts)) : []
  const tokenOf = (name: string) => (name === 'view' ? '{view}' : `{{${name}}}`)

  const jump = (h: Head) => {
    const el = ta.current
    if (!el) return
    const scroller = el.closest('.adm-main') as HTMLElement | null
    const y = offsetY(el, h.at)
    if (scroller) {
      const top = el.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop
      scroller.scrollTo({ top: top + y - 90, behavior: 'smooth' })
    }
    el.focus({ preventScroll: true })
    el.setSelectionRange(h.at, h.at + h.len)
  }

  const insert = (name: string) => {
    const el = ta.current
    if (!el) return
    const token = tokenOf(name)
    const at = caret.current ?? value.length
    onChange(value.slice(0, at) + token + value.slice(at))
    requestAnimationFrame(() => {
      el.focus({ preventScroll: true })
      el.setSelectionRange(at + token.length, at + token.length)
      caret.current = at + token.length
    })
  }

  const noInput = inserts && Object.keys(inserts).some(k => k !== 'view') && !value.split('\n').some(l => INPUT_LINE.test(l))
  // недостающую строку подсказываем на языке вставок шаблона
  const inputMark = inserts && Object.keys(inserts).some(k => /[а-яё]/i.test(k)) ? '=== ВХОД ===' : '=== INPUT ==='

  return (
    <section className="adm-doc">
      <div className="adm-doc-hd">
        <h2>{title}</h2>
        <span className="mono dim2">{t('doc.chars', { n: value.length.toLocaleString(locale()) })}</span>
        <div className="spacer" />
        {changed && <button className="ghost tiny" onClick={onReset}>{t('doc.reset')}</button>}
      </div>
      <div className="adm-doc-body">
        <textarea ref={ta} className="adm-doc-text" value={value} spellCheck={false}
          onChange={e => { onChange(e.target.value); caret.current = e.target.selectionStart }}
          onSelect={e => { caret.current = (e.target as HTMLTextAreaElement).selectionStart }} />
        <aside className="adm-rail">
          {inserts && (
            <div className="adm-rail-block">
              <div className="adm-rail-lab">{t('doc.inserts')}</div>
              {noInput && <div className="adm-ins bad">{inputMark}</div>}
              {Object.entries(inserts).map(([name, about]) => (
                <button key={name} type="button" title={String(about)}
                  className={`adm-ins${used.has(name) ? '' : ' off'}`}
                  onMouseDown={e => e.preventDefault()} onClick={() => insert(name)}>
                  <code>{tokenOf(name)}</code>
                  <span>{String(about)}</span>
                </button>
              ))}
              {unknown.map(s => (
                <div key={s} className="adm-ins bad"><code>{tokenOf(s)}</code></div>
              ))}
            </div>
          )}
          {toc.length > 0 && (
            <div className="adm-rail-block">
              <div className="adm-rail-lab">{t('doc.toc')}</div>
              {toc.map(h => (
                <button key={h.at} type="button" className={`adm-toc${h.input ? ' input' : ''}`}
                  onMouseDown={e => e.preventDefault()} onClick={() => jump(h)}>{h.text}</button>
              ))}
            </div>
          )}
        </aside>
      </div>
    </section>
  )
}
