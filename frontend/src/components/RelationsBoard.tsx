import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api, c, isPublicView, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import { Modal, rankRoman } from '../ui'
import { IconTrash } from './icons'
import HeatBoard from './HeatBoard'
import EntityPeek from './EntityPeek'
import '../styles.relations.css'

/* Faction status dashboard: organizations the table already knows (the server doesn't send hidden ones),
   status level -3…+3 and a log of jobs done for them. */

const STANCES = ['-3', '-2', '-1', '0', '+1', '+2', '+3']

// level labels: the same words used at the table
const STANCE_LABEL: Dict = {
  '-3': 'stance.war', '-2': 'stance.hostile', '-1': 'stance.interfering', '0': 'stance.neutral',
  '+1': 'stance.helpful', '+2': 'stance.friendly', '+3': 'stance.allies',
}

const CATEGORIES: [string, string][] = [
  ['hegemony', 'relations.cat.hegemony'],
  ['criminal', 'relations.cat.criminal'],
  ['weird', 'relations.cat.weird'],
  ['', 'relations.cat.other'],
]

type Deed = { id?: string; text?: string; at?: string; by?: string | null }

const fld = (e: Dict, key: string) => String(e.fields?.[key] ?? '').trim()
const deedsOf = (e: Dict): Deed[] =>
  Array.isArray(e.fields?.deeds) ? (e.fields.deeds as Deed[]) : []

/** "1" and "+1" are the same level: old cards stored it without a sign. */
const stanceOf = (e: Dict): string => {
  const raw = fld(e, 'stance')
  if (!raw) return ''
  const n = Number(raw)
  if (!Number.isFinite(n)) return raw
  return n > 0 ? `+${n}` : String(n)
}

const stanceTone = (s: string) => (s.startsWith('-') ? 'red' : s && s !== '0' ? 'green' : '')

