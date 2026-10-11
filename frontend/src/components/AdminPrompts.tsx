import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, type Dict } from '../api'
import { useAsync } from '../ctx'
import { PromptDoc } from './PromptDoc'
import { SaveBar, type SavePhase } from './SaveBar'

/** Несохранённое в Admin space: меню спрашивает перед уходом. */
export const adminDirty = { current: false }

type Doc = { id: string; group: string; title: string; doc?: string; section?: string; key?: string }

const DOCS: Record<'images' | 'news', Doc[]> = {
  images: [
    { id: 'person', group: 'prompts.doc.hub', title: 'prompts.doc.person', doc: 'person' },
    { id: 'frame', group: 'prompts.doc.hub', title: 'prompts.doc.frame', doc: 'frame' },
    { id: 'action', group: 'prompts.doc.hub', title: 'prompts.doc.action', doc: 'action' },
    { id: 'inpaint', group: 'prompts.doc.inpaint', title: 'prompts.doc.inpaint', doc: 'inpaint' },
  ],
  news: [
    { id: 'dispatch', group: 'prompts.doc.templates', title: 'prompts.doc.dispatch', section: 'news_templates', key: 'dispatch' },
    { id: 'comments', group: 'prompts.doc.templates', title: 'prompts.doc.comments', section: 'news_templates', key: 'comments' },
  ],
}

const CARDS: Record<'images' | 'news', string[]> = {
  images: ['views', 'registers', 'anchors'],
  news: ['dispatch_journalists', 'dispatch_lenses', 'comment_manners', 'comment_lengths', 'comment_writing'],
}

const SECTION_TITLES: Dict = {
  views: 'prompts.sec.views',
  registers: 'prompts.sec.registers',
  anchors: 'prompts.sec.anchors',
  dispatch_journalists: 'prompts.sec.dispatch_journalists',
  dispatch_lenses: 'prompts.sec.dispatch_lenses',
  comment_manners: 'prompts.sec.comment_manners',
  comment_lengths: 'prompts.sec.comment_lengths',
  comment_writing: 'prompts.sec.comment_writing',
}

// секции, где админ добавляет и убирает записи, в том числе пришедшие из кода; «сбросить к коду» их возвращает
const GROWS: Dict = {
  registers: 'prompts.new.register', anchors: 'prompts.new.anchor', dispatch_journalists: 'prompts.new.journalist',
  dispatch_lenses: 'prompts.new.lens', comment_manners: 'prompts.new.manner', comment_lengths: 'prompts.new.length',
  comment_writing: 'prompts.new.writing',
}
// поля регистра: подписи для ГМа, облик кадра и строка, по которой хаб сам выбирает угол
const REG_FIELDS: [string, string, number][] = [
  ['hint', 'prompts.reg.hint', 1],
  ['look', 'prompts.reg.look', 2],
  ['corner', 'prompts.reg.corner', 1],
  ['vocab', 'prompts.reg.vocab', 2],
  ['vocab_person', 'prompts.reg.vocab_person', 2],
  ['vocab_ship', 'prompts.reg.vocab_ship', 2],
]

const VIEW_INSERTS: Dict = { view: 'prompts.view_insert' }

const clone = (v: any) => JSON.parse(JSON.stringify(v))
const same = (a: any, b: any) => JSON.stringify(a) === JSON.stringify(b)

