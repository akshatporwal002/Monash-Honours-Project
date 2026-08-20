import { BarChart3, BookOpen, ClipboardCheck, ClipboardList, LayoutDashboard, LogOut, Menu, Settings, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { NavLink, Link, Outlet } from 'react-router-dom'

import type { AuthUser, UserRole } from '../app/types'
import { cx } from './ui/cx'
import { homePath } from './paths'
import styles from './AppShell.module.css'

interface NavigationItem {
  to: string
  end?: boolean
  label: string
  icon: ReactNode
}

const iconSize = 18

const navigation: Record<UserRole, NavigationItem[]> = {
  student: [{ to: '/student', end: true, label: 'My learning', icon: <LayoutDashboard size={iconSize} /> }],
  educator: [
    { to: '/educator', end: true, label: 'Dashboard', icon: <LayoutDashboard size={iconSize} /> },
    { to: '/educator/courses', label: 'Course editor', icon: <BookOpen size={iconSize} /> },
    { to: '/educator/students', label: 'Students', icon: <Users size={iconSize} /> },
    { to: '/educator/analytics', label: 'Analytics', icon: <BarChart3 size={iconSize} /> },
  ],
  admin: [
    { to: '/admin', end: true, label: 'Overview', icon: <LayoutDashboard size={iconSize} /> },
    { to: '/admin/users', label: 'Accounts', icon: <Users size={iconSize} /> },
    { to: '/admin/courses', label: 'Courses', icon: <BookOpen size={iconSize} /> },
    { to: '/admin/settings', label: 'Settings', icon: <Settings size={iconSize} /> },
  ],
}

const assessorNavigation: NavigationItem[] = [
  { to: '/assessor/setup', label: 'Assessment setup', icon: <ClipboardList size={iconSize} /> },
  { to: '/assessor/review', label: 'Assessment review', icon: <ClipboardCheck size={iconSize} /> },
]

function LensMark({ size = 22 }: { size?: number }) {
  return (
    <svg className={styles.lens} width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
      <path d="M12 3v18" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  )
}

export function AppShell({
  user,
  hasAssessorAccess,
  onLogout,
}: {
  user: AuthUser
  hasAssessorAccess: boolean
  onLogout: () => Promise<void>
}) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const initials = user.full_name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  useEffect(() => {
    if (!mobileOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [mobileOpen])

  const items =
    user.role === 'educator' && hasAssessorAccess ? [...navigation.educator, ...assessorNavigation] : navigation[user.role]

  return (
    <div className={cx('ll-root', styles.shell)}>
      <a className={styles.skipLink} href="#main-content">
        Skip to content
      </a>
      <aside id="app-sidebar" className={cx(styles.sidebar, mobileOpen && styles.sidebarOpen)}>
        <Link className={styles.brand} to={homePath(user.role)} onClick={() => setMobileOpen(false)}>
          <LensMark />
          <span>LearnLens</span>
        </Link>
        <p className={styles.workspace}>{user.role} workspace</p>
        <nav className={styles.nav} aria-label={`${user.role} navigation`}>
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={styles.navLink}
              onClick={() => setMobileOpen(false)}
            >
              <span className={styles.navIcon} aria-hidden="true">
                {item.icon}
              </span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className={styles.spacer} />
        <div className={styles.user}>
          <span className={styles.avatar} aria-hidden="true">
            {initials}
          </span>
          <div className={styles.userText}>
            <span className={styles.userName}>{user.full_name}</span>
            <span className={styles.userEmail}>{user.email}</span>
          </div>
        </div>
        <button type="button" className={styles.signOut} onClick={() => void onLogout()}>
          <span className={styles.navIcon} aria-hidden="true">
            <LogOut size={iconSize} />
          </span>
          <span>Sign out</span>
        </button>
      </aside>

      {mobileOpen ? <div className={styles.scrim} aria-hidden="true" onClick={() => setMobileOpen(false)} /> : null}

      <div className={styles.mainArea}>
        <header className={styles.topbar}>
          <button
            type="button"
            className={cx(styles.menuButton)}
            aria-label="Open navigation"
            aria-expanded={mobileOpen}
            aria-controls="app-sidebar"
            onClick={() => setMobileOpen((open) => !open)}
          >
            <Menu size={20} aria-hidden="true" />
          </button>
          <span className={styles.topbarBrand}>
            <LensMark size={18} />
            LearnLens
          </span>
        </header>
        <main id="main-content" tabIndex={-1} className={styles.main}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
