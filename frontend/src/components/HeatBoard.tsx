import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c, isPublicView, type Dict } from '../api'
import { useApp } from '../ctx'

/* Heat and wanted level by Procyon system (rulebook pp. 186–187):
   heat builds up in the system where the crew left traces, on the eighth point
   it resets and raises the wanted level, the remainder carries over. Lives in the ship sheet:
   it's a crew stat, not a separate entity. */

const HEAT_MAX = 8
const WANTED_MAX = 4

type Cell = { heat: number; wanted: number }

const num = (v: any, max: number) => {
  const n = Number(v)
  return Number.isFinite(n) ? Math.min(max, Math.max(0, Math.trunc(n))) : 0
}

const cellOf = (raw: any): Cell => ({
  heat: num(raw?.heat, HEAT_MAX),
  wanted: num(raw?.wanted, WANTED_MAX),
})

/** Overflow: the eighth heat point is removed and raises the wanted level, the remainder stays. */
const bump = (cell: Cell, heat: number): Cell => {
  if (heat < HEAT_MAX) return { ...cell, heat }
  if (cell.wanted >= WANTED_MAX) return { ...cell, heat: HEAT_MAX }
  return { heat: heat - HEAT_MAX, wanted: cell.wanted + 1 }
}

export default function HeatBoard() {
  const { meta, campaign } = useApp()
  const { t } = useTranslation('crew')
  const systems: string[] = meta?.systems || []
  const [ship, setShip] = useState<Dict | null>(null)
  const [heat, setHeat] = useState<Dict>({})
  const [oops, setOops] = useState('')

  const canEdit = !isPublicView() && campaign?.my_role !== 'observer'

  useEffect(() => {
    let alive = true
    api.get(`${c()}/entities?kind=ship`)
      .then(r => {
        if (!alive) return
        const e = (Array.isArray(r) ? r : []).find((x: Dict) => x.kind === 'ship') || null
        setShip(e)
        setHeat((e?.fields?.heat && typeof e.fields.heat === 'object') ? e.fields.heat : {})
      })
      .catch(() => { if (alive) setShip(null) })
    return () => { alive = false }
  }, [])

  if (!ship || systems.length === 0) return null

  const save = async (next: Dict) => {
    const before = heat
    setHeat(next); setOops('')
    try {
      await api.patch(`${c()}/entities/${ship.id}`, { fields: { heat: next } })
    } catch (e: any) {
      setHeat(before); setOops(e?.message || t('err_save'))
    }
  }

  const put = (sys: string, cell: Cell) => save({ ...heat, [sys]: cell })

  return (
    <div className="panel col heat">
      <div className="row wrap">
        <h3>{t('heat.title')}</h3>
      </div>
      <div className="small dim2">
        {t('heat.hint')}
      </div>
      {oops && <div className="rel-oops">{oops}</div>}

      <div className="heat-grid">
        {systems.map(sys => {
          const cell = cellOf(heat[sys])
          return (
            <div className="heat-row" key={sys}>
              <div className="heat-sys">{sys}</div>
              <div className="heat-line">
                <span className="heat-lbl">{t('heat.heat')}</span>
                <Pips n={HEAT_MAX} value={cell.heat} tone="heat"
                  onSet={canEdit ? v => put(sys, bump(cell, v)) : undefined} />
                <span className="mono dim2">{cell.heat}</span>
              </div>
              <div className="heat-line">
                <span className="heat-lbl">{t('heat.wanted')}</span>
                <Pips n={WANTED_MAX} value={cell.wanted} tone="wanted"
                  onSet={canEdit ? v => put(sys, { ...cell, wanted: v }) : undefined} />
                <span className="mono dim2">{cell.wanted}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Pips({ n, value, tone, onSet }: {
  n: number; value: number; tone: string; onSet?: (v: number) => void
}) {
  const { t } = useTranslation('crew')
  return (
    <span className="heat-pips" title={t('of', { value, n })}>
      {Array.from({ length: n }, (_, i) => {
        const cls = `heat-pip ${tone}${i < value ? ' on' : ''}`
        return onSet
          ? <button type="button" key={i} className={cls} aria-label={`${i + 1}`}
              onClick={() => onSet(value === i + 1 ? i : i + 1)} />
          : <span key={i} className={cls} />
      })}
    </span>
  )
}
