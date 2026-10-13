import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c, thumbFull, type Dict } from '../api'
import VisibilityMenu from '../components/VisibilityMenu'
import { LOOK_SCOPES } from '../components/studio/kit'
import { useAsync } from '../ctx'
import '../styles.looks.css'

const asText = (v: any) => (Array.isArray(v) ? v.join(', ') : String(v ?? ''))
const fromText = (s: string) => s.split(',').map(x => x.trim()).filter(Boolean)

/** Campaign looks: outfits from good frames that the studio puts on verbatim.
 *  Saved with the button under a character's frame; viewed, edited and forgotten here. */
export default function LooksPage() {
  const { t } = useTranslation('media')
  const [data, , reload, err] = useAsync<Dict>(() => api.get(`${c()}/wardrobe`), [])
  const [edit, setEdit] = useState<Dict>({})
  const [busy, setBusy] = useState('')

  if (err) return <div className="panel"><div className="eg-err">{err}</div></div>
  if (!data) return <div className="dim">{t('common:loading')}</div>
  const list: Dict[] = data.wardrobe || []
  if (!list.length) {
    return <div className="panel empty">{t('looks.empty')}</div>
  }

  const cur = (o: Dict) => edit[o.key] || { ...o, wear: asText(o.wear) }
  const put = (o: Dict, field: string, v: string) => setEdit({ ...edit, [o.key]: { ...cur(o), [field]: v } })
  const done = (key: string) => { const { [key]: _, ...rest } = edit; setEdit(rest) }

  const save = async (o: Dict) => {
    setBusy(o.key)
    try {
      const e = edit[o.key]
      await api.put(`${c()}/wardrobe/${encodeURIComponent(o.key)}`,
        { ...o, ...e, visibility: o.visibility, wear: fromText(e.wear) })
      done(o.key); reload()
    } catch (e: any) { alert(e.message) } finally { setBusy('') }
  }
  const show = async (o: Dict, visibility: string) => {
    setBusy(o.key)
    try {
      await api.put(`${c()}/wardrobe/${encodeURIComponent(o.key)}`, { ...o, visibility })
      reload()
    } catch (e: any) { alert(e.message) } finally { setBusy('') }
  }
  const drop = async (o: Dict) => {
    if (!confirm(t('looks.forget_confirm', { title: o.title || o.key }))) return
    setBusy(o.key)
    try {
      await api.del(`${c()}/wardrobe/${encodeURIComponent(o.key)}`)
      done(o.key); reload()
    } catch (e: any) { alert(e.message) } finally { setBusy('') }
  }

  return (
    <div className="looks">
      {list.map(o => {
        const v = cur(o)
        return (
          <div className="look-card" key={o.key}>
            <div className="look-shot">
              {o.image ? <img src={thumbFull(o.image, 480)} alt="" loading="lazy" /> : <span>{t('looks.no_frame')}</span>}
            </div>
            <div className="look-body">
              <input className="look-title" value={v.title} onChange={e => put(o, 'title', e.target.value)} />
              <label>{t('looks.outfit')}</label>
              <textarea rows={5} value={v.wear} onChange={e => put(o, 'wear', e.target.value)} />
              <div className="look-acts">
                <button className="ghost tiny" disabled={!!busy} onClick={() => drop(o)}>{t('looks.forget')}</button>
                <span className="sp" />
                {edit[o.key] && <button className="ghost tiny" onClick={() => done(o.key)}>{t('common:cancel')}</button>}
                {edit[o.key] && (
                  <button className="primary tiny" disabled={!!busy} onClick={() => save(o)}>
                    {busy === o.key ? t('saving') : t('common:save')}
                  </button>
                )}
                <VisibilityMenu value={o.visibility || 'crew'} visibleTo={[]} scopes={LOOK_SCOPES}
                  disabled={!!busy} onChange={s => void show(o, s)} />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
