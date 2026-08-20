import { cx } from '../cx'
import styles from './Skeleton.module.css'

export interface SkeletonProps {
  /** CSS width, e.g. '12rem' or '100%'. */
  width?: string
  /** CSS height, e.g. '1rem'. */
  height?: string
  className?: string
}

export function Skeleton({ width = '100%', height = '1rem', className }: SkeletonProps) {
  return <span aria-hidden="true" className={cx(styles.skeleton, className)} style={{ width, height }} />
}
