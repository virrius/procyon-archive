import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, NavLink, useLocation, useNavigate } from 'react-router-dom'
import i18n, { LANG_TITLES, LANGS, locale, setLang, type Lang } from '../i18n'
import { api, store, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import { Chip } from '../ui'
import AdminPrompts, { adminDirty } from '../components/AdminPrompts'
import PasswordModal from '../components/PasswordModal'
import { TransferBar, download, upload, useJob, type Job } from '../components/Transfer'
import { SaveBar, type SavePhase } from '../components/SaveBar'
import '../styles.nav.css'
import '../styles.admin.css'

const SECTIONS = ['hub', 'images', 'news', 'campaigns', 'users', 'lang']

const leave = (e: React.MouseEvent) => {
  if (adminDirty.current && !confirm(i18n.t('admin:leave_confirm'))) e.preventDefault()
}

export default function AdminSpace() {
  const { me } = useApp()
  const { pathname } = useLocation()
  const nav = useNavigate()
  const { t } = useTranslation('admin')
  const [navOpen, setNavOpen] = useState(false)
  const [pw, setPw] = useState(false)
  const seg = pathname.split('/').filter(Boolean)[1] || ''

  if (!store.token) return <Navigate to="/login" replace />
  if (!me) return <div className="content dim">{t('common:loading')}</div>
  if (!me.is_admin) return <Navigate to="/campaigns" replace />
  if (!SECTIONS.includes(seg)) return <Navigate to="/admin/hub" replace />

  const here = (me.campaigns || []).find((x: Dict) => x.campaign_id === store.campaign)

  return (
    <div className="app">
      <header className="frame-top">
        <div className="top-bar">
          <div className="top-in">
            <button className="nav-burger" aria-expanded={navOpen} aria-label={t('sections_label')}
              onClick={() => setNavOpen(v => !v)}><i /><i /><i /></button>
            <div className="brand inline">Procyon<span>{t('app:archive')}</span></div>
            <span className="adm-mark">Admin space</span>
            <div className="spacer" />
            <Chip tone="amber">{t('admin_chip')}</Chip>
          </div>
        </div>
      </header>
      <div className="shell">
        {navOpen && <div className="nav-scrim" onClick={() => setNavOpen(false)} />}
        <nav className={`sidenav${navOpen ? ' open' : ''}`} aria-label="Admin space">
          <div className="sidenav-scroll">
            <Link className="adm-back" to={here ? '/crew' : '/campaigns'} onClick={leave}>
              ← {here ? here.name : t('back_campaigns')}
            </Link>
            {SECTIONS.map(k => (
              <div className="nav-group" key={k}>
                <NavLink to={`/admin/${k}`} onClick={e => { leave(e); setNavOpen(false) }}
                  className={({ isActive }) => (isActive ? 'nav-head on' : 'nav-head')}>{t(`sections.${k}`)}</NavLink>
              </div>
            ))}
          </div>
          <div className="sidenav-foot">
            <div className="sidenav-camp">
              <div className="sidenav-lab">{t('signed_in')}</div>
              <div className="mono">{me.login}</div>
            </div>
            <div className="row">
              <button className="ghost tiny" onClick={() => {
                store.token = null; store.campaign = null; store.viewAs = null; nav('/login')
              }}>{t('logout')}</button>
              <button className="ghost tiny" onClick={() => setPw(true)}>{t('auth:pw.open')}</button>
            </div>
          </div>
        </nav>
        <div className="main-col adm-main">
          <main className="content frame-in adm-content">
            <h1 className="adm-title">{t(`sections.${seg}`)}</h1>
            {seg === 'hub' && <HubCard />}
            {seg === 'images' && <AdminPrompts key="images" scope="images" />}
            {seg === 'news' && <AdminPrompts key="news" scope="news" />}
            {seg === 'campaigns' && <CampaignsAdmin />}
            {seg === 'users' && <UsersAdmin />}
            {seg === 'lang' && <LangCard />}
          </main>
        </div>
      </div>
      {pw && <PasswordModal onClose={() => setPw(false)} />}
    </div>
  )
}

function LangCard() {
  const { t, i18n: i } = useTranslation('admin')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const pick = async (next: Lang) => {
    setBusy(true); setErr('')
    try {
      const r = await api.patch('/api/admin/lang', { lang: next })
      setLang(r.lang)
    } catch (e: any) { setErr(e.message) }
    setBusy(false)
  }

  return (
    <div className="panel adm-lang">
      <div className="field">
        <label>{t('lang.ui')}</label>
        <select value={i.language} disabled={busy} onChange={e => pick(e.target.value as Lang)}>
          {LANGS.map(l => <option key={l} value={l}>{LANG_TITLES[l]}</option>)}
        </select>
      </div>
      {err && <div className="eg-err">{err}</div>}
    </div>
  )
}

const HUB_FIELDS: [string, string][] = [
  ['base_url', 'hub.url'],
  ['img_model', 'hub.img_model'],
  ['news_model', 'hub.news_model'],
]

function HubCard() {
  const { t } = useTranslation('admin')
  const [data, , reload, err] = useAsync<Dict>(() => api.get('/api/admin/hub'), [])
  const [form, setForm] = useState<Dict>({})
  const [key, setKey] = useState('')
  const [drawKey, setDrawKey] = useState('')
  const [check, setCheck] = useState<{ busy?: boolean; target?: string; models?: string[]; err?: string }>({})
  const [phase, setPhase] = useState<SavePhase>('')
  const [saveErr, setSaveErr] = useState('')
  const [copied, setCopied] = useState('')

  if (err) return <div className="panel"><div className="eg-err">{err}</div></div>
  if (!data) return <div className="dim">{t('common:loading')}</div>

  const fb = data.fallback || {}
  const dirty = Object.keys(form).some(k => form[k] !== data[k]) || !!key.trim() || !!drawKey.trim()
  const keyShown = data.api_key_set ? data : fb
  const val = (k: string) => form[k] ?? data[k]
  const set = (k: string, v: string) => { setForm({ ...form, [k]: v }); setPhase('') }
  const drawKind = val('draw_kind')
  const textBase = val('base_url') || fb.base_url

  async function runCheck(target: 'text' | 'draw') {
    setCheck({ busy: true, target })
    try {
      const body = target === 'draw'
        ? { target, base_url: val('draw_base_url'), api_key: drawKey }
        : { target, base_url: val('base_url'), api_key: key }
      const r = await api.post('/api/admin/hub/check', body)
      setCheck({ target, models: r.models || [] })
    } catch (e: any) { setCheck({ target, err: e.message || t('hub.check_failed') }) }
  }

  const copy = (m: string) => {
    navigator.clipboard.writeText(m).then(() => {
      setCopied(m); setTimeout(() => setCopied(c => (c === m ? '' : c)), 1200)
    })
  }
  const uses = (m: string) => [
    m === val('img_model') && t('hub.use_prompts'), m === val('news_model') && t('hub.use_news'),
    drawKind !== 'worker' && m === val('draw_model') && t('hub.draw'),
  ].filter(Boolean).join(' · ')

  const save = async () => {
    setPhase('busy'); setSaveErr('')
    try {
      const body: Dict = { ...form }
      if (key.trim()) body.api_key = key.trim()
      if (drawKey.trim()) body.draw_api_key = drawKey.trim()
      await api.patch('/api/admin/hub', body)
      setForm({}); setKey(''); setDrawKey(''); setPhase('ok'); reload()
    } catch (e: any) { setSaveErr(e.message); setPhase('') }
  }

  return (
    <div className="adm-hub-grid">
      <div className="adm-hub-col">
        <div className="panel adm-hub">
          <div className="adm-hub-wide adm-hub-head">
            <span className="adm-models-lab">{t('hub.text')}</span>
            <div className="spacer" />
            <button className="ghost tiny" disabled={check.busy} onClick={() => runCheck('text')}>
              {check.busy && check.target === 'text' ? t('hub.checking') : t('hub.check')}
            </button>
          </div>
          {HUB_FIELDS.map(([k, label]) => (
            <div className={`field${k === 'base_url' ? ' adm-hub-wide' : ''}`} key={k}>
              <label>{t(label)}</label>
              <input value={val(k)} spellCheck={false} placeholder={fb[k] || ''}
                onChange={e => set(k, e.target.value)} />
            </div>
          ))}
          <div className="field adm-hub-wide">
            <label>{t('hub.key')}</label>
            <input autoComplete="off" spellCheck={false} value={key}
              placeholder={keyShown.api_key_set ? t('hub.key_set', { tail: keyShown.api_key_tail }) : t('hub.key_unset')}
              onChange={e => { setKey(e.target.value); setPhase('') }} />
          </div>
        </div>
        <div className="panel adm-hub">
          <div className="adm-hub-wide adm-hub-head">
            <span className="adm-models-lab">{t('hub.draw')}</span>
            <div className="spacer" />
            {drawKind !== 'worker' && (
              <button className="ghost tiny" disabled={check.busy} onClick={() => runCheck('draw')}>
                {check.busy && check.target === 'draw' ? t('hub.checking') : t('hub.check')}
              </button>
            )}
          </div>
          <div className="field adm-hub-wide">
            <label>{t('hub.draw_kind')}</label>
            <select value={drawKind} onChange={e => set('draw_kind', e.target.value)}>
              {Object.entries(data.draw_kinds as Dict).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
          </div>
          {drawKind !== 'worker' && <>
            <div className="field adm-hub-wide">
              <label>{t('hub.url')}</label>
              <input value={val('draw_base_url')} spellCheck={false}
                placeholder={textBase ? t('hub.as_text_url', { url: textBase }) : ''}
                onChange={e => set('draw_base_url', e.target.value)} />
            </div>
            <div className="field">
              <label>{t('hub.model')}</label>
              <input value={val('draw_model')} spellCheck={false}
                placeholder="gpt-image-1"
                onChange={e => set('draw_model', e.target.value)} />
            </div>
            <div className="field">
              <label>{t('hub.key')}</label>
              <input autoComplete="off" spellCheck={false} value={drawKey}
                placeholder={data.draw_api_key_set ? t('hub.key_set', { tail: data.draw_api_key_tail }) : t('hub.as_text')}
                onChange={e => { setDrawKey(e.target.value); setPhase('') }} />
            </div>
          </>}
        </div>
        <div className="adm-hub-save">
          <SaveBar dirty={dirty} phase={phase} err={saveErr} onSave={save}
            onReset={() => { setForm({}); setKey(''); setDrawKey(''); setSaveErr('') }} />
        </div>
      </div>
      <div className="panel pad0 adm-models">
        <div className="adm-models-head">
          <span className="adm-models-lab">
            {t('hub.models')}{check.target ? ` · ${check.target === 'draw' ? t('hub.draw') : t('hub.text')}` : ''}
            {check.models ? ` · ${check.models.length}` : ''}
          </span>
        </div>
        {check.err && <div className="eg-err adm-models-pad">{check.err}</div>}
        {check.models && (
          <ul className="adm-model-list">
            {check.models.map(m => {
              const use = uses(m)
              return (
                <li key={m}>
                  <button className={`adm-model${use ? ' on' : ''}`} title={t('hub.copy')} onClick={() => copy(m)}>
                    <span className="mono">{m}</span>
                    <span className="adm-model-tag">{copied === m ? t('hub.copied') : use}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

function CampaignsAdmin() {
  const [list, loading, reload, err] = useAsync<Dict[]>(() => api.get('/api/admin/campaigns'), [])
  const { reload: reloadApp } = useApp()
  const { t } = useTranslation('admin')
  const nav = useNavigate()
  const [name, setName] = useState('')
  const [fail, setFail] = useState('')

  const create = async () => {
    if (!name.trim()) return
    setFail('')
    try {
      await api.post('/api/campaigns', { name: name.trim() })
      setName(''); reload(); reloadApp()
    } catch (e: any) { setFail(e.message) }
  }

  if (err) return <div className="panel"><div className="eg-err">{err}</div></div>

  return (
    <div className="panel pad0 adm-camps">
      <table>
        <thead>
          <tr><th>{t('camps.campaign')}</th><th>{t('camps.gm')}</th><th>{t('camps.players')}</th><th>{t('camps.created')}</th><th /></tr>
        </thead>
        <tbody>
          {(list || []).map(cp => (
            <CampaignRow key={cp.id} cp={cp} open={() => {
              store.campaign = cp.id; store.viewAs = null; nav('/crew')
            }} />
          ))}
        </tbody>
      </table>
      {loading && !list && <div className="dim adm-camps-pad">{t('common:loading')}</div>}
      <div className="row adm-camps-pad adm-camp-new">
        <input placeholder={t('camps.new')} value={name} onChange={e => setName(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') create() }} />
        <button disabled={!name.trim()} onClick={create}>{t('camps.create')}</button>
      </div>
      {fail && <div className="chip red">{fail}</div>}
      <ImportBox onDone={() => { reload(); reloadApp() }} />
    </div>
  )
}

function CampaignRow({ cp, open }: { cp: Dict; open: () => void }) {
  const { t } = useTranslation('admin')
  const [job, setJob] = useJob(download)
  const running = job?.status === 'running'

  const start = async (files: boolean) => {
    try {
      setJob(await api.post(`/api/admin/campaigns/${cp.id}/export`, { files }))
    } catch (e: any) { setJob({ id: '', status: 'failed', stage: '', done: 0, total: 0, error: e.message }) }
  }

  return (
    <tr>
      <td>
        <strong>{cp.name}</strong>
        {job && <TransferBar job={job} />}
      </td>
      <td>{cp.gms.join(', ')}</td>
      <td className="mono">{cp.players}</td>
      <td className="mono dim">{new Date(cp.created_at).toLocaleDateString(locale())}</td>
      <td>
        <div className="row adm-camp-acts">
          {cp.member && <button className="ghost tiny" onClick={open}>{t('camps.open')}</button>}
          <button className="ghost tiny" disabled={running} title={t('xfer.json_hint')}
            onClick={() => start(false)}>JSON</button>
          <button className="ghost tiny" disabled={running} title={t('xfer.zip_hint')}
            onClick={() => start(true)}>{t('xfer.export')}</button>
        </div>
      </td>
    </tr>
  )
}

function ImportBox({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation('admin')
  const nav = useNavigate()
  const pick = useRef<HTMLInputElement>(null)
  const [job, setJob] = useJob(onDone)
  const running = job?.status === 'running'

  const send = async (file: File) => {
    setJob({ id: '', status: 'running', stage: 'upload', done: 0, total: file.size })
    try {
      const next: Job = await upload(file, (done, total) =>
        setJob(j => (j && j.stage === 'upload' ? { ...j, done, total } : j)))
      setJob({ ...next, stage: next.stage === 'upload' ? 'read' : next.stage })
    } catch (e: any) { setJob({ id: '', status: 'failed', stage: 'upload', done: 0, total: 0, error: e.message }) }
  }

  return (
    <div className="adm-camps-pad adm-import">
      <div className="row">
        <button disabled={running} onClick={() => pick.current?.click()}>{t('xfer.import')}</button>
        <span className="small dim">{t('xfer.import_hint')}</span>
        <input ref={pick} type="file" accept=".zip,.json" hidden onChange={e => {
          const f = e.target.files?.[0]
          e.target.value = ''
          if (f) send(f)
        }} />
      </div>
      {job && <TransferBar job={job} />}
      {job?.status === 'done' && (
        <div className="row">
          <span>{t('xfer.imported', { name: job.name })}</span>
          <button className="ghost tiny" onClick={() => {
            store.campaign = job.campaign_id; store.viewAs = null; nav('/crew')
          }}>{t('camps.open')}</button>
        </div>
      )}
    </div>
  )
}

const ROLES = ['gm', 'player', 'observer']

function UsersAdmin() {
  const [list, loading, reload, err] = useAsync<Dict[]>(() => api.get('/api/admin/users'), [])
  const [camps] = useAsync<Dict[]>(() => api.get('/api/admin/campaigns'), [])
  const { me } = useApp()
  const { t } = useTranslation('admin')
  const [busy, setBusy] = useState('')
  const [fail, setFail] = useState('')

  const run = async (id: string, f: () => Promise<any>) => {
    setBusy(id); setFail('')
    try { await f(); reload() } catch (e: any) { setFail(e.message) }
    setBusy('')
  }
  const patch = (u: Dict, body: Dict) => run(u.id, () => api.patch(`/api/admin/users/${u.id}`, body))
  const grant = (u: Dict, cid: string, role: string) =>
    run(u.id, () => api.put(`/api/admin/users/${u.id}/campaigns/${cid}`, { role }))
  const revoke = (u: Dict, c: Dict) => {
    if (!confirm(t('users.revoke_confirm', { login: u.login, name: c.name }))) return
    run(u.id, () => api.del(`/api/admin/users/${u.id}/campaigns/${c.id}`))
  }

  if (err) return <div className="panel"><div className="eg-err">{err}</div></div>

  return (
    <div className="panel pad0 adm-camps adm-users">
      <table>
        <thead>
          <tr><th>{t('users.user')}</th><th>{t('users.login')}</th><th>{t('users.access')}</th><th>{t('users.since')}</th><th>{t('users.signin')}</th><th>{t('users.admin')}</th></tr>
        </thead>
        <tbody>
          {(list || []).map(u => {
            const self = u.id === me?.id
            const off = !!busy
            const free = (camps || []).filter(cp => !u.campaigns.some((c: Dict) => c.id === cp.id))
            return (
              <tr key={u.id} className={u.is_active ? '' : 'adm-user-blocked'}>
                <td><strong>{u.display_name}</strong>{self && <span className="dim"> · {t('users.you')}</span>}</td>
                <td className="mono">{u.login}</td>
                <td>
                  <div className="adm-user-camps">
                    {u.campaigns.map((c: Dict) => (
                      <span key={c.id} className="adm-user-camp">
                        <span>{c.name}</span>
                        <select value={c.role} disabled={off || c.owner} onChange={e => grant(u, c.id, e.target.value)}>
                          {ROLES.map(k => <option key={k} value={k}>{t(`roles.${k}`)}</option>)}
                        </select>
                        {!c.owner && <button className="ghost tiny" disabled={off} title={t('users.revoke')}
                          onClick={() => revoke(u, c)}>×</button>}
                      </span>
                    ))}
                    {free.length > 0 && (
                      <select className="adm-user-add" value="" disabled={off}
                        onChange={e => e.target.value && grant(u, e.target.value, 'player')}>
                        <option value="">{t('users.add_campaign')}</option>
                        {free.map(cp => <option key={cp.id} value={cp.id}>{cp.name}</option>)}
                      </select>
                    )}
                  </div>
                </td>
                <td className="mono dim">{new Date(u.created_at).toLocaleDateString(locale())}</td>
                <td>
                  <button className={`ghost tiny ${u.is_active ? '' : 'adm-user-unblock'}`} disabled={off || self}
                    onClick={() => patch(u, { is_active: !u.is_active })}>
                    {u.is_active ? t('users.block') : t('users.unblock')}
                  </button>
                </td>
                <td>
                  <label className="adm-user-admin">
                    <input type="checkbox" checked={u.is_admin} disabled={off || (self && u.is_admin)}
                      onChange={() => patch(u, { is_admin: !u.is_admin })} />
                    {u.is_admin ? t('users.yes') : t('users.no')}
                  </label>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {loading && !list && <div className="dim adm-camps-pad">{t('common:loading')}</div>}
      {fail && <div className="adm-camps-pad"><span className="chip red">{fail}</span></div>}
    </div>
  )
}