function AddRow({ placeholder, taken, onAdd }: { placeholder: string; taken: string[]; onAdd: (name: string) => void }) {
  const { t } = useTranslation('admin')
  const [name, setName] = useState('')
  const n = name.trim()
  const ok = !!n && !taken.includes(n)
  const add = () => { if (ok) { onAdd(n); setName('') } }
  return (
    <div className="row adm-add">
      <input placeholder={placeholder} value={name} onChange={e => setName(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') add() }} />
      <button className="ghost tiny" disabled={!ok} onClick={add}>{t('prompts.add')}</button>
    </div>
  )
}

function AutoText({ value, onChange, rows = 2 }: { value: string; onChange: (v: string) => void; rows?: number }) {
  const ta = useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(() => {
    const el = ta.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight + 2}px`
  }, [value])
  return <textarea ref={ta} rows={rows} className="adm-auto" value={value}
    onChange={e => onChange(e.target.value)} />
}

export default function AdminPrompts({ scope }: { scope: 'images' | 'news' }) {
  const { t } = useTranslation('admin')
  const [data, , reload, err] = useAsync<Dict>(() => api.get('/api/admin/prompts'), [])
  const [docs, setDocs] = useState<Dict>({})
  const [kitEdit, setKitEdit] = useState<Dict>({})
  const [phase, setPhase] = useState<SavePhase>('')
  const [saveErr, setSaveErr] = useState('')
  const list = DOCS[scope]
  const [open, setOpen] = useState(list[0].id)

  const dirtyNames = [
    ...list.filter(d => (d.doc ? d.doc in docs : !!d.section && d.section in kitEdit
      && !same(kitEdit[d.section][d.key!], data?.kit[d.section][d.key!]))),
    ...CARDS[scope].filter(s => s in kitEdit).map(s => ({ id: `card-${s}`, title: SECTION_TITLES[s] } as Doc)),
  ]
  const dirty = dirtyNames.length > 0

  useEffect(() => {
    adminDirty.current = dirty
    const warn = (e: BeforeUnloadEvent) => { if (dirty) e.preventDefault() }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  useEffect(() => () => { adminDirty.current = false }, [])

  if (err) return <div className="panel"><div className="eg-err">{err}</div></div>
  if (!data) return <div className="dim">{t('common:loading')}</div>

  const kit: Dict = { ...data.kit, ...kitEdit }
  const putSection = (section: string, value: any) => {
    setKitEdit({ ...kitEdit, [section]: value }); setPhase('')
  }
  const patchIn = (section: string, path: string[], value: any) => {
    const cur = clone(kit[section])
    let node = cur
    for (const k of path.slice(0, -1)) node = node[k]
    node[path[path.length - 1]] = value
    putSection(section, cur)
  }

  const docValue = (d: Doc): string => d.doc
    ? (docs[d.doc] ?? data.docs[d.doc]) : String(kit[d.section!]?.[d.key!] ?? '')
  const docDefault = (d: Doc): string => d.doc
    ? data.doc_defaults[d.doc] : String(data.defaults[d.section!]?.[d.key!] ?? '')
  const setDoc = (d: Doc, v: string) => {
    if (d.doc) { setDocs({ ...docs, [d.doc]: v }); setPhase('') } else patchIn(d.section!, [d.key!], v)
  }
  const inserts = (d: Doc): Dict | undefined =>
    d.doc === 'frame' ? Object.fromEntries(Object.entries(VIEW_INSERTS).map(([k, v]) => [k, t(v)]))
      : d.section === 'news_templates' ? data.news_slots[d.key!] : undefined

  const save = async () => {
    setPhase('busy'); setSaveErr('')
    try {
      await api.patch('/api/admin/prompts', { docs, kit: kitEdit })
      setDocs({}); setKitEdit({}); setPhase('ok'); reload()
    } catch (e: any) { setSaveErr(e.message); setPhase('') }
  }
  const undo = () => { setDocs({}); setKitEdit({}); setSaveErr(''); setPhase('') }

  const goTo = (id: string) => {
    if (list.some(d => d.id === id)) { setOpen(id); id = 'adm-docs' }
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const cur = list.find(d => d.id === open) || list[0]
  const groups = [...new Set(list.map(d => d.group))]
  const docLabel = (d: Doc) => (d.group && d.group !== d.title ? `${t(d.group)} · ${t(d.title)}` : t(d.title))

  const cardHead = (section: string) => (
    <div className="adm-sec-hd">
      <h3>{t(SECTION_TITLES[section])}</h3>
      {!same(kit[section], data.defaults[section]) && (
        <button className="ghost tiny" onClick={() => putSection(section, {
          ...Object.fromEntries(Object.keys(kit[section]).map(k => [k, null])), ...clone(data.defaults[section]),
        })}>
          {t('prompts.reset')}
        </button>
      )}
    </div>
  )

  const live = (node: Dict) => Object.keys(node).filter(k => node[k] != null)
  const drop = (section: string, k: string, path: string[] = []) => (
    <button className="ghost tiny adm-drop" onClick={() => patchIn(section, [...path, k], null)}>{t('prompts.remove')}</button>
  )

  const pairs = (section: string, path: string[] = []) => {
    let node = kit[section]
    for (const k of path) node = node[k]
    return live(node).map(k => (
      <div key={k} className={`adm-pair${String(node[k]).trim() ? '' : ' off'}`}>
        <span className="adm-pair-k">{k}{GROWS[section] && drop(section, k, path)}</span>
        <AutoText rows={1} value={String(node[k] ?? '')}
          onChange={v => patchIn(section, [...path, k], v)} />
      </div>
    ))
  }

  const card = (section: string) => {
    if (section === 'views') {
      return Object.keys(kit.views).map(k => (
        <div className="adm-card" key={k}>
          <input className="adm-card-title" value={kit.views[k].title}
            onChange={e => patchIn('views', [k, 'title'], e.target.value)} />
          <AutoText value={kit.views[k].law} onChange={v => patchIn('views', [k, 'law'], v)} />
        </div>
      ))
    }
    if (section === 'registers') {
      return live(kit.registers).map(k => (
        <div className={`adm-card${String(kit.registers[k].vocab || '').trim() ? '' : ' off'}`} key={k}>
          <div className="row adm-card-hd">
            <input className="adm-card-title" value={kit.registers[k].title || ''}
              onChange={e => patchIn('registers', [k, 'title'], e.target.value)} />
            {drop('registers', k)}
          </div>
          {REG_FIELDS.map(([f, lab, rows]) => (
            <div key={f} className="field">
              <label>{t(lab)}</label>
              <AutoText rows={rows} value={kit.registers[k][f] || ''} onChange={v => patchIn('registers', [k, f], v)} />
            </div>
          ))}
        </div>
      ))
    }
    if (section === 'anchors') {
      return Object.keys(kit.anchors).map(k => (
        <div className="adm-card" key={k}>
          <div className="adm-card-name">{kit.views[k.replace(/^frame:/, '')]?.title || k}</div>
          {pairs('anchors', [k])}
          <AddRow placeholder={t(GROWS.anchors)} taken={live(kit.anchors[k])}
            onAdd={name => patchIn('anchors', [k, name], '')} />
        </div>
      ))
    }
    if (section === 'dispatch_journalists') {
      return live(kit.dispatch_journalists).map(k => {
        const j = kit.dispatch_journalists[k]
        return (
          <div className={`adm-card${String(j.persona || '').trim() ? '' : ' off'}`} key={k}>
            <div className="row adm-card-hd">
              <input className="adm-card-title" value={j.title || ''}
                onChange={e => patchIn('dispatch_journalists', [k, 'title'], e.target.value)} />
              {drop('dispatch_journalists', k)}
            </div>
            <AutoText rows={6} value={j.persona || ''}
              onChange={v => patchIn('dispatch_journalists', [k, 'persona'], v)} />
            <div className="field">
              <label>{t('prompts.signature')}</label>
              <input value={j.signature || ''}
                onChange={e => patchIn('dispatch_journalists', [k, 'signature'], e.target.value)} />
            </div>
          </div>
        )
      })
    }
    return <div className="adm-card">{pairs(section)}{GROWS[section] && grow(section)}</div>
  }

  const grow = (section: string) => (
    <AddRow placeholder={t(GROWS[section])} taken={live(kit[section])} onAdd={name => {
      const key = `${section === 'registers' ? 'r' : 'j'}${Date.now().toString(36)}`
      if (section === 'dispatch_journalists') patchIn(section, [key], { title: name, persona: '', signature: '' })
      else if (section === 'registers') {
        patchIn(section, [key], { title: name, hint: '', look: '', corner: '', vocab: '', vocab_person: '', vocab_ship: '' })
      } else patchIn(section, [name], '')
    }} />
  )

  const wide = (s: string) => ['registers', 'dispatch_journalists'].includes(s)

  return (
    <div className="adm-page">
      <section className="adm-docs" id="adm-docs">
        <nav className="adm-doc-tabs">
          {groups.map(g => {
            const items = list.filter(d => d.group === g)
            return (
              <div className="adm-doc-group" key={g}>
                {(items.length > 1 || items[0].title !== g) && <span className="adm-doc-glab">{t(g)}</span>}
                {items.map(d => (
                  <button key={d.id} type="button" className={`adm-doc-tab${d.id === cur.id ? ' on' : ''}`}
                    onClick={() => setOpen(d.id)}>
                    {t(d.title)}
                    {docValue(d).trim() !== docDefault(d).trim() && <i className="adm-mod" title={t('prompts.differs')} />}
                  </button>
                ))}
              </div>
            )
          })}
        </nav>
        <PromptDoc key={cur.id} title={docLabel(cur)}
          value={docValue(cur)} onChange={v => setDoc(cur, v)} inserts={inserts(cur)}
          changed={docValue(cur).trim() !== docDefault(cur).trim()}
          onReset={() => setDoc(cur, docDefault(cur))} />
      </section>

      {CARDS[scope].map(s => (
        <section className="adm-sec" id={`card-${s}`} key={s}>
          {cardHead(s)}
          <div className={`adm-cards${wide(s) ? ' wide' : ''}`}>
            {card(s)}
            {(s === 'dispatch_journalists' || s === 'registers') && <div className="adm-card adm-card-new">{grow(s)}</div>}
          </div>
        </section>
      ))}

      <div className={`adm-savebar${dirty || saveErr ? ' on' : ''}`}>
        <div className="adm-unsaved">
          {dirtyNames.map(d => (
            <button key={d.id} type="button" className="adm-unsaved-item" onClick={() => goTo(d.id)}>
              {docLabel(d)}
            </button>
          ))}
        </div>
        <SaveBar dirty={dirty} phase={phase} err={saveErr} onSave={save} onReset={undo} />
      </div>
    </div>
  )
}
