/* Заглушка вместо снимка: тёмный силуэт по виду записи под виньеткой и зерном.
   Фигура кадрируется по нижнему краю, как обрезанное фото; знаки стоят по центру.
   Сами обводки — в stubShapes.ts. */

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

/** у работёнки два лица: слух — перехваченный шёпот, работа — контракт */
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

/** Заглушка на месте снимка. Размер и пропорции даёт класс места
    (`eg-photo`, `lnk-thumb`, `avatar`, `ch-noshot`). */
export default function Stub({ kind, sub, className = '', caption, style }: {
  kind?: string | null
  /** уточнение вида: своё лицо у слуха и у работы */
  sub?: string | null
  className?: string
  /** подпись поверх кадра — только там, где место позволяет */
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
