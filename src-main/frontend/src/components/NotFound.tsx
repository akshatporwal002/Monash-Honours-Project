import { Link } from 'react-router-dom'

import { cx } from './ui/cx'
import styles from './NotFound.module.css'

export interface NotFoundProps {
  /** Where "Go to your workspace" points; defaults to the sign-in page. */
  homeTo?: string
}

/**
 * Rendered for unknown URLs and for valid URLs outside the signed-in user's
 * authority. The two cases are deliberately identical so the page never leaks
 * whether a record or area exists (D2 §13.3 posture).
 */
export function NotFound({ homeTo = '/login' }: NotFoundProps) {
  return (
    <div className={cx('ll-root', styles.page)}>
      <p className={styles.eyebrow}>Page not found</p>
      <h1 className={styles.title}>This page does not exist or is not available to your account</h1>
      <p className={styles.description}>Check the address, or head back to your workspace to continue.</p>
      <Link className={styles.action} to={homeTo}>
        Go to your workspace
      </Link>
    </div>
  )
}
