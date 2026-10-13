/* Placeholder instead of a picture: a dark silhouette by entry kind under a vignette and grain.
   The figure is framed on the bottom edge, like a cropped photo; signs sit in the center.
   The tracings themselves are in stubShapes.ts. */

import type { CSSProperties } from 'react'
import {
  CONTAINER, CONTRACT, FIGHTER, FIGURE, PLANET, SIGIL, WHISPER, type StubShape,
} from './stubShapes'
import '../styles.stub.css'

const SHAPES: Record<string, StubShape> = {
  character: FIGURE, npc: FIGURE,
  ship: FIGHTER, item: CONTAINER, location: PLANET,
  faction: SIGIL, job: CONTRACT,
}

/** a job has two faces: a rumor is an intercepted whisper, a job is a contract */
const SUB_SHAPES: Record<string, StubShape> = {
  'job:rumor': WHISPER,
}

function Silhouette({ shape }: { shape: StubShape }) {
  return (
    <svg viewBox={shape.box} preserveAspectRatio="xMidYMax meet"
      style={{ height: shape.height }} aria-hidden="true" focusable="false">
      <g>
        {shape.paths.map((d, i) => <path key={`p${i}`} d={d} />)}
        {shape.cuts?.map((d, i) => <path key={`c${i}`} className="cut" d={d} />)}
        {shape.ribs?.map(([w, d], i) => (
          <path key={`r${i}`} className="rib" strokeWidth={w} d={d} />
        ))}
        {shape.marks?.map(([w, d], i) => (
          <path key={`m${i}`} className="mark" strokeWidth={w} d={d} />
        ))}
      </g>
    </svg>
  )
}

/** Placeholder in place of a picture. Size and proportions come from the slot's class
    (`eg-photo`, `lnk-thumb`, `avatar`, `ch-noshot`). */
export default function Stub({ kind, sub, className = '', caption, style }: {
  kind?: string | null
  /** kind detail: rumors and jobs get their own face */
  sub?: string | null
  className?: string
  /** caption over the frame, only where there is room */
  caption?: string
  style?: CSSProperties
}) {
  const shape = SUB_SHAPES[`${kind}:${sub}`] || SHAPES[String(kind || '')]
  return (
    <div className={`stub ${shape?.crop ? 'stub-crop' : ''} ${className}`} style={style}>
      {shape && <Silhouette shape={shape} />}
      {caption && <span className="stub-cap">{caption}</span>}
    </div>
  )
}
