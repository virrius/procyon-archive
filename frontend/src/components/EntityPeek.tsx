import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api, c, thumb, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import { Chip, Modal, VisChip, rankRoman } from '../ui'
import RecordsPanel from './RecordsPanel'
import { IconLink } from './icons'
import Lightbox from './Lightbox'
import Stub from './Stub'
import '../styles.entity.css'
import '../styles.peek.css'

/* Быстрый просмотр карточки окном поверх экрана — только чтение, экран под ним не трогается.
   Ответы те же, что у страницы сущности: закрытое от стола сервер сюда не отдаёт. */

function Unknown() {
  const { t } = useTranslation('entity')
  return <span className="unknown" title={t('unknown_tip')}>?</span>
}
const UNKNOWN = <Unknown />

export default function EntityPeek({ id, name, onClose }: {
  id: string; name?: string; onClose: () => void
}) {
  const { meta, isGM, L } = useApp()
  const { t } = useTranslation('entity')
  const [e, loading, , err] = useAsync<Dict>(() => api.get(`${c()}/entities/${id}`), [id])
  // связь в записи открывает следующее окно поверх этого: закрыл — вернулся сюда
  const [next, setNext] = useState<{ id: string; name: string } | null>(null)
  const [full, setFull] = useState(false)

  const body = () => {
    if (err) return <div className="empty">{err}</div>
    if (loading || !e) return <div className="dim">{t('common:loading')}</div>

    const def: Dict = meta?.kinds?.[e.kind] || {}
    const own: Dict = e.fields || {}
    const hidden = new Set<string>((e.hidden_fields || []) as string[])
    const has = (key: string) => (def.fields || []).some((f: Dict) => f.key === key)
    // у ГМа закрытое от стола видно, но с рустовой меткой — как на странице карточки
    const shut = (key: string) => (isGM && hidden.has(key) ? ' shut' : '')
    const locked = (key: string) => !isGM && hidden.has(key)

    const cat = String(own.category ?? '').trim()
    const rank = String(own.rank ?? '').trim()
    const showCat = has('category') && (cat !== '' || hidden.has('category'))
    const showRank = has('rank') && (rank !== '' || hidden.has('rank'))

    return (
      <div className="peek">
        <div className="peek-head">
          <div className={`peek-shot${shut('image_url')}`}>
            {e.image_url
              ? <img className="zoomable" src={thumb(e.image_url, 480)} alt={e.name}
                  title={t('view_full')} onClick={() => setFull(true)} />
              : <Stub kind={e.kind} sub={own.job_type} className="peek-stub" />}
          </div>

          <div className="peek-body">
            <div className="peek-meta">
              <span className="mono dim2 small">{def.label || L(e.kind)}</span>
              {showCat && (
                <Chip tone={shut('category') ? 'red' : ''}>{locked('category') ? '?' : L(cat)}</Chip>
              )}
              {isGM && <VisChip v={e.visibility} />}
            </div>
            {e.alias && <span className="dos-alias">{t('quoted', { s: e.alias })}</span>}
            <div className={`dos-summary${shut('summary')}`}>
              {locked('summary')
                ? UNKNOWN
                : e.summary
                  ? <div style={{ whiteSpace: 'pre-wrap' }}>{e.summary}</div>
                  : <div className="empty">{t('peek.no_summary')}</div>}
            </div>
          </div>

          {showRank && (
            <div className={`rank-gauge${shut('rank')}`}>
              <span className="rg-lbl">{t('rank')}</span>
              <span className="rg-read">
                <span className={`rg-mark${rank === '' ? ' none' : ''}`}>
                  {locked('rank') ? '?' : rank === '' ? '—' : rankRoman(rank)}
                </span>
              </span>
            </div>
          )}
        </div>

        <RecordsPanel entityType="entity" entityId={e.id} readOnly
          onOpen={(nid, nname) => setNext({ id: nid, name: nname })} />
      </div>
    )
  }

  return (
    <Modal onClose={onClose} title={<>
      {e?.name || name || ''}
      {e && <Link className="peek-go" to={`/entity/${e.id}/profile`} title={t('peek.open_page')}>
        <IconLink size={14} />
      </Link>}
    </>}>
      {body()}
      {next && <EntityPeek id={next.id} name={next.name} onClose={() => setNext(null)} />}
      {full && e?.image_url && (
        <Lightbox src={e.image_url} alt={e.name} onClose={() => setFull(false)} />
      )}
    </Modal>
  )
}
