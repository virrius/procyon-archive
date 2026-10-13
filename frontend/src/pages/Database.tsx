import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { locale } from '../i18n'
import { Link, Navigate, useLocation, useSearchParams } from 'react-router-dom'
import { api, c, isPublicView, store, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import { EntityGallery } from '../components/EntityGallery'
import EntityPicker from '../components/EntityPicker'
import { ClockForm, blankClock, useClockKinds } from '../components/ClockForm'
import { VisibilityMenu } from '../components/VisibilityMenu'
import { RecordsPanel } from '../components/RecordsPanel'
import { ANY_PLAYER, OwnerMenu } from '../components/OwnerMenu'
import { ClockMoves, useClockMay, useClockMoves } from '../components/ClockMoves'
import { IconButton, IconClose } from '../components/icons'
import {
  Chip, ClockDial, ColorPicker, Input, Modal, OwnerPicker, VisChip, VisibilityPicker,
  clockTitle, rankRoman,
} from '../ui'

const SUBS: [string, string][] = [
  ['npc', 'title.npc'],
  ['factions', 'title.factions'],
  ['locations', 'title.locations'],
  ['clocks', 'title.clocks'],
]

const fld = (e: Dict, key: string) => String(e.fields?.[key] ?? '').trim()

/** within a category — as on the sheet and in Faction status: strongest first, then by name */
const byRank = (a: Dict, b: Dict) =>
  (Number(fld(b, 'rank')) || 0) - (Number(fld(a, 'rank')) || 0)
  || String(a.name || '').localeCompare(String(b.name || ''), 'ru')

export default function Database() {
  const { L } = useApp()
  const { t } = useTranslation('database')
  const { pathname } = useLocation()
  const sub = pathname.split('/').filter(Boolean)[1] || ''
  const entry = SUBS.find(([k]) => k === sub)

  if (!entry) return <Navigate to="/database/npc" replace />

  return (
    <div className="col">
      {sub === 'clocks' && <h1>{t(entry[1])}</h1>}

      {sub === 'npc' && (
        <EntityGallery key="npc" kind="npc" title={t('title.npc')} search visRow />
      )}
      {sub === 'factions' && (
        <EntityGallery key="faction" kind="faction" title={t('title.factions')} search visRow
          sectionBy="category" sort={byRank} />
      )}
      {sub === 'locations' && (
        <EntityGallery key="location" kind="location" title={t('title.locations')} search visRow
          sectionBy="system" />
      )}
      {sub === 'clocks' && <ClocksTab key="clocks" />}
    </div>
  )
}

/* --- clocks ---------------------------------------------------------------- */

function ClocksTab() {
  const { isGM, memberName, campaign, L } = useApp()
  const { t } = useTranslation('database')
  // ?open=<id> — coming from an entity card: the clock opens in a window right away
  const [params, setParams] = useSearchParams()
  const asked = params.get('open') || ''
  const [form, setForm] = useState<Dict | null>(null)
  const [owner, setOwner] = useState<Dict | null>(null)  // entry the clock is linked to
  const [tickFor, setTickFor] = useState<Dict | null>(null)
  const [openId, setOpenId] = useState(asked)  // the full card lives in a modal
  const closeOpen = () => {
    setOpenId('')
    if (asked) setParams({}, { replace: true })
  }
  // search can lead here while already on clocks: the tab doesn't remount
  useEffect(() => { if (asked) setOpenId(asked) }, [asked])
  const [rows, loading, reload, error] = useAsync<Dict[]>(
    () => api.get(`${c()}/clocks?status=`), [])
  const kinds = useClockKinds(rows)
  const readonly = isPublicView()  // table view is read-only
  const canEdit = !readonly && campaign?.my_role !== 'observer'
  const may = useClockMay()
  const moves = useClockMoves(rows, reload)
  const shown = (rows || []).map(moves.view)
  // the clock window always has fresh data; a completed clock leaves "active",
  // but the window stays on the last snapshot — it can be put back to work right away
  const lastOpen = useRef<Dict | null>(null)
  const openRow = (rows || []).find(cl => cl.id === openId)
  if (openRow) lastOpen.current = moves.view(openRow)
  const open = !openId ? null
    : openRow ? moves.view(openRow)
    : lastOpen.current?.id === openId ? moves.view(lastOpen.current) : null
  // history is re-read once the server has replied, not on the optimistic tick
  const histKey = useRef('')
  if (open && !moves.busy(open)) histKey.current = `${open.id}:${open.filled}:${open.status}`
  // the server returns them sorted by type, "no type" last; split into groups in that order
  const groups: [string, Dict[]][] = []
  for (const cl of shown) {
    const k = String(cl.kind || '')
    if (groups.length && groups[groups.length - 1][0] === k) groups[groups.length - 1][1].push(cl)
    else groups.push([k, [cl]])
  }
  // completed and cancelled ones go to the dimmed tail of their group
  const idle = (cl: Dict) => cl.status !== 'active'
  for (const g of groups) g[1].sort((a, b) => Number(idle(a)) - Number(idle(b)))

  const startEdit = (cl: Dict) => {
    setOwner(cl.owner_type === 'entity' && cl.owner_id
      ? { id: cl.owner_id, name: cl.owner_name || cl.owner_id, kind: '' } : null)
    setForm({
      id: cl.id, name: cl.name, description: cl.description || '', outcome: cl.outcome || '',
      kind: cl.kind || '', color: cl.color, segments: cl.segments,
    })
  }

  return (
    <div className="col">
      <div className="row wrap">
        <div className="spacer" />
        <span className="mono dim2 small">{shown.length}</span>
        {canEdit && (
          <button className="primary" onClick={() => {
            setOwner(null)
            setForm(blankClock('', isGM))
          }}>{t('clocks.add')}</button>
        )}
      </div>

      {loading && !rows && <div className="dim">{t('common:loading')}</div>}
      {!loading && !!error && <div className="empty">{error}</div>}
      {!loading && !error && !shown.length && <div className="empty">{t('clocks.empty')}</div>}

      {groups.map(([gk, list]) => (
        <div key={gk || '—'} className="col">
          {kinds.length > 0 && (
            <div className="clock-group">{gk || t('clocks.no_kind')}</div>
          )}
          <div className="clocks-grid">
        {list.map(cl => (
          <div key={cl.id}
            className={`panel clock-card${cl.visibility === 'gm' ? ' gm-block' : ''}${idle(cl) ? ' off' : ''}`}>
            <button type="button" className="clock-open" onClick={() => setOpenId(cl.id)}
              title={t('clocks.open_tip')}>
              {clockTitle(cl)}
              {cl.status !== 'active' && (
                <> <Chip tone={cl.status === 'completed' ? 'green' : 'black'}>{L(cl.status)}</Chip></>
              )}
            </button>
            <div className="clock-line">
              <ClockDial segments={cl.segments} filled={cl.filled} size={22}
                hidden={cl.visibility === 'gm'} color={cl.color} />
              <span className="mono dim2 small">{cl.filled}/{cl.segments}</span>
              <div className="spacer" />
              <ClockMoves cl={cl} moves={moves} />
              {may(cl) && cl.status === 'active' && isGM && (
                <IconButton icon={<IconClose size={13} />} title={t('clocks.abandon_tip')} danger
                  onClick={() => {
                    if (confirm(t('clocks.abandon_confirm', { name: clockTitle(cl) }))) {
                      void moves.act(cl, () => api.del(`${c()}/clocks/${cl.id}`))
                    }
                  }} />
              )}
            </div>
            {moves.oops(cl) && <div className="clock-err">{moves.oops(cl)}</div>}
            <div className="clock-chips">
              {isGM && readonly && <VisChip v={cl.visibility} />}
              {!readonly && isGM && (
                <OwnerMenu value={cl.owner_member_id === '' ? null : cl.owner_member_id} compact
                  onChange={who => moves.act(cl, () =>
                    api.patch(`${c()}/clocks/${cl.id}`, { owner_member_id: who ?? '' }))} />
              )}
              {!readonly && isGM && (
                <VisibilityMenu value={cl.visibility} visibleTo={cl.visible_to || []} compact
                  onChange={(vis, to) => moves.act(cl, () =>
                    api.patch(`${c()}/clocks/${cl.id}`, { visibility: vis, visible_to: to }))} />
              )}
            </div>
          </div>
        ))}
          </div>
        </div>
      ))}

      {form && (
        <ClockForm form={form} setForm={setForm} owner={owner} setOwner={setOwner} kinds={kinds}
          onClose={() => setForm(null)}
          onDone={() => { setForm(null); setOwner(null); reload() }} />
      )}

      {tickFor && (
        <Modal title={t('clocks.tick_title', { name: tickFor.name })} onClose={() => setTickFor(null)}>
          {moves.oops(tickFor) && <div className="clock-err">{moves.oops(tickFor)}</div>}
          <TickForm busy={moves.busy(tickFor)}
            onSubmit={async (d, cm) => { if (await moves.tick(tickFor, d, cm)) setTickFor(null) }} />
        </Modal>
      )}

      {open && (
        <Modal title={clockTitle(open)} onClose={() => closeOpen()}>
          <div className="col">
            <div className="row">
              <ClockDial segments={open.segments} filled={open.filled} size={54}
                hidden={open.visibility === 'gm'} color={open.color} />
              <div className="col" style={{ gap: 4, minWidth: 0 }}>
                <div className="row wrap">
                  {open.kind && <Chip tone="cyan">{open.kind}</Chip>}
                  {isGM && readonly && <VisChip v={open.visibility} />}
                  {open.status !== 'active' && (
                    <Chip tone={open.status === 'completed' ? 'green' : 'black'}>
                      {L(open.status)}
                    </Chip>
                  )}
                </div>
                <div className="mono dim2 small">
                  {open.filled}/{open.segments}
                  {open.owner_name && <> · <Link to={`/entity/${open.owner_id}`}
                    onClick={() => closeOpen()}>{open.owner_name}</Link></>}
                </div>
              </div>
            </div>

            {open.description && <div className="small">{open.description}</div>}
            {open.outcome && (
              <div className="small dim">{t('clocks.outcome', { text: open.outcome })}</div>
            )}

            {may(open) && open.status === 'active' && (
              <div className="row wrap">
                <button className="tiny" disabled={moves.busy(open) || open.filled >= open.segments}
                  onClick={() => moves.tick(open, 1)}>+1</button>
                <button className="tiny ghost" disabled={moves.busy(open) || open.filled <= 0}
                  onClick={() => moves.tick(open, -1)}>−1</button>
                <button className="tiny" onClick={() => { setTickFor(open); closeOpen() }}>
                  {t('clocks.tick_note')}
                </button>
                <button className={open.filled >= open.segments ? 'primary tiny' : 'tiny'}
                  disabled={moves.busy(open) || open.filled < open.segments}
                  onClick={() => moves.complete(open)}>{t('clocks.complete')}</button>
                <div className="spacer" />
                <button className="tiny ghost" onClick={() => { startEdit(open); closeOpen() }}>
                  {t('clocks.edit')}
                </button>
              </div>
            )}
            {may(open) && open.status !== 'active' && (open.status !== 'abandoned' || isGM) && (
              <div className="row wrap">
                <button className="tiny" disabled={moves.busy(open)}
                  onClick={() => moves.reopen(open)}>{t('clocks.reopen')}</button>
              </div>
            )}
            {moves.oops(open) && <div className="clock-err">{moves.oops(open)}</div>}

            {!readonly && isGM && (
              <div className="row wrap">
                <div className="spacer" />
                <OwnerMenu value={open.owner_member_id === '' ? null : open.owner_member_id}
                  onChange={who => moves.act(open, () =>
                    api.patch(`${c()}/clocks/${open.id}`, { owner_member_id: who ?? '' }))} />
                <VisibilityMenu value={open.visibility} visibleTo={open.visible_to || []}
                  onChange={(vis, to) => moves.act(open, () =>
                    api.patch(`${c()}/clocks/${open.id}`, { visibility: vis, visible_to: to }))} />
                {open.status === 'active' && (
                  <button className="tiny danger" onClick={async () => {
                    if (confirm(t('clocks.abandon_confirm', { name: open.name }))) {
                      if (await moves.act(open, () => api.del(`${c()}/clocks/${open.id}`))) closeOpen()
                    }
                  }}>{t('clocks.abandon')}</button>
                )}
                <button className="tiny danger" onClick={async () => {
                  if (confirm(t('clocks.delete_confirm', { name: open.name }))) {
                    if (await moves.act(open, () => api.del(`${c()}/clocks/${open.id}/purge`))) closeOpen()
                  }
                }}>{t('common:delete')}</button>
              </div>
            )}

            <RecordsPanel entityType="clock" entityId={open.id} />

            <div className="clock-group">{t('clocks.history')}</div>
            <History key={histKey.current} clockId={open.id}
              memberName={memberName} />
          </div>
        </Modal>
      )}
    </div>
  )
}

function TickForm({ busy, onSubmit }: { busy?: boolean; onSubmit: (d: number, comment: string) => void }) {
  const { t } = useTranslation('database')
  const [d, setD] = useState(1)
  const [cm, setCm] = useState('')
  return (
    <div className="col">
      <Input label={t('tick.delta')} type="number" value={d} onChange={v => setD(Number(v) || 0)} />
      <Input label={t('tick.comment')} type="textarea" value={cm} onChange={setCm} />
      <button className="primary" disabled={busy} onClick={() => onSubmit(d, cm)}>{t('tick.apply')}</button>
    </div>
  )
}

function History({ clockId, memberName }: {
  clockId: string; memberName: (id?: string | null) => string
}) {
  const { t } = useTranslation('database')
  const [rows, loading] = useAsync<Dict[]>(() => api.get(`${c()}/clocks/${clockId}/history`), [clockId])
  return (
    <div className="col">
      {loading && <div className="dim">{t('common:loading')}</div>}
      {!loading && !(rows || []).length && <div className="empty">{t('history.empty')}</div>}
      {(rows || []).map((r, i) => (
        <div key={i} className="row wrap small" style={{ borderBottom: '1px solid var(--line)' }}>
          <Chip tone={r.delta > 0 ? 'amber' : ''}>{r.delta > 0 ? `+${r.delta}` : r.delta}</Chip>
          <span className="mono">{r.from} → {r.to}</span>
          {r.comment && <span>{r.comment}</span>}
          <div className="spacer" />
          <span className="dim">{memberName(r.author_member_id)}</span>
          <span className="mono dim2">{new Date(r.at).toLocaleString(locale())}</span>
        </div>
      ))}
    </div>
  )
}
