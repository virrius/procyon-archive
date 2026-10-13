/* Icons over a picture, with one layout everywhere. The picture container gets the class
   imgbox; state marks sit in the top left corner and are always visible, actions sit
   in one bar in the top right corner and appear on hover. */

import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { FieldEye } from './FieldEye'
import { IconBrush, IconCrop, IconEyeOff, IconImage, IconSpark, IconStack, IconTrash } from './icons'
import '../styles.vis.css'

type Act = { title: string; onClick: () => void }

/** The bar order is fixed: visibility, brush, crop, generation,
 *  upload a file, take from media, delete. Whatever is missing is simply not drawn. */
export function ImgActions({ vis, inpaint, crop, gen, upload, pick, remove, small }: {
  /** picture visibility to the table: the same eye as on card fields */
  vis?: { hidden: boolean; onChange: (hide: boolean) => void }
  inpaint?: Act
  crop?: Act
  gen?: Act & { on?: boolean }
  upload?: { title: string; onFile: (file: File) => void }
  pick?: Act
  remove?: Act
  /** small tile: buttons one step smaller */
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

/** Picture state marks: hidden from the table, generating. */
export function ImgFlags({ hidden, busy, mark = true }: {
  hidden?: boolean
  busy?: boolean
  /** "hidden" icon in the corner; not needed where the bar's eye is always visible nearby */
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
