import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c, thumbFull, type Dict } from '../../api'
import { IconBrush } from '../icons'
import {
  CYRILLIC, PARTS, PART_LABELS, aspectBySize, hoursLeft, isLive, kindTitle, registerTitle, strengthTitle, when,
  type Attempt, type Candidate, type Dest, type PromptKind,
} from './kit'

export type Pick = 'avatar' | 'media' | 'scene' | 'replace'
export type Change = { prompt: string; slots: Dict | null; hand: boolean; prompts?: string[] }

/** Prompt part: an edit goes straight into the build */
function Part({ label, take, value, onChange }: {
  label: string; take?: number; value: string; onChange: (v: string) => void
}) {
  const { t } = useTranslation('studio')
  return (
    <label className="st-part">
      <span className="st-part-k">{label}{take !== undefined && <i>{t('take', { n: take + 1 })}</i>}</span>
      <textarea rows={2} value={value} onChange={e => onChange(e.target.value)}
        ref={el => { if (el) { el.style.height = 'auto'; el.style.height = `${el.scrollHeight}px` } }} />
    </label>
  )
}

export default function AttemptCard({
  att, no, open, onToggle, dest, draft, kept, busy,
  onPick, onBrush, onAgain, onDiscard, onZoom, onSaveOutfit, onError,
}: {
  att: Attempt; no: number; open: boolean; onToggle: () => void
  dest: Dest; draft?: boolean
  kept?: { id: string; label: string }
  busy: boolean
  onPick: (cand: Candidate, how: Pick, keepSource?: boolean) => void
  onBrush: (cand: Candidate) => void
  onAgain: (change?: Change) => void
  onDiscard: () => void
  onZoom: (url: string) => void
  onSaveOutfit: (slots: Dict, url: string) => void
  onError: (msg: string) => void
}) {
  const { t } = useTranslation('studio')
  const p = att.params || {}
  const kind = p.kind as PromptKind | undefined
  // the hub writes parts, the code joins the line; without parts (area edit, line via API) the line itself is edited
  const parted = !!p.slots && 'takes' in p.slots
  const inpaint = att.kind === 'inpaint'
  const [tab, setTab] = useState<'parts' | 'line'>(parted ? 'parts' : 'line')
  const [ti, setTi] = useState(0)
  const [over, setOver] = useState<Change | null>(null)
  const [editLine, setEditLine] = useState(false)
  const [remembered, setRemembered] = useState('')
  const [picked, setPicked] = useState('')
  const [keepSrc, setKeepSrc] = useState(false)
  const sig = useRef('')

  const slots = over?.slots ?? (parted ? p.slots : null)
  const prompt = over?.prompt ?? att.prompt
  const hand = over ? over.hand : !!p.hand
  const changed = !!over && (over.prompt !== att.prompt || over.hand !== !!p.hand)
  const cyr = CYRILLIC.test(prompt)

  // editing a chip rebuilds the line in code, without the hub
  const rebuild = async (s: Dict, wardrobeKey = '') => {
    try {
      const r = await api.post(`${c()}/image-prompt/rebuild`, {
        slots: s, kind, view: p.view || 'interior', register: p.register || '', wardrobe: wardrobeKey,
      })
      sig.current = JSON.stringify(r.slots || s)
      setOver({ slots: r.slots || s, prompt: r.prompt || '', hand: false, prompts: r.prompts })
    } catch (e: any) { onError(e?.message || t('err.rebuild_failed')) }
  }

  useEffect(() => {
    if (!over?.slots || over.hand) return
    const now = JSON.stringify(over.slots)
    if (now === sig.current) return
    const t = window.setTimeout(() => { sig.current = now; void rebuild(over.slots!) }, 150)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [over?.slots])

  const setSlots = (next: Dict) => setOver({ slots: next, prompt, hand: false, prompts: over?.prompts })
  const setTakeField = (i: number, key: string, v: string) => setSlots({
    ...(slots || {}),
    takes: ((slots?.takes as Dict[]) || []).map((t, j) => (j === i ? { ...t, [key]: v } : t)),
  })
  const takes: Dict[] = parted && slots ? (slots.takes as Dict[]) || [] : []
  const shownPrompt = (tab === 'line' && over?.prompts?.[ti]) || prompt
  const setField = (key: string, v: unknown) => setSlots({ ...(slots || {}), [key]: v })

  const live = !draft && isLive(att.status)
  const ready = att.status === 'ready' || att.status === 'done'
  const ratio = `${att.width} / ${att.height}`
  const n = att.n_images || 1
  const again = dest === 'scene' && !inpaint ? t('again_once') : t('again_n', { n })

  const chips: string[] = []
  if (inpaint) chips.push(t('chip_edit'), strengthTitle(att.denoise))
  else {
    if (p.kind) chips.push(kindTitle(p))
    if (p.register) chips.push(registerTitle(p.register))
    chips.push(aspectBySize(att.width, att.height))
  }
  // no register chosen: the hub picked a corner of the world with its own palette
  const corner = !inpaint && !p.register && p.slots?.corner ? registerTitle(p.slots.corner) : ''
  const left = att.status === 'ready' && att.expires_at ? hoursLeft(att.expires_at) : null
  const canRemember = kind === 'person' && !!slots
    && !!(slots.wear as string[] | undefined)?.length

  const candBar = (cd: Candidate) => {
    if (kept?.id === cd.id) return <span className="st-kept-l">{kept.label}</span>
    if (kept) return null
    const zoom = <button type="button" className="ghost tiny st-ico" title={t('zoom')}
      onClick={() => onZoom(cd.url)}>⤢</button>
    const brush = <button type="button" className="ghost tiny st-ico" title={t('brush.brush')}
      disabled={busy} onClick={() => onBrush(cd)}><IconBrush size={12} /></button>
    if (dest === 'replace') return (
      <>
        <button type="button" className="tiny primary" disabled={busy}
          onClick={() => onPick(cd, 'replace', keepSrc)}>{t('take_edit')}</button>
        <span className="sp" />{zoom}
      </>
    )
    if (dest === 'scene') return (
      <>
        <button type="button" className="tiny primary" disabled={busy}
          onClick={() => onPick(cd, 'scene')}>{t('to_collection')}</button>
        <span className="sp" />{brush}{zoom}
      </>
    )
    return (
      <>
        <button type="button" className="tiny primary" disabled={busy}
          onClick={() => onPick(cd, 'avatar')}>{t('as_portrait')}</button>
        <button type="button" className="tiny" disabled={busy}
          onClick={() => onPick(cd, 'media')}>{t('to_media')}</button>
        {canRemember && (
          <button type="button" className="ghost tiny" disabled={busy || remembered === cd.id}
            title={t('remember_look_hint')}
            onClick={() => { setRemembered(cd.id); onSaveOutfit(slots!, cd.url) }}>
            {remembered === cd.id ? t('look_remembered') : t('remember_look')}
          </button>
        )}
        <span className="sp" />{brush}{zoom}
      </>
    )
  }

  const promptBlock = (
    <div className="st-pr">
      <div className="st-pr-tabs">
        {parted && (
          <button type="button" className={`tb${tab === 'parts' ? ' on' : ''}`}
            onClick={() => setTab('parts')}>{t('tab.parts')}</button>
        )}
        {parted && (
          <button type="button" className={`tb${tab === 'line' ? ' on' : ''}`}
            onClick={() => setTab('line')}>{t('tab.prompt')}</button>
        )}
        {parted && n > 1 && takes.length > 1 && (
          <span className="st-takes">
            {takes.slice(0, n).map((_, i) => (
              <button key={i} type="button" className={`tb${ti === i ? ' on' : ''}`}
                title={t('take_hint')} onClick={() => setTi(i)}>{i + 1}</button>
            ))}
          </span>
        )}
        <span className="sp" />
        {hand && <span className="st-pill">{t('hand_edited')}</span>}
        {cyr && <span className="st-pill warn">{t('cyrillic')}</span>}
      </div>

      {tab === 'parts' && slots && kind && (
        <div className={`st-parts${hand ? ' stale' : ''}`}>
          {PARTS[kind].filter(([k, own]) => (own ? k in (takes[ti] || {}) : k in slots)).map(([k, own]) => (
            <Part key={`${k}${own ? ti : ''}`} label={t(k === 'subject' && kind === 'action' ? 'part.action' : PART_LABELS[k])}
              take={own && n > 1 ? ti : undefined}
              value={String((own ? takes[ti]?.[k] : slots[k]) ?? '')}
              onChange={v => (own ? setTakeField(ti, k, v) : setField(k, v))} />
          ))}
        </div>
      )}

      {tab === 'line' && (
        <>
          {inpaint && p.text && <div className="st-pr-src">{p.text}</div>}
          {editLine || draft
            ? <textarea autoFocus={!draft} rows={8} value={prompt}
                onChange={e => setOver({ slots: slots, prompt: e.target.value, hand: true })}
                onBlur={() => { if (!draft && !changed) setEditLine(false) }} />
            : <div className="st-pr-str" title={t('edit_by_hand')}
                onClick={() => setEditLine(true)}>{shownPrompt || '—'}</div>}
        </>
      )}

      {(changed || draft) && (
        <div className="st-pr-ft">
          {hand && parted && (
            <button type="button" className="ghost tiny"
              onClick={() => (slots ? void rebuild(slots) : setOver(null))}>{t('restore_build')}</button>
          )}
          {changed && !draft && (
            <button type="button" className="ghost tiny" onClick={() => setOver(null)}>{t('undo_edit')}</button>
          )}
          <button type="button" className="tiny primary" disabled={busy || cyr || !prompt.trim()}
            onClick={() => { onAgain({ prompt, slots, hand }); setOver(null); setEditLine(false) }}>
            {draft ? t('draw_n', { n }) : t('draw_edited_n', { n })}
          </button>
        </div>
      )}
    </div>
  )

  return (
    <div className={`st-att${open ? ' open' : ''}${live ? ' live' : ''}${n === 1 ? ' one' : ''}`}>
      <div className="st-att-hd" onClick={onToggle}>
        <span className="st-att-car">{open ? '▾' : '▸'}</span>
        <span className="st-att-no">{draft ? t('draft_title') : t('attempt_no', { no })}</span>
        {!draft && <span className="st-att-when">{when(att.created_at)}</span>}
        {chips.map(t => <span key={t} className="st-chip">{t}</span>)}
        {corner && <span className="st-chip auto" title={t('corner_auto')}>{corner}</span>}
        <span className="sp" />
        <span onClick={e => e.stopPropagation()} className="st-att-acts">
          {!draft && (
            <span className={`st-chip st-st ${att.status}`} title={left !== null ? t('expires_hint') : undefined}>
              {t(`status.${att.status}`)}{left !== null && ` · ${t('expires', { h: left })}`}
            </span>
          )}
          {dest === 'replace' && att.status === 'ready' && !kept && (
            <label className="st-keep-src">
              <input type="checkbox" checked={keepSrc} onChange={e => setKeepSrc(e.target.checked)} />
              {t('keep_source')}
            </label>
          )}
          {!draft && !live && !kept && (
            <button type="button" className="ghost tiny" disabled={busy || !att.prompt.trim()}
              onClick={() => onAgain()}>{again}</button>
          )}
          {!kept && (
            <button type="button" className="ghost tiny" disabled={busy} onClick={onDiscard}>
              {draft ? t('remove') : live ? t('common:cancel') : t('discard')}
            </button>
          )}
        </span>
      </div>

      {!open && att.candidates.length > 0 && (
        <div className="st-att-mini" onClick={onToggle}>
          {att.candidates.map(cd => (
            <img key={cd.id} src={thumbFull(cd.url, 240)} alt="" loading="lazy"
              className={kept?.id === cd.id ? 'kept' : ''} />
          ))}
        </div>
      )}

      {open && (
        <div className="st-att-main">
          {promptBlock}
          {att.status === 'failed' && <div className="st-att-err">{att.error || t('worker_failed')}</div>}
          {!draft && att.status !== 'failed' && (
            <div className={`st-cands${n === 1 ? ' one' : ''}`}>
              {ready
                ? att.candidates.map(cd => (
                    <figure key={cd.id}
                      className={`st-cand${picked === cd.id ? ' on' : ''}${kept?.id === cd.id ? ' kept' : ''}`}>
                      <div className="st-cand-shot" style={{ aspectRatio: ratio }}
                        onClick={() => setPicked(picked === cd.id ? '' : cd.id)}>
                        <img src={thumbFull(cd.url, n === 1 ? 960 : 480)} alt={t('candidate_alt')} loading="lazy" />
                      </div>
                      <div className="st-cand-bar">{candBar(cd)}</div>
                    </figure>
                  ))
                : Array.from({ length: n }, (_, i) => {
                    const cd = att.candidates[i]
                    return (
                      <figure key={cd?.id || i} className="st-cand">
                        <div className="st-cand-shot" style={{ aspectRatio: ratio }}>
                          {cd
                            ? <img src={thumbFull(cd.url, n === 1 ? 960 : 480)} alt={t('candidate_alt')} />
                            : <span className="wait">{t(`status.${att.status}`)}</span>}
                        </div>
                      </figure>
                    )
                  })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
