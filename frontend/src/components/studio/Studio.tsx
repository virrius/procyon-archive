import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c, store, thumbFull, type Dict } from '../../api'
import { useApp } from '../../ctx'
import { useLayer } from '../../layers'
import { GenWorkerBadge } from '../GenWorkerBadge'
import Lightbox from '../Lightbox'
import AttemptCard, { type Change, type Pick } from './AttemptCard'
import MaskCanvas, { type MaskApi } from './MaskCanvas'
import { append, canDictate, useDictation } from './useDictation'
import {
  ASPECTS, CYRILLIC, KINDS, STRENGTH, VIEWS, aspectKey, aspectOf, codeRegisters, destOf, isLive,
  kindForEntity, rememberRegisters, startAspect,
  type Attempt, type Candidate, type FrameView, type Outfit, type PromptKind, type Register,
} from './kit'
import '../../styles.gallery.css'
import '../../styles.studio.css'

const POLL_MS = 2500
const SAVE_MS = 700

/** What the brush edits: a saved picture or an unpicked candidate of an attempt */
export type BrushSource = { id: string; url: string; title: string; sub: string }

type Pult = {
  draft: string; kind: PromptKind; view: FrameView; register: Register; aspect: string; outfit: string
  // portrait: who and gender; frame: whether there are people. Empty: the hub decides
  who: string; sex: string; people: string
}

const WHO = ['human', 'xenos']
const SEX = ['male', 'female']
const PEOPLE = ['some', 'none']

const sceneKey = () => `pa_scene_form:${store.campaign || ''}`

/** What a card's control panel stores on the server: the choices, and the description only if the GM edited it.
 *  An unedited description is rebuilt from the card: an appearance edit in the card reaches here on its own */
function formOf(p: Pult, auto: string): Dict {
  const { draft, ...forks } = p
  return draft.trim() && draft.trim() !== auto.trim() ? { ...forks, draft, edited: true } : forks
}

function loadScene(): Partial<Pult> {
  try {
    const raw = JSON.parse(localStorage.getItem(sceneKey()) || '{}')
    return { ...raw, draft: raw.draft ?? raw.text ?? '', aspect: aspectKey(raw.aspect) }
  } catch { return {} }
}

/** Studio: the control panel on the left (what to draw), the attempts feed on the right. One for a card portrait,
 *  a campaign frame and an area edit. Without entity: "Campaign frames". */
