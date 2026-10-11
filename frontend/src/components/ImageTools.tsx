/* Значки поверх картинки — одна раскладка везде. Контейнер картинки получает класс
   imgbox; метки состояния стоят в левом верхнем углу и видны всегда, действия —
   одной планкой в правом верхнем углу и всплывают по наведению. */

import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { FieldEye } from './FieldEye'
import { IconBrush, IconCrop, IconEyeOff, IconImage, IconSpark, IconStack, IconTrash } from './icons'
import '../styles.vis.css'

type Act = { title: string; onClick: () => void }

/** Порядок в планке постоянный: видимость, кисть, кадрирование, генерация,
 *  загрузить файл, взять из медиа, удалить. Чего нет — того просто не рисуем. */
export function ImgActions({ vis, inpaint, crop, gen, upload, pick, remove, small }: {
  /** видимость картинки столу — тот же глаз, что у полей карточки */
  vis?: { hidden: boolean; onChange: (hide: boolean) => void }
  inpaint?: Act
  crop?: Act
  gen?: Act & { on?: boolean }
  upload?: { title: string; onFile: (file: File) => void }
  pick?: Act
  remove?: Act
  /** мелкая плитка — кнопки на ступень меньше */
  small?: boolean
}) {
  if (!vis && !inpaint && !crop && !gen && !upload && !pick && !remove) return null
  const sz = small ? 12 : 13
  const btn = (a: Act | undefined, icon: ReactNode, extra = '') => a && (
    <button type="button" className={`ibtn${extra}`} title={a.title} aria-label={a.title}
      onClick={a.onClick}>
      {icon}
    </button>
  )
  return (
    <div className={`imgbar${small ? ' sm' : ''}`}>
      <span className="imgbar-acts img-hover">
      {btn(inpaint, <IconBrush size={sz} />)}
      {btn(crop, <IconCrop size={sz} />)}
      {btn(gen, <IconSpark size={sz} />, gen?.on ? ' on' : '')}
      {upload && (
        <label className="ibtn" title={upload.title} aria-label={upload.title}>
          <IconImage size={sz} />
          <input type="file" accept="image/*" onChange={ev => {
            const file = ev.target.files?.[0]
            ev.target.value = ''
            if (file) upload.onFile(file)
          }} />
        </label>
      )}
      {btn(pick, <IconStack size={sz} />)}
      {btn(remove, <IconTrash size={sz} />, ' danger')}
      </span>
      {vis && <FieldEye hidden={vis.hidden} onChange={vis.onChange} />}
    </div>
  )
}

/** Метки состояния картинки: закрыта от стола, идёт генерация. */
export function ImgFlags({ hidden, busy, mark = true }: {
  hidden?: boolean
  busy?: boolean
  /** значок «закрыто» в углу; не нужен, где рядом всегда виден глаз планки */
  mark?: boolean
}) {
  const { t } = useTranslation('media')
  if (!hidden && !busy) return null
  return (
    <>
      {hidden && <span className="imgshut" aria-hidden="true" />}
      <div className="imgflags">
        {hidden && mark && <span className="imgflag gm ico" title={t('img.hidden')}><IconEyeOff size={14} /></span>}
        {busy && <span className="imgflag work" title={t('img.generating')}>{t('img.drawing')}</span>}
      </div>
    </>
  )
}
