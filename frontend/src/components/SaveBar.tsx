/* Единая панель сохранения: индикатор «изменено» + явные «сохранить»/«отменить».
   Один вид во всех формах — бланк корабля, лист персонажа, карточка сущности. */

import { useTranslation } from 'react-i18next'
import '../styles.save.css'

export type SavePhase = '' | 'busy' | 'ok'

export function SaveBar({
  dirty, phase = '', err = '', onSave, onReset, saveLabel, compact,
}: {
  dirty: boolean
  phase?: SavePhase
  err?: string
  onSave: () => void
  onReset?: () => void
  saveLabel?: string
  compact?: boolean
}) {
  const { t } = useTranslation('common')
  const busy = phase === 'busy'
  return (
    <div className={`sv${compact ? ' compact' : ''}`}>
      <span className={`sv-state${err ? ' bad' : dirty ? ' warn' : ''}`}>
        {err || (dirty ? t('unsaved') : busy ? t('saving') : phase === 'ok' ? t('saved') : '')}
      </span>
      {onReset && (
        <button className="ghost tiny" disabled={!dirty || busy} onClick={onReset}>{t('cancel')}</button>
      )}
      <button className="sv-save" disabled={!dirty || busy} onClick={onSave}>
        {busy ? t('saving') : saveLabel ?? t('save')}
      </button>
    </div>
  )
}

/** Пометка «изменено» без кнопок — для строк и заголовков. */
export function DirtyDot({ on }: { on: boolean }) {
  const { t } = useTranslation('common')
  if (!on) return null
  return <span className="sv-dot" title={t('unsaved')} />
}
