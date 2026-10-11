import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c } from '../api'
import { Modal } from '../ui'
import CropBox, { cropParam, cropSize, type Box } from './CropBox'

/** Рамка вложения из пикселей оригинала в доли — в них рисует CropBox. */
const toBox = (raw: string, w: number, h: number): Box | null => {
  const n = raw.split(',').map(Number)
  if (n.length !== 4 || n.some(v => !isFinite(v)) || n[2] < 1 || n[3] < 1) return null
  return { x: n[0] / w, y: n[1] / h, w: n[2] / w, h: n[3] / h }
}

/** Кадрирование превью: рамка живёт у вложения и режет только миниатюры — оригинал
 *  цел, по клику открывается он же целиком, а рамку можно переиграть в любой момент. */
/** Рамка во всю ширину или высоту снимка по центру, с заданной пропорцией. */
const fit = (aspect: number, ratio: number): Box =>
  ratio > aspect
    ? { x: 0, w: 1, h: aspect / ratio, y: (1 - aspect / ratio) / 2 }
    : { y: 0, h: 1, w: ratio / aspect, x: (1 - ratio / aspect) / 2 }

export default function CropModal({ attachmentId, src, title, ratio, onClose, onDone }: {
  attachmentId: string
  /** ширина/высота превью: рамка держит её, чтобы снимок ложился в плитку без полей */
  ratio: number
  src: string
  title: string
  onClose: () => void
  onDone: () => void
}) {
  const { t } = useTranslation('media')
  const [size, setSize] = useState<[number, number] | null>(null)
  const [box, setBox] = useState<Box | null>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let alive = true
    ;(async () => {
      let raw = ''
      try {
        const a = await api.get(`${c()}/attachments/${attachmentId}`)
        raw = String(a?.crop_box || '')
      } catch (e: any) {
        if (alive) setErr(e?.message || t('crop.err_attachment'))
        return
      }
      const im = new Image()
      im.onload = () => {
        if (!alive) return
        setSize([im.naturalWidth, im.naturalHeight])
        const was = toBox(raw, im.naturalWidth, im.naturalHeight)
        const same = was && Math.abs((was.w * im.naturalWidth) / (was.h * im.naturalHeight) - ratio) < 0.02
        setBox(same ? was : fit(im.naturalWidth / im.naturalHeight, ratio))
      }
      im.onerror = () => { if (alive) setErr(t('crop.err_image')) }
      im.src = src
    })()
    return () => { alive = false }
  }, [attachmentId, src, ratio])

  const save = async (whole?: boolean) => {
    if (!size) return
    setBusy(true); setErr('')
    try {
      await api.patch(`${c()}/attachments/${attachmentId}`,
        { crop_box: whole ? '' : cropParam(box, size[0], size[1]) })
      onDone()
    } catch (e: any) {
      setErr(e?.message || t('crop.err_save'))
      setBusy(false)
    }
  }

  return (
    <Modal title={t('crop.title', { title })} onClose={onClose}>
      {err && <div className="eg-err">{err}</div>}
      {!size && !err && <div className="dim">{t('crop.loading')}</div>}
      {size && (
        <div className="col" style={{ gap: 8 }}>
          <CropBox src={src} ratio={`${size[0]} / ${size[1]}`} lock={ratio}
            box={box} onBox={setBox} />
          <div className="row wrap">
            <div className="spacer" />
            <span className="dim2 small">
              {box && t('crop.size', { size: cropSize(box, size[0], size[1]) })}
            </span>
            <button type="button" className="ghost tiny" disabled={!box}
              onClick={() => setBox(fit(size[0] / size[1], ratio))}>{t('crop.center')}</button>
          </div>
          <div className="row">
            <button className="primary" disabled={busy} onClick={() => save()}>
              {busy ? t('saving') : t('crop.save')}
            </button>
            <button className="ghost" disabled={busy} onClick={() => save(true)}>{t('crop.whole')}</button>
            <span className="dim2 small">
              {t('crop.note')}
            </span>
          </div>
        </div>
      )}
    </Modal>
  )
}
