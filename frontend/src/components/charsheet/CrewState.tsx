import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { type Dict } from '../../api'
import { useApp } from '../../ctx'
import { asList } from '../../ui'
import { dict, list, num } from '../sheet/parts'
import {
  bookOf, effective, loadLimit, loadUsed, playbookKey, talentKey, talentOf,
} from './model'

const HARM_ROW: Record<number, string[]> = { 3: ['h3'], 2: ['h2a', 'h2b'], 1: ['h1a', 'h1b'] }

/** ГМу на плитке «Команды»: стресс и нагрузка полосками, травмы, раны, таланты с текстом по наведению. */
export function CrewState({ e }: { e: Dict }) {
  const { meta, campaign } = useApp()
  const { t } = useTranslation('crew')
  const { t: tc } = useTranslation('char')
  // открытая карточка таланта: на телефоне — по нажатию, на компьютере ещё и по наведению
  const [open, setOpen] = useState('')
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const shut = (x: MouseEvent) => { if (!box.current?.contains(x.target as Node)) setOpen('') }
    const esc = (x: KeyboardEvent) => { if (x.key === 'Escape') setOpen('') }
    document.addEventListener('click', shut)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('click', shut); document.removeEventListener('keydown', esc) }
  }, [open])

  const f = dict(e.fields)
  const pb = playbookKey(meta, f.playbook)
  const setup = dict(campaign?.sheet_setup)
  const eff = effective(bookOf(meta, pb), dict(meta?.char_sheet), setup)
  const stress = num(f.stress)
  const hotStress = stress >= eff.stressMax - 2
  const traumas = asList(f.trauma)
  const harm = dict(f.harm)
  const wounds = [3, 2, 1]
    .map(lv => ({ lv, names: HARM_ROW[lv].map(k => String(harm[k] || '').trim()).filter(Boolean) }))
    .filter(w => w.names.length)
  const level = String(f.load || 'normal')
  const used = loadUsed(dict(f.items))
  const lim = loadLimit(level)
  const own = new Map(eff.talents.map(x => [talentKey(pb, x.key), x]))
  const talents = list(f.talents).map(k => {
    const x = own.get(k) || talentOf(meta, setup, k)
    return { key: k, name: x?.name || k, text: x?.text || '', from: own.has(k) ? '' : talentOf(meta, setup, k)?.pbLabel || '' }
  })

  return (
    <div className="crew-state" ref={box}>
      <div className="crew-meter">
        <div className="crew-ml">
          {t('summary.stress')}
          <span className={`crew-n${hotStress ? ' hot' : ''}`}>{stress}/{eff.stressMax}</span>
        </div>
        <div className={`crew-segs${hotStress ? ' hot' : ''}`}>
          {Array.from({ length: Math.max(eff.stressMax, stress) }, (_, i) => <i key={i} className={i < stress ? 'on' : ''} />)}
        </div>
      </div>

      <dl className="crew-facts">
        <dt>{t('summary.trauma')}</dt>
        <dd>{traumas.length ? <span className="hot">{traumas.join(', ')}</span> : <span className="calm">{t('summary.no_trauma')}</span>}</dd>
        <dt>{t('summary.harm')}</dt>
        <dd>{wounds.length
          ? wounds.map(w => (
              <div key={w.lv} className="hot">
                {w.names.join(', ')} · {tc(`harm.${w.names.length > 1 ? 'levels' : 'level'}.${w.lv}`)}
              </div>
            ))
          : <span className="calm">{t('summary.unhurt')}</span>}</dd>
      </dl>

      <div className="crew-meter">
        <div className="crew-ml">
          {t('summary.load')}
          <span className="calm">{tc(`gear.load.${level}`)}</span>
          <span className={`crew-n${used > lim ? ' hot' : ''}`}>{used}/{lim}</span>
        </div>
        <div className="crew-segs">
          {Array.from({ length: Math.max(lim, used) }, (_, i) => (
            <i key={i} className={i >= lim ? 'over' : i < used ? 'on' : ''} />
          ))}
        </div>
      </div>

      <div className="crew-tal">
        {talents.length
          ? talents.map(x => (
              <button key={x.key} type="button" className={`crew-chip${open === x.key ? ' open' : ''}${x.text ? '' : ' bare'}`}
                aria-expanded={x.text ? open === x.key : undefined}
                onClick={() => { if (x.text) setOpen(open === x.key ? '' : x.key) }}>
                {x.name}{x.from && <em> · {x.from.toLowerCase()}</em>}
                {x.text && <span className="crew-pop" role="tooltip"><b>{x.name}</b>{x.text}</span>}
              </button>
            ))
          : <span className="calm">{t('summary.no_talents')}</span>}
      </div>
    </div>
  )
}
