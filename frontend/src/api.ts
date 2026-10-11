import { lang } from './i18n'

export type Dict = Record<string, any>

const TOKEN_KEY = 'pa_token'
const CAMP_KEY = 'pa_campaign'
const VIEWAS_KEY = 'pa_viewas'

// куки не различают порты: два экземпляра на одном хосте затирали бы токен друг друга
const COOKIE = location.port ? `${TOKEN_KEY}_${location.port}` : TOKEN_KEY

function syncCookie(v: string | null) {
  document.cookie = v
    ? `${COOKIE}=${v}; path=/; max-age=2592000; SameSite=Lax`
    : `${COOKIE}=; path=/; max-age=0; SameSite=Lax`
}

export const store = {
  get token() { return localStorage.getItem(TOKEN_KEY) },
  set token(v: string | null) {
    v ? localStorage.setItem(TOKEN_KEY, v) : localStorage.removeItem(TOKEN_KEY)
    syncCookie(v)
  },
  get campaign() { return localStorage.getItem(CAMP_KEY) },
  set campaign(v: string | null) { v ? localStorage.setItem(CAMP_KEY, v) : localStorage.removeItem(CAMP_KEY) },
  get viewAs() { return localStorage.getItem(VIEWAS_KEY) },
  set viewAs(v: string | null) { v ? localStorage.setItem(VIEWAS_KEY, v) : localStorage.removeItem(VIEWAS_KEY) },
}

// <img src> ходит без заголовка и живёт на этой куке, а ставится она только при
// логине — на другом хосте (127.0.0.1 вместо localhost) её нет. Подсыпаем на старте
if (store.token) syncCookie(store.token)
// общая pa_token осталась от версий без суффикса порта: «Выйти» её не стирает
if (COOKIE !== TOKEN_KEY) document.cookie = `${TOKEN_KEY}=; path=/; max-age=0; SameSite=Lax`

/** витрина «как видят игроки»: общий вид без конкретного участника, только чтение */
export const PUBLIC_VIEW = 'crew'
export const isPublicView = () => store.viewAs === PUBLIC_VIEW

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

async function request(method: string, path: string, body?: any, raw = false): Promise<any> {
  const headers: Dict = { 'Accept-Language': lang() }
  if (store.token) headers['Authorization'] = `Bearer ${store.token}`
  if (store.viewAs) headers['X-View-As'] = store.viewAs
  let payload: any = undefined
  if (body instanceof FormData) payload = body
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }

  const res = await fetch(path, { method, headers, body: payload })
  if (res.status === 401) { store.token = null; location.hash = '#/login' }
  if (!res.ok) {
    let msg = res.statusText
    try { const j = await res.json(); msg = j.detail || msg } catch { /* noop */ }
    throw new ApiError(res.status, typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  if (raw) return res
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  get: (p: string) => request('GET', p),
  post: (p: string, b?: any) => request('POST', p, b),
  patch: (p: string, b?: any) => request('PATCH', p, b),
  put: (p: string, b?: any) => request('PUT', p, b),
  del: (p: string) => request('DELETE', p),
  raw: (p: string) => request('GET', p, undefined, true),
}

export const c = () => `/api/campaigns/${store.campaign}`

/** Соль в адресе миниатюры. Адрес снимка не меняется, когда правят рамку превью, а
 *  браузеры, однажды получившие миниатюру без Cache-Control, держат её часами и не
 *  ходят на сервер. Поднять число — и стол увидит миниатюры заново. */
const THUMB_SALT = 2

/** Миниатюра вместо оригинала: в плитку 230px незачем тянуть кадр 1344×768.
 *  Ширины закрыты на сервере (240/480/960), лишние игнорируются и вернут оригинал. */
export const thumb = (url?: string | null, w: 240 | 480 | 960 = 480, ver?: number) =>
  !url ? '' : `${url}${url.includes('?') ? '&' : '?'}w=${w}&s=${THUMB_SALT}`
    + (ver ? `&r=${ver}` : '')

/** Миниатюра всего кадра, мимо рамки превью: рамка кадрирует снимок карточки,
 *  а в списке вложений файл показываем таким, какой он есть. */
export const thumbFull = (url?: string | null, w: 240 | 480 | 960 = 480, ver?: number) =>
  !url ? '' : `${thumb(url, w, ver)}&crop=0`
