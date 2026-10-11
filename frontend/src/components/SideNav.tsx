import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { api, c, store, type Dict } from '../api'
import { useApp } from '../ctx'
import '../styles.nav.css'

type Group = {
  root: string           // префикс раздела: по нему считаем активность
  label: string          // ключ в словаре nav
  to: string             // куда ведёт заголовок раздела
  items?: [string, string][]
}

const GROUPS: Group[] = [
  {
    root: '/crew', label: 'crew', to: '/crew/ship',
    items: [
      ['/crew/ship', 'ship'],
      ['/crew/team', 'team'],
      ['/crew/relations', 'relations'],
      ['/crew/mail', 'mail'],
      ['/crew/jobs', 'jobs'],
      ['/crew/items', 'items'],
    ],
  },
  { root: '/news', label: 'news', to: '/news' },
  {
    root: '/database', label: 'database', to: '/database/npc',
    items: [
      ['/database/npc', 'npc'],
      ['/database/factions', 'factions'],
      ['/database/locations', 'locations'],
      ['/database/clocks', 'clocks'],
    ],
  },
  { root: '/map', label: 'map', to: '/map' },
  { root: '/frames', label: 'frames', to: '/frames' },
]

const GM_GROUP: Group = {
  root: '/gm', label: 'gm', to: '/gm/accounts',
  // все разделы ГМа живут здесь: своей полосы вкладок у страницы больше нет —
  // она отнимала высоту у доски, дублируя это же меню
  items: [
    ['/gm/accounts', 'accounts'],
    ['/gm/boards', 'boards'],
    ['/gm/history', 'history'],
    ['/gm/rules', 'rules'],
    ['/gm/looks', 'looks'],
  ],
}

const inSection = (path: string, root: string) =>
  path === root || path.startsWith(root + '/')

export default function SideNav({ open, onClose }: { open?: boolean; onClose?: () => void }) {
  const { campaign, isGM, isAdmin } = useApp()
  const nav = useNavigate()
  const { pathname } = useLocation()
  const { t } = useTranslation('nav')

  const groups = isGM ? [...GROUPS, GM_GROUP] : GROUPS

  // заказанные депеши пишутся в фоне: ГМ видит в меню, что черновики готовы
  const [news, setNews] = useState<Dict | null>(null)
  useEffect(() => {
    if (!isGM || !campaign) return
    let alive = true
    const pull = () => api.get(`${c()}/news/jobs/summary`)
      .then(r => { if (alive) setNews(r) }).catch(() => {})
    pull()
    const t = setInterval(pull, 15000)
    return () => { alive = false; clearInterval(t) }
  }, [isGM, campaign, pathname])
  const newsMark = !news ? null
    : news.drafts > 0 ? <span className="nav-badge" title={t('drafts_wait')}>{news.drafts}</span>
      : news.pending > 0 ? <span className="nav-badge wait">{t('writing')}</span> : null

  // на узком экране меню выезжает сбоку и закрывается после перехода
  useEffect(() => { onClose?.() }, [pathname])

  return (
    <>
    {open && <div className="nav-scrim" onClick={onClose} />}
    <nav className={`sidenav${open ? ' open' : ''}`} aria-label={t('sections')}>
      <div className="sidenav-scroll">
        {groups.map(g => {
          const on = inSection(pathname, g.root)
          return (
            <div className="nav-group" key={g.root}>
              <Link to={g.to} className={on ? 'nav-head on' : 'nav-head'}>
                {t(g.label)}{g.root === '/news' && newsMark}
              </Link>
              {g.items && (
                <div className={on ? 'nav-sub on' : 'nav-sub'}>
                  {g.items.map(([to, label]) => (
                    <NavLink key={to} to={to} end={to === g.root}
                      className={({ isActive }) => (isActive ? 'active' : undefined)}>
                      {t(label)}
                    </NavLink>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="sidenav-foot">
        <div className="sidenav-camp">
          <div className="sidenav-lab">{t('campaign')}</div>
          <div className="mono">{campaign?.name || '…'}</div>
        </div>
        <div className="row">
          {isAdmin && (
            <button className="ghost tiny" onClick={() => nav('/admin')}>Admin space</button>
          )}
          <button className="ghost tiny" onClick={() => {
            store.campaign = null; store.viewAs = null; nav('/campaigns')
          }}>{t('switch_campaign')}</button>
          <button className="ghost tiny" onClick={() => {
            store.token = null; store.campaign = null; store.viewAs = null
            location.hash = '#/login'; location.reload()
          }}>{t('logout')}</button>
        </div>
      </div>
    </nav>
    </>
  )
}

export { SideNav }
