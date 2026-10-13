import { type Dict } from '../../api'
import { dict, entries, list, num, type Entry } from '../sheet/parts'

export const STRESS_MAX = 9
export const TRAUMA_MAX = 4
export const HEAL_MAX = 6
export const ACT_MAX = 3
export const ATTR_XP = 6
export const PB_XP = 8
export const CREDS_MAX = 4
export const STASH_MAX = 40
export const VET_MAX = 3
export const LOADS: [string, number][] = [['light', 3], ['normal', 5], ['heavy', 6]]
export const HARM_KEYS = ['h3', 'h2a', 'h2b', 'h1a', 'h1b'] as const
export const ARMOR_KEYS = ['armor', 'heavy', 'special'] as const

export type Attr = { key: string; name: string; actions: { key: string; name: string; text?: string; more?: string }[] }
export type Book = {
  key: string; label: string; blurb: string; unique: Entry; talents: Entry[]; items: Entry[]
  xp_trigger: string; start: Dict
}

/** Playbook by the `fields.playbook` value: a label there (as in the campaign book), less often a key. */
export function playbookKey(meta: Dict | null, value: any): string {
  const v = String(value || '').trim()
  if (!v) return ''
  const pbs = dict(meta?.playbooks)
  if (pbs[v]) return v
  return Object.keys(pbs).find(k => list(pbs[k].aliases).includes(v) || pbs[k].label === v) || ''
}

export function bookOf(meta: Dict | null, key: string): Book | null {
  const p = dict(meta?.playbooks)[key]
  if (!p) return null
  return {
    key, label: String(p.label || key), blurb: String(p.blurb || ''),
    unique: entries([p.unique])[0] || { key: 'unique', name: '' },
    talents: entries(p.talents), items: entries(p.items),
    xp_trigger: String(p.xp_trigger || ''), start: dict(p.start),
  }
}

/** Playbook abilities, items and limits: the book, with the GM's campaign setup on top
 *  (`campaign.sheet_setup`, edited in GM space). */
export function effective(book: Book | null, sheet: Dict, setup: Dict) {
  const own = dict(dict(setup.playbooks)[book?.key || ''])
  return {
    talents: Array.isArray(own.talents) ? entries(own.talents) : book?.talents || [],
    items: Array.isArray(own.items) ? entries(own.items) : book?.items || [],
    common: Array.isArray(setup.common) ? entries(setup.common) : entries(sheet.items),
    stressMax: own.stress_max != null ? Math.max(1, num(own.stress_max)) : STRESS_MAX,
    xpTrigger: typeof own.xp_trigger === 'string' && own.xp_trigger.trim() ? own.xp_trigger : book?.xp_trigger || '',
  }
}

export const STRESS_TOP = 12

/** Crew setup in the form it goes to the server: without abandoned empty rows. */
export function cleanSetup(all: Dict): Dict {
  const rows = (v: any) => entries(v).filter(x => x.name.trim())
  const out: Dict = {}
  if (Array.isArray(all.common)) out.common = rows(all.common)
  const pbs: Dict = {}
  for (const [k, p] of Object.entries(dict(all.playbooks))) {
    const q: Dict = {}
    for (const s of ['talents', 'items']) if (Array.isArray(dict(p)[s])) q[s] = rows(dict(p)[s])
    if (dict(p).stress_max != null) q.stress_max = Math.min(STRESS_TOP, Math.max(1, num(dict(p).stress_max)))
    if (typeof dict(p).xp_trigger === 'string' && dict(p).xp_trigger.trim()) q.xp_trigger = dict(p).xp_trigger.trim()
    if (Object.keys(q).length) pbs[k] = q
  }
  if (Object.keys(pbs).length) out.playbooks = pbs
  return out
}

export const talentKey = (pb: string, key: string) => `${pb || 'own'}:${key}`

/** A veteran or former ability: search across all playbooks, with the campaign setup. */
export function talentOf(meta: Dict | null, setup: Dict, key: string): (Entry & { pb: string; pbLabel: string }) | null {
  const [pk, tk] = key.split(':')
  const book = bookOf(meta, pk)
  const t = book && effective(book, {}, setup).talents.find(x => x.key === tk)
  return t && book ? { ...t, key, pb: pk, pbLabel: book.label } : null
}

export const loadUsed = (items: Dict) => Object.values(items).reduce((s: number, n) => s + num(n), 0)
export const loadLimit = (level: any) => (LOADS.find(([k]) => k === level) || LOADS[1])[1]
export const rating = (attr: Attr, acts: Dict) => attr.actions.filter(a => num(acts[a.key]) > 0).length
export const pointsOf = (acts: Dict) => Object.values(acts).reduce((s: number, n) => s + num(n), 0)
export const loadChoices = (v: Entry['load']): number[] =>
  Array.isArray(v) ? v : [v == null ? 1 : num(v)]
