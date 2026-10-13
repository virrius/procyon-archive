import { type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { type Dict } from '../../api'
import { useApp } from '../../ctx'
import { dict, entries, type Entry, EntryRows, GrowText, newKey, num, Pips, Sect } from '../sheet/parts'
import { bookOf, STRESS_MAX, STRESS_TOP } from './model'

const LOAD_MAX = 3

/** Crew playbook setup (GM space): own rows on top of the book for the whole campaign.
 *  `part`: a playbook key or `common` (ordinary items shared by all playbooks).
 *  The page holds the draft of the whole setup: switching between playbooks doesn't lose it. */
export default function CrewSetup({ part, all, setAll, state }: {
  part: string; all: Dict; setAll: (fn: (prev: Dict) => Dict) => void; state: ReactNode
}) {
  const { meta } = useApp()
  const { t } = useTranslation('char')
  const sheet: Dict = dict(meta?.char_sheet)
  const book = part === 'common' ? null : bookOf(meta, part)
  const d: Dict = part === 'common' ? all : dict(dict(all.playbooks)[part])

  const patch = (k: string, v: any) => {
    setAll(prev => {
      const cur = part === 'common' ? { ...prev } : { ...dict(dict(prev.playbooks)[part]) }
      if (v === undefined) delete cur[k]
      else cur[k] = v
      if (part === 'common') return cur
      return { ...prev, playbooks: { ...dict(prev.playbooks), [part]: cur } }
    })
  }
  const own = (k: string) => Array.isArray(d[k])
  const rowsOf = (k: string, base: Entry[]) => (own(k) ? entries(d[k]) : base)
  const load = { key: 'load' as const, label: t('builder.load_title'), min: 0, max: LOAD_MAX }

  const list = (k: string, label: string, base: Entry[], withLoad: boolean, fresh: Entry) => {
    const cur = rowsOf(k, base)
    return (
      <Sect label={label} own={own(k)} count={cur.length} onReset={() => patch(k, undefined)}>
        <EntryRows items={cur} num={withLoad ? load : undefined} onChange={arr => patch(k, arr)}
          onAdd={() => patch(k, [...cur, { ...fresh, key: newKey() }])} />
      </Sect>
    )
  }

  return (
    <div className="sb">
      <div className="sb-note">{part === 'common' ? t('builder.note_common') : t('builder.note')}</div>

      {part === 'common' && list('common', t('builder.common'), entries(sheet.items), true, { key: '', name: '', load: 1 })}

      {book && <>
        {list('talents', t('builder.talents'), book.talents, false, { key: '', name: '' })}
        {list('items', t('builder.items'), book.items, true, { key: '', name: '', load: 1 })}

        <div className="sb-pair">
          <Sect label={t('builder.stress')} own={d.stress_max != null} onReset={() => patch('stress_max', undefined)}>
            <div className="sb-meter">
              <Pips n={STRESS_TOP} value={d.stress_max != null ? num(d.stress_max) : STRESS_MAX}
                onSet={v => patch('stress_max', Math.max(1, v))} />
              <span className="sb-meter-n">{d.stress_max != null ? num(d.stress_max) : STRESS_MAX}</span>
            </div>
          </Sect>
          <Sect label={t('builder.xp')} own={typeof d.xp_trigger === 'string'}
            onReset={() => patch('xp_trigger', undefined)}>
            <GrowText value={typeof d.xp_trigger === 'string' ? d.xp_trigger : book.xp_trigger || ''}
              placeholder={t('builder.xp_ph')} onChange={v => patch('xp_trigger', v)} />
          </Sect>
        </div>
      </>}

      {((book && Object.keys(d).length > 0) || state) && <div className="sb-foot">
        {book && Object.keys(d).length > 0 && (
          <button className="ghost" onClick={() => {
            if (!confirm(t('builder.reset_all_ask'))) return
            setAll(prev => {
              const p = { ...dict(prev.playbooks) }
              delete p[part]
              return { ...prev, playbooks: p }
            })
          }}>{t('builder.reset_all')}</button>
        )}
        <div className="spacer" />
        {state}
      </div>}
    </div>
  )
}
