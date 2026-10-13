import type { Dict } from '../../api'
import i18n, { locale } from '../../i18n'

export type Candidate = { id: string; url: string }
export type Status = 'pending' | 'claimed' | 'ready' | 'done' | 'failed'
export type Attempt = {
  id: string; kind: 'txt2img' | 'inpaint'; status: Status; error: string
  entity_id: string | null; candidates: Candidate[]; n_images: number
  prompt: string; width: number; height: number; denoise: number
  source_url: string | null; params: Dict; created_at: string; expires_at?: string | null
}

export const isLive = (s: Status) => s === 'pending' || s === 'claimed'
/** How many hours unpicked candidates have left: then the server deletes them */
export const hoursLeft = (iso: string) => Math.max(0, Math.ceil((+new Date(iso) - Date.now()) / 3600e3))
export const CYRILLIC = /[а-яёА-ЯЁ]/

/* Native Z-Image sizes: sides are multiples of 16 at a budget of about a megapixel */
export type Aspect = { key: string; width: number; height: number }
export const ASPECTS: Aspect[] = [
  { key: '4:5', width: 832, height: 1216 },
  { key: '3:2', width: 1216, height: 832 },
  { key: '16:9', width: 1344, height: 768 },
  { key: '1:1', width: 1024, height: 1024 },
  { key: '9:16', width: 768, height: 1344 },
]
export const aspectOf = (key?: string) => ASPECTS.find(a => a.key === key) ?? ASPECTS[0]
export const aspectBySize = (w: number, h: number) =>
  ASPECTS.find(a => a.width === w && a.height === h)?.key ?? `${w}×${h}`

/* Old form snapshots stored the aspect index in a list of the same order */
export const aspectKey = (v: unknown): string | undefined =>
  typeof v === 'number' ? ASPECTS[v]?.key : typeof v === 'string' && ASPECTS.some(a => a.key === v) ? v : undefined

export type PromptKind = 'person' | 'frame' | 'action'
export const KINDS: PromptKind[] = ['person', 'frame', 'action']

export type FrameView = 'ship' | 'handheld' | 'structure' | 'planet' | 'landscape' | 'interior'
export const VIEWS: FrameView[] = ['ship', 'handheld', 'structure', 'planet', 'landscape', 'interior']

// the register goes to the hub as a setting-corner dictionary, and into the prompt line as its own style head
export type Register = string
export const REGISTERS: Register[] = ['derelict', 'junk', 'frontier', 'hightech', 'hegemony', 'luxe', 'precursor']
export const codeRegisters = (): [Register, string, string][] =>
  REGISTERS.map(r => [r, i18n.t(`studio:register.${r}`), i18n.t(`studio:register_hint.${r}`)])

export const DEFAULT_ASPECT: Record<string, string> = {
  person: '4:5', action: '16:9',
  ship: '3:2', handheld: '3:2', structure: '16:9',
  planet: '1:1', landscape: '16:9', interior: '16:9',
}
export const startAspect = (kind: PromptKind, view: FrameView) =>
  DEFAULT_ASPECT[kind === 'frame' ? view : kind] || '4:5'

/** Direction and subtype by card kind: a ship gets a ship frame, a place goes by its type */
export function kindForEntity(e: Dict): { kind: PromptKind; view: FrameView } {
  const lt = String(e.fields?.loc_type || '')
  if (e.kind === 'ship') return { kind: 'frame', view: 'ship' }
  if (e.kind === 'item') return { kind: 'frame', view: 'handheld' }
  if (e.kind === 'location') {
    if (lt === 'planet') return { kind: 'frame', view: 'planet' }
    if (lt === 'station' || lt === 'gate') return { kind: 'frame', view: 'structure' }
    if (lt === 'port') return { kind: 'frame', view: 'interior' }
    return { kind: 'frame', view: 'landscape' }
  }
  return { kind: 'person', view: 'interior' }
}

export const kindTitle = (p: Dict) => {
  if (p.kind === 'frame') return i18n.t(VIEWS.includes(p.view) ? `studio:view.${p.view}` : 'studio:kind.frame')
  return KINDS.includes(p.kind) ? i18n.t(`studio:kind.${p.kind}`) : ''
}
// campaign registers come from the server: ones added by the admin get labels the same way as built-in ones
let loadedRegisters: [Register, string, string][] = []
export const rememberRegisters = (rows: [Register, string, string][]) => { loadedRegisters = rows }
export const registerTitle = (r?: string) =>
  loadedRegisters.find(([k]) => k === r)?.[1]
  || (r && REGISTERS.includes(r) ? i18n.t(`studio:register.${r}`) : r) || ''

/* Prompt parts: the hub writes them, the code joins them in this order. Flagged: a part of its own for each
   take (face, pose, light); unflagged: shared by all */
export const PARTS: Record<PromptKind, [string, boolean][]> = {
  person: [['look', false], ['face', true], ['outfit', false], ['pose', true], ['place', false], ['light', true]],
  frame: [['subject', false], ['people', false], ['place', false], ['angle', true], ['light', true]],
  action: [['subject', false], ['place', false], ['angle', true], ['light', true]],
}
export const PART_LABELS: Record<string, string> = {
  look: 'part.look', face: 'part.face', outfit: 'part.outfit', pose: 'part.pose', place: 'part.place',
  light: 'part.light', subject: 'part.subject', people: 'part.people', angle: 'part.angle',
}

export const STRENGTH: [string, number][] = [
  ['replace', 1.0],
  ['touch_up', 0.75],
]
export const strengthTitle = (d: number) => i18n.t(`studio:strength.${d >= 0.99 ? STRENGTH[0][0] : STRENGTH[1][0]}`)

export type Outfit = { key: string; title: string; wear: string[]; image?: string }

/** Where the picked candidate of an attempt goes */
export type Dest = 'entity' | 'scene' | 'replace'
export const destOf = (a: Attempt): Dest =>
  a.kind === 'inpaint' && a.params?.mode !== 'new' ? 'replace' : a.entity_id ? 'entity' : 'scene'

export const when = (iso: string) => {
  const d = new Date(iso)
  return isNaN(+d) ? '' : d.toLocaleTimeString(locale(), { hour: '2-digit', minute: '2-digit' })
}
