/* Единый набор иконок приборной панели: 16×16, currentColor, штрих 1.5. */

import type { ReactNode, SVGProps } from 'react'
import '../styles.vis.css'

type IconProps = SVGProps<SVGSVGElement> & { size?: number }

function Glyph({ size = 16, children, ...rest }: IconProps & { children: ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor"
      strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" focusable="false" {...rest}>
      {children}
    </svg>
  )
}

export function IconEdit(p: IconProps) {
  return (
    <Glyph {...p}>
      <path d="M11.3 2.5a1.7 1.7 0 0 1 2.4 2.4L5.1 13.5l-3.3.8.8-3.3 8.7-8.5Z" />
      <path d="M10.2 3.6l2.4 2.4" />
    </Glyph>
  )
}

export function IconTrash(p: IconProps) {
  return (
    <Glyph {...p}>
      <path d="M2.6 4.2h10.8" />
      <path d="M6.2 4.2V2.8h3.6v1.4" />
      <path d="M4.2 4.2l.6 8.4a1 1 0 0 0 1 .9h4.4a1 1 0 0 0 1-.9l.6-8.4" />
      <path d="M6.7 6.8v4.2M9.3 6.8v4.2" />
    </Glyph>
  )
}

export function IconPlus(p: IconProps) {
  return <Glyph {...p}><path d="M8 3.2v9.6M3.2 8h9.6" /></Glyph>
}

export function IconMinus(p: IconProps) {
  return <Glyph {...p}><path d="M3.2 8h9.6" /></Glyph>
}

export function IconClose(p: IconProps) {
  return <Glyph {...p}><path d="M4 4l8 8M12 4l-8 8" /></Glyph>
}

export function IconCheck(p: IconProps) {
  return <Glyph {...p}><path d="M3 8.4l3.3 3.3L13 4.6" /></Glyph>
}

export function IconEye(p: IconProps) {
  return (
    <Glyph {...p}>
      <path d="M1.5 8S4 3.8 8 3.8 14.5 8 14.5 8 12 12.2 8 12.2 1.5 8 1.5 8Z" />
      <circle cx="8" cy="8" r="2.1" />
    </Glyph>
  )
}

export function IconEyeOff(p: IconProps) {
  return (
    <Glyph {...p}>
      <path d="M6.6 4.1A6.4 6.4 0 0 1 8 3.9c4 0 6.5 4.1 6.5 4.1a12.6 12.6 0 0 1-2.3 2.7" />
      <path d="M4.1 5.4A12.4 12.4 0 0 0 1.5 8.1s2.5 4.1 6.5 4.1c1 0 1.9-.2 2.7-.6" />
      <path d="M6.6 6.7a2 2 0 0 0 2.8 2.8" />
      <path d="M2.3 2.3l11.4 11.4" />
    </Glyph>
  )
}

export function IconLock(p: IconProps) {
  return (
    <Glyph {...p}>
      <rect x="3.4" y="7" width="9.2" height="6.4" rx="1" />
      <path d="M5.6 7V5.2a2.4 2.4 0 0 1 4.8 0V7" />
      <path d="M8 9.4v1.7" />
    </Glyph>
  )
}

export function IconUsers(p: IconProps) {
  return (
    <Glyph {...p}>
      <path d="M10.2 13.6v-1.3a2.6 2.6 0 0 0-2.6-2.6H4.1a2.6 2.6 0 0 0-2.6 2.6v1.3" />
      <circle cx="5.85" cy="4.8" r="2.4" />
      <path d="M14.5 13.6v-1.3a2.6 2.6 0 0 0-2-2.5" />
      <path d="M10.4 2.5a2.6 2.6 0 0 1 0 5" />
    </Glyph>
  )
}

export function IconUser(p: IconProps) {
  return (
    <Glyph {...p}>
      <path d="M13 13.6v-1.4a3.1 3.1 0 0 0-3.1-3.1H6.1A3.1 3.1 0 0 0 3 12.2v1.4" />
      <circle cx="8" cy="5" r="2.7" />
    </Glyph>
  )
}

export function IconLink(p: IconProps) {
  return (
    <Glyph {...p}>
      <path d="M6.6 8.7a2.6 2.6 0 0 0 3.9.3l2-2a2.6 2.6 0 0 0-3.7-3.7l-1.2 1.1" />
      <path d="M9.4 7.3a2.6 2.6 0 0 0-3.9-.3l-2 2a2.6 2.6 0 0 0 3.7 3.7l1.2-1.1" />
    </Glyph>
  )
}

export function IconImage(p: IconProps) {
  return (
    <Glyph {...p}>
      <rect x="1.9" y="3" width="12.2" height="10" rx="1" />
      <circle cx="5.7" cy="6.4" r="1.1" />
      <path d="M2 10.9l3.3-3 3 2.7 2.2-1.9 3.5 3.2" />
    </Glyph>
  )
}

export function IconStack(p: IconProps) {
  return (
    <Glyph {...p}>
      <rect x="1.9" y="1.9" width="8.4" height="8.4" rx="1" />
      <path d="M5.7 12.6a1 1 0 0 0 1 1h6.4a1 1 0 0 0 1-1V6.2" />
      <path d="M2 8.4l2.4-2.2 2.3 2.1" />
    </Glyph>
  )
}

export function IconSpark(p: IconProps) {
  return (
    <Glyph {...p}>
      <path d="M6.4 1.8l1.1 3.1 3.1 1.1-3.1 1.1-1.1 3.1-1.1-3.1L2.2 6l3.1-1.1 1.1-3.1Z" />
      <path d="M11.8 9.2l.6 1.6 1.6.6-1.6.6-.6 1.6-.6-1.6-1.6-.6 1.6-.6.6-1.6Z" />
    </Glyph>
  )
}

export function IconBrush(p: IconProps) {
  return (
    <Glyph {...p}>
      <path d="M13.4 2.6a1.6 1.6 0 0 0-2.3 0L6.2 7.5l2.3 2.3 4.9-4.9a1.6 1.6 0 0 0 0-2.3Z" />
      <path d="M6.2 7.5 4.6 9.1c-.9.9-.6 2.1-1.3 2.8-.5.5-1.1.6-1.6.6.6 1.2 1.9 1.9 3.2 1.7 1.3-.2 2.3-1.2 2.4-2.5l.2-1.9" />
    </Glyph>
  )
}

export function IconCrop(p: IconProps) {
  return (
    <Glyph {...p}>
      <path d="M4.5 1.5v10h10" />
      <path d="M1.5 4.5h10v10" />
    </Glyph>
  )
}

export function IconCalendar(p: IconProps) {
  return (
    <Glyph {...p}>
      <rect x="2.2" y="3.2" width="11.6" height="10.6" rx="1" />
      <path d="M2.2 6.6h11.6M5.4 1.8v2.8M10.6 1.8v2.8" />
    </Glyph>
  )
}

export function IconChevron(p: IconProps) {
  return <Glyph {...p}><path d="M3.8 6.2L8 10.3l4.2-4.1" /></Glyph>
}

/* Квадратная кнопка без подписи: смысл несёт title + aria-label. */
export function IconButton({ icon, title, onClick, danger, disabled }: {
  icon: ReactNode
  title: string
  onClick?: () => void
  danger?: boolean
  disabled?: boolean
}) {
  return (
    <button type="button" className={`ibtn${danger ? ' danger' : ''}`}
      title={title} aria-label={title} disabled={disabled} onClick={onClick}>
      {icon}
    </button>
  )
}
