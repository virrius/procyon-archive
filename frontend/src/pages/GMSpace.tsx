import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useLocation } from 'react-router-dom'
import { api, c, store, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import { Chip, Input, Modal, Select } from '../ui'
import HistoryFeed from '../components/HistoryFeed'
import BoardsPage from './BoardsPage'
import LooksPage from './LooksPage'
import RulesPage from './RulesPage'

// разделы ГМа: полоса вкладок снята, переключает их левое меню — здесь остался
// только список допустимых адресов
const SUBS = ['accounts', 'boards', 'history', 'rules', 'looks']

const ROLE_LABEL: Dict = { gm: 'role.gm', player: 'role.player', observer: 'role.observer' }
const ROLE_TONE: Dict = { gm: 'red', player: 'cyan', observer: 'violet' }
const ROLE_PICK: Dict = {
  player: 'role_pick.player', observer: 'role_pick.observer', gm: 'role_pick.gm',
}

export default function GMSpace() {
  const { pathname } = useLocation()
  const seg = pathname.split('/').filter(Boolean)[1] || ''
  const tab = SUBS.includes(seg) ? seg : ''

  const { campaign, reload, isRealGM, L } = useApp()
  const { t } = useTranslation('gm')
  const [newPlayer, setNewPlayer] = useState<Dict | null>(null)
  const [created, setCreated] = useState<Dict | null>(null)
  const [resetFor, setResetFor] = useState<Dict | null>(null)

  if (!tab) return <Navigate to="/gm/accounts" replace />

  if (store.viewAs) {
    return <div className="panel"><h2>{t('no_viewas')}</h2></div>
  }
  if (!isRealGM) return <div className="panel"><h2>{t('gm_only')}</h2></div>

  const members: Dict[] = (campaign?.members || []).slice()
    .sort((a: Dict, b: Dict) => (a.role === 'gm' ? 0 : 1) - (b.role === 'gm' ? 0 : 1))

  const roleName = (r?: string) => (ROLE_LABEL[r || ''] ? t(ROLE_LABEL[r || '']) : L(r))

  const toggleActive = async (m: Dict) => {
    try {
      await api.patch(`${c()}/players/${m.id}`, { is_active: m.is_active === false })
      reload()
    } catch (e: any) { alert(e.message) }
  }

  const revoke = async (m: Dict) => {
    if (!confirm(t('accounts.revoke_confirm', { name: m.display_name }))) return
    try {
      await api.del(`${c()}/members/${m.id}`)
      reload()
    } catch (e: any) { alert(e.message) }
  }

  const createPlayer = async () => {
    if (!newPlayer) return
    const body: Dict = { ...newPlayer }
    try {
      const r = await api.post(`${c()}/players`, body)
      setCreated({ login: r.login || body.login, password: body.password })
      setNewPlayer(null)
      reload()
    } catch (e: any) { alert(e.message) }
  }

  const setPassword = async (pwd: string) => {
    if (!resetFor) return
    try {
      await api.patch(`${c()}/players/${resetFor.id}`, { password: pwd })
      setResetFor(null)
      alert(t('accounts.password_updated'))
    } catch (e: any) { alert(e.message) }
  }

  return (
    <div className="col">
      {tab === 'accounts' && (
        <div className="panel col">
          <div className="row">
            <h3>{t('accounts.title')}</h3>
            <div className="spacer" />
            <button className="tiny primary" onClick={() => setNewPlayer({
              login: '', password: '', display_name: '', role: 'player',
            })}>{t('accounts.grant')}</button>
          </div>
          <div className="small dim2">
            {t('accounts.no_signup')}
          </div>
          <table>
            <thead>
              <tr><th>{t('accounts.login')}</th><th>{t('accounts.name')}</th><th>{t('accounts.role')}</th><th>{t('accounts.status')}</th><th /></tr>
            </thead>
            <tbody>
              {members.map((m: Dict) => (
                <tr key={m.id}>
                  <td className="mono">{m.login}</td>
                  <td>{m.display_name}</td>
                  <td><Chip tone={ROLE_TONE[m.role] || ''}>{roleName(m.role)}</Chip></td>
                  <td>{m.is_active === false
                    ? <Chip tone="red">{t('accounts.blocked')}</Chip>
                    : <Chip tone="green">{t('accounts.active')}</Chip>}</td>
                  <td>
                    <div className="row wrap">
                      <button className="tiny ghost"
                        onClick={() => setResetFor(m)}>{t('accounts.change_password')}</button>
                      {m.role !== 'gm' && (
                        <>
                          <button className="tiny ghost" onClick={() => toggleActive(m)}>
                            {m.is_active === false ? t('accounts.unblock') : t('accounts.block')}
                          </button>
                          <button className="tiny danger" onClick={() => revoke(m)}>{t('accounts.revoke')}</button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!members.length && <div className="empty">{t('accounts.empty')}</div>}
        </div>
      )}

      {tab === 'boards' && <BoardsPage />}

      {tab === 'history' && <HistoryFeed />}

      {tab === 'rules' && <RulesPage />}

      {tab === 'looks' && <LooksPage />}


      {newPlayer && (
        <Modal title={t('new_account.title')} onClose={() => setNewPlayer(null)} watch={newPlayer}
          dirtyAsk={t('new_account.dirty_ask')}>
          <Input label={t('new_account.login')} value={newPlayer.login}
            onChange={v => setNewPlayer({ ...newPlayer, login: v })} />
          <Input label={t('password_min')} value={newPlayer.password}
            onChange={v => setNewPlayer({ ...newPlayer, password: v })} />
          <Input label={t('new_account.display_name')} value={newPlayer.display_name}
            onChange={v => setNewPlayer({ ...newPlayer, display_name: v })} />
          <div className="field">
            <label>{t('accounts.role')}</label>
            <Select value={newPlayer.role} empty={null} title={t('accounts.role')}
              options={['player', 'observer', 'gm']}
              optionLabel={r => (ROLE_PICK[r] ? t(ROLE_PICK[r]) : r)}
              onChange={r => setNewPlayer({ ...newPlayer, role: r })} />
          </div>
          <button className="primary" onClick={createPlayer}
            disabled={!newPlayer.login.trim() || newPlayer.password.length < 4
              || !newPlayer.display_name.trim()}>{t('new_account.create')}</button>
        </Modal>
      )}

      {created && (
        <Modal title={t('created.title')} onClose={() => setCreated(null)}>
          <div className="panel col">
            <div className="row">
              <span className="dim">{t('created.login')}</span>
              <strong className="mono">{created.login}</strong>
            </div>
            <div className="row">
              <span className="dim">{t('created.password')}</span>
              <strong className="mono">{created.password}</strong>
            </div>
            <div className="row">
              <span className="dim">{t('created.address')}</span>
              <span className="mono">{location.origin}</span>
            </div>
          </div>
          <div className="small dim2">
            {t('created.note')}
          </div>
        </Modal>
      )}

      {resetFor && (
        <Modal title={t('new_password', { name: resetFor.display_name })} onClose={() => setResetFor(null)}>
          <PasswordForm onSave={setPassword} />
        </Modal>
      )}
    </div>
  )
}

function PasswordForm({ onSave }: { onSave: (p: string) => void }) {
  const { t } = useTranslation('gm')
  const [p, setP] = useState('')
  return (
    <div className="col">
      <Input label={t('password_min')} value={p} onChange={setP} />
      <button className="primary" disabled={p.length < 4} onClick={() => onSave(p)}>{t('set_password')}</button>
    </div>
  )
}
