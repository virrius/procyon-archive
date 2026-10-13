import { lang } from './i18n'

export type Dict = Record<string, any>

const TOKEN_KEY = 'pa_token'
const CAMP_KEY = 'pa_campaign'
const VIEWAS_KEY = 'pa_viewas'

// cookies ignore ports: two instances on one host would overwrite each other's token
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

// <img src> requests carry no header and rely on this cookie, which is set only at
// login — on another host (127.0.0.1 instead of localhost) it's missing. Set it on startup
if (store.token) syncCookie(store.token)
// the shared pa_token is left over from versions without a port suffix: “sign out” doesn't clear it
if (COOKIE !== TOKEN_KEY) document.cookie = `${TOKEN_KEY}=; path=/; max-age=0; SameSite=Lax`

/** “as players see it” preview: the shared view without a specific member, read-only */
export const PUBLIC_VIEW = 'crew'
export const isPublicView = () => store.viewAs === PUBLIC_VIEW

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

async function request(method: string, path: string, body?: any): Promise<any> {
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
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  get: (p: string) => request('GET', p),
  post: (p: string, b?: any) => request('POST', p, b),
  patch: (p: string, b?: any) => request('PATCH', p, b),
  put: (p: string, b?: any) => request('PUT', p, b),
  del: (p: string) => request('DELETE', p),
}

export const c = () => `/api/campaigns/${store.campaign}`

/** Salt in the thumbnail URL. The image URL doesn't change when the preview crop is edited, and
 *  browsers that once got a thumbnail without Cache-Control keep it for hours without
 *  hitting the server. Bump the number and the table sees fresh thumbnails. */
const THUMB_SALT = 2

/** A thumbnail instead of the original: no need to load 1344×768 into a 230px tile.
 *  Widths are fixed on the server (240/480/960); others are ignored and return the original. */
export const thumb = (url?: string | null, w: 240 | 480 | 960 = 480, ver?: number) =>
  !url ? '' : `${url}${url.includes('?') ? '&' : '?'}w=${w}&s=${THUMB_SALT}`
    + (ver ? `&r=${ver}` : '')

/** A thumbnail of the whole image, ignoring the preview crop: the crop frames the entry image,
 *  while the attachment list shows the file as it is. */
export const thumbFull = (url?: string | null, w: 240 | 480 | 960 = 480, ver?: number) =>
  !url ? '' : `${thumb(url, w, ver)}&crop=0`
