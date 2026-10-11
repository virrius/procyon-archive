import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c, type Dict, thumbFull } from '../api'
import { useAsync } from '../ctx'
import { Modal } from '../ui'
import '../styles.gallery.css'

/** Выбор портрета из уже сохранённых медиа кампании: свои вложения карточки идут
 *  первыми, дальше вся остальная библиотека — один и тот же файл может быть
 *  портретом нескольких карточек, ничего не копируется. */
export function MediaPickModal({ entityId, current, onClose, onPick }: {
  entityId: string
  current?: string
  onClose: () => void
  onPick: (url: string) => Promise<void> | void
}) {
  const { t } = useTranslation('media')
  const [rows, loading, , err] = useAsync<Dict[]>(() => api.get(`${c()}/attachments`), [entityId])
  // файлы карточек подписываем именем карточки: имена файлов генерации ничего не говорят
  const [cards] = useAsync<Dict[]>(() => api.get(`${c()}/entities?limit=2000`), [])
  const [busy, setBusy] = useState(false)
  const [oops, setOops] = useState('')
  const [onlyMine, setOnlyMine] = useState(true)

  const names = new Map<string, string>((cards || []).map(e => [String(e.id), String(e.name || '')]))
  const images = (rows || []).filter(a => String(a.mime || '').startsWith('image/'))
  const mine = images.filter(a => a.target_type === 'entity' && a.target_id === entityId)
  // служебные файлы (маски и исходники правки, кандидаты, развороты книги, картинки досок)
  // портретом не бывают — в библиотеке только три источника
  const groups: [string, Dict[]][] = [
    ['frames', images.filter(a => a.target_type === 'scene_frame')],
    ['other_entries', images.filter(a => a.target_type === 'entity' && a.target_id !== entityId)],
    ['uploads', images.filter(a => !a.target_type)],
  ]
  const library = groups.reduce((n, [, list]) => n + list.length, 0)
  const showMine = onlyMine && mine.length > 0

  const labelOf = (a: Dict) => String(a.caption || (a.target_type === 'entity'
    ? names.get(String(a.target_id)) || ''
    : a.target_type ? '' : a.filename || ''))

  const choose = async (a: Dict) => {
    setBusy(true); setOops('')
    try {
      await onPick(a.url)
    } catch (ex: any) {
      setOops(ex?.message || t('pick.err_save')); setBusy(false)
    }
  }

  // у своих вложений имя карточки повторялось бы на каждой плитке — там только подпись
  const grid = (list: Dict[], own = false) => (
    <div className="att-grid">
      {list.map(a => {
        const label = own ? String(a.caption || '') : labelOf(a)
        return (
          <div key={a.id} className="att" title={label || a.filename || t('pick.file')}>
            <button type="button" disabled={busy}
              className={`att-shot${a.url === current ? ' att-current' : ''}`}
              aria-label={t('pick.make_portrait', { name: label || a.filename || t('pick.file') })}
              onClick={() => choose(a)}>
              <img src={thumbFull(a.url, 240)} alt={label} loading="lazy" />
            </button>
            {label && <span className="att-cap">{label}</span>}
          </div>
        )
      })}
    </div>
  )

  return (
    <Modal title={t('pick.title')} onClose={onClose} wide>
      {mine.length > 0 && (
        <div className="row wrap" style={{ marginBottom: 10 }}>
          <button type="button" className={`eg-tog ${onlyMine ? 'on' : ''}`}
            onClick={() => setOnlyMine(true)}>{t('pick.entry_attachments', { n: mine.length })}</button>
          <button type="button" className={`eg-tog ${onlyMine ? '' : 'on'}`}
            onClick={() => setOnlyMine(false)}>{t('pick.whole_campaign', { n: library })}</button>
        </div>
      )}
      {oops && <div className="eg-err">{oops}</div>}
      {loading && !rows
        ? <div className="dim">{t('common:loading')}</div>
        : err
          ? <div className="empty">{t('pick.unavailable')}</div>
          : showMine
            ? grid(mine, true)
            : !library
              ? <div className="empty">{t('pick.empty')}</div>
              : (
                <div className="eg-groups">
                  {groups.filter(([, list]) => list.length > 0).map(([title, list]) => (
                    <div key={title} className="eg-group">
                      <div className="eg-group-hd">
                        <span className="t">{t(`pick.group.${title}`)}</span>
                        <span className="n">{list.length}</span>
                      </div>
                      {grid(list)}
                    </div>
                  ))}
                </div>
              )}
    </Modal>
  )
}

export default MediaPickModal
