import type { CSSProperties, ReactNode } from 'react'

export type IconName =
  | 'analytics'
  | 'arrow'
  | 'book'
  | 'check'
  | 'circuit'
  | 'close'
  | 'code'
  | 'course'
  | 'dashboard'
  | 'logout'
  | 'menu'
  | 'people'
  | 'settings'
  | 'spark'
  | 'trophy'
  | 'user'
  | 'warning'

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    analytics: <><path d="M4 19V9m6 10V5m6 14v-7m5 7H2" /><path d="m4 6 5-3 6 5 5-4" /></>,
    arrow: <><path d="M5 12h14" /><path d="m14 7 5 5-5 5" /></>,
    book: <><path d="M4 5a3 3 0 0 1 3-3h13v17H7a3 3 0 0 0-3 3Z" /><path d="M4 5v17M8 6h7" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    circuit: <><path d="M3 6h5m4 0h9M3 18h9m4 0h5M8 3v6m8 6v6" /><circle cx="8" cy="6" r="2" /><circle cx="16" cy="18" r="2" /></>,
    close: <><path d="m6 6 12 12" /><path d="m18 6-12 12" /></>,
    code: <><path d="m9 18-6-6 6-6" /><path d="m15 6 6 6-6 6" /></>,
    course: <><path d="M3 6.5 12 2l9 4.5-9 4.5Z" /><path d="M6 9v6c3 3 9 3 12 0V9m3-2.5V16" /></>,
    dashboard: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    logout: <><path d="M10 4H5v16h5" /><path d="M14 8l4 4-4 4m4-4H9" /></>,
    menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
    people: <><circle cx="9" cy="8" r="3" /><path d="M3 20c0-4 2-6 6-6s6 2 6 6" /><path d="M16 5a3 3 0 0 1 0 6m1 3c3 .5 4 2.5 4 6" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.5-2.5 1a8 8 0 0 0-1.7-1L14.4 3h-4.8l-.4 3a8 8 0 0 0-1.7 1L5 6 3 9.5 5.1 11a7 7 0 0 0 0 2L3 14.5 5 18l2.5-1a8 8 0 0 0 1.7 1l.4 3h4.8l.4-3a8 8 0 0 0 1.7-1l2.5 1 2-3.5-2.1-1.5a7 7 0 0 0 .1-1Z" /></>,
    spark: <><path d="m12 2 1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8Z" /><path d="m19 17 .6 2.4L22 20l-2.4.6L19 23l-.6-2.4L16 20l2.4-.6Z" /></>,
    trophy: <><path d="M8 4h8v4a4 4 0 0 1-8 0Z" /><path d="M10 12v4m4-4v4m-6 4h8M9 16h6M8 6H4v1a4 4 0 0 0 4 4m8-5h4v1a4 4 0 0 1-4 4" /></>,
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 21c0-5 3-7 8-7s8 2 8 7" /></>,
    warning: <><path d="M12 3 2.5 20h19Z" /><path d="M12 9v5m0 3h.01" /></>,
  }

  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  )
}

export function ProgressRing({
  value,
  label = 'complete',
  size = 'regular',
}: {
  value: number
  label?: string
  size?: 'small' | 'regular'
}) {
  const safeValue = Math.min(100, Math.max(0, Math.round(value)))
  return (
    <div
      className={`progress-ring progress-ring--${size}`}
      style={{ '--progress': `${safeValue * 3.6}deg` } as CSSProperties}
      role="img"
      aria-label={`${safeValue}% ${label}`}
    >
      <div><strong>{safeValue}%</strong><span>{label}</span></div>
    </div>
  )
}

export function ScreenState({
  kind,
  title,
  message,
  action,
}: {
  kind: 'loading' | 'empty' | 'error'
  title: string
  message: string
  action?: ReactNode
}) {
  return (
    <div className={`screen-state screen-state--${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      {kind === 'loading' ? <div className="quantum-loader" aria-hidden="true"><i /><i /><i /></div> : <Icon name={kind === 'error' ? 'warning' : 'spark'} size={28} />}
      <h2>{title}</h2>
      <p>{message}</p>
      {action}
    </div>
  )
}

export function PageHeading({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string
  title: string
  description: string
  actions?: ReactNode
}) {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="page-heading__actions">{actions}</div>}
    </header>
  )
}

export function Panel({
  title,
  eyebrow,
  children,
  className = '',
  action,
}: {
  title: string
  eyebrow?: string
  children: ReactNode
  className?: string
  action?: ReactNode
}) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel__header">
        <div>
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h2>{title}</h2>
        </div>
        {action}
      </header>
      {children}
    </section>
  )
}
