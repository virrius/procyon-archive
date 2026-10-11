import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { api, c, thumbFull, type Dict } from '../api'
import { useAsync } from '../ctx'
import { Modal } from '../ui'
import Lightbox from '../components/Lightbox'
import PasteImage from '../paste'
import '../styles.rules.css'

type Item = { id: string; kind: 'shot' | 'text'; title: string; text: string; src: string }
type Section = { id: string; title: string; note: string; items: Item[] }
type BookGroup = { title: string; pages: { file: string; label: string; src: string }[] }
type Shot = { src: string; caption: string }

const titleOf = (f: string) => f.replace(/\.[a-z0-9]+$/i, '')

export default function RulesPage() {
  const { t } = useTranslation('rules')
  const [secs, loading, reload, err] = useAsync<Section[]>(() => api.get(`${c()}/rules`), [])
  const [book] = useAsync<BookGroup[]>(() => api.get(`${c()}/rules/book`), [])

  const [shots, setShots] = useState<Shot[] | null>(null)
  const [at, setAt] = useState(0)
  const [busy, setBusy] = useState(false)
  const [oops, setOops] = useState('')
  const [active, setActive] = useState('')      // куда падают Ctrl+V и выбор файла
  const [pickFor, setPickFor] = useState('')    // раздел, для которого открыт комплект
  const [noteFor, setNoteFor] = useState<Dict | null>(null)  // текстовая вырезка в правке
  const filePick = useRef<HTMLInputElement | null>(null)
  // ?open=<id> — приход из поиска: раздел раскрывается, вырезка подсвечена
  const [params, setParams] = useSearchParams()
  const asked = params.get('open') || ''
  const [lit, setLit] = useState('')

  const sections = secs || []

  useEffect(() => {
    if (!asked || !secs) return
    setParams({}, { replace: true })
    const sec = secs.find(s => s.id === asked || s.items.some(i => i.id === asked))
    if (!sec) return
    setLit(asked)
    const box = document.getElementById(`rs-${sec.id}`) as HTMLDetailsElement | null
    if (box) box.open = true
    requestAnimationFrame(() => document.getElementById(asked === sec.id ? `rs-${sec.id}` : `ri-${asked}`)
      ?.scrollIntoView({ block: 'center' }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asked, secs])

  const fail = (e: any, what: string) => setOops(e?.message || what)
  const after = () => reload(false)

  const show = (list: Shot[], i: number) => { setShots(list); setAt(i) }
  const step = (d: number) => () =>
    setAt(i => (i + d + (shots?.length || 1)) % (shots?.length || 1))

  const restore = async () => {
    setOops('')
    try {
      const r = await api.post(`${c()}/rules/reseed`)
      const back: string[] = r?.restored || []
      setOops(back.length ? t('restored', { list: back.join(', ') }) : t('all_in_place'))
    } catch (e) { fail(e, t('restore_failed')) }
    after()
  }

  const addSection = async () => {
    setOops('')
    try { await api.post(`${c()}/rules/sections`, { title: t('new_section'), note: '' }) }
    catch (e) { fail(e, t('section_add_failed')) }
    after()
  }

  const patchSection = async (s: Section, body: Dict) => {
    setOops('')
    try { await api.patch(`${c()}/rules/sections/${s.id}`, body) }
    catch (e) { fail(e, t('section_save_failed')) }
    after()
  }

  const dropSection = async (s: Section) => {
    const n = s.items.length
    const warn = t('section_delete_confirm', { title: s.title, n })
    if (!confirm(warn)) return
    setOops('')
    try { await api.del(`${c()}/rules/sections/${s.id}`) }
    catch (e) { fail(e, t('section_delete_failed')) }
    after()
  }

  const addItem = async (sid: string, body: Dict) => {
    setOops('')
    try { await api.post(`${c()}/rules/sections/${sid}/items`, body) }
    catch (e) { fail(e, t('item_add_failed')) }
    after()
  }

  const patchItem = async (id: string, body: Dict) => {
    setOops('')
    try { await api.patch(`${c()}/rules/items/${id}`, body) }
    catch (e) { fail(e, t('item_save_failed')) }
    after()
  }

  const dropItem = async (it: Item) => {
    if (!confirm(it.title ? t('item_delete_confirm_named', { title: it.title }) : t('item_delete_confirm'))) return
    setOops('')
    try { await api.del(`${c()}/rules/items/${it.id}`) }
    catch (e) { fail(e, t('item_delete_failed')) }
    after()
  }

  const upload = async (files: File[], sid: string) => {
    const pics = files.filter(f => f.type.startsWith('image/'))
    if (!pics.length || !sid) return
    setBusy(true); setOops('')
    try {
      for (const f of pics) {
        const fd = new FormData()
        fd.append('file', f)
        fd.append('target_type', 'rules')
        fd.append('target_id', sid)
        fd.append('visibility', 'gm')
        const up = await api.post(`${c()}/upload`, fd)
        await api.post(`${c()}/rules/sections/${sid}/items`,
          { kind: 'shot', attachment_id: up.id, title: titleOf(f.name) })
      }
    } catch (e) { fail(e, t('upload_failed')) }
    setBusy(false)
    after()
  }

  if (loading && !secs) return <div className="panel">…</div>

  return (
    <div className="col">
      <div className="panel col">
        <div className="row wrap">
          <h3>{t('title')}</h3>
          <span className="mono dim2 small">
            {t('counts', { sections: sections.length, items: sections.reduce((n, s) => n + s.items.length, 0) })}
          </span>
          <div className="spacer" />
          <button className="tiny ghost" onClick={restore}>{t('restore')}</button>
          <button className="tiny primary" onClick={addSection}>{t('add_section')}</button>
        </div>
        <div className="small dim2">
          {t('help')}
        </div>
        {oops && <div className="rules-oops">{oops}</div>}
        {!!err && <div className="rules-oops">{err}</div>}
      </div>

      <input ref={filePick} type="file" accept="image/*" multiple hidden
        onChange={ev => {
          upload(Array.from(ev.target.files || []), active)
          ev.target.value = ''
        }} />

      {sections.length === 0 && (
        <div className="empty">{t('no_sections')}</div>
      )}

      {sections.map(s => {
        const pics = s.items.filter(i => i.kind === 'shot')
        return (
          <details className={`panel col rules-sec${lit === s.id ? ' lit' : ''}`} key={s.id} id={`rs-${s.id}`}
            onToggle={ev => { if ((ev.target as HTMLDetailsElement).open) setActive(s.id) }}
            onDragOver={ev => ev.preventDefault()}
            onDrop={ev => {
              ev.preventDefault()
              upload(Array.from(ev.dataTransfer.files || []), s.id)
            }}>
            <summary>
              {s.title}
              <span className="dim2 small"> · {s.items.length || t('empty')}</span>
            </summary>

            <div className="row wrap">
              <input className="rules-title" key={`t${s.id}`} defaultValue={s.title}
                onBlur={ev => {
                  if (ev.target.value !== s.title) patchSection(s, { title: ev.target.value })
                }} />
              <div className="spacer" />
              <button className="tiny ghost" disabled={busy}
                onClick={() => { setActive(s.id); filePick.current?.click() }}>
                {busy && active === s.id ? t('uploading') : t('add_image')}
              </button>
              <button className="tiny ghost" onClick={() => setPickFor(s.id)}>{t('add_from_kit')}</button>
              <button className="tiny ghost"
                onClick={() => setNoteFor({ section: s.id, title: '', text: '' })}>
                {t('add_text')}
              </button>
              <button className="tiny danger" onClick={() => dropSection(s)}>{t('delete_section')}</button>
            </div>
            <input className="rules-note" key={`n${s.id}`} defaultValue={s.note}
              placeholder={t('note_placeholder')}
              onBlur={ev => {
                if (ev.target.value !== s.note) patchSection(s, { note: ev.target.value })
              }} />

            {s.items.length === 0 && (
              <div className="small dim2">
                {t('section_empty')}
              </div>
            )}

            <div className="rules-grid">
              {s.items.map(it => (
                <div className={`rules-cut${lit === it.id ? ' lit' : ''}`} key={it.id} id={`ri-${it.id}`}>
                  {it.kind === 'shot' ? (
                    <button type="button" className="rules-page"
                      onClick={() => show(
                        pics.map(p => ({ src: p.src, caption: p.title })),
                        pics.findIndex(p => p.id === it.id))}>
                      <img src={it.src.startsWith('/api') ? thumbFull(it.src, 480) : it.src}
                        alt={it.title} loading="lazy" />
                    </button>
                  ) : (
                    <button type="button" className="rules-text"
                      onClick={() => setNoteFor({ id: it.id, title: it.title, text: it.text })}>
                      {it.text || <span className="dim2">{t('empty_note')}</span>}
                    </button>
                  )}
                  <input className="rules-cap" defaultValue={it.title} placeholder={t('caption')}
                    onBlur={ev => {
                      if (ev.target.value !== it.title) patchItem(it.id, { title: ev.target.value })
                    }} />
                  <button type="button" className="tiny ghost"
                    onClick={() => dropItem(it)}>{t('common:delete')}</button>
                </div>
              ))}
            </div>
          </details>
        )
      })}

      <PasteImage onFiles={files => upload(files, active)} enabled={!!active}
        title={t('paste_title')} question={t('paste_question')} />

      {pickFor && (
        <Modal title={t('kit_pages')} onClose={() => setPickFor('')}>
          <div className="col">
            {(book || []).map(g => (
              <div className="col" key={g.title} style={{ gap: 6 }}>
                <div className="small dim2">{g.title}</div>
                <div className="rules-grid">
                  {g.pages.map(p => (
                    <button type="button" className="rules-page" key={p.file}
                      onClick={() => {
                        addItem(pickFor, { kind: 'shot', media: p.file, title: t('page_title', { label: p.label }) })
                        setPickFor('')
                      }}>
                      <img src={p.src} alt={t('page_alt', { label: p.label })} loading="lazy" />
                      <span className="mono dim2">{p.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
            {(book || []).length === 0 && (
              <div className="small dim2">
                {t('kit_missing')}
              </div>
            )}
          </div>
        </Modal>
      )}

      {noteFor && (
        <Modal title={noteFor.id ? t('text_clipping') : t('new_text_clipping')}
          onClose={() => setNoteFor(null)} watch={noteFor}
          dirtyAsk={t('dirty')}>
          <div className="col">
            <div className="field">
              <label>{t('caption')}</label>
              <input value={noteFor.title}
                onChange={ev => setNoteFor({ ...noteFor, title: ev.target.value })} />
            </div>
            <div className="field">
              <label>{t('text')}</label>
              <textarea rows={12} value={noteFor.text}
                onChange={ev => setNoteFor({ ...noteFor, text: ev.target.value })} />
            </div>
            <div className="row">
              <div className="spacer" />
              <button className="ghost" onClick={() => setNoteFor(null)}>{t('cancel')}</button>
              <button className="primary" onClick={async () => {
                const body = { title: noteFor.title, text: noteFor.text }
                if (noteFor.id) await patchItem(noteFor.id, body)
                else await addItem(noteFor.section, { kind: 'text', ...body })
                setNoteFor(null)
              }}>{t('common:save')}</button>
            </div>
          </div>
        </Modal>
      )}

      {shots && (
        <Lightbox
          src={shots[at].src}
          alt={shots[at].caption}
          caption={shots[at].caption}
          onClose={() => setShots(null)}
          onPrev={shots.length > 1 ? step(-1) : undefined}
          onNext={shots.length > 1 ? step(1) : undefined}
        />
      )}
    </div>
  )
}
