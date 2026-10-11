import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router-dom'
import { api, c, store, type Dict } from './api'
import i18n from './i18n'

type Ctx = {
  meta: Dict | null
  campaign: Dict | null
  me: Dict | null
  reload: () => void
  isGM: boolean
  isRealGM: boolean
  isAdmin: boolean
  memberName: (id?: string | null) => string
  L: (key?: string | null) => string
}

const AppCtx = createContext<Ctx>({
  meta: null, campaign: null, me: null, reload: () => {}, isGM: false, isRealGM: false,
  isAdmin: false, memberName: () => '', L: k => k || '',
})

export const useApp = () => useContext(AppCtx)

export function AppProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Dict | null>(null)
  const [loaded, setLoaded] = useState<Dict | null>(null)
  const [me, setMe] = useState<Dict | null>(null)
  const [tick, setTick] = useState(0)

  const { i18n } = useTranslation()
  useEffect(() => { api.get('/api/meta').then(setMeta).catch(() => {}) }, [i18n.language])
  // токен и кампания живут в localStorage: без подписки на переход провайдер не
  // перерисуется после входа или смены кампании и останется со старыми
  useLocation()
  const token = store.token
  const campaignId = store.campaign
  const campaign = loaded?.id === campaignId ? loaded : null

  useEffect(() => {
    if (!token) { setMe(null); return }
    api.get('/api/auth/me').then(setMe).catch(() => setMe(null))
  }, [tick, token])
  useEffect(() => {
    if (!campaignId || !token) { setLoaded(null); return }
    let live = true
    api.get(c()).then(r => live && setLoaded(r)).catch((e: any) => {
      if (!live) return
      setLoaded(null)
      // кампанию удалили или участника убрали: сперва снимаем «глазами игрока», потом саму кампанию
      if (e?.status === 403 || e?.status === 404) {
        if (store.viewAs) store.viewAs = null
        else store.campaign = null
        setTick(t => t + 1)
      }
    })
    return () => { live = false }
  }, [tick, token, campaignId])

  const memberName = (id?: string | null) => {
    if (!id || !campaign) return ''
    const m = (campaign.members || []).find((x: Dict) => x.id === id)
    return m ? m.display_name : ''
  }

  const L = (key?: string | null) => {
    if (!key) return ''
    return (meta?.labels && meta.labels[key]) || key
  }

  return (
    <AppCtx.Provider value={{
      meta, campaign, me, reload: () => setTick(t => t + 1),
      isGM: campaign?.my_role === 'gm',
      isRealGM: !!campaign?.is_real_gm,
      isAdmin: !!me?.is_admin,
      memberName, L,
    }}>
      {children}
    </AppCtx.Provider>
  )
}

/** Загрузка с обновлением. reload() тихий: старые данные остаются на экране,
 *  loading не поднимается — обновление не мигает списком. reload(false) — с индикатором. */
export function useAsync<T>(fn: () => Promise<T>, deps: any[] = []):
  [T | null, boolean, (silent?: boolean) => void, string] {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [tick, setTick] = useState(0)
  const silent = useRef(false)
  useEffect(() => {
    let alive = true
    const quiet = silent.current
    silent.current = false
    if (!quiet) setLoading(true)
    setErr('')
    fn().then(d => { if (alive) { setData(d); setLoading(false) } })
      .catch(e => { if (alive) { setErr(e.message || i18n.t('common:error')); setLoading(false) } })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])
  const reload = (quiet = true) => { silent.current = quiet; setTick(t => t + 1) }
  return [data, loading, reload, err]
}
