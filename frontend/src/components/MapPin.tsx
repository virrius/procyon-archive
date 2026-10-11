import { PALETTE_HEX } from '../ui'

export const MARKER_ICONS = ['dot', 'ring', 'target', 'cross', 'diamond', 'star'] as const

export const ICON_NAME: Record<string, string> = {
  dot: 'map:icon.dot', ring: 'map:icon.ring', target: 'map:icon.target',
  cross: 'map:icon.cross', diamond: 'map:icon.diamond', star: 'map:icon.star',
}

export const iconOf = (v: any) =>
  MARKER_ICONS.includes(String(v) as any) ? String(v) : 'dot'

const DARK = '#100f0d'
const star = (r: number, ri: number) => Array.from({ length: 10 }, (_, i) => {
  const a = -Math.PI / 2 + (i * Math.PI) / 5
  const rr = i % 2 ? ri : r
  return `${(Math.cos(a) * rr).toFixed(2)},${(Math.sin(a) * rr).toFixed(2)}`
}).join(' ')

/** Двойная отрисовка: сначала тёмный контур пожирнее, поверх — цветная фигура.
    Иначе значок теряется на светлых участках карты. */
function shape(icon: string, hex: string, w: number) {
  const pair = (el: (stroke: string, sw: number, fill: string) => any) => (
    <>{el(DARK, w + 3.5, DARK)}{el(hex, w, hex)}</>
  )
  switch (icon) {
    case 'ring':
      return pair((s, sw) => <circle r="6.4" fill="none" stroke={s} strokeWidth={sw} />)
    case 'target':
      return pair((s, sw) => (
        <g fill="none" stroke={s} strokeWidth={sw} strokeLinecap="round">
          <circle r="6.4" />
          <path d="M0,-11 V-8 M0,8 V11 M-11,0 H-8 M8,0 H11" />
          <circle r="1.1" fill={s} stroke="none" />
        </g>
      ))
    case 'cross':
      return pair((s, sw) => (
        <path d="M-6,-6 L6,6 M6,-6 L-6,6" fill="none" stroke={s}
          strokeWidth={sw} strokeLinecap="round" />
      ))
    case 'diamond':
      return pair((s, sw, fill) => (
        <polygon points="0,-7.5 7.5,0 0,7.5 -7.5,0" fill={fill} stroke={s}
          strokeWidth={sw} strokeLinejoin="round" />
      ))
    case 'star':
      return pair((s, sw, fill) => (
        <polygon points={star(8, 3.4)} fill={fill} stroke={s}
          strokeWidth={sw} strokeLinejoin="round" />
      ))
    default:
      return <circle r="6" fill={hex} stroke={DARK} strokeWidth="2" />
  }
}

/** Значок отметки. Рисуется от центра (0,0) — точка привязки совпадает с координатой. */
export function Glyph({ icon, color, size = 26, on = false, hit = false, children, ...rest }: {
  icon?: string; color?: string; size?: number; on?: boolean; hit?: boolean
} & React.SVGProps<SVGSVGElement>) {
  const hex = PALETTE_HEX[color || 'amber'] || PALETTE_HEX.amber
  return (
    <svg viewBox="-13 -13 26 26" width={size} height={size} {...rest}>
      {children}
      {on && <circle r="11.4" fill="none" stroke="var(--amber)" strokeWidth="1.6" />}
      {hit && <circle r="12" fill="transparent" />}
      {shape(iconOf(icon), hex, 2.4)}
    </svg>
  )
}
