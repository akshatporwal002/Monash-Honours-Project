import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  GraduationCap,
  Sparkles,
  UserPlus,
  Users,
} from 'lucide-react'

import { api } from '../app/api'
import type { AdminUser, CourseSummary, SystemSettings, UserRole } from '../app/types'
import {
  AlertDialog,
  BarList,
  Button,
  Card,
  Checkbox,
  DescriptionList,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  Input,
  PageHeader,
  Select,
  Skeleton,
  Tag,
  cx,
} from './ui'
import styles from './AdminWorkspace.module.css'

export type AdminSection = 'overview' | 'users' | 'courses' | 'settings'

const roleOptions = [
  { value: 'student', label: 'Student' },
  { value: 'educator', label: 'Educator' },
  { value: 'admin', label: 'Administrator' },
]

/* Radix Select items cannot carry an empty-string value; this sentinel maps to
   the stored '' (no provider configured). */
const noProviderValue = 'no-provider'

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
  const [pendingRole, setPendingRole] = useState<{ user: AdminUser; role: UserRole } | null>(null)
  const [newUser, setNewUser] = useState({
    full_name: '',
    email: '',
    role: 'student' as UserRole,
    password: '',
  })

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

  const applyRole = async (user: AdminUser, role: UserRole) => {
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

  const requestRoleChange = (user: AdminUser, role: UserRole) => {
    if (role === user.role) return
    if (user.role === 'educator' && role !== 'educator') {
      setPendingRole({ user, role })
      return
    }
    void applyRole(user, role)
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
    return (
      <div className={styles.screen}>
        <ErrorState title="Admin workspace unavailable" description={error} onRetry={() => void load()} />
      </div>
    )
  }
  if (!users || !courses || !settings) {
    return (
      <div className={styles.screen}>
        <p role="status" className={styles.loading}>
          Loading administration: checking accounts, courses and system configuration.
        </p>
        <Skeleton height="2.5rem" width="24rem" />
        <Skeleton height="9rem" />
        <Skeleton height="9rem" />
      </div>
    )
  }

  return (
    <div className={styles.screen}>
      {section === 'overview' && (
        <>
          <PageHeader
            eyebrow="Administration"
            title="System overview"
            description="A concise view of the people, courses and configuration behind LearnLens."
          />
          <section className={styles.metrics} aria-label="System metrics">
            {[
              { label: 'Active accounts', value: counts.active, detail: 'Across all roles', icon: <Users size={18} /> },
              { label: 'Students', value: counts.students, detail: 'Learner accounts', icon: <BookOpen size={18} /> },
              { label: 'Educators', value: counts.educators, detail: 'Course owners', icon: <GraduationCap size={18} /> },
              { label: 'Published courses', value: counts.published, detail: `${courses.length} total courses`, icon: <BarChart3 size={18} /> },
            ].map((item) => (
              <Card key={item.label} className={styles.metric}>
                <span className={styles.metricIcon} aria-hidden="true">{item.icon}</span>
                <p className={styles.metricLabel}>{item.label}</p>
                <p className={styles.metricValue}>{item.value}</p>
                <p className={styles.metricDetail}>{item.detail}</p>
              </Card>
            ))}
          </section>
          <div className={styles.grid}>
            <Card eyebrow="Account mix" heading="Users by role">
              <BarList
                max={Math.max(1, users.length)}
                items={(['student', 'educator', 'admin'] as const).map((role) => ({
                  label: role,
                  value: users.filter((user) => user.role === role).length,
                }))}
              />
            </Card>
            <Card eyebrow="Governance" heading="Configuration health">
              <DescriptionList
                items={[
                  { term: 'AI provider', description: settings.llm_provider || 'Not configured' },
                  { term: 'Model', description: settings.llm_model || 'Not configured' },
                  { term: 'At-risk threshold', description: `${settings.at_risk_threshold}%` },
                  { term: 'Passing score', description: `${settings.passing_score}%` },
                  { term: 'Points per level', description: String(settings.points_per_level) },
                  { term: 'Automatic reminders', description: settings.reminders_enabled ? 'Enabled' : 'Disabled' },
                ]}
              />
            </Card>
          </div>
        </>
      )}

      {section === 'users' && (
        <>
          <PageHeader
            eyebrow="Account management"
            title="Users"
            description="Create role-scoped accounts and deactivate access without deleting learning records."
            actions={
              <Button variant="primary" onClick={() => setShowCreateUser(true)}>
                <UserPlus size={16} aria-hidden="true" /> Add user
              </Button>
            }
          />
          <Card padding="none" className={styles.tablePanel} aria-labelledby="admin-users-title">
            <header className={styles.toolbar}>
              <div>
                <p className={styles.eyebrow}>Directory</p>
                <h2 id="admin-users-title" className={styles.tableTitle}>{users.length} accounts</h2>
              </div>
            </header>
            <div className={styles.tableScroll}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th scope="col">User</th>
                    <th scope="col">Role</th>
                    <th scope="col">Status</th>
                    <th scope="col">Created</th>
                    <th scope="col">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <th scope="row" className={styles.userCell}>
                        <strong className={styles.userName}>{user.full_name}</strong>
                        <small className={styles.userEmail}>{user.email}</small>
                      </th>
                      <td>
                        <Select
                          aria-label={`Role for ${user.full_name}`}
                          value={user.role}
                          disabled={busy}
                          onValueChange={(value) => requestRoleChange(user, value as UserRole)}
                          options={roleOptions}
                        />
                      </td>
                      <td>
                        <Tag className={cx(!user.is_active && styles.inactiveTag)}>
                          {user.is_active ? 'Active' : 'Inactive'}
                        </Tag>
                      </td>
                      <td>{user.created_at ? new Date(user.created_at).toLocaleDateString('en-AU') : '—'}</td>
                      <td>
                        <Button variant="quiet" size="sm" onClick={() => setPendingUser(user)}>
                          {user.is_active ? 'Deactivate' : 'Reactivate'}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      {section === 'courses' && (
        <>
          <PageHeader
            eyebrow="Course governance"
            title="Courses"
            description="Review ownership and archive courses while preserving dependent student records."
          />
          {courses.length === 0 ? (
            <EmptyState
              icon={<BookOpen size={20} />}
              title="No courses configured"
              description="Educators can create the first course from their course editor."
            />
          ) : (
            <div className={styles.courseGrid}>
              {courses.map((course) => (
                <Card
                  key={course.id}
                  eyebrow={course.code}
                  heading={course.title}
                  actions={<Tag>{course.status}</Tag>}
                  className={styles.courseCard}
                >
                  <p className={styles.courseDescription}>
                    {course.description || 'No course description provided.'}
                  </p>
                  <DescriptionList
                    items={[
                      { term: 'Students', description: String(course.enrolled_students ?? 0) },
                      { term: 'Modules', description: String(course.module_count ?? 0) },
                    ]}
                  />
                  <div className={styles.courseAction}>
                    <Button
                      variant="quiet"
                      disabled={course.status === 'archived'}
                      onClick={() => setPendingCourse(course)}
                    >
                      Archive course
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {section === 'settings' && (
        <>
          <PageHeader
            eyebrow="System configuration"
            title="Settings"
            description="Choose shared AI defaults and learner-support thresholds for the MVP."
          />
          <form className={styles.settingsForm} onSubmit={(event) => void saveSettings(event)}>
            <Card className={styles.settingsSection}>
              <div className={styles.sectionHead}>
                <span className={styles.sectionIcon} aria-hidden="true"><Sparkles size={18} /></span>
                <div>
                  <h2 className={styles.sectionTitle}>AI generation</h2>
                  <p className={styles.sectionText}>
                    Changing provider or model affects future task and feedback generation.
                  </p>
                </div>
              </div>
              <div className={styles.formGrid}>
                <Field label="Provider">
                  <Select
                    value={settings.llm_provider || noProviderValue}
                    onValueChange={(value) => setSettings({
                      ...settings,
                      llm_provider: value === noProviderValue ? '' : value,
                    })}
                    options={[
                      { value: noProviderValue, label: 'Select provider' },
                      { value: 'openai', label: 'OpenAI' },
                      { value: 'anthropic', label: 'Anthropic' },
                      { value: 'local', label: 'Local provider' },
                    ]}
                  />
                </Field>
                <Field label="Model">
                  <Input
                    value={settings.llm_model}
                    onChange={(event) => setSettings({ ...settings, llm_model: event.target.value })}
                    placeholder="Configured model identifier"
                  />
                </Field>
              </div>
              {!settings.llm_provider && (
                <p className={styles.settingsWarning}>
                  <AlertTriangle size={16} aria-hidden="true" /> AI generation remains unavailable
                  until a provider and its server-side credentials are configured.
                </p>
              )}
            </Card>
            <Card className={styles.settingsSection}>
              <div className={styles.sectionHead}>
                <span className={styles.sectionIcon} aria-hidden="true"><Users size={18} /></span>
                <div>
                  <h2 className={styles.sectionTitle}>Student support</h2>
                  <p className={styles.sectionText}>
                    Set when low progress should become an educator alert.
                  </p>
                </div>
              </div>
              <div className={styles.rangeRow}>
                <Field label="At-risk completion threshold" className={styles.rangeField}>
                  <input
                    type="range"
                    className={styles.range}
                    min="10"
                    max="90"
                    step="5"
                    value={settings.at_risk_threshold}
                    onChange={(event) => setSettings({ ...settings, at_risk_threshold: Number(event.target.value) })}
                  />
                </Field>
                <strong className={styles.rangeValue}>{settings.at_risk_threshold}%</strong>
              </div>
              <div className={styles.rangeRow}>
                <Field label="Passing score" className={styles.rangeField}>
                  <input
                    type="range"
                    className={styles.range}
                    min="0"
                    max="100"
                    step="5"
                    value={settings.passing_score}
                    onChange={(event) => setSettings({ ...settings, passing_score: Number(event.target.value) })}
                  />
                </Field>
                <strong className={styles.rangeValue}>{settings.passing_score}%</strong>
              </div>
              <Field label="Points required per level" className={styles.numberField}>
                <Input
                  type="number"
                  min={1}
                  max={100000}
                  value={settings.points_per_level}
                  onChange={(event) => setSettings({ ...settings, points_per_level: Number(event.target.value) })}
                />
              </Field>
              <Checkbox
                label="Automatic overdue reminders"
                help="Send one deduplicated reminder when a task becomes overdue."
                checked={settings.reminders_enabled}
                onChange={(event) => setSettings({ ...settings, reminders_enabled: event.target.checked })}
              />
            </Card>
            <div className={styles.settingsActions}>
              <Button type="submit" variant="primary" loading={busy}>Save settings</Button>
            </div>
          </form>
        </>
      )}

      {message && <p className={styles.toast} role="status">{message}</p>}
      {error && <p className={cx(styles.toast, styles.toastError)} role="alert">{error}</p>}

      <Dialog
        open={showCreateUser}
        onOpenChange={setShowCreateUser}
        title="Add a user"
        description="Create a role-scoped account with a temporary password."
      >
        <form className={styles.dialogForm} onSubmit={(event) => void createUser(event)}>
          <Field label="Full name">
            <Input
              value={newUser.full_name}
              onChange={(event) => setNewUser({ ...newUser, full_name: event.target.value })}
              required
            />
          </Field>
          <Field label="Email address">
            <Input
              type="email"
              value={newUser.email}
              onChange={(event) => setNewUser({ ...newUser, email: event.target.value })}
              required
            />
          </Field>
          <Field label="Role">
            <Select
              value={newUser.role}
              onValueChange={(value) => setNewUser({ ...newUser, role: value as UserRole })}
              options={roleOptions}
            />
          </Field>
          <Field label="Temporary password">
            <Input
              type="password"
              minLength={8}
              value={newUser.password}
              onChange={(event) => setNewUser({ ...newUser, password: event.target.value })}
              required
            />
          </Field>
          <div className={styles.dialogActions}>
            <Button variant="quiet" onClick={() => setShowCreateUser(false)}>Cancel</Button>
            <Button type="submit" variant="primary" loading={busy}>Create account</Button>
          </div>
        </form>
      </Dialog>

      <AlertDialog
        open={Boolean(pendingUser)}
        onOpenChange={(open) => {
          if (!open) setPendingUser(null)
        }}
        title={pendingUser
          ? `${pendingUser.is_active ? 'Deactivate' : 'Reactivate'} ${pendingUser.full_name}?`
          : 'Update account?'}
        description={pendingUser?.is_active
          ? 'They will lose access immediately. Their submissions, feedback and dependent course data will be preserved.'
          : 'They will regain access according to their assigned role.'}
        confirmLabel="Confirm"
        confirmLoading={busy}
        onConfirm={() => void confirmUserState()}
      />

      <AlertDialog
        open={Boolean(pendingRole)}
        onOpenChange={(open) => {
          if (!open) setPendingRole(null)
        }}
        title={pendingRole ? `Change ${pendingRole.user.full_name}'s role?` : 'Change role?'}
        description="This educator may own active courses. Confirm that those courses have been archived or can remain administrator-managed before changing the role."
        confirmLabel="Change role"
        confirmLoading={busy}
        onConfirm={() => {
          if (!pendingRole) return
          const { user, role } = pendingRole
          setPendingRole(null)
          void applyRole(user, role)
        }}
      />

      <AlertDialog
        open={Boolean(pendingCourse)}
        onOpenChange={(open) => {
          if (!open) setPendingCourse(null)
        }}
        title={pendingCourse ? `Archive ${pendingCourse.title}?` : 'Archive course?'}
        description="The course will be hidden from active learning. Enrolments, submissions and analytics will be retained for audit and research."
        confirmLabel="Archive course"
        confirmLoading={busy}
        onConfirm={() => void archiveCourse()}
      />
    </div>
  )
}
