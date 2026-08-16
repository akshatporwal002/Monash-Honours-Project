import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api } from './app/api'
import type { AuthUser, LearningNotification, LearningTask, StudentDashboardData, UserRole } from './app/types'
import { AdminWorkspace } from './components/AdminWorkspace'
import { AnalyticsView } from './components/AnalyticsView'
import { AppShell } from './components/AppShell'
import type { ScreenId } from './components/AppShell'
import { CourseEditor } from './components/CourseEditor'
import { EducatorDashboard } from './components/EducatorDashboard'
import { LoginScreen } from './components/LoginScreen'
import { ScreenState } from './components/ScreenPrimitives'
import { StudentDashboard } from './components/StudentDashboard'
import { StudentsView } from './components/StudentsView'
import { TaskView } from './components/TaskView'
import { AssessorSetup } from './features/assessment/AssessorSetup'
import { AssessorReviewQueue } from './features/assessment/AssessorReviewQueue'

type SessionState = 'checking' | 'anonymous' | 'authenticated'

function defaultScreen(role: UserRole): ScreenId {
  if (role === 'educator') return 'educator-dashboard'
  if (role === 'admin') return 'admin-overview'
  return 'student-dashboard'
}

function hasActiveAssessorAssignment(user: AuthUser): boolean {
  return user.role === 'educator' && user.scoped_assignments.some((assignment) => assignment.role === 'assessor')
}

function loginError(error: unknown): string {
  if (error instanceof ApiError && error.status === 401) return 'Email or password is incorrect.'
  if (error instanceof ApiError) return error.message
  return 'QuantumLearn could not reach the sign-in service. Please try again.'
}

