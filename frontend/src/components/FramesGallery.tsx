import { useEffect, useMemo, useRef, useState, type DragEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c, isPublicView, thumb, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import i18n, { lang, locale } from '../i18n'
import { IconPlus } from './icons'
import { ImgActions, ImgFlags } from './ImageTools'
import Lightbox from './Lightbox'
import PasteImage from '../paste'
import '../styles.frames.css'

export type Frame = {
  id: string; url: string; caption: string
  width: number; height: number; created_at?: string
  /** кадр завёл этот участник: свой можно подписать и убрать */
  mine?: boolean
  visibility?: string; prompt?: string
}

// кадров бывает сотня: дорисовываем ленту порциями, когда до конца доскроллили
const STEP = 60

const time = (iso?: string) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/** день кадра — заголовок ленты: дни совпадают с сессиями */
const day = (iso?: string) => {
  if (!iso) return ''
  const d = new Date(iso)
  const dm = d.toLocaleDateString(locale(), { day: 'numeric', month: 'long' })
  return d.getFullYear() === new Date().getFullYear() ? dm : i18n.t('media:day_year', { day: dm, year: d.getFullYear() })
}

/** Коллекция кадров кампании: снимки одного размера, подпись под каждым. Свой кадр
 *  участник подписывает и убирает сам, любой — ГМ; видимость держит только ГМ. */
export default function FramesGallery({ tick, onBrush }: {
  tick?: number
  /** кисть по кадру — правка уходит в мастерскую над коллекцией */
  onBrush?: (f: Frame) => void
}) {
  const { t } = useTranslation('media')
  const lng = lang()
  const { campaign, isGM } = useApp()
  const role = campaign?.my_role || ''
  // кадр заводит весь стол; чужой кадр правит и убирает только ГМ
  const canAdd = (role === 'gm' || role === 'player') && !isPublicView()
  const isRealGM = isGM && !isPublicView()
  const [uploading, setUploading] = useState(false)
  const [over, setOver] = useState(false)      // над панелью тащат файл
  const pick = useRef<HTMLInputElement>(null)
  const depth = useRef(0)                      // dragleave стреляет и на детях панели
  const [frames, loading, reload, loadErr] = useAsync<Frame[]>(
    () => api.get(`${c()}/scene-frames`), [tick || 0])
  const [limit, setLimit] = useState(STEP)
  const tail = useRef<HTMLDivElement>(null)
  const [zoom, setZoom] = useState(-1)
  const [err, setErr] = useState('')

  const rows = frames || []
  const more = rows.length > limit
  // сервер отдаёт свежие сверху — режем ленту на дни по порядку
  const days = useMemo(() => {
    const out: [string, [Frame, number][]][] = []
    rows.slice(0, limit).forEach((f, i) => {
      const d = day(f.created_at)
      if (out.length && out[out.length - 1][0] === d) out[out.length - 1][1].push([f, i])
      else out.push([d, [[f, i]]])
    })
    return out
  }, [rows, limit, lng])

  useEffect(() => {
    const el = tail.current
    if (!el || !more) return
    const io = new IntersectionObserver(ents => {
      if (ents.some(x => x.isIntersecting)) setLimit(n => n + STEP)
    })
    io.observe(el)
    return () => io.disconnect()
  }, [more, limit])

  const patch = async (f: Frame, body: Dict) => {
    setErr('')
    try { await api.patch(`${c()}/scene-frames/${f.id}`, body); reload() }
    catch (e: any) { setErr(e?.message || t('err.save_failed')) }
  }

  const drop = async (f: Frame) => {
    if (!confirm(t('frame_delete_confirm'))) return
    setErr('')
    try { await api.del(`${c()}/scene-frames/${f.id}`); reload() }
    catch (e: any) { setErr(e?.message || t('err.delete_failed')) }
  }

  /** свои файлы — те же кадры коллекции, только без промпта и очереди */
  const upload = async (files: FileList | File[] | null) => {
    const pics = Array.from(files || []).filter(f => f.type.startsWith('image/'))
    if (!pics.length) {
      if (files && files.length) setErr(t('err.only_images'))
      return
    }
    setErr(''); setUploading(true)
    try {
      for (const file of pics) {
        const fd = new FormData()
        fd.append('file', file)
        fd.append('target_type', 'scene_frame')
        await api.post(`${c()}/upload`, fd)
      }
      reload()
    } catch (e: any) { setErr(e?.message || t('err.upload_failed')); reload() }
    finally { setUploading(false) }
  }

  // снимок из буфера — тот же кадр коллекции
  const paste = (
    <PasteImage enabled={canAdd} onFiles={files => upload(files)}
      question={t('paste_question')} />
  )

  // на панель можно просто бросить файлы из проводника. Тип содержимого не проверяем:
  // в Safari и в синтетических событиях dataTransfer.types пуст до самого drop —
  // картинку от прочего отсеиваем уже в upload
  const dnd = canAdd ? {
    onDragEnter: () => { depth.current += 1; setOver(true) },
    onDragOver: (e: DragEvent) => {
      e.preventDefault()          // без этого браузер просто откроет файл вместо drop
      e.dataTransfer.dropEffect = 'copy'
    },
    onDragLeave: () => {
      depth.current = Math.max(0, depth.current - 1)
      if (!depth.current) setOver(false)
    },
    onDrop: (e: DragEvent) => {
      e.preventDefault()
      depth.current = 0
      setOver(false)
      upload(e.dataTransfer.files)
    },
  } : {}

  // трафарет карточки: та же плитка, но пустая — кликнул, выбрал файл, кадр в коллекции.
  // input держим рядом, а не внутри кнопки: вложенный он открывает диалог дважды
  const addTile = canAdd && (
    <div className={`frame-card frame-add${uploading ? ' busy' : ''}${over ? ' over' : ''}`}
      key="add">
      <button type="button" className="frame-shot" disabled={uploading}
        onClick={() => pick.current?.click()}>
        <span className="frame-add-in">
          <IconPlus size={20} />
          <span>
            {uploading ? t('uploading') : over ? t('drop_here')
              : t('add_hint')}
          </span>
        </span>
      </button>
      <input ref={pick} type="file" accept="image/*" multiple hidden
        onChange={e => { upload(e.target.files); e.target.value = '' }} />
    </div>
  )

  if (loading) return <div className="panel dim2 small">{t('frames_loading')}</div>
  if (loadErr) return <div className="panel eg-err">{loadErr}</div>
  if (!rows.length) {
    return (
      <div className={`panel col frames-panel${over ? ' over' : ''}`} {...dnd}>
        <h3>{t('collection')}</h3>
        <div className="dim2 small">
          {canAdd
            ? t('empty_can_add')
            : t('empty')}
        </div>
        {addTile && <div className="frames-grid">{addTile}</div>}
        {err && <div className="eg-err">{err}</div>}
        {paste}
      </div>
    )
  }

  return (
    <div className={`panel col frames-panel${over ? ' over' : ''}`} {...dnd}>
      {paste}
      <div className="row wrap frames-bar">
        <h3>{t('collection')}</h3>
        <span className="frames-count">{rows.length}</span>
      </div>

      {err && <div className="eg-err">{err}</div>}

      {addTile && <div className="frames-grid">{addTile}</div>}

      {days.map(([d, items]) => (
        <section key={d || '—'} className="frames-day">
          <div className="frames-day-hd">
            <span className="t">{d}</span>
            <span className="frames-count">{items.length}</span>
          </div>
          <div className="frames-grid">
        {items.map(([f, i]) => (
          <figure key={f.id} className={`frame-card${f.visibility === 'gm' ? ' hidden gm-only' : ''}`}>
            <div className="frame-shot imgbox">
              <img src={thumb(f.url, 480)} alt={f.caption || t('frame_alt')} loading="lazy"
                onClick={() => setZoom(i)} />
              <ImgFlags hidden={f.visibility === 'gm'} />
              {(isRealGM || (canAdd && f.mine)) && (
                <ImgActions
                  vis={isRealGM ? {
                    hidden: f.visibility === 'gm',
                    onChange: hide => patch(f, { visibility: hide ? 'gm' : 'crew' }),
                  } : undefined}
                  inpaint={onBrush ? { title: t('frame_inpaint'), onClick: () => onBrush(f) } : undefined}
                  remove={{ title: t('frame_delete'), onClick: () => drop(f) }} />
              )}
            </div>
            <figcaption>
              <FrameCaption frame={f} canEdit={isRealGM || (canAdd && !!f.mine)}
                onSave={text => patch(f, { caption: text })} />
              <div className="frame-when">{time(f.created_at)}</div>
            </figcaption>
          </figure>
        ))}
          </div>
        </section>
      ))}
      {more && <div ref={tail} />}


      {zoom >= 0 && rows[zoom] && (
        <Lightbox src={rows[zoom].url} caption={rows[zoom].caption}
          onClose={() => setZoom(-1)}
          onPrev={zoom > 0 ? () => setZoom(zoom - 1) : undefined}
          onNext={zoom < rows.length - 1 ? () => setZoom(zoom + 1) : undefined} />
      )}
    </div>
  )
}

/** Подпись: у стола — текст, у ГМа — то же место, но правится по клику. */
export function FrameCaption({ frame, canEdit, onSave }: {
  frame: Frame
  canEdit: boolean
  onSave: (text: string) => void
}) {
  const { t } = useTranslation('media')
  const [edit, setEdit] = useState(false)
  const [text, setText] = useState(frame.caption || '')

  useEffect(() => { setText(frame.caption || '') }, [frame.caption])

  if (!canEdit) {
    return frame.caption
      ? <div className="frame-cap">{frame.caption}</div>
      : <div className="frame-cap none" />
  }

  const commit = () => {
    setEdit(false)
    if (text.trim() !== (frame.caption || '')) onSave(text.trim())
  }

  if (!edit) {
    return (
      <button type="button" className={`frame-cap edit${frame.caption ? '' : ' none'}`}
        title={t('caption_edit')} onClick={() => setEdit(true)}>
        {frame.caption || t('caption_add')}
      </button>
    )
  }

  return (
    <textarea className="frame-cap-box" rows={2} autoFocus value={text}
      placeholder={t('caption_placeholder')}
      onChange={e => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); commit() }
        if (e.key === 'Escape') { e.stopPropagation(); setText(frame.caption || ''); setEdit(false) }
      }} />
  )
}
