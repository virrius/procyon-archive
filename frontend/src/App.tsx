import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { HashRouter, Link, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { api, c, isPublicView, PUBLIC_VIEW, store, type Dict } from './api'
import { AppProvider, useApp } from './ctx'
import { Chip, Select } from './ui'
import { useLayer } from './layers'
import { GenWorkerBadge } from './components/GenWorkerBadge'
import SideNav from './components/SideNav'
import { WorldTime } from './components/WorldTime'
import Login from './pages/Login'
import Campaigns from './pages/Campaigns'
import Crew from './pages/Crew'
import Database from './pages/Database'
import Frames from './pages/Frames'
import MapPage from './pages/MapPage'
import News from './pages/News'
import GMSpace from './pages/GMSpace'
import AdminSpace from './pages/AdminSpace'
import EntityPage from './pages/EntityPage'
import { DefaultPasswordGate } from './components/PasswordModal'

/** Куда ведёт находка: сама цель, а не раздел, где её ещё искать */
function searchHref(r: Dict): string {
  const id = encodeURIComponent(String(r.target_id || ''))
  if (!id) return ''
  switch (r.target_type) {
    case 'entity': return `/entity/${id}`
    case 'clock': return `/database/clocks?open=${id}`
    case 'message': return `/crew/mail?open=${id}`
    case 'news': return `/news?open=${id}`
    case 'rule': return `/gm/rules?open=${id}`
    case 'marker': return r.map_id ? `/map/${encodeURIComponent(r.map_id)}?m=${id}` : ''
    default: return ''
  }
}

const HIT_WORD: Dict = {
  message: 'message', news: 'news', note: 'note',
  'block:entity': 'block_entity', 'block:clock': 'block_clock', 'block:rule': 'block_rule',
}

function GlobalSearch() {
  const [q, setQ] = useState('')
  const [res, setRes] = useState<Dict[]>([])
  const [open, setOpen] = useState(false)
  const [hot, setHot] = useState(0)
  const box = useRef<HTMLDivElement>(null)
  const nav = useNavigate()
  const { L } = useApp()
  const { t } = useTranslation('app')
  useEffect(() => {
    if (q.trim().length < 2) { setRes([]); return }
    const t = setTimeout(() => {
      api.get(`${c()}/search?q=${encodeURIComponent(q)}`)
        .then(r => {
          setRes(((r || []) as Dict[]).filter(x => searchHref(x)))
          setHot(0); setOpen(true)
        }).catch(() => {})
    }, 250)
    return () => clearTimeout(t)
  }, [q])

  const shown = open && res.length > 0
  const close = () => setOpen(false)
  useLayer(shown, close)

  useEffect(() => {
    if (!shown) return
    const away = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) close() }
    document.addEventListener('mousedown', away)
    return () => document.removeEventListener('mousedown', away)
  }, [shown])

  useEffect(() => {
    if (shown) box.current?.querySelector('.search-pop .on')?.scrollIntoView({ block: 'nearest' })
  }, [hot, shown])

  const go = (r: Dict) => { close(); setQ(''); nav(searchHref(r)) }
  const keys = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!res.length) return
    const step = e.key === 'ArrowDown' ? 1 : e.key === 'ArrowUp' ? -1 : 0
    if (step) {
      e.preventDefault()
      if (shown) setHot(h => (h + step + res.length) % res.length)
      else setOpen(true)
    } else if (e.key === 'Enter' && shown && res[hot]) {
      e.preventDefault()
      go(res[hot])
    }
  }
  const word = (r: Dict) => {
    if (r.type === 'entity') return L(r.kind)
    const k = HIT_WORD[r.type === 'block' ? `block:${r.target_type}` : r.type]
    return k ? t(`hit.${k}`) : ''
  }

  return (
    <div className="top-search" ref={box}>
      <input placeholder={t('search')} value={q} role="combobox"
        aria-expanded={shown} aria-controls="search-pop" aria-autocomplete="list"
        onChange={e => setQ(e.target.value)} onFocus={() => setOpen(true)} onKeyDown={keys} />
      {shown && (
        <div className="search-pop" id="search-pop" role="listbox">
          {res.map((r, i) => (
            <Link key={i} to={searchHref(r)} role="option" aria-selected={i === hot}
              className={i === hot ? 'on' : undefined}
              onMouseEnter={() => setHot(i)} onClick={() => { close(); setQ('') }}>
              <div className="row"><Chip>{word(r)}</Chip><strong>{r.title}</strong></div>
              {r.snippet && <div className="small dim">{r.snippet}</div>}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function ViewAsSwitch() {
  const { campaign, reload } = useApp()
  const { t } = useTranslation('app')
  if (!campaign?.is_real_gm && !store.viewAs) return null
  const players = (campaign?.members || []).filter((m: Dict) => m.role !== 'gm')
  return (
    <Select className="viewas-pick" value={store.viewAs || ''} empty={t('viewas.gm')} title={t('viewas.title')}
      options={[PUBLIC_VIEW, ...players.map((m: Dict) => m.id)]}
      optionLabel={v => v === PUBLIC_VIEW
        ? t('viewas.public')
        : t('viewas.as', { name: players.find((m: Dict) => m.id === v)?.display_name || v })}
      onChange={v => { store.viewAs = v || null; reload(); location.reload() }} />
  )
}

/** /entity/:id → /entity/:id/profile */
function EntityIndex() {
  const { id } = useParams()
  return <Navigate to={`/entity/${id}/profile`} replace />
}

function Shell() {
  const { campaign, isGM, L } = useApp()
  const { t } = useTranslation('app')
  const isRealGM = useApp().isRealGM && !isPublicView()
  const [navOpen, setNavOpen] = useState(false)

  if (!store.token) return <Navigate to="/login" replace />
  if (!store.campaign) return <Navigate to="/campaigns" replace />
  /* кампания ещё летит с сервера: роли пока нет, и маршруты ГМа не смонтированы.
     Показать сейчас Routes — значит выкинуть ГМа с его страницы на общий экран */
  if (!campaign) {
    return (
      <div className="app">
        <div className="shell">
          <div className="main-col">
            <main className="content frame-in"><div className="dim">{t('loading_campaign')}</div></main>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="frame-top">
        <div className="top-bar">
          <div className="top-in">
            <button className="nav-burger" aria-expanded={navOpen} aria-label={t('sections')}
              title={t('sections_hint')} onClick={() => setNavOpen(v => !v)}>
              <i /><i /><i />
            </button>
            <div className="brand inline">Procyon<span>{t('archive')}</span></div>
            <GlobalSearch />
            <div className="spacer" />
            <WorldTime canShift={isRealGM} />
            <div className="spacer" />
            {isRealGM && <GenWorkerBadge compact />}
            <ViewAsSwitch />
            <Chip tone={isGM ? 'red' : 'cyan'}>
              {campaign?.my_role === 'gm' ? t('gm') : L(campaign?.my_role) || '…'}
            </Chip>
          </div>
        </div>

        {store.viewAs && (
          <div className={`viewas-bar${isPublicView() ? ' show' : ''}`}>
            {isPublicView()
              ? t('viewas.public_bar')
              : t('viewas.player_bar')}
            <button className="tiny ghost" style={{ marginLeft: 10 }}
              onClick={() => { store.viewAs = null; location.reload() }}>{t('viewas.back')}</button>
          </div>
        )}
      </header>

      <div className="shell">
        <SideNav open={navOpen} onClose={() => setNavOpen(false)} />
        <div className="main-col">
          <main className="content frame-in">
            <Routes>
              <Route path="/crew" element={<Navigate to="/crew/ship" replace />} />
              <Route path="/crew/*" element={<Crew />} />

              <Route path="/news" element={<News />} />

              <Route path="/database" element={<Navigate to="/database/npc" replace />} />
              <Route path="/database/*" element={<Database />} />

              <Route path="/characters" element={<Navigate to="/crew/team" replace />} />
              <Route path="/characters/:cid" element={<CharacterRedirect />} />

              <Route path="/frames" element={<Frames />} />
              <Route path="/frames/*" element={<Navigate to="/frames" replace />} />

              <Route path="/map" element={<MapPage />} />
              <Route path="/map/:mapId" element={<MapPage />} />

              {isRealGM && <Route path="/gm" element={<Navigate to="/gm/accounts" replace />} />}
              {isRealGM && <Route path="/gm/*" element={<GMSpace />} />}

              <Route path="/entity/:id" element={<EntityIndex />} />
              <Route path="/entity/:id/*" element={<EntityPage />} />

              <Route path="*" element={<Navigate to="/crew/ship" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </div>
  )
}

/* старые ссылки на персонажа ведут в «Экипаж · Команда» */
function CharacterRedirect() {
  const { cid } = useParams()
  return <Navigate to={cid ? `/crew/team/${cid}` : '/crew/team'} replace />
}

export default function App() {
  return (
    <HashRouter>
      <AppProvider>
        <DefaultPasswordGate />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/campaigns" element={<Campaigns />} />
          <Route path="/admin/*" element={<AdminSpace />} />
          <Route path="*" element={<Shell />} />
        </Routes>
      </AppProvider>
    </HashRouter>
  )
}
