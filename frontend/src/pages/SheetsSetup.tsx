import { Fragment, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import { Select } from '../ui'
import CrewSetup from '../components/charsheet/CrewSetup'
import { cleanSetup } from '../components/charsheet/model'
import ShipSetup from '../components/sheet/ShipSetup'
import { clone, dict, useAutosave } from '../components/sheet/parts'
import '../styles.char.css'

/** GM space → "Sheets": setup of the ship sheet and crew sheets on top of the book.
 *  The sheets themselves have no settings — players see only the result. */
export default function SheetsSetup() {
  const { meta, campaign, reload } = useApp()
  const { t } = useTranslation('gm')
  const [ships, loading] = useAsync<Dict[]>(() => api.get(`${c()}/entities?kind=ship`), [])
  const [part, setPart] = useState('ship')
  const [shipId, setShipId] = useState('')
  const [ship, setShip] = useState<Dict | null>(null)
  const [crew, setCrew] = useState<Dict>(() => clone(dict(campaign?.sheet_setup)))
  const saved = cleanSetup(crew)
  const auto = useAutosave(saved, async b => {
    await api.put(`${c()}/sheet-setup`, b)
    reload()
  }, t('char:err.save'))

  const list = ships || []
  useEffect(() => {
    setShip(list.find(s => s.id === shipId) || list[0] || null)
  }, [ships, shipId])  // eslint-disable-line react-hooks/exhaustive-deps

  const pbs = Object.keys(dict(meta?.playbooks))
  const own = dict(saved.playbooks)
  const parts: [string, string, boolean][] = [
    ['ship', t('sheets.ship'), !!dict(ship?.fields).custom],
    ['common', t('sheets.common'), Array.isArray(saved.common)],
    ...pbs.map(k => [k, String(dict(dict(meta?.playbooks)[k]).label || k), !!own[k]] as [string, string, boolean]),
  ]
  const state = auto.err ? <span className="ss-state bad">{auto.err}</span>
    : auto.phase === 'busy' ? <span className="ss-state">{t('char:saving')}</span>
    : auto.phase === 'ok' && <span className="ss-state">{t('char:saved')}</span>

  return (
    <div className="col gs">
      <div className="panel col">
        <div className="gs-parts">
          {parts.map(([k, label, custom], i) => (
            <Fragment key={k}>
              {i > 0 && i < 3 && <span className="gs-sep" />}
              <button className={`gs-part${part === k ? ' on' : ''}${custom ? ' own' : ''}`}
                title={custom ? t('sheets.custom') : undefined} onClick={() => setPart(k)}>{label}</button>
            </Fragment>
          ))}
        </div>

        {loading && !ships
          ? part === 'ship' && <div className="dim">{t('common:loading')}</div>
          : ship
            ? <div className="col" style={part === 'ship' ? undefined : { display: 'none' }}>
                {list.length > 1 && (
                  <label className="ss-sel">
                    <span className="ss-cap">{t('sheets.which_ship')}</span>
                    <Select value={ship.id} options={list.map(s => s.id)} empty={null}
                      optionLabel={id => list.find(s => s.id === id)?.name || id} onChange={setShipId} />
                  </label>
                )}
                <ShipSetup key={ship.id} ship={ship} onSaved={setShip} />
              </div>
            : part === 'ship' && <div className="empty">{t('sheets.no_ship')}</div>}
        {part !== 'ship' && <CrewSetup key={part} part={part} all={crew} setAll={setCrew} state={state} />}
      </div>
    </div>
  )
}
