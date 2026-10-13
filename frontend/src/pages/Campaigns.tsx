import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { api, store, type Dict } from '../api'
import { LANG_TITLES, LANGS, lang, type Lang } from '../i18n'
import { useApp, useAsync } from '../ctx'
import { Chip, Input, Modal } from '../ui'
import PasswordModal from '../components/PasswordModal'

/** Language of the campaign's starting presets: book canon, map, ship. What's already created stays as is. */
export function SetupLang({ value, onChange }: { value: Lang; onChange: (v: Lang) => void }) {
  const { t } = useTranslation('admin')
  return (
    <label className="setup-lang">
      <span>{t('camps.materials')}</span>
      <select value={value} onChange={e => onChange(e.target.value as Lang)}>
        {LANGS.map(l => <option key={l} value={l}>{LANG_TITLES[l]}</option>)}
      </select>
    </label>
  )
}

export default function Campaigns() {
  const nav = useNavigate()
  const { isAdmin, L, reload: reloadApp } = useApp()
  const { t } = useTranslation('gm')
  const [list, loading, reload] = useAsync<Dict[]>(() => api.get('/api/campaigns'), [])
  const [pw, setPw] = useState(false)
  const [ren, setRen] = useState<Dict | null>(null)
  const [name, setName] = useState('')
  const [setup, setSetup] = useState<Lang>(lang())
  const [fail, setFail] = useState('')

  if (!store.token) { nav('/login'); return null }

  const pick = (id: string) => { store.campaign = id; store.viewAs = null; nav('/crew') }
  const create = async () => {
    if (!name.trim()) return
    setFail('')
    try {
      await api.post('/api/campaigns', { name: name.trim(), lang: setup })
      setName(''); reload(); reloadApp()
    } catch (e: any) { setFail(e.message) }
  }

  return (
    <div style={{ maxWidth: 720, margin: '40px auto', padding: 16 }} className="col">
      <div className="brand">Procyon<span>{t('app:archive')}</span></div>

      <div className="panel col">
        <h2>{t('campaigns.title')}</h2>
        {loading && <div className="dim">{t('common:loading')}</div>}
        {(list || []).map(cp => (
          <div key={cp.id} className="row wrap">
            <button className="primary" onClick={() => pick(cp.id)}>{t('campaigns.open')}</button>
            <strong>{cp.name}</strong>
            <Chip tone={cp.role === 'gm' ? 'red' : 'cyan'}>{cp.role === 'gm' ? t('role.gm') : L(cp.role)}</Chip>
            {cp.role === 'gm' && (
              <button className="ghost tiny" onClick={() => setRen({ id: cp.id, name: cp.name })}>
                {t('campaigns.rename')}
              </button>
            )}
          </div>
        ))}
        {!loading && (list || []).length === 0 && (
          <div className="empty">{t('campaigns.empty')} {isAdmin ? t('campaigns.empty_admin') : t('campaigns.empty_player')}</div>
        )}
        {isAdmin && (
          <div className="row wrap setup-row">
            <input placeholder={t('admin:camps.new')} value={name} onChange={e => setName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') create() }} />
            <SetupLang value={setup} onChange={setSetup} />
            <button disabled={!name.trim()} onClick={create}>{t('admin:camps.create')}</button>
          </div>
        )}
        {fail && <div className="chip red">{fail}</div>}
      </div>

      <div className="row wrap">
        <button className="ghost" onClick={() => setPw(true)}>
          {t('campaigns.change_password')}
        </button>
        {isAdmin && <button className="ghost" onClick={() => nav('/admin')}>Admin space</button>}
        <div className="spacer" />
        <button className="ghost" onClick={() => {
          store.token = null; store.campaign = null; store.viewAs = null; nav('/login')
        }}>{t('campaigns.logout')}</button>
      </div>

      {ren && (
        <Modal title={t('campaigns.rename_title')} onClose={() => setRen(null)}>
          <Input label={t('campaigns.name')} value={ren.name} onChange={v => setRen({ ...ren, name: v })} />
          <button className="primary" disabled={!ren.name.trim()} onClick={async () => {
            try {
              await api.patch(`/api/campaigns/${ren.id}`, { name: ren.name })
              setRen(null); reload(); reloadApp()
            } catch (e: any) { alert(e.message) }
          }}>{t('common:save')}</button>
        </Modal>
      )}

      {pw && <PasswordModal onClose={() => setPw(false)} />}
    </div>
  )
}
