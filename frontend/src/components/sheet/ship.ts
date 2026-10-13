import { type Dict } from '../../api'
import { dict, entries, type Entry, list, num } from './parts'

export type ShipBook = {
  slots: Dict; modules: Dict; talents: Entry[]; upgrades: Entry[]
  xp_triggers: string[]; sizes: string[]
}

export const SYSTEMS: { sec: string; label: string; key: string; dmg: string }[] = [
  { sec: 'hull', label: 'system.hull', key: 'sys_hull', dmg: 'dmg_hull' },
  { sec: 'engines', label: 'system.engines', key: 'sys_engines', dmg: 'dmg_engines' },
  { sec: 'sensors', label: 'system.sensors', key: 'sys_sensors', dmg: 'dmg_sensors' },
  { sec: 'guns', label: 'system.guns', key: 'sys_guns', dmg: 'dmg_guns' },
]

export const KITS: { sec: string; label: string }[] = [
  { sec: 'extra', label: 'kit.extra' },
  { sec: 'gear', label: 'kit.gear' },
  { sec: 'crew_gear', label: 'kit.crew_gear' },
  { sec: 'training', label: 'kit.training' },
]

export const MOD_SECS = [...SYSTEMS.map(s => ({ sec: s.sec, label: s.label })), ...KITS]

/** The book ship sheet of this type: what the GM's setup is laid over. */
export function shipBook(meta: Dict | null, fields: Dict): { types: Dict; type: Dict; book: ShipBook } {
  const types = dict(meta?.ship_types)
  const type = dict(types[String(fields.ship_type || '')])
  const mods = dict(meta?.ship_modules)
  return {
    types, type,
    book: {
      slots: dict(type.slots),
      modules: Object.fromEntries(MOD_SECS.map(s => [s.sec, entries(mods[s.sec])] as [string, Entry[]])),
      talents: entries(type.talents),
      upgrades: entries(type.upgrades),
      xp_triggers: list(type.xp_triggers),
      sizes: list(meta?.ship_sizes),
    },
  }
}

/** A type change sets the new ship's stock loadout instead of the old marks:
 *  foreign modules on the sheet confuse more than losing a couple of checks.
 *  `dropped`: how many marks will be lost, to ask for confirmation. */
export function stockFields(meta: Dict | null, fields: Dict, k: string): { patch: Dict; dropped: number } {
  const t = dict(dict(meta?.ship_types)[k])
  const stock = list(t.start_modules)
  const start = dict(t.systems)
  const quals = Object.fromEntries(
    SYSTEMS.filter(s => start[s.sec] != null).map(s => [s.key, String(num(start[s.sec]))]))
  return {
    patch: { ...quals, ship_type: k, modules: stock },
    dropped: list(fields.modules).filter(m => !stock.includes(m)).length,
  }
}
