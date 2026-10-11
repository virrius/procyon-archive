/* Фракции и место контакта/персонажа — не тег, а настоящая связь на сущность
   нужного kind. Список для поиска и подписи чипов берём из тех же данных,
   что использует галерея (фракции/локации кампании). */

import { useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api, c, type Dict } from '../api'
import { useAsync } from '../ctx'
import PopLayer from './PopLayer'

export function useKindIndex(kind: string) {
  const [rows, loading] = useAsync<Dict[]>(() => api.get(`${c()}/entities?kind=${kind}`), [kind])
  const list = rows || []
  const byId = useMemo(() => {
    const m = new Map<string, Dict>()
    for (const e of list) m.set(e.id, e)
    return m
  }, [list])
  return { list, byId, loading }
}

/** Имя привязки. Своя карточка может быть закрыта от стола — тогда имя приходит
    отдельным словарём (`peer_names`), а перехода на карточку нет. */
function peerName(id: string, byId: Map<string, Dict>, names?: Dict): string {
  return byId.get(id)?.name || String(names?.[id] || '') || '…'
}

export function AffiliationView({ ids, kind, names }: {
  ids?: string[] | null
  kind: string
  /** id → имя для карточек, закрытых от смотрящего */
  names?: Dict
}) {
  const { t } = useTranslation('entity')
  const { byId } = useKindIndex(kind)
  const list = (ids || []).filter(id => byId.has(id) || names?.[id])
  if (!list.length) return null
  return (
    <div className="row wrap" style={{ gap: 5 }}>
      {list.map(id => (byId.has(id)
        ? <Link key={id} className="tag" to={`/entity/${id}`}>
            <span className="t">{peerName(id, byId, names)}</span>
          </Link>
        : <span key={id} className="tag" title={t('aff.closed')}>
            <span className="t">{peerName(id, byId, names)}</span>
          </span>
      ))}
    </div>
  )
}

export function AffiliationPicker({ ids, kind, onChange, disabled, names }: {
  ids?: string[] | null
  kind: string
  onChange: (ids: string[]) => void
  disabled?: boolean
  /** id → имя для карточек, закрытых от смотрящего */
  names?: Dict
}) {
  const { t } = useTranslation('entity')
  const { list } = useKindIndex(kind)
  const entry = useRef<HTMLDivElement | null>(null)
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const picked = ids || []
  const byId = useMemo(() => new Map(list.map(e => [e.id, e])), [list])
  const needle = q.trim().toLowerCase()
  const options = list
    .filter(e => !picked.includes(e.id) && (!needle || e.name.toLowerCase().includes(needle)))
    .slice(0, 8)

  const add = (id: string) => { onChange([...picked, id]); setQ(''); setOpen(false) }
  const drop = (id: string) => onChange(picked.filter(x => x !== id))

  return (
    <div>
      <div className={`tagbox ${disabled ? 'off' : ''}`}>
        {picked.map(id => (
          <span key={id} className={`tag ${disabled ? 'off' : ''}`}>
            {/* тег — и связь, и вход на карточку: правка не должна запирать переход */}
            {byId.has(id)
              ? <Link className="t" to={`/entity/${id}`} title={t('aff.open')}>
                  {peerName(id, byId, names)}
                </Link>
              : <span className="t" title={t('aff.closed')}>
                  {peerName(id, byId, names)}
                </span>}
            {!disabled && <button type="button" title={t('aff.remove')} onClick={() => drop(id)}>×</button>}
          </span>
        ))}
        {!disabled && (
          <div className="tag-entry" ref={entry}>
            <input type="text" value={q} placeholder={t('aff.search')}
              onChange={e => { setQ(e.target.value); setOpen(true) }}
              onFocus={() => setOpen(true)}
              onBlur={() => setOpen(false)} />
            {open && q.trim() && options.length > 0 && (
              <PopLayer anchor={entry} className="tag-pop" onClose={() => setOpen(false)}>
                {options.map(e => (
                  <button key={e.id} type="button" className="tag-opt"
                    onMouseDown={ev => ev.preventDefault()}
                    onClick={() => add(e.id)}>
                    <span className="t">{e.name}</span>
                  </button>
                ))}
              </PopLayer>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