export default function Studio({ entity, source, embedded, onClose, onChanged }: {
  entity?: Dict
  /** open straight to the brush over this picture */
  source?: BrushSource | null
  /** embedded in the page ("Frames"), not a window over a card */
  embedded?: boolean
  onClose?: () => void
  /** something landed in the card or collection: time for the page to reload */
  onChanged?: (how?: Pick) => void
}) {
  const { t } = useTranslation('studio')
  const { isGM } = useApp()
  const scene = !entity
  const base = useMemo<Pult>(() => {
    if (scene) {
      const s = loadScene()
      const kind = (s.kind as PromptKind) || 'frame'
      const view = (s.view as FrameView) || 'interior'
      return { draft: s.draft || '', kind, view, register: (s.register as Register) || '',
               aspect: s.aspect || startAspect(kind, view), outfit: '', who: '', sex: '', people: s.people || '' }
    }
    const { kind, view } = kindForEntity(entity!)
    const look = String((entity!.kind === 'character' ? entity!.fields?.look : entity!.fields?.gm_appearance) || '').trim()
    const name = String(entity!.name || '').trim()
    const summary = String(entity!.summary || '').trim()
    const said = [summary, look].filter(Boolean).join(' ')
    const named = name && said.toLowerCase().startsWith(name.toLowerCase())
    return { draft: [named ? '' : name, said].filter(Boolean).join(', '),
             kind, view, register: '', aspect: startAspect(kind, view), outfit: '', who: '', sex: '', people: '' }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entity?.id])

  const [pult, setPultRaw] = useState<Pult>(base)
  const [loaded, setLoaded] = useState(scene)
  // panel memory is written only after a GM action: opening the studio is not an edit
  const touched = useRef(false)
  const setPult: typeof setPultRaw = v => { touched.current = true; setPultRaw(v) }
  const [attempts, setAttempts] = useState<Attempt[]>([])
  const [kept, setKept] = useState<Record<string, { att: Attempt; id: string; label: string }>>({})
  const [draftAtt, setDraftAtt] = useState<Attempt | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [phase, setPhase] = useState<'' | 'hub' | 'send'>('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [zoom, setZoom] = useState('')
  const [wardrobe, setWardrobe] = useState<Outfit[]>([])
  const [registers, setRegisters] = useState<[Register, string, string][] | null>(null)

  // brush
  const [brushSrc, setBrushSrc] = useState<BrushSource | null>(source || null)
  const [brush, setBrush] = useState(64)
  const [erase, setErase] = useState(false)
  const [painted, setPainted] = useState(false)
  const [ask, setAsk] = useState('')
  const [strength, setStrength] = useState(0)
  const mask = useRef<MaskApi>(null)
  const feedBox = useRef<HTMLDivElement>(null)

  useEffect(() => { if (source) { setBrushSrc(source); setAsk('') } }, [source])
  // the canvas sits above the feed: show it wherever the feed is scrolled
  useEffect(() => { if (brushSrc) feedBox.current?.scrollTo({ top: 0 }) }, [brushSrc])

  const stopped = useRef(false)
  const timer = useRef<number | undefined>(undefined)

  const listUrl = scene ? `${c()}/scene-jobs` : `${c()}/entities/${entity!.id}/image-jobs`
  const jobsUrl = scene ? `${c()}/scene-jobs` : `${c()}/entities/${entity!.id}/image-jobs`

  useLayer(!embedded, () => onClose?.())

  const mic = useDictation(
    text => (brushSrc ? setAsk(a => append(a, text)) : setPult(p => ({ ...p, draft: append(p.draft, text) }))),
    setErr, !!embedded)

  // --- feed -------------------------------------------------------------------

  const refresh = async () => {
    window.clearTimeout(timer.current)
    try {
      const rows: Attempt[] = await api.get(listUrl)
      if (stopped.current) return
      setAttempts(rows)
      if (rows.some(r => isLive(r.status))) timer.current = window.setTimeout(refresh, POLL_MS)
    } catch (e: any) {
      if (stopped.current) return
      setErr(e?.message || t('err.feed_failed'))
      timer.current = window.setTimeout(refresh, POLL_MS * 4)
    }
  }

  useEffect(() => {
    stopped.current = false
    void refresh()
    api.get(`${c()}/wardrobe`).then(r => setWardrobe(r?.wardrobe || [])).catch(() => {})
    api.get(`${c()}/registers`).then(r => {
      const rows = (r?.registers || []).map((x: Dict) => [x.key, x.title, x.hint] as [Register, string, string])
      if (rows.length) { rememberRegisters(rows); setRegisters(rows) }
    }).catch(() => {})
    return () => { stopped.current = true; window.clearTimeout(timer.current) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listUrl])

  // panel memory: on the server for a card, in the browser for "Frames"
  useEffect(() => {
    if (scene) return
    let dead = false
    api.get(`${c()}/entities/${entity!.id}/gen-form`)
      .then(r => {
        if (dead) return
        const f = (r?.form || {}) as Dict
        setPultRaw(p => ({
          draft: (f.edited && f.draft) || p.draft,
          kind: f.kind || p.kind,
          view: f.view || p.view,
          register: f.register || '',
          aspect: aspectKey(f.aspect) || (f.kind ? startAspect(f.kind, f.view || p.view) : p.aspect),
          outfit: f.outfit || '',
          who: f.who || '', sex: f.sex || '', people: f.people || '',
        }))
        setLoaded(true)
      })
      // memory didn't load: the panel works but doesn't overwrite what's saved
      .catch(() => {})
    return () => { dead = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entity?.id])

  useEffect(() => {
    if (!loaded || !touched.current) return
    if (scene) {
      try { localStorage.setItem(sceneKey(), JSON.stringify(pult)) } catch { /* disk full */ }
      return
    }
    const t = window.setTimeout(() => {
      api.put(`${c()}/entities/${entity!.id}/gen-form`, { form: formOf(pult, base.draft) }).catch(() => {})
    }, SAVE_MS)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, pult])

  const pickKind = (k: PromptKind) => setPult(p => ({ ...p, kind: k, aspect: startAspect(k, p.view) }))
  const pickView = (w: FrameView) => setPult(p => ({ ...p, view: w, aspect: startAspect(p.kind, w) }))

  // --- attempts ---------------------------------------------------------------

  const post = async (prompt: string, width: number, height: number, params: Dict) => {
    const j: Attempt = await api.post(jobsUrl, { prompt, width, height, params })
    setOpenId(j.id)
    await refresh()
  }

  const draw = async () => {
    const text = (pult.draft + ' ' + mic.interim).trim()
    if (!text) { setErr(t('err.describe')); return }
    mic.stop()
    setErr(''); setPhase('hub'); setDraftAtt(null)
    try {
      const r = await api.post(`${c()}/image-prompt`,
        { text, kind: pult.kind, register: pult.register, view: pult.view, wardrobe: outfit,
          who: pult.kind === 'person' ? pult.who : '', sex: pult.kind === 'person' ? pult.sex : '',
          people: pult.kind === 'person' ? '' : pult.people, seed_key: entity?.id || '', candidates: n })
      const box = aspectOf(pult.aspect)
      const params = {
        kind: pult.kind, view: pult.kind === 'frame' ? pult.view : undefined,
        register: pult.register, aspect: box.key, draft: text, slots: r.slots || null, hand: false,
        outfit: outfit || undefined,
      }
      // only the shown prompt is drawn: look and edit first, then "draw"
      setDraftAtt({
        id: 'draft', kind: 'txt2img', status: 'pending', error: '', entity_id: entity?.id || null,
        candidates: [], n_images: scene ? 1 : 4, prompt: r.prompt || '', width: box.width,
        height: box.height, denoise: 1, source_url: null, params, created_at: new Date().toISOString(),
      })
      setOpenId('draft')
    } catch (e: any) {
      setErr(e?.message || t('err.generic'))
    } finally {
      setPhase('')
    }
  }

  const again = async (a: Attempt, ch?: Change) => {
    setErr(''); setBusy(true)
    try {
      if (a.id === 'draft') {
        setDraftAtt(null)
        await post(ch?.prompt ?? a.prompt, a.width, a.height,
          { ...a.params, slots: ch?.slots ?? a.params.slots, hand: ch?.hand ?? false })
      } else if (a.kind === 'inpaint') {
        const j: Attempt = await api.post(`${c()}/inpaint-jobs/${a.id}/again`, { prompt: ch?.prompt || '' })
        setOpenId(j.id)
        await refresh()
      } else {
        await post(ch?.prompt ?? a.prompt, a.width, a.height,
          { ...a.params, slots: ch?.slots ?? a.params?.slots ?? null, hand: ch ? ch.hand : !!a.params?.hand })
      }
    } catch (e: any) {
      setErr(e?.message || t('err.queue_failed'))
    } finally {
      setBusy(false)
    }
  }

  const discardUrl = (a: Attempt) =>
    a.kind === 'inpaint' ? `${c()}/inpaint-jobs/${a.id}`
      : scene ? `${c()}/scene-jobs/${a.id}` : `${c()}/image-jobs/${a.id}`

  const discard = async (a: Attempt) => {
    if (a.id === 'draft') { setDraftAtt(null); return }
    if (a.status === 'ready' && !confirm(t('discard_confirm'))) return
    setBusy(true); setErr('')
    try { await api.del(discardUrl(a)); await refresh() }
    catch (e: any) { setErr(e?.message || t('err.discard_failed')) }
    finally { setBusy(false) }
  }

  const pick = async (a: Attempt, cd: Candidate, how: Pick, keepSource?: boolean) => {
    setBusy(true); setErr('')
    try {
      if (how === 'replace') {
        await api.post(`${c()}/inpaint-jobs/${a.id}/pick`, { candidate_id: cd.id, keep_source: !!keepSource })
        if (brushSrc && !keepSource) setBrushSrc(null)
      } else if (how === 'scene') {
        await api.post(`${c()}/scene-jobs/${a.id}/keep`, { candidate_id: cd.id })
      } else {
        await api.post(`${c()}/image-jobs/${a.id}/pick`, { candidate_id: cd.id, set_avatar: how === 'avatar' })
      }
      setKept(k => ({ ...k, [a.id]: { att: { ...a, status: 'done', candidates: [cd] }, id: cd.id, label: how } }))
      await refresh()
      onChanged?.(how)
    } catch (e: any) {
      setErr(e?.message || t('err.pick_failed'))
    } finally {
      setBusy(false)
    }
  }

  // look: the outfit of a good frame; from here on it's inserted verbatim into every frame
  const saveOutfit = async (slots: Dict, image: string) => {
    const wear = ((slots.wear as string[]) || []).filter(Boolean)
    if (!wear.length) { setErr(t('err.no_wear')); return }
    const base = entity?.name ? `${entity.name}` : t('look_default')
    const taken = new Set(wardrobe.map(o => o.title))
    let title = base
    for (let i = 2; taken.has(title); i++) title = `${base} ${i}`
    try {
      const r = await api.post(`${c()}/wardrobe`, { title, wear, image })
      setWardrobe(r?.wardrobe || [])
      if (r?.key) setPult(p => ({ ...p, outfit: r.key }))
    } catch (e: any) { setErr(e?.message || t('err.look_save_failed')) }
  }

  const renameOutfit = async (o: Outfit, title: string) => {
    if (!title.trim() || title.trim() === o.title) return
    try {
      const r = await api.put(`${c()}/wardrobe/${encodeURIComponent(o.key)}`, { ...o, title: title.trim() })
      setWardrobe(r?.wardrobe || [])
    } catch (e: any) { setErr(e?.message || t('err.rename_failed')) }
  }

  const dropOutfit = async (o: Outfit) => {
    if (!confirm(t('forget_confirm', { title: o.title }))) return
    try {
      const r = await api.del(`${c()}/wardrobe/${encodeURIComponent(o.key)}`)
      setWardrobe(r?.wardrobe || [])
      setPult(p => (p.outfit === o.key ? { ...p, outfit: '' } : p))
    } catch (e: any) { setErr(e?.message || t('err.forget_failed')) }
  }

  // --- brush ------------------------------------------------------------------

  const brushOn = (cd: Candidate, no: number) => {
    mic.stop()
    setBrushSrc({ id: cd.id, url: cd.url, title: t('brush.source_title', { no }), sub: t('brush.not_picked') })
    setAsk(''); setErr('')
  }

  const inpaint = async () => {
    if (!brushSrc) return
    const said = (ask + ' ' + mic.interim).trim()
    if (!said) { setErr(t('err.no_ask')); return }
    if (!mask.current?.hasPaint()) { setErr(t('err.no_paint')); return }
    mic.stop()
    setErr(''); setPhase('hub')
    try {
      // without the source prompt an area edit redraws the whole frame: a read failure stops, no guessing
      const baseRow = await api.get(`${c()}/inpaint-base/${brushSrc.id}`)
      const r = await api.post(`${c()}/inpaint-prompt`, { text: said, base_prompt: baseRow?.prompt || '' })
      const prompt = String(r.prompt || '').trim()
      if (!prompt || CYRILLIC.test(prompt)) throw new Error(t('err.not_english'))
      setPhase('send')
      const blob = await mask.current!.blob()
      if (!blob) throw new Error(t('err.mask_failed'))
      const fd = new FormData()
      fd.append('source_attachment_id', brushSrc.id)
      fd.append('prompt', prompt)
      fd.append('denoise', String(STRENGTH[strength][1]))
      fd.append('text', said)
      fd.append('mask', blob, 'mask.png')
      const j: Attempt = await api.post(`${c()}/inpaint-jobs`, fd)
      setOpenId(j.id)
      await refresh()
    } catch (e: any) {
      setErr(e?.message || t('err.inpaint_failed'))
    } finally {
      setPhase('')
    }
  }

  // --- layout -----------------------------------------------------------------

  const feed = useMemo(() => {
    const live = attempts.map(a => ({ a, kept: undefined as undefined | { id: string; label: string } }))
    const done = Object.values(kept).filter(k => !attempts.some(a => a.id === k.att.id))
      .map(k => ({ a: k.att, kept: { id: k.id, label: k.label } }))
    const all = [...live, ...done].sort((x, y) => (x.a.created_at < y.a.created_at ? 1 : -1))
    return all.map((r, i) => ({ ...r, no: all.length - i }))
  }, [attempts, kept])

  const openOf = (id: string, i: number) => (openId ? openId === id : i === 0)
  const working = !!phase || busy
  const n = scene ? 1 : 4
  const box = aspectOf(pult.aspect)
  const outfit = pult.kind === 'person' && wardrobe.some(o => o.key === pult.outfit) ? pult.outfit : ''
  const curOutfit = wardrobe.find(o => o.key === outfit)

  const left = brushSrc ? (
    <div className="st-left">
      <button type="button" className="ghost tiny st-back" disabled={working}
        onClick={() => { mic.stop(); setBrushSrc(null); setErr('') }}>{t('brush.back')}</button>
      <div className="st-src">
        <img src={thumbFull(brushSrc.url, 240)} alt="" />
        <div><div className="t">{t('brush.area_edit')}</div><div className="s">{brushSrc.title}</div></div>
      </div>
      <div className="st-lp">
        <label>{t('brush.label')}</label>
        <div className="st-opts">
          <button type="button" className={`eg-tog${erase ? '' : ' on'}`} onClick={() => setErase(false)}>{t('brush.brush')}</button>
          <button type="button" className={`eg-tog${erase ? ' on' : ''}`} onClick={() => setErase(true)}>{t('brush.eraser')}</button>
          <span className="sp" />
          <button type="button" className="ghost tiny" title={t('brush.undo')} onClick={() => mask.current?.undo()}>↶</button>
          <button type="button" className="ghost tiny" disabled={!painted} onClick={() => mask.current?.clear()}>{t('clear')}</button>
        </div>
        <div className="st-brush">
          <input type="range" min={8} max={256} step={4} value={brush}
            onChange={e => setBrush(Number(e.target.value))} />
          <span className="v">{brush}</span>
        </div>
      </div>
      <div className="st-lp">
        <div className="st-lp-hd">
          <label>{t('brush.ask')}</label><span className="sp" />
          {canDictate && (
            <button type="button" className={`ghost tiny st-mic${mic.listening ? ' on' : ''}`}
              onClick={mic.toggle}><i className="dot" />{t('speak')}</button>
          )}
        </div>
        <textarea rows={4} value={ask + (mic.interim ? ' ' + mic.interim : '')}
          onChange={e => setAsk(e.target.value)} />
      </div>
      <div className="st-lp second">
        <label>{t('strength_label')}</label>
        <div className="st-opts">
          {STRENGTH.map(([k], i) => (
            <button key={k} type="button" className={`eg-tog${strength === i ? ' on' : ''}`}
              title={t(`strength.${k}_hint`)} onClick={() => setStrength(i)}>{t(`strength.${k}`)}</button>
          ))}
        </div>
      </div>
      {err && <div className="eg-err">{err}</div>}
      <div className="st-go">
        <button type="button" className="primary" disabled={working || !painted || !(ask + mic.interim).trim()}
          onClick={inpaint}>
          {phase === 'hub' ? t('brush.writing') : phase === 'send' ? t('brush.sending') : t('brush.go')}
        </button>
      </div>
    </div>
  ) : (
    <div className="st-left">
      <div className="st-lp">
        <div className="st-lp-hd">
          <label>{t('description')}</label><span className="sp" />
          <button type="button" className="ghost tiny" disabled={!pult.draft && !mic.interim}
            onClick={() => setPult(p => ({ ...p, draft: '' }))}>{t('clear')}</button>
          {canDictate && (
            <button type="button" className={`ghost tiny st-mic${mic.listening ? ' on' : ''}`}
              title={embedded ? t('space_key') : undefined} onClick={mic.toggle}>
              <i className="dot" />{t('speak')}
            </button>
          )}
        </div>
        <textarea value={pult.draft + (mic.interim ? ' ' + mic.interim : '')}
          onChange={e => setPult(p => ({ ...p, draft: e.target.value }))} />
      </div>
      <div className="st-lp">
        <label>{t('direction')}</label>
        <div className="st-opts">
          {KINDS.map(k => (
            <button key={k} type="button" className={`eg-tog${pult.kind === k ? ' on' : ''}`}
              title={t(`kind_hint.${k}`)} onClick={() => pickKind(k)}>{t(`kind.${k}`)}</button>
          ))}
        </div>
      </div>
      {pult.kind === 'frame' && (
        <div className="st-lp">
          <label>{t('subtype')}</label>
          <div className="st-opts">
            {VIEWS.map(w => (
              <button key={w} type="button" className={`eg-tog${pult.view === w ? ' on' : ''}`}
                title={t(`view_hint.${w}`)} onClick={() => pickView(w)}>{t(`view.${w}`)}</button>
            ))}
          </div>
        </div>
      )}
      <div className="st-lp second">
        <label>{t('register_label')}</label>
        <div className="st-opts">
          {(registers ?? codeRegisters()).map(([r, label, hint]) => (
            <button key={r} type="button" className={`eg-tog${pult.register === r ? ' on' : ''}`}
              title={hint}
              onClick={() => setPult(p => ({ ...p, register: p.register === r ? '' : r }))}>{label}</button>
          ))}
        </div>
      </div>
      {pult.kind === 'person' && !scene && (
        <div className="st-lp">
          <label>{t('look_label')}</label>
          {wardrobe.length ? (
            <div className="st-looks">
              <button type="button" className={`st-look none${outfit ? '' : ' on'}`}
                onClick={() => setPult(p => ({ ...p, outfit: '' }))}>{t('look_as_described')}</button>
              {wardrobe.map(o => (
                <button key={o.key} type="button" className={`st-look${outfit === o.key ? ' on' : ''}`}
                  title={o.wear.join(' · ')}
                  onClick={() => setPult(p => ({ ...p, outfit: p.outfit === o.key ? '' : o.key }))}>
                  {o.image ? <img src={thumbFull(o.image, 240)} alt="" /> : <i />}
                  <span>{o.title}</span>
                </button>
              ))}
            </div>
          ) : (
            <div className="st-hint">{t('look_hint')}</div>
          )}
          {curOutfit && isGM && (
            <div className="st-look-cur">
              <span className="w">{curOutfit.wear.join(' · ')}</span>
              <div className="st-opts">
                <input className="st-look-name" key={curOutfit.key} defaultValue={curOutfit.title}
                  title={t('look_name')}
                  onBlur={e => void renameOutfit(curOutfit, e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} />
                <button type="button" className="ghost tiny" onClick={() => void dropOutfit(curOutfit)}>{t('forget')}</button>
              </div>
            </div>
          )}
        </div>
      )}
      {pult.kind === 'person' ? (
        <div className="st-lp">
          <label>{t('who_label')}</label>
          <div className="st-opts">
            {WHO.map(k => (
              <button key={k} type="button" className={`eg-tog${pult.who === k ? ' on' : ''}`}
                onClick={() => setPult(p => ({ ...p, who: p.who === k ? '' : k }))}>{t(`who.${k}`)}</button>
            ))}
            <span className="st-opt-gap" />
            {SEX.map(k => (
              <button key={k} type="button" className={`eg-tog${pult.sex === k ? ' on' : ''}`}
                onClick={() => setPult(p => ({ ...p, sex: p.sex === k ? '' : k }))}>{t(`sex.${k}`)}</button>
            ))}
          </div>
        </div>
      ) : (
        <div className="st-lp">
          <label>{t('people_label')}</label>
          <div className="st-opts">
            {PEOPLE.map(k => (
              <button key={k} type="button" className={`eg-tog${pult.people === k ? ' on' : ''}`}
                onClick={() => setPult(p => ({ ...p, people: p.people === k ? '' : k }))}>{t(`people.${k}`)}</button>
            ))}
          </div>
        </div>
      )}
      <div className="st-sep" />
      <div className="st-lp">
        <label>{t('format')}</label>
        <div className="st-opts">
          {ASPECTS.map(a => (
            <button key={a.key} type="button" className={`eg-tog st-asp${pult.aspect === a.key ? ' on' : ''}`}
              title={`${a.width}×${a.height}`} onClick={() => setPult(p => ({ ...p, aspect: a.key }))}>
              <i style={{ width: Math.round(a.width / 96), height: Math.round(a.height / 96) }} />{a.key}
            </button>
          ))}
        </div>
      </div>
      {err && <div className="eg-err">{err}</div>}
      <div className="st-go">
        <button type="button" className="primary" disabled={working || !loaded}
          title={t('show_prompt_hint')} onClick={() => draw()}>
          {phase === 'hub' ? t('writing_prompt') : t('show_prompt')}
        </button>
      </div>
    </div>
  )

  const right = (
    <div className="st-feed" ref={feedBox}>
      <div className="st-feed-hd">
        <span className="t">{t('attempts')}</span>
        {feed.length > 0 && <span className="n">{feed.length}</span>}
      </div>
      {brushSrc && (
        <div className="st-cv">
          <div className="st-cv-hd"><span className="t">{t('canvas')}</span><span className="s">{brushSrc.title}</span></div>
          <div className="st-cv-wrap">
            <MaskCanvas ref={mask} key={brushSrc.id} src={brushSrc.url} brush={brush} erase={erase}
              locked={working} onPaint={setPainted} />
          </div>
        </div>
      )}
      {phase === 'hub' && !brushSrc && (
        <div className="st-att live"><div className="st-att-hd">
          <span className="st-att-car">▸</span><span className="st-att-no">{t('writing_prompt')}</span>
        </div></div>
      )}
      {draftAtt && (
        <AttemptCard att={draftAtt} no={0} draft open={openId === 'draft'}
          onToggle={() => setOpenId(openId === 'draft' ? '' : 'draft')}
          dest={scene ? 'scene' : 'entity'} busy={working}
          onPick={() => {}} onBrush={() => {}} onAgain={ch => again(draftAtt, ch)}
          onDiscard={() => setDraftAtt(null)} onZoom={setZoom}
          onSaveOutfit={() => {}} onError={setErr} />
      )}
      {feed.map(({ a, kept: k, no }, i) => (
        <AttemptCard key={a.id} att={a} no={no} kept={k && { ...k, label: t(`kept.${k.label}`) }}
          open={!draftAtt && openOf(a.id, i)}
          onToggle={() => setOpenId(openOf(a.id, i) ? '' : a.id)}
          dest={destOf(a)} busy={working}
          onPick={(cd, how, ks) => pick(a, cd, how, ks)}
          onBrush={cd => brushOn(cd, no)}
          onAgain={ch => again(a, ch)}
          onDiscard={() => discard(a)}
          onZoom={setZoom}
          onSaveOutfit={(s, url) => saveOutfit(s, url)}
          onError={setErr} />
      ))}
      {!feed.length && !draftAtt && phase !== 'hub' && !brushSrc && (
        <div className="st-stencil">
          <div className="row">
            {Array.from({ length: n }, (_, i) => (
              <i key={i} style={{ aspectRatio: `${box.width} / ${box.height}` }} />
            ))}
          </div>
          <span className="t">{t('no_attempts')}</span>
        </div>
      )}
    </div>
  )

  const shell = (
    <div className={`st ${embedded ? 'st-embed' : 'st-modal'}`} onMouseDown={e => e.stopPropagation()}>
      <div className="st-hd">
        {entity?.image_url && <img className="st-ava" src={thumbFull(entity.image_url, 240)} alt="" />}
        <span className="st-title">{t('title')}</span>
        {entity && <span className="st-name">{entity.name}</span>}
        <span className="sp" />
        {!embedded && <GenWorkerBadge compact />}
        {!embedded && <button type="button" className="ghost st-x" title={t('common:close')} onClick={onClose}>×</button>}
      </div>
      <div className="st-body">{left}{right}</div>
      {zoom && <Lightbox src={zoom} onClose={() => setZoom('')} />}
    </div>
  )

  if (embedded) return shell
  return (
    <div className="backdrop st-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose?.() }}>
      {shell}
    </div>
  )
}
