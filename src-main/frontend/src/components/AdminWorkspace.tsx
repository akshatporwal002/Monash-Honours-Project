import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../app/api'
import type { AdminUser, CourseSummary, SystemSettings, UserRole } from '../app/types'
import { Icon, PageHeading, Panel, ScreenState } from './ScreenPrimitives'

export type AdminSection = 'overview' | 'users' | 'courses' | 'settings'

export function AdminWorkspace({ section }: { section: AdminSection }) {
  const [users, setUsers] = useState<AdminUser[] | null>(null)
  const [courses, setCourses] = useState<CourseSummary[] | null>(null)
  const [settings, setSettings] = useState<SystemSettings | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [showCreateUser, setShowCreateUser] = useState(false)
  const [pendingUser, setPendingUser] = useState<AdminUser | null>(null)
  const [pendingCourse, setPendingCourse] = useState<CourseSummary | null>(null)
  const [newUser, setNewUser] = useState({
    full_name: '',
    email: '',
    role: 'student' as UserRole,
    password: '',
  })
  const dialogRef = useRef<HTMLElement>(null)

  useEffect(() => {
    if (!showCreateUser && !pendingUser && !pendingCourse) return
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const dialog = dialogRef.current
    const focusableSelector = 'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled)'
    dialog?.querySelector<HTMLElement>(focusableSelector)?.focus()
    const close = () => {
      setShowCreateUser(false)
      setPendingUser(null)
      setPendingCourse(null)
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        close()
        return
      }
      if (event.key !== 'Tab' || !dialog) return
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(focusableSelector))
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      previousFocus?.focus()
    }
  }, [pendingCourse, pendingUser, showCreateUser])

  const load = async (signal?: AbortSignal) => {
    try {
      const [userData, courseData, settingData] = await Promise.all([
        api.admin.users(signal),
        api.courses.list(signal),
        api.admin.settings(signal),
      ])
      setUsers(userData)
      setCourses(courseData)
      setSettings(settingData)
      setError('')
    } catch (caught) {
      if (!signal?.aborted) setError(caught instanceof Error ? caught.message : 'Admin data could not be loaded.')
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    async function loadInitialData() {
      try {
        const [userData, courseData, settingData] = await Promise.all([
          api.admin.users(controller.signal),
          api.courses.list(controller.signal),
          api.admin.settings(controller.signal),
        ])
        setUsers(userData)
        setCourses(courseData)
        setSettings(settingData)
        setError('')
      } catch (caught) {
        if (!controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : 'Admin data could not be loaded.')
        }
      }
    }
    void loadInitialData()
    return () => controller.abort()
  }, [])

  const counts = useMemo(() => ({
    active: users?.filter((user) => user.is_active).length ?? 0,
    students: users?.filter((user) => user.role === 'student').length ?? 0,
    educators: users?.filter((user) => user.role === 'educator').length ?? 0,
    published: courses?.filter((course) => course.status === 'published').length ?? 0,
  }), [courses, users])

  const createUser = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const saved = await api.admin.createUser(newUser)
      setUsers((current) => current ? [saved, ...current] : [saved])
      setShowCreateUser(false)
      setNewUser({ full_name: '', email: '', role: 'student', password: '' })
      setMessage(`${saved.full_name}'s account was created.`)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The account could not be created.')
    } finally {
      setBusy(false)
    }
  }

  const confirmUserState = async () => {
    if (!pendingUser) return
    setBusy(true)
    setMessage('')
    try {
      const updated = await api.admin.setUserActive(pendingUser.id, !pendingUser.is_active)
      setUsers((current) => current?.map((user) => user.id === updated.id ? updated : user) ?? null)
      setMessage(`${updated.full_name} is now ${updated.is_active ? 'active' : 'inactive'}.`)
      setPendingUser(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The account could not be updated.')
    } finally {
      setBusy(false)
    }
  }

  const updateRole = async (user: AdminUser, role: UserRole) => {
    if (
      user.role === 'educator'
      && role !== 'educator'
      && !window.confirm(
        'This educator may own active courses. Confirm that those courses have been archived '
        + 'or can remain administrator-managed before changing the role.',
      )
    ) {
      return
    }
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const updated = await api.admin.updateUser(user.id, { role })
      setUsers((current) => current?.map((item) => item.id === updated.id ? updated : item) ?? null)
      setMessage(`${updated.full_name}'s role was updated to ${role}.`)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The account role could not be updated.')
    } finally {
      setBusy(false)
    }
  }

  const archiveCourse = async () => {
    if (!pendingCourse) return
    setBusy(true)
    setMessage('')
    try {
      const updated = await api.admin.archiveCourse(pendingCourse.id)
      setCourses((current) => current?.map((course) => course.id === updated.id ? updated : course) ?? null)
      setMessage(`${updated.title} was archived.`)
      setPendingCourse(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The course could not be archived.')
    } finally {
      setBusy(false)
    }
  }

  const saveSettings = async (event: FormEvent) => {
    event.preventDefault()
    if (!settings) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      setSettings(await api.admin.updateSettings(settings))
      setMessage('System settings saved.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Settings could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  if (error && (!users || !courses || !settings)) {
    return <div className="screen"><ScreenState kind="error" title="Admin workspace unavailable" message={error} action={<button className="button button--secondary" onClick={() => void load()}>Try again</button>} /></div>
  }
  if (!users || !courses || !settings) {
    return <div className="screen"><ScreenState kind="loading" title="Loading administration" message="Checking accounts, courses and system configuration." /></div>
  }

  return (
    <div className="screen">
      {section === 'overview' && (
        <>
          <PageHeading eyebrow="Administration" title="System overview" description="A concise view of the people, courses and configuration behind QuantumLearn." />
          <section className="metric-grid">
            {[
              { label: 'Active accounts', value: counts.active, detail: 'Across all roles', icon: 'user' as const },
              { label: 'Students', value: counts.students, detail: 'Learner accounts', icon: 'book' as const },
              { label: 'Educators', value: counts.educators, detail: 'Course owners', icon: 'course' as const },
              { label: 'Published courses', value: counts.published, detail: `${courses.length} total courses`, icon: 'analytics' as const },
            ].map((item) => (
              <article className="metric-card" key={item.label}>
                <span><Icon name={item.icon} /></span><p>{item.label}</p><strong>{item.value}</strong><small>{item.detail}</small>
              </article>
            ))}
          </section>
          <div className="admin-overview-grid">
            <Panel eyebrow="Account mix" title="Users by role">
              <div className="role-breakdown">
                {(['student', 'educator', 'admin'] as const).map((role) => {
                  const count = users.filter((user) => user.role === role).length
                  return <div key={role}><span>{role}</span><div><i style={{ width: `${users.length ? (count / users.length) * 100 : 0}%` }} /></div><strong>{count}</strong></div>
                })}
              </div>
            </Panel>
            <Panel eyebrow="Governance" title="Configuration health">
              <dl className="settings-summary">
                <div><dt>AI provider</dt><dd>{settings.llm_provider || 'Not configured'}</dd></div>
                <div><dt>Model</dt><dd>{settings.llm_model || 'Not configured'}</dd></div>
                <div><dt>At-risk threshold</dt><dd>{settings.at_risk_threshold}%</dd></div>
                <div><dt>Passing score</dt><dd>{settings.passing_score}%</dd></div>
                <div><dt>Points per level</dt><dd>{settings.points_per_level}</dd></div>
                <div><dt>Automatic reminders</dt><dd>{settings.reminders_enabled ? 'Enabled' : 'Disabled'}</dd></div>
              </dl>
            </Panel>
          </div>
        </>
      )}

      {section === 'users' && (
        <>
          <PageHeading
            eyebrow="Account management"
            title="Users"
            description="Create role-scoped accounts and deactivate access without deleting learning records."
            actions={<button className="button button--primary" onClick={() => setShowCreateUser(true)}><Icon name="user" size={18} /> Add user</button>}
          />
          <section className="table-panel" aria-labelledby="admin-users-title">
            <header className="table-toolbar"><div><p className="eyebrow">Directory</p><h2 id="admin-users-title">{users.length} accounts</h2></div></header>
            <div className="table-scroll">
              <table>
                <thead><tr><th scope="col">User</th><th scope="col">Role</th><th scope="col">Status</th><th scope="col">Created</th><th scope="col">Action</th></tr></thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <th scope="row"><strong>{user.full_name}</strong><small>{user.email}</small></th>
                      <td>
                        <select
                          className="table-role-select"
                          aria-label={`Role for ${user.full_name}`}
                          value={user.role}
                          disabled={busy}
                          onChange={(event) => void updateRole(user, event.target.value as UserRole)}
                        >
                          <option value="student">Student</option>
                          <option value="educator">Educator</option>
                          <option value="admin">Administrator</option>
                        </select>
                      </td>
                      <td><span className={`risk-badge risk-badge--${user.is_active ? 'on_track' : 'not_started'}`}>{user.is_active ? 'Active' : 'Inactive'}</span></td>
                      <td>{user.created_at ? new Date(user.created_at).toLocaleDateString('en-AU') : '—'}</td>
                      <td><button className="button button--ghost" onClick={() => setPendingUser(user)}>{user.is_active ? 'Deactivate' : 'Reactivate'}</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {section === 'courses' && (
        <>
          <PageHeading eyebrow="Course governance" title="Courses" description="Review ownership and archive courses while preserving dependent student records." />
          {courses.length === 0 ? (
            <ScreenState kind="empty" title="No courses configured" message="Educators can create the first course from their course editor." />
          ) : (
            <div className="admin-course-grid">
              {courses.map((course) => (
                <article className="admin-course-card" key={course.id}>
                  <header><span className="icon-chip"><Icon name="course" /></span><span className={`status-chip status-chip--${course.status}`}>{course.status}</span></header>
                  <p className="eyebrow">{course.code}</p>
                  <h2>{course.title}</h2>
                  <p>{course.description || 'No course description provided.'}</p>
                  <dl><div><dt>Students</dt><dd>{course.enrolled_students ?? 0}</dd></div><div><dt>Modules</dt><dd>{course.module_count ?? 0}</dd></div></dl>
                  <button className="button button--ghost" disabled={course.status === 'archived'} onClick={() => setPendingCourse(course)}>Archive course</button>
                </article>
              ))}
            </div>
          )}
        </>
      )}

      {section === 'settings' && (
        <>
          <PageHeading eyebrow="System configuration" title="Settings" description="Choose shared AI defaults and learner-support thresholds for the MVP." />
          <form className="settings-form" onSubmit={(event) => void saveSettings(event)}>
            <section>
              <div><span className="icon-chip"><Icon name="spark" /></span><div><h2>AI generation</h2><p>Changing provider or model affects future task and feedback generation.</p></div></div>
              <div className="form-grid">
                <label className="field"><span>Provider</span><select value={settings.llm_provider} onChange={(event) => setSettings({ ...settings, llm_provider: event.target.value })}><option value="">Select provider</option><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option><option value="local">Local provider</option></select></label>
                <label className="field"><span>Model</span><input value={settings.llm_model} onChange={(event) => setSettings({ ...settings, llm_model: event.target.value })} placeholder="Configured model identifier" /></label>
              </div>
              {!settings.llm_provider && <p className="settings-warning"><Icon name="warning" size={17} /> AI generation remains unavailable until a provider and its server-side credentials are configured.</p>}
            </section>
            <section>
              <div><span className="icon-chip"><Icon name="people" /></span><div><h2>Student support</h2><p>Set when low progress should become an educator alert.</p></div></div>
              <label className="range-field"><span>At-risk completion threshold</span><input type="range" min="10" max="90" step="5" value={settings.at_risk_threshold} onChange={(event) => setSettings({ ...settings, at_risk_threshold: Number(event.target.value) })} /><strong>{settings.at_risk_threshold}%</strong></label>
              <label className="range-field"><span>Passing score</span><input type="range" min="0" max="100" step="5" value={settings.passing_score} onChange={(event) => setSettings({ ...settings, passing_score: Number(event.target.value) })} /><strong>{settings.passing_score}%</strong></label>
              <label className="field settings-number"><span>Points required per level</span><input type="number" min="1" max="100000" value={settings.points_per_level} onChange={(event) => setSettings({ ...settings, points_per_level: Number(event.target.value) })} /></label>
              <label className="switch-field"><input type="checkbox" checked={settings.reminders_enabled} onChange={(event) => setSettings({ ...settings, reminders_enabled: event.target.checked })} /><span><i /></span><div><strong>Automatic overdue reminders</strong><small>Send one deduplicated reminder when a task becomes overdue.</small></div></label>
            </section>
            <div className="wizard-actions"><button className="button button--primary" disabled={busy}>{busy ? 'Saving…' : 'Save settings'} <Icon name="check" size={17} /></button></div>
          </form>
        </>
      )}

      {message && <p className="toast-message" role="status">{message}</p>}
      {error && <p className="toast-message toast-message--error" role="alert">{error}</p>}

      {showCreateUser && (
        <div className="confirm-overlay" role="dialog" aria-modal="true" aria-labelledby="create-user-title">
          <form className="confirm-dialog create-user-dialog" ref={(node) => { dialogRef.current = node }} onSubmit={(event) => void createUser(event)}>
            <header><span className="icon-chip"><Icon name="user" /></span><div><p className="eyebrow">New account</p><h2 id="create-user-title">Add a user</h2></div></header>
            <label className="field"><span>Full name</span><input value={newUser.full_name} onChange={(event) => setNewUser({ ...newUser, full_name: event.target.value })} required /></label>
            <label className="field"><span>Email address</span><input type="email" value={newUser.email} onChange={(event) => setNewUser({ ...newUser, email: event.target.value })} required /></label>
            <label className="field"><span>Role</span><select value={newUser.role} onChange={(event) => setNewUser({ ...newUser, role: event.target.value as UserRole })}><option value="student">Student</option><option value="educator">Educator</option><option value="admin">Administrator</option></select></label>
            <label className="field"><span>Temporary password</span><input type="password" minLength={8} value={newUser.password} onChange={(event) => setNewUser({ ...newUser, password: event.target.value })} required /></label>
            <div><button type="button" className="button button--ghost" onClick={() => setShowCreateUser(false)}>Cancel</button><button className="button button--primary" disabled={busy}>Create account</button></div>
          </form>
        </div>
      )}

      {pendingUser && (
        <div className="confirm-overlay" role="dialog" aria-modal="true" aria-labelledby="confirm-user-title">
          <section className="confirm-dialog" ref={(node) => { dialogRef.current = node }}>
            <span className="icon-chip icon-chip--warning"><Icon name="warning" /></span>
            <h2 id="confirm-user-title">{pendingUser.is_active ? 'Deactivate' : 'Reactivate'} {pendingUser.full_name}?</h2>
            <p>{pendingUser.is_active ? 'They will lose access immediately. Their submissions, feedback and dependent course data will be preserved.' : 'They will regain access according to their assigned role.'}</p>
            <div><button className="button button--ghost" onClick={() => setPendingUser(null)}>Cancel</button><button className="button button--primary" onClick={() => void confirmUserState()} disabled={busy}>Confirm</button></div>
          </section>
        </div>
      )}

      {pendingCourse && (
        <div className="confirm-overlay" role="dialog" aria-modal="true" aria-labelledby="confirm-course-title">
          <section className="confirm-dialog" ref={(node) => { dialogRef.current = node }}>
            <span className="icon-chip icon-chip--warning"><Icon name="warning" /></span>
            <h2 id="confirm-course-title">Archive {pendingCourse.title}?</h2>
            <p>The course will be hidden from active learning. Enrolments, submissions and analytics will be retained for audit and research.</p>
            <div><button className="button button--ghost" onClick={() => setPendingCourse(null)}>Cancel</button><button className="button button--primary" onClick={() => void archiveCourse()} disabled={busy}>Archive course</button></div>
          </section>
        </div>
      )}
    </div>
  )
}
