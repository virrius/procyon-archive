import { useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { api, c, isPublicView, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import { EntityGallery, type Group } from '../components/EntityGallery'
import { CrewState } from '../components/charsheet/CrewState'
import { Chip, Input, Modal, OwnerPicker, Select, VisibilityPicker } from '../ui'

const KIND = 'character'

const cardPath = (id: string) => `/crew/team/${id}`
const STATE_KEY = 'pa_crew_state'


/** Team: the crew's characters. Lives as a tab in the Crew section. */
export default function Team() {
  const { meta, campaign, isGM, L } = useApp()
  const { t } = useTranslation('crew')
  const nav = useNavigate()
  const readonly = isPublicView()  // table view is read-only
  const [creating, setCreating] = useState<Dict | null>(null)
  // for the GM: whether to show characters' condition on tiles — remembered in the browser
  const [showState, setShowState] = useState(() => {
    try { return localStorage.getItem(STATE_KEY) !== '0' } catch { return true }
  })
  const flipState = () => {
    const v = !showState
    setShowState(v)
    try { localStorage.setItem(STATE_KEY, v ? '1' : '0') } catch { /* no storage — until reload */ }
  }
  const [rows, loading, reloadRows, error] = useAsync<Dict[]>(
    () => api.get(`${c()}/entities?kind=${KIND}`), [])
  /* the gallery lives on its own: refresh it through a handle, not by remounting via key */
  const galleryReload = useRef<((silent?: boolean) => void) | null>(null)

  const def: Dict = meta?.kinds?.[KIND] || {}
  const statuses: string[] = def.statuses || []
  const players: Dict[] = (campaign?.members || []).filter((m: Dict) => m.role !== 'gm')
  const all = rows || []
  const myId = campaign?.my_member_id
  const refresh = () => { reloadRows(); galleryReload.current?.() }

  // a group per owning player: yours first, then by name, no player last.
  // a player without a single visible character is a dimmed empty group; your own empty one has an add button
  const byPlayer = useCallback((list: Dict[]): Group[] => {
    const members = (campaign?.members || []) as Dict[]
    const who = new Map<string, string>(
      members.map(m => [String(m.id), String(m.display_name || '')]))
    const owned = new Map<string, Dict[]>()
    const free: Dict[] = []
    for (const e of list) {
      const id = String(e.owner_member_id || '')
      if (!who.has(id)) { free.push(e); continue }
      const arr = owned.get(id)
      arr ? arr.push(e) : owned.set(id, [e])
    }
    if (rows) {
      for (const m of members) {
        const id = String(m.id)
        if (m.role === 'player' && !owned.has(id) && !rows.some(e => e.owner_member_id === id)) {
          owned.set(id, [])
        }
      }
    }
    const out: Group[] = Array.from(owned.entries())
      .sort(([a], [b]) => Number(b === myId) - Number(a === myId)
        || String(who.get(a)).localeCompare(String(who.get(b)), 'ru'))
      .map(([id, items]) => [id, who.get(id) || '', items,
        items.length ? undefined : { idle: true, add: id === myId }])
    if (free.length) out.push(['', t('team.no_player'), free, { idle: true }])
    return out
  }, [campaign, myId, rows, t])

  const blank = (owner = ''): Dict => ({
    name: '', alias: '',
    status: statuses[0] || 'active', owner_member_id: owner,
    visibility: 'crew', visible_to: [],
  })

  const create = async () => {
    if (!creating?.name?.trim()) return
    const r = await api.post(`${c()}/entities`, {
      ...creating, kind: KIND, name: creating.name.trim(),
      owner_member_id: creating.owner_member_id || null,
      fields: {},
    })
    setCreating(null); refresh()
    nav(cardPath(r.id))
  }

  const bind = async (id: string, member: string | null) => {
    await api.patch(`${c()}/entities/${id}`, { owner_member_id: member })
    refresh()
  }

  return (
    <div className="col">
      <EntityGallery kind={KIND} title={t('team.title')} reloadRef={galleryReload}
        groupBy={byPlayer} linkTo={e => cardPath(e.id)} hideFacts
        beside={isGM && !readonly && (
          <button type="button" role="switch" aria-checked={showState} className="crew-switch" onClick={flipState}>
            <span className="crew-switch-track" aria-hidden="true" />{t('summary.toggle')}
          </button>
        )}
        extra={isGM && !readonly && showState ? e => <CrewState e={e} /> : undefined} />

      {!!error && <div className="empty">{error}</div>}

      {isGM && !readonly && !loading && (
        <div className="panel col">
          <div className="row">
            <h3>{t('team.players')}</h3>
            <div className="spacer" />
            <button className="tiny" onClick={() => setCreating(blank())}>{t('team.add')}</button>
          </div>
          {players.length === 0 && <div className="empty">{t('team.no_players')}</div>}
          {players.map(m => (
            <PlayerRow key={m.id} member={m}
              owned={all.filter(e => e.owner_member_id === m.id)}
              free={all.filter(e => !e.owner_member_id)}
              onBind={bind} onCreate={() => setCreating(blank(m.id))} L={L} />
          ))}
        </div>
      )}

      {creating && (
        <Modal title={t('team.new')} onClose={() => setCreating(null)} watch={creating}>
          <Input label={t('team.name')} value={creating.name}
            onChange={v => setCreating({ ...creating, name: v })} />
          <Input label={t('team.alias')} value={creating.alias}
            onChange={v => setCreating({ ...creating, alias: v })} />
          <Input label={t('team.status')} value={creating.status} options={statuses}
            onChange={v => setCreating({ ...creating, status: v })} />
          <OwnerPicker value={creating.owner_member_id}
            onChange={v => setCreating({ ...creating, owner_member_id: v || '' })} />
          <VisibilityPicker visibility={creating.visibility} visibleTo={creating.visible_to}
            onChange={(v, to) => setCreating({ ...creating, visibility: v, visible_to: to })} />
          <button className="primary" disabled={!creating.name?.trim()}
            onClick={create}>{t('team.create')}</button>
        </Modal>
      )}
    </div>
  )
}

/* --- GM: who plays whom ----------------------------------------------------- */

function PlayerRow({ member, owned, free, onBind, onCreate, L }: {
  member: Dict
  owned: Dict[]
  free: Dict[]
  onBind: (id: string, member: string | null) => void
  onCreate: () => void
  L: (k?: string | null) => string
}) {
  const { t } = useTranslation('crew')
  const [pick, setPick] = useState('')
  return (
    <div className="row wrap" style={{ borderTop: '1px solid var(--line)', paddingTop: 8 }}>
      <strong style={{ minWidth: 140 }}>{member.display_name}</strong>
      {owned.map(e => (
        <span key={e.id} className="row" style={{ gap: 6 }}>
          <Link to={cardPath(e.id)}>{e.name}</Link>
          <Chip>{L(e.status)}</Chip>
          <button className="tiny ghost" onClick={() => {
            if (confirm(t('team.unlink_confirm', { name: e.name, player: member.display_name }))) onBind(e.id, null)
          }}>{t('team.unlink')}</button>
        </span>
      ))}
      {owned.length === 0 && <span className="dim small">{t('team.unlinked')}</span>}
      <div className="spacer" />
      {free.length > 0 && <>
        <div style={{ maxWidth: 200 }}>
          <Select value={pick} options={free.map(e => e.id)} empty={t('team.free_empty')}
            optionLabel={id => free.find(e => e.id === id)?.name || id}
            title={t('team.free')} onChange={setPick} />
        </div>
        <button className="tiny" disabled={!pick}
          onClick={() => { onBind(pick, member.id); setPick('') }}>{t('team.link')}</button>
      </>}
      <button className="tiny ghost" onClick={onCreate}>{t('team.add_create')}</button>
    </div>
  )
}
