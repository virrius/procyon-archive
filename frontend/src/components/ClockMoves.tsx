import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c, isPublicView, type Dict } from '../api'
import { useApp } from '../ctx'
import { clockTitle } from '../ui'
import { IconButton, IconCheck, IconMinus, IconPlus } from './icons'

type Oops = { id: string; text: string } | null

/** Тик, завершение и возврат счётчика — одна механика в разделе и на карточке записи.
 *  Пока запрос идёт, кнопки счётчика заняты; сдвиг виден сразу и откатывается при ошибке. */
export function useClockMoves(rows: Dict[] | null, reload: () => void) {
  const { t } = useTranslation('clocks')
  const [busy, setBusy] = useState<Record<string, boolean>>({})
  const [fresh, setFresh] = useState<Record<string, Dict>>({})
  const [oops, setOops] = useState<Oops>(null)
  const going = useRef(new Set<string>())

  // пришёл новый список — свои снимки больше не нужны, кроме тех, что ещё в пути
  useEffect(() => {
    setFresh(cur => {
      const keep = Object.fromEntries(Object.entries(cur).filter(([id]) => going.current.has(id)))
      return Object.keys(keep).length === Object.keys(cur).length ? cur : keep
    })
  }, [rows])

  const run = async (cl: Dict, guess: Dict, call: () => Promise<any>): Promise<boolean> => {
    if (going.current.has(cl.id)) return false
    going.current.add(cl.id)
    setBusy(b => ({ ...b, [cl.id]: true }))
    setOops(null)
    setFresh(f => ({ ...f, [cl.id]: { ...cl, ...guess } }))
    let ok = true
    try {
      const r = await call()
      setFresh(f => ({ ...f, [cl.id]: r?.id ? r : { ...cl, ...guess } }))
    } catch (e: any) {
      ok = false
      setFresh(f => { const n = { ...f }; delete n[cl.id]; return n })
      setOops({ id: cl.id, text: e?.message || t('err_move') })
    }
    going.current.delete(cl.id)
    setBusy(b => { const n = { ...b }; delete n[cl.id]; return n })
    reload()
    return ok
  }

  const tick = (cl: Dict, delta: number, comment = '') =>
    run(cl, { filled: Math.max(0, Math.min(cl.segments, cl.filled + delta)) },
      () => api.post(`${c()}/clocks/${cl.id}/tick`, { delta, comment }))

  const complete = (cl: Dict) => {
    if (!confirm(t('complete_confirm', { title: clockTitle(cl) }))) return
    return run(cl, { status: 'completed' }, () => api.post(`${c()}/clocks/${cl.id}/complete`, {}))
  }

  const reopen = (cl: Dict) =>
    run(cl, { status: 'active' }, () => api.post(`${c()}/clocks/${cl.id}/reopen`, {}))

  /** Прочие правки счётчика (права, видимость, отмена): ошибку показываем там же. */
  const act = async (cl: Dict, call: () => Promise<any>): Promise<boolean> => {
    setOops(null)
    let ok = true
    try { await call() }
    catch (e: any) { ok = false; setOops({ id: cl.id, text: e?.message || t('err_edit') }) }
    reload()
    return ok
  }

  return {
    view: (cl: Dict): Dict => fresh[cl.id] || cl,
    busy: (cl: Dict) => !!busy[cl.id],
    oops: (cl: Dict) => (oops && oops.id === cl.id ? oops.text : ''),
    tick, complete, reopen, act,
  }
}

export type ClockMovesApi = ReturnType<typeof useClockMoves>

/** Право двигать счётчик отдаёт сервер: ГМ, «все игроки» или назначенный игрок. */
export function useClockMay() {
  const { campaign } = useApp()
  const canEdit = !isPublicView() && campaign?.my_role !== 'observer'
  return (cl: Dict) => canEdit && cl.can_edit !== false
}

/** Кнопки плитки: «−» и «+» на своих местах, «завершить» — отдельной кнопкой с вопросом,
 *  у закрытого счётчика — «вернуть». Отменённый возвращает только ГМ. */
export function ClockMoves({ cl, moves }: { cl: Dict; moves: ClockMovesApi }) {
  const { isGM } = useApp()
  const { t } = useTranslation('clocks')
  const may = useClockMay()
  if (!may(cl)) return null
  const wait = moves.busy(cl)
  const full = cl.filled >= cl.segments
  if (cl.status !== 'active') {
    if (cl.status === 'abandoned' && !isGM) return null
    return (
      <button type="button" className="tiny ghost" disabled={wait}
        title={t('reopen_title')}
        onClick={() => moves.reopen(cl)}>{t('reopen')}</button>
    )
  }
  return (
    <>
      <IconButton icon={<IconMinus size={13} />} title={t('tick_down')}
        disabled={wait || cl.filled <= 0} onClick={() => moves.tick(cl, -1)} />
      <IconButton icon={<IconPlus size={13} />} title={t('tick_up')}
        disabled={wait || full} onClick={() => moves.tick(cl, 1)} />
      <IconButton icon={<IconCheck size={13} />}
        title={full ? t('complete') : t('complete_need_full')}
        disabled={wait || !full} onClick={() => moves.complete(cl)} />
    </>
  )
}
