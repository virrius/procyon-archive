import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, store } from '../api'

export default function Login() {
  const nav = useNavigate()
  const { t } = useTranslation('auth')
  const [f, setF] = useState({ login: '', password: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setErr(''); setBusy(true)
    try {
      const r = await api.post('/api/auth/login', {
        login: f.login.trim(), password: f.password,
      })
      store.token = r.token
      nav('/campaigns')
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <div style={{ display: 'grid', placeItems: 'center', minHeight: '100vh', padding: 20 }}>
      <div className="panel col" style={{ width: 'min(400px,100%)' }}>
        <div className="brand">Procyon<span>{t('archive')}</span></div>
        <div className="mono dim2">{t('tagline')}</div>

        <div className="field">
          <label>{t('login')}</label>
          <input autoFocus value={f.login} autoComplete="username"
            onChange={e => setF({ ...f, login: e.target.value })}
            onKeyDown={e => e.key === 'Enter' && submit()} />
        </div>
        <div className="field">
          <label>{t('password')}</label>
          <input type="password" value={f.password} autoComplete="current-password"
            onChange={e => setF({ ...f, password: e.target.value })}
            onKeyDown={e => e.key === 'Enter' && submit()} />
        </div>

        {err && <div className="chip red">{err}</div>}
        <button className="primary" disabled={busy} onClick={submit}>
          {busy ? t('checking') : t('enter')}
        </button>
        <div className="small dim2">{t('no_signup')}</div>
      </div>
    </div>
  )
}
