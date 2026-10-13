import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c, type Dict } from '../api'
import { useApp, useAsync } from '../ctx'
import EntityPicker from './EntityPicker'
import { ANY_PLAYER, OwnerMenu } from './OwnerMenu'
import {
  ColorPicker, Input, Modal, OwnerPicker, VisibilityPicker,
} from '../ui'

void OwnerMenu

/** Clock types aren't predefined: the dictionary is built from what was already entered. */
export function useClockKinds(rows: Dict[] | null): string[] {
  const [known, loading] = useAsync<string[]>(() => api.get(`${c()}/clock-kinds`), [])
  const seen = new Set<string>([
    ...(loading ? [] : known || []),
    ...(rows || []).map(r => String(r.kind || '')).filter(Boolean),
  ])
  return [...seen].sort((a, b) => a.localeCompare(b))
}

/** A GM clock is created hidden and only the GM edits it, until they reveal it */
export const blankClock = (kind = '', isGM = false): Dict => ({
  name: '', description: '', outcome: '', kind, color: 'amber',
  segments: 6, filled: 0, visible_to: [],
  visibility: isGM ? 'gm' : 'crew',
  owner_member_id: isGM ? '' : ANY_PLAYER,
})

/** Creating and editing a clock: one form for the campaign database and for a story board. */
export function ClockForm({ form, setForm, owner, setOwner, kinds, onDone, onClose }: {
  form: Dict
  setForm: (v: Dict) => void
  owner: Dict | null
  setOwner: (v: Dict | null) => void
  kinds: string[]
  /** clock id: a new one on create, the same one on edit */
  onDone: (id: string) => void
  onClose: () => void
}) {
  const { isGM } = useApp()
  const { t } = useTranslation('clocks')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const save = async () => {
    if (!form?.name?.trim()) return
    const { id, ...body } = form
    const owned = { owner_type: owner ? 'entity' : null, owner_id: owner?.id || null }
    setBusy(true); setErr('')
    try {
      const r = id
        ? await api.patch(`${c()}/clocks/${id}`, { ...body, ...owned })
        : await api.post(`${c()}/clocks`, { ...body, ...owned })
      onDone(String(id || r?.id || ''))
    } catch (e: any) {
      setErr(e?.message || t('err_save'))
      setBusy(false)
    }
  }

  return (
    <Modal title={form.id ? t('edit_title') : t('new_title')}
      onClose={onClose} watch={[form, owner]}
      dirtyAsk={t('dirty')}>
      <Input label={t('name')} value={form.name}
        onChange={v => setForm({ ...form, name: v })} />
      <Input label={t('kind')} value={form.kind} suggest={kinds}
        placeholder={t('kind_placeholder')}
        onChange={v => setForm({ ...form, kind: v })} />
      <ColorPicker value={form.color} onChange={v => setForm({ ...form, color: v })} />
      <Input label={t('segments')} type="number" value={form.segments}
        onChange={v => setForm({ ...form, segments: Number(v) || 6 })} />
      <Input label={t('description')} type="textarea" value={form.description}
        onChange={v => setForm({ ...form, description: v })} />
      <Input label={t('outcome')} type="textarea" value={form.outcome}
        onChange={v => setForm({ ...form, outcome: v })} />
      <EntityPicker label={t('link')} value={owner} onChange={setOwner} />
      {!form.id && (
        <VisibilityPicker visibility={form.visibility} visibleTo={form.visible_to}
          onChange={(v, to) => setForm({ ...form, visibility: v, visible_to: to })} />
      )}
      {!form.id && isGM && (
        <OwnerPicker label={t('owner')}
          value={form.owner_member_id === '' ? null : form.owner_member_id ?? ANY_PLAYER}
          onChange={who => setForm({ ...form, owner_member_id: who ?? '' })} />
      )}
      {err && <div className="eg-err">{err}</div>}
      <button className="primary" disabled={busy || !form.name?.trim()} onClick={save}>
        {busy ? t('saving') : form.id ? t('common:save') : t('create')}
      </button>
    </Modal>
  )
}

/** Ready-made wrapper for places where a clock is created in passing (story board). */
export function NewClockModal({ preset, onDone, onClose }: {
  preset?: Dict
  onDone: (id: string) => void
  onClose: () => void
}) {
  const { isGM } = useApp()
  const [form, setForm] = useState<Dict>({ ...blankClock('', isGM), ...(preset || {}) })
  const [owner, setOwner] = useState<Dict | null>(null)
  const kinds = useClockKinds(null)
  return (
    <ClockForm form={form} setForm={setForm} owner={owner} setOwner={setOwner}
      kinds={kinds} onDone={onDone} onClose={onClose} />
  )
}

export default ClockForm
