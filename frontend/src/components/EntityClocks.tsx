import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api, c, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import { Chip, ClockDial, VisChip } from '../ui'
import { ClockMoves, useClockMoves } from './ClockMoves'

/** An entry's clocks are moved right from the card, as in the campaign database;
 *  description, history and editing are in the database. */
export default function EntityClocks({ entityId }: { entityId: string }) {
  const { L, isGM } = useApp()
  const { t } = useTranslation('entity')
  const [rows, loading, reload, err] = useAsync<Dict[]>(
    () => api.get(`${c()}/clocks?status=&owner_id=${entityId}`), [entityId])
  const moves = useClockMoves(rows, reload)
  const list = (rows || [])
    .filter(cl => cl.owner_type === 'entity' && cl.owner_id === entityId).map(moves.view)

  return (
    <div className="col">
      <div className="row">
        <h3>{t('clocks.title')}</h3>
      </div>

      {err && <div className="empty">{t('clocks.unavailable')}</div>}
      {!err && loading && !rows && <div className="dim">{t('common:loading')}</div>}
      {!err && !loading && list.length === 0 && <div className="empty">{t('clocks.empty')}</div>}

      {!err && list.length > 0 && (
        <div className="lnk-list clocks-list">
          {list.map(cl => (
            <div key={cl.id} className="lnk">
              <ClockDial segments={cl.segments} filled={cl.filled} size={34}
                hidden={cl.visibility === 'gm'} color={cl.color} />
              <div className="lnk-main">
                <div className="lnk-head">
                  <Link className="lnk-name" to={`/database/clocks?open=${cl.id}`}
                    title={t('clocks.open_tip')}>{cl.name}</Link>
                  {cl.kind && <Chip tone="cyan">{cl.kind}</Chip>}
                  {cl.status === 'abandoned' && <Chip tone="black">{L(cl.status)}</Chip>}
                  {cl.status === 'completed' && <Chip tone="green">{L(cl.status)}</Chip>}
                  {cl.status === 'active' && cl.filled >= cl.segments &&
                    <Chip tone="amber">{t('clocks.filled')}</Chip>}
                  {isGM && <VisChip v={cl.visibility} />}
                </div>
                <div className="clock-line">
                  <span className="lnk-sub">{cl.filled}/{cl.segments}</span>
                  <div className="spacer" />
                  <ClockMoves cl={cl} moves={moves} />
                </div>
                {moves.oops(cl) && <div className="clock-err">{moves.oops(cl)}</div>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
