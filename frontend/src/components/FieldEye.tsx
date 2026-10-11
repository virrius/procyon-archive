import { useTranslation } from 'react-i18next'
import { IconEye, IconEyeOff } from './icons'

/** Открыть поле столу или держать при себе. Значение живёт всегда — меняется только видимость.
 *  Стоит сразу за подписью поля; на картинке — первым в планке действий. */
export function FieldEye({ hidden, onChange }: {
  hidden: boolean; onChange: (hide: boolean) => void
}) {
  const { t } = useTranslation('entity')
  const tip = hidden ? t('field_eye.hidden') : t('field_eye.shown')
  return (
    <button type="button" className={`fvis${hidden ? ' off' : ''}`}
      title={tip} aria-label={tip} aria-pressed={hidden} onClick={() => onChange(!hidden)}>
      {hidden ? <IconEyeOff size={13} /> : <IconEye size={13} />}
    </button>
  )
}
