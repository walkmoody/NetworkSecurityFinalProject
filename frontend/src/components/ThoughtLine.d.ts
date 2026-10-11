import type { CSSProperties, ReactNode } from 'react'

// Types for ThoughtLine.jsx (React Bits), matching its props table.
export type ThoughtLineProps = {
  label?: string
  doneLabel?: string
  renderLabel?: (text: string, working: boolean) => ReactNode
  glyph?: 'sparkle' | 'dot' | 'none' | ReactNode
  steps?: string[]
  collapsible?: boolean
  collapseOnSettle?: boolean
  color?: string
  glyphColor?: string
  fontSize?: number
  breathPeriod?: number
  breathDepth?: number
  shimmer?: boolean
  shimmerDuration?: number
  settleDuration?: number
  settleBlur?: number
  working?: boolean
  settleAfter?: number
  elapsed?: number
  showTimer?: boolean
  onSettle?: (seconds: number) => void
  className?: string
  style?: CSSProperties
}

declare function ThoughtLine(props: ThoughtLineProps): ReactNode
export default ThoughtLine
