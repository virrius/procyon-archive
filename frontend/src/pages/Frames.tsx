import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { isPublicView } from '../api'
import { useApp } from '../ctx'
import Studio, { type BrushSource } from '../components/studio/Studio'
import FramesGallery from '../components/FramesGallery'
import '../styles.frames.css'

/** "Campaign frames": what the table saw with their own eyes. Studio on top,
 *  collection below. Anyone at the table adds frames; the GM hides extra ones with the eye. */
export default function Frames() {
  const { t } = useTranslation('media')
  const { campaign } = useApp()
  const role = campaign?.my_role || ''
  const canAdd = (role === 'gm' || role === 'player') && !isPublicView()
  const [tick, setTick] = useState(0)
  const [brush, setBrush] = useState<BrushSource | null>(null)
  const top = useRef<HTMLDivElement>(null)

  return (
    <div className="col">
      <div className="row wrap frames-head" style={{ alignItems: 'baseline' }}>
        <h1>{t('frames_title')}</h1>
      </div>

      {canAdd && (
        <div ref={top}>
          <Studio embedded source={brush} onChanged={() => setTick(t => t + 1)} />
        </div>
      )}
      <FramesGallery tick={tick} onBrush={canAdd ? f => {
        setBrush({ id: f.id, url: f.url, title: f.caption || t('collection_frame'), sub: '' })
        top.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      } : undefined} />
    </div>
  )
}
