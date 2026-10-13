import { useTranslation } from 'react-i18next'
import { IconEye, IconEyeOff } from './icons'

/** Reveal a field to the table or keep it to yourself. The value always lives; only visibility changes.
 *  Sits right after the field label; on a picture, first in the action bar. */
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
