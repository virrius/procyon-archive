import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, store } from '../api'
import { useApp } from '../ctx'
import { Input, Modal } from '../ui'

/** Change own password. forced: login with the default password; the old one isn't asked, can't be closed. */
export default function PasswordModal({ forced, onClose }: { forced?: boolean; onClose?: () => void }) {
  const { t } = useTranslation('auth')
  const { reload } = useApp()
  const [f, setF] = useState({ old: '', next: '', again: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const mismatch = !!f.again && f.next !== f.again

  const save = async () => {
    setBusy(true); setErr('')
    try {
      const r = await api.post('/api/auth/password', { old_password: f.old, new_password: f.next })
      store.token = r.token
      // before the password change the server answered 403 to everything except /auth/me: reload gated pages
      if (forced) { location.reload(); return }
      reload()
      onClose?.()
      if (!forced) alert(t('pw.done'))
    } catch (e: any) { setErr(e.message) }
    setBusy(false)
  }

  return (
    <Modal title={t(forced ? 'pw.forced_title' : 'pw.title')} onClose={() => { if (!forced) onClose?.() }}>
      {forced && <div className="small dim">{t('pw.forced_note')}</div>}
      {!forced && (
        <Input label={t('pw.old')} type="password" value={f.old} onChange={v => setF({ ...f, old: v })} />
      )}
      <Input label={t('pw.new')} type="password" value={f.next} onChange={v => setF({ ...f, next: v })} />
      <Input label={t('pw.repeat')} type="password" value={f.again} onChange={v => setF({ ...f, again: v })} />
      {(mismatch || err) && <div className="chip red">{mismatch ? t('pw.mismatch') : err}</div>}
      <button className="primary" disabled={busy || f.next.length < 4 || f.next !== f.again || (!forced && !f.old)}
        onClick={save}>{t('pw.save')}</button>
    </Modal>
  )
}

/** An account with the default password isn't let further until it sets its own. */
export function DefaultPasswordGate() {
  const { me } = useApp()
  return me?.password_default ? <PasswordModal forced /> : null
}
