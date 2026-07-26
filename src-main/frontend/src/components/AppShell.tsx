import { useState } from 'react'
import type { ReactNode } from 'react'
import type { AuthUser, UserRole } from '../app/types'
import { Icon } from './ScreenPrimitives'
import type { IconName } from './ScreenPrimitives'

export type ScreenId =
  | 'student-dashboard'
  | 'educator-dashboard'
  | 'course-editor'
  | 'students'
  | 'analytics'
  | 'admin-overview'
  | 'admin-users'
  | 'admin-courses'
  | 'admin-settings'

interface NavigationItem {
  id: ScreenId
  label: string
  icon: IconName
}

const navigation: Record<UserRole, NavigationItem[]> = {
  student: [
    { id: 'student-dashboard', label: 'My learning', icon: 'dashboard' },
  ],
  educator: [
    { id: 'educator-dashboard', label: 'Dashboard', icon: 'dashboard' },
    { id: 'course-editor', label: 'Course editor', icon: 'course' },
    { id: 'students', label: 'Students', icon: 'people' },
    { id: 'analytics', label: 'Analytics', icon: 'analytics' },
  ],
  admin: [
    { id: 'admin-overview', label: 'Overview', icon: 'dashboard' },
    { id: 'admin-users', label: 'Accounts', icon: 'people' },
    { id: 'admin-courses', label: 'Courses', icon: 'course' },
    { id: 'admin-settings', label: 'Settings', icon: 'settings' },
  ],
}

function defaultScreen(role: UserRole): ScreenId {
  return navigation[role][0].id
}

export function AppShell({
  user,
  activeScreen,
  onNavigate,
  onLogout,
  children,
}: {
  user: AuthUser
  activeScreen: ScreenId
  onNavigate: (screen: ScreenId) => void
  onLogout: () => Promise<void>
  children: ReactNode
}) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const initials = user.full_name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  const navigate = (screen: ScreenId) => {
    onNavigate(screen)
    setMobileOpen(false)
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <aside className={`app-sidebar ${mobileOpen ? 'open' : ''}`}>
        <a className="brand" href="#main-content" onClick={() => navigate(defaultScreen(user.role))}>
          <span className="brand-mark"><i /><i /><b /></span>
          <span>Quantum<strong>Learn</strong></span>
        </a>
        <p className="workspace-label">{user.role} workspace</p>
        <nav aria-label={`${user.role} navigation`}>
          {navigation[user.role].map((item) => (
            <button
              key={item.id}
              className={activeScreen === item.id ? 'active' : ''}
              aria-current={activeScreen === item.id ? 'page' : undefined}
              onClick={() => navigate(item.id)}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-user">
          <span className="avatar">{initials}</span>
          <div><strong>{user.full_name}</strong><small>{user.email}</small></div>
        </div>
        <button className="sidebar-logout" onClick={() => void onLogout()}>
          <Icon name="logout" size={18} />
          <span>Sign out</span>
        </button>
      </aside>

      {mobileOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}

      <div className="app-main">
        <header className="mobile-header">
          <button className="icon-button" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
            <Icon name="menu" />
          </button>
          <span className="brand brand--mobile">Quantum<strong>Learn</strong></span>
          <span className="avatar avatar--small">{initials}</span>
        </header>
        <main id="main-content" tabIndex={-1}>{children}</main>
      </div>
    </div>
  )
}
