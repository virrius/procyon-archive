import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c, type Dict, thumbFull } from '../api'
import { useApp, useAsync } from '../ctx'
import { ImgActions, ImgFlags } from './ImageTools'
import Lightbox from './Lightbox'

/* --- вложения --------------------------------------------------------------- */

/** Вложения карточки: миниатюры плиткой, снимок разворачивается на весь экран,
 *  свой файл убирает загрузивший, чужой — ГМ. */
export default function EntityMedia({ entityId, bump, readonly, onChange, onBrush, tail }: {
  entityId: string; bump: number; readonly: boolean; onChange: () => void
  onBrush: (a: Dict) => void
  /** плитки «добавить» в конце сетки, на месте следующего снимка */
  tail?: ReactNode
}) {
  const { isGM, campaign } = useApp()
  const { t } = useTranslation('entity')
  const [rows, loading, reload, err] = useAsync<Dict[]>(
    () => api.get(`${c()}/attachments?target_type=entity&target_id=${entityId}`), [entityId, bump])
  const [shot, setShot] = useState(-1)
  const [oops, setOops] = useState('')
  const atts = rows || []
  const isImage = (a: Dict) => String(a.mime || '').startsWith('image/')
  const shots = atts.filter(isImage)
  const myMemberId = campaign?.my_member_id

  const drop = async (a: Dict) => {
    const name = a.caption || a.filename || t('page.file')
    if (!confirm(t('media.delete_confirm', { name }))) return
    setOops('')
    try {
      await api.del(`${c()}/attachments/${a.id}`)
      reload(); onChange()
    } catch (ex: any) { setOops(ex?.message || t('media.delete_failed')) }
  }

  // видимость поштучная: файл остаётся у ГМа, стол его просто не получает
  const setVis = async (a: Dict, hide: boolean) => {
    setOops('')
    try {
      await api.patch(`${c()}/attachments/${a.id}`, { visibility: hide ? 'gm' : 'crew' })
      reload(); onChange()
    } catch (ex: any) { setOops(ex?.message || t('media.vis_failed')) }
  }

  if (loading && !rows) return <div className="dim">{t('common:loading')}</div>
  if (err) return <div className="empty">{t('media.unavailable')}</div>
  if (!atts.length && !tail) return <div className="empty">{t('media.empty')}</div>

  return (
    <>
      {oops && <div className="lnk-err">{oops}</div>}
      <div className="att-grid">
        {atts.map(a => {
          const label = a.caption || a.filename || t('page.file')
          const mine = isGM || (!!myMemberId && a.uploaded_by === myMemberId)
          const i = shots.indexOf(a)
          const shut = isGM && a.visibility === 'gm'
          return (
            <div key={a.id} className={`att${shut ? ' att-shut' : ''}`} title={label}>
              <div className="att-box imgbox">
                {isImage(a)
                  ? <button type="button" className="att-shot" onClick={() => setShot(i)}
                      aria-label={t('media.open', { name: label })}>
                      <img src={thumbFull(a.url, 240, bump)} alt={label} loading="lazy" />
                    </button>
                  : <a className="att-shot att-file" href={a.url} target="_blank" rel="noreferrer">
                      <span className="att-ext">
                        {String(a.filename || '').split('.').pop()?.slice(0, 4) || t('page.file')}
                      </span>
                    </a>}
                <ImgFlags hidden={shut} />
                {!readonly && (
                  <ImgActions small
                    vis={isGM ? { hidden: shut, onChange: hide => setVis(a, hide) } : undefined}
                    inpaint={isGM && isImage(a) ? {
                      title: t('media.inpaint'), onClick: () => onBrush(a),
                    } : undefined}
                    remove={mine ? { title: t('media.delete_tip'), onClick: () => drop(a) } : undefined} />
                )}
              </div>
              <span className="att-cap">{label}</span>
            </div>
          )
        })}
        {tail}
      </div>

      {shot >= 0 && shots[shot] && (
        <Lightbox src={shots[shot].url} alt={shots[shot].filename}
          caption={shots.length > 1
            ? `${shots[shot].caption || shots[shot].filename} · ${shot + 1}/${shots.length}`
            : shots[shot].caption || shots[shot].filename}
          onClose={() => setShot(-1)}
          onPrev={shots.length > 1 ? () => setShot((shot - 1 + shots.length) % shots.length) : undefined}
          onNext={shots.length > 1 ? () => setShot((shot + 1) % shots.length) : undefined} />
      )}

    </>
  )
}