function App() {
  const [sessionState, setSessionState] = useState<SessionState>('checking')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [activeScreen, setActiveScreen] = useState<ScreenId>('student-dashboard')
  const [loginBusy, setLoginBusy] = useState(false)
  const [authError, setAuthError] = useState('')
  const [studentData, setStudentData] = useState<StudentDashboardData | null>(null)
  const [studentError, setStudentError] = useState('')
  const [activeTask, setActiveTask] = useState<LearningTask | null>(null)
  const [pendingTask, setPendingTask] = useState<LearningTask | null>(null)
  const [taskOpenError, setTaskOpenError] = useState('')
  const taskRequestId = useRef(0)

  const acceptUser = (authenticatedUser: AuthUser) => {
    setUser(authenticatedUser)
    setActiveScreen(defaultScreen(authenticatedUser.role))
    setSessionState('authenticated')
    setAuthError('')
  }

  useEffect(() => {
    const controller = new AbortController()
    api.auth.me(controller.signal)
      .then(acceptUser)
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setSessionState('anonymous')
        if (!(error instanceof ApiError) || error.status !== 401) {
          setAuthError('Your session could not be verified. You can still sign in below.')
        }
      })
    return () => controller.abort()
  }, [])

  const loadStudentDashboard = useCallback(async (signal?: AbortSignal) => {
    try {
      setStudentData(await api.student.dashboard(signal))
      setStudentError('')
    } catch (error) {
      if (!signal?.aborted) {
        setStudentError(error instanceof Error ? error.message : 'Your learning dashboard could not be loaded.')
      }
    }
  }, [])

  useEffect(() => {
    if (user?.role !== 'student') return
    const controller = new AbortController()
    async function loadInitialDashboard() {
      try {
        setStudentData(await api.student.dashboard(controller.signal))
        setStudentError('')
      } catch (error) {
        if (!controller.signal.aborted) {
          setStudentError(error instanceof Error ? error.message : 'Your learning dashboard could not be loaded.')
        }
      }
    }
    void loadInitialDashboard()
    return () => controller.abort()
  }, [user])

  const login = async (email: string, password: string, selectedRole: UserRole) => {
    setLoginBusy(true)
    setAuthError('')
    try {
      const authenticatedUser = await api.auth.login(email, password)
      if (authenticatedUser.role !== selectedRole) {
        await api.auth.logout()
        const actualRole = authenticatedUser.role === 'admin' ? 'admin' : authenticatedUser.role
        setAuthError(`This account belongs to the ${actualRole} workspace. Select that role and sign in again.`)
        return
      }
      acceptUser(authenticatedUser)
    } catch (error) {
      setAuthError(loginError(error))
    } finally {
      setLoginBusy(false)
    }
  }

  const loadDemo = async (selectedRole: UserRole) => {
    setLoginBusy(true)
    setAuthError('')
    const email = `${selectedRole}@quantumlearn.demo`
    try {
      let authenticatedUser: AuthUser
      try {
        authenticatedUser = await api.auth.login(email, 'quantumlearn-demo')
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 401) throw error
        await api.admin.bootstrapDemo()
        authenticatedUser = await api.auth.login(email, 'quantumlearn-demo')
      }
      acceptUser(authenticatedUser)
    } catch (error) {
      if (error instanceof ApiError && (error.status === 403 || error.status === 404)) {
        setAuthError('Demo setup is not enabled in this environment. Sign in with your account.')
      } else {
        setAuthError(error instanceof Error ? error.message : 'The demo workspace could not be prepared.')
      }
    } finally {
      setLoginBusy(false)
    }
  }

  const logout = async () => {
    taskRequestId.current += 1
    try {
      await api.auth.logout()
    } finally {
      setUser(null)
      setStudentData(null)
      setActiveTask(null)
      setPendingTask(null)
      setTaskOpenError('')
      setSessionState('anonymous')
      setAuthError('')
    }
  }

  const refreshAssessorAccess = useCallback(async (): Promise<boolean> => {
    const refreshedUser = await api.auth.me()
    const active = hasActiveAssessorAssignment(refreshedUser)
    setUser(refreshedUser)
    if (!active) {
      setActiveScreen((current) => (current === 'assessor-setup' || current === 'assessor-review')
        ? defaultScreen(refreshedUser.role)
        : current)
    }
    return active
  }, [])

  const leaveAssessorWorkspace = useCallback(() => {
    setActiveScreen(defaultScreen('educator'))
  }, [])

  const openStudentTask = async (task: LearningTask) => {
    const requestId = taskRequestId.current + 1
    taskRequestId.current = requestId
    setPendingTask(task)
    setTaskOpenError('')
    setActiveTask(null)
    try {
      const openedTask = await api.student.task(task.id)
      if (taskRequestId.current !== requestId) return
      setActiveTask(openedTask)
      setPendingTask(null)
    } catch (error) {
      if (taskRequestId.current !== requestId) return
      setTaskOpenError(
        error instanceof Error
          ? error.message
          : 'This activity could not be opened. Please try again.',
      )
    }
  }

  const closeStudentTask = () => {
    taskRequestId.current += 1
    setActiveTask(null)
    setPendingTask(null)
    setTaskOpenError('')
  }

  const markNotificationRead = async (notification: LearningNotification) => {
    if (notification.is_read) return
    try {
      await api.student.markNotificationRead(notification.id)
      setStudentData((current) => current ? {
        ...current,
        notifications: current.notifications.map((item) =>
          item.id === notification.id ? { ...item, is_read: true } : item),
      } : current)
    } catch (error) {
      setStudentError(error instanceof Error ? error.message : 'The reminder could not be updated.')
    }
  }

  if (sessionState === 'checking') {
    return (
      <main className="standalone-state">
        <ScreenState kind="loading" title="Opening QuantumLearn" message="Checking your secure learning session." />
      </main>
    )
  }

  if (sessionState === 'anonymous' || !user) {
    return <LoginScreen onLogin={login} onLoadDemo={loadDemo} busy={loginBusy} error={authError} />
  }

  let content
  if (user.role === 'student') {
    if (studentError) {
      content = (
        <div className="screen">
          <ScreenState
            kind="error"
            title="Learning dashboard unavailable"
            message={studentError}
            action={<button className="button button--secondary" onClick={() => void loadStudentDashboard()}>Try again</button>}
          />
        </div>
      )
    } else if (!studentData) {
      content = <div className="screen"><ScreenState kind="loading" title="Preparing your pathway" message="Loading activities, progress and recommendations." /></div>
    } else {
      content = (
        <StudentDashboard
          data={studentData}
          onOpenTask={(task) => void openStudentTask(task)}
          onReadNotification={markNotificationRead}
        />
      )
    }
  } else if (user.role === 'educator') {
    if (activeScreen === 'assessor-setup' && hasActiveAssessorAssignment(user)) {
      content = (
        <AssessorSetup
          assignments={user.scoped_assignments}
          onCheckAccess={refreshAssessorAccess}
          onAccessRevoked={leaveAssessorWorkspace}
        />
      )
    } else if (activeScreen === 'assessor-review' && hasActiveAssessorAssignment(user)) {
      content = (
        <AssessorReviewQueue
          assignments={user.scoped_assignments}
          onCheckAccess={refreshAssessorAccess}
          onAccessRevoked={leaveAssessorWorkspace}
        />
      )
    } else if (activeScreen === 'course-editor') content = <CourseEditor />
    else if (activeScreen === 'students') content = <StudentsView />
    else if (activeScreen === 'analytics') content = <AnalyticsView />
    else {
      content = (
        <EducatorDashboard
          onCreateCourse={() => setActiveScreen('course-editor')}
          onViewStudents={() => setActiveScreen('students')}
        />
      )
    }
  } else {
    const section = activeScreen === 'admin-users'
      ? 'users'
      : activeScreen === 'admin-courses'
        ? 'courses'
        : activeScreen === 'admin-settings'
          ? 'settings'
          : 'overview'
    content = <AdminWorkspace section={section} />
  }

  return (
    <AppShell
      user={user}
      hasAssessorAccess={hasActiveAssessorAssignment(user)}
      activeScreen={activeScreen}
      onNavigate={setActiveScreen}
      onLogout={logout}
    >
      {content}
      {activeTask && (
        <TaskView
          key={activeTask.id}
          task={activeTask}
          onClose={closeStudentTask}
          onSubmitted={() => loadStudentDashboard()}
        />
      )}
      {pendingTask && (
        <div className="task-overlay" role="dialog" aria-modal="true" aria-label="Open learning activity">
          <article className="task-workspace">
            <ScreenState
              kind={taskOpenError ? 'error' : 'loading'}
              title={taskOpenError ? 'Activity unavailable' : `Opening ${pendingTask.title}`}
              message={taskOpenError || 'Loading the latest task, saved work and feedback.'}
              action={taskOpenError ? (
                <div className="page-actions">
                  <button className="button button--primary" onClick={() => void openStudentTask(pendingTask)}>
                    Try again
                  </button>
                  <button className="button button--ghost" onClick={closeStudentTask}>Close</button>
                </div>
              ) : undefined}
            />
          </article>
        </div>
      )}
    </AppShell>
  )
}

export default App