export default function RelationsBoard() {
  const { campaign, isGM } = useApp()
  const { t } = useTranslation('crew')
  const [rows, loading, reload, error] = useAsync<Dict[]>(
    () => api.get(`${c()}/entities?kind=faction`), [])
  const [q, setQ] = useState('')
  const [deedsId, setDeedsId] = useState<string | null>(null)
  const [peek, setPeek] = useState<Dict | null>(null)
  const [oops, setOops] = useState('')

  const readonly = isPublicView()  // showcase for the table: read only
  const isObserver = campaign?.my_role === 'observer'
  const canEdit = !readonly && !isObserver

  const all = rows || []
  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return all.filter(e => !needle ||
      [e.name, e.alias, e.summary].some(x => String(x || '').toLowerCase().includes(needle)))
  }, [all, q])

  const groups: [string, string, Dict[]][] = CATEGORIES.map(([key, label]) => {
    const known = CATEGORIES.map(([k]) => k).filter(Boolean)
    // as on the sheet: strong organizations on top, alphabetical within a Tier
    const list = shown.filter(e => {
      const cat = fld(e, 'category')
      return key ? cat === key : !known.includes(cat)
    }).sort((a, b) =>
      (Number(fld(b, 'rank')) || 0) - (Number(fld(a, 'rank')) || 0) ||
      String(a.name).localeCompare(String(b.name)))
    return [key, label, list] as [string, string, Dict[]]
    // the sheet's three main columns are always shown, otherwise a single remaining one stretches
    // to full width; "Other" is shown only when there is something to put there
  }).filter(([key, , list]) => key !== '' || list.length > 0)

  const patch = async (e: Dict, body: Dict) => {
    setOops('')
    try { await api.patch(`${c()}/entities/${e.id}/standing`, body) }
    catch (ex: any) { setOops(ex?.message || t('err_save')) }
    reload()
  }

  const setStance = (e: Dict, v: string) => patch(e, { stance: v })
  const setDeeds = (e: Dict, deeds: Deed[]) => patch(e, { deeds })
  const deedsFor = all.find(e => e.id === deedsId) || null

  const total = all.length

  return (
    <div className="col rel">
      <HeatBoard />

      <div className="row wrap">
        <h2>{t('relations.title')}</h2>
        <div className="spacer" />
        {total > 0 && (
          <input style={{ maxWidth: 260 }} placeholder={t('relations.search_ph')}
            value={q} onChange={ev => setQ(ev.target.value)} />
        )}
      </div>

      {oops && <div className="rel-oops">{oops}</div>}
      {loading && !rows && <div className="dim">{t('common:loading')}</div>}
      {!loading && !!error && <div className="empty">{error}</div>}
      {!loading && !error && total === 0 && (
        <div className="empty">
          {t('relations.empty')}
        </div>
      )}
      {!loading && total > 0 && shown.length === 0 && (
        <div className="empty">{t('no_match')}</div>
      )}

      <div className="rel-cols">
        {(shown.length === 0 ? [] : groups).map(([key, label, list]) => (
          <div key={key || 'other'} className="rel-col">
            <div className="rel-cap">{t(label)}</div>
            {list.length === 0 ? (
              <div className="rel-void">{t('relations.nobody')}</div>
            ) : (
            <table className="rel-tab">
              <thead>
                <tr>
                  <th>{t('relations.col_faction')}</th>
                  <th className="rel-th-rank">{t('relations.col_tier')}</th>
                  <th className="rel-th-stance">{t('relations.col_status')}</th>
                  <th className="rel-th-deeds">{t('relations.col_jobs')}</th>
                </tr>
              </thead>
              <tbody>
                {list.map(e => {
                  const hidden = new Set<string>((e.hidden_fields || []) as string[])
                  const stance = stanceOf(e)
                  const deeds = deedsOf(e)
                  return (
                    <tr key={e.id} className={isGM && e.visibility === 'gm' ? 'gm-only' : undefined}>
                      <td className="rel-name">
                        <Link to={`/entity/${e.id}`} onClick={ev => {
                          // card as a window over the board; with Ctrl/Shift, as a normal link
                          if (ev.ctrlKey || ev.metaKey || ev.shiftKey) return
                          ev.preventDefault(); setPeek(e)
                        }}>{e.name}</Link>
                      </td>
                      <td className="rel-rank mono">
                        {hidden.has('rank') && !isGM
                          ? <span className="unknown" title={t('relations.hidden')}>?</span>
                          : rankRoman(fld(e, 'rank'))}
                      </td>
                      <td className="rel-stance">
                        <StanceBar value={stance} disabled={!canEdit}
                          onChange={v => setStance(e, v)} />
                      </td>
                      <td className="rel-deeds">
                        <button type="button" className="rel-tally" title={t('relations.jobs_title')}
                          onClick={() => setDeedsId(e.id)}>
                          {deeds.length === 0
                            ? <span className="dim2">—</span>
                            : <Tally deeds={deeds} />}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            )}
          </div>
        ))}
      </div>

      {deedsFor && (
        <Modal title={t('relations.jobs_of', { name: deedsFor.name })} onClose={() => setDeedsId(null)}>
          <DeedList entity={deedsFor} canEdit={canEdit}
            onChange={deeds => setDeeds(deedsFor, deeds)} />
        </Modal>
      )}
      {peek && <EntityPeek id={peek.id} name={peek.name} onClose={() => setPeek(null)} />}
    </div>
  )
}

/** Job marks: checkboxes with labels are shown denser than a list. */
function Tally({ deeds }: { deeds: Deed[] }) {
  const { t } = useTranslation('crew')
  const marks = deeds.slice(0, 10)
  return (
    <span className="rel-marks">
      {marks.map((d, i) => (
        <i key={d.id || i} className={d.text ? 'note' : ''} title={d.text || t('relations.mark')} />
      ))}
      {deeds.length > marks.length && <span className="mono dim2">+{deeds.length - marks.length}</span>}
    </span>
  )
}

/** Scale -3…+3: the center is neutral, left is hostility, right is friendship.
 *  Clicking the current level changes nothing: a stray tap doesn't erase the status. */
function StanceBar({ value, disabled, onChange }: {
  value: string; disabled?: boolean; onChange: (v: string) => void
}) {
  const { t } = useTranslation('crew')
  const cur = STANCES.includes(value) ? value : ''
  const idx = cur ? STANCES.indexOf(cur) : -1
  const zero = STANCES.indexOf('0')
  return (
    <span className="rel-bar" title={cur ? t(STANCE_LABEL[cur]) : t('relations.unset')}>
      {STANCES.map((s, i) => {
        // everything from neutral to the current level is filled: the sign reads by the bar length
        const on = idx >= 0 && (i === zero
          ? idx === zero
          : idx > zero ? i > zero && i <= idx : i < zero && i >= idx)
        const cls = `rel-cell${on ? ' on' : ''}${s.startsWith('-') ? ' bad' : ''}${s === '0' ? ' mid' : ''}`
        return disabled
          ? <span key={s} className={cls} />
          : <button key={s} type="button" className={cls} title={`${s} — ${t(STANCE_LABEL[s])}`}
              aria-pressed={s === cur} onClick={() => { if (s !== cur) onChange(s) }} />
      })}
      <b className={`rel-val ${stanceTone(cur)}`}>{cur || '—'}</b>
    </span>
  )
}

function DeedList({ entity, canEdit, onChange }: {
  entity: Dict; canEdit: boolean; onChange: (deeds: Deed[]) => void
}) {
  const { memberName } = useApp()
  const { t } = useTranslation('crew')
  const deeds = deedsOf(entity)
  const [text, setText] = useState('')

  const add = () => {
    const v = text.trim()
    if (!v) return
    onChange([...deeds, { text: v }]); setText('')
  }
  const edit = (i: number, v: string) =>
    onChange(deeds.map((d, k) => (k === i ? { ...d, text: v } : d)))
  const drop = (i: number) => onChange(deeds.filter((_, k) => k !== i))

  return (
    <div className="col rel-deedlist">
      {deeds.length === 0 && <div className="empty">{t('relations.no_jobs')}</div>}
      {deeds.map((d, i) => (
        <div key={d.id || i} className="row rel-deed">
          <span className="rel-deed-n mono dim2">{i + 1}</span>
          {canEdit
            ? <DeedText value={d.text || ''} onCommit={v => edit(i, v)} />
            : <span className="rel-deed-t">{d.text || t('relations.mark')}</span>}
          {d.by && <span className="dim2 small rel-deed-m">{memberName(d.by)}</span>}
          {canEdit && (
            <button className="tiny danger" title={t('relations.remove')} onClick={() => drop(i)}>
              <IconTrash size={12} />
            </button>
          )}
        </div>
      ))}

      {canEdit && (
        <input className="rel-deed-add" placeholder={t('relations.new_job')}
          value={text} onChange={ev => setText(ev.target.value)}
          onKeyDown={ev => { if (ev.key === 'Enter') add() }} />
      )}
    </div>
  )
}

/* a job edit goes to the server on leaving the field, not on every keystroke */
function DeedText({ value, onCommit }: { value: string; onCommit: (t: string) => void }) {
  const { t } = useTranslation('crew')
  const [v, setV] = useState(value)
  useEffect(() => { setV(value) }, [value])
  const commit = () => { if (v !== value) onCommit(v) }
  return (
    <input value={v} placeholder={t('relations.job_ph')}
      onChange={ev => setV(ev.target.value)} onBlur={commit}
      onKeyDown={ev => { if (ev.key === 'Enter') (ev.target as HTMLInputElement).blur() }} />
  )
}

export { RelationsBoard }
