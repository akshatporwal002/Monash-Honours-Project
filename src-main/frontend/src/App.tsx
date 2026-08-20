import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom'

import { ApiError, api } from './app/api'
import type { AuthUser, LearningNotification, StudentDashboardData, UserRole } from './app/types'
import { AdminWorkspace } from './components/AdminWorkspace'
import { AnalyticsView } from './components/AnalyticsView'
import { AppShell } from './components/AppShell'
import { homePath } from './components/paths'
import { CourseEditor } from './components/CourseEditor'
import { EducatorDashboard } from './components/EducatorDashboard'
import { LoginScreen } from './components/LoginScreen'
import { NotFound } from './components/NotFound'
import { ScreenState } from './components/ScreenPrimitives'
import { Button } from './components/ui'
import { StudentDashboard } from './components/StudentDashboard'
import { StudentsView } from './components/StudentsView'
import { TaskPage } from './components/TaskPage'
import { AssessorSetup } from './features/assessment/AssessorSetup'
import { AssessorReviewQueue } from './features/assessment/AssessorReviewQueue'

type SessionState = 'checking' | 'anonymous' | 'authenticated'

function hasActiveAssessorAssignment(user: AuthUser, courseId?: string): boolean {
  return user.role === 'educator' && user.scoped_assignments.some((assignment) => (
    assignment.role === 'assessor' && (!courseId || assignment.course_id === courseId)
  ))
}

function loginError(error: unknown): string {
  if (error instanceof ApiError && error.status === 401) return 'Email or password is incorrect.'
  if (error instanceof ApiError) return error.message
  return 'LearnLens could not reach the sign-in service. Please try again.'
}

function AppRoutes() {
  const navigate = useNavigate()
  const [sessionState, setSessionState] = useState<SessionState>('checking')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loginBusy, setLoginBusy] = useState(false)
  const [authError, setAuthError] = useState('')
  const [studentData, setStudentData] = useState<StudentDashboardData | null>(null)
  const [studentError, setStudentError] = useState('')

  const acceptUser = (authenticatedUser: AuthUser) => {
    setUser(authenticatedUser)
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
    try {
      await api.auth.logout()
    } finally {
      setUser(null)
      setStudentData(null)
      setSessionState('anonymous')
      setAuthError('')
      navigate('/login', { replace: true })
    }
  }

  const refreshAssessorAccess = useCallback(async (courseId: string): Promise<boolean> => {
    const refreshedUser = await api.auth.me()
    const active = hasActiveAssessorAssignment(refreshedUser, courseId)
    setUser(refreshedUser)
    return active
  }, [])

  const leaveAssessorWorkspace = useCallback(() => {
    navigate('/educator')
  }, [navigate])

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
      <main>
        <ScreenState fullscreen kind="loading" title="Opening LearnLens" message="Checking your secure learning session." />
      </main>
    )
  }

  if (sessionState === 'anonymous' || !user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginScreen onLogin={login} onLoadDemo={loadDemo} busy={loginBusy} error={authError} />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  // A valid path outside the user's authority renders the same not-found page
  // as an unknown path, so URLs never reveal what exists (D2 §13.3 posture).
  const guard = (allowed: boolean, element: ReactNode) =>
    allowed ? element : <NotFound homeTo={homePath(user.role)} />

  const assessorAccess = hasActiveAssessorAssignment(user)

  const studentHome = studentError ? (
    <ScreenState
      kind="error"
      title="Learning dashboard unavailable"
      message={studentError}
      action={<Button variant="secondary" onClick={() => void loadStudentDashboard()}>Try again</Button>}
    />
  ) : !studentData ? (
    <ScreenState kind="loading" title="Preparing your pathway" message="Loading activities, progress and recommendations." />
  ) : (
    <StudentDashboard
      data={studentData}
      onOpenTask={(task) => navigate(`/student/tasks/${task.id}`)}
      onReadNotification={markNotificationRead}
    />
  )

  return (
    <Routes>
      <Route path="/login" element={<Navigate to={homePath(user.role)} replace />} />
      <Route path="/" element={<Navigate to={homePath(user.role)} replace />} />
      <Route element={<AppShell user={user} hasAssessorAccess={assessorAccess} onLogout={logout} />}>
        <Route path="/student" element={guard(user.role === 'student', studentHome)} />
        <Route
          path="/student/tasks/:taskId"
          element={guard(user.role === 'student', <TaskPage onSubmitted={loadStudentDashboard} />)}
        />
        <Route
          path="/educator"
          element={guard(
            user.role === 'educator',
            <EducatorDashboard
              onCreateCourse={() => navigate('/educator/courses')}
              onViewStudents={() => navigate('/educator/students')}
            />,
          )}
        />
        <Route path="/educator/courses" element={guard(user.role === 'educator', <CourseEditor />)} />
        <Route path="/educator/students" element={guard(user.role === 'educator', <StudentsView />)} />
        <Route path="/educator/analytics" element={guard(user.role === 'educator', <AnalyticsView />)} />
        <Route
          path="/assessor/setup"
          element={guard(
            assessorAccess,
            <AssessorSetup
              assignments={user.scoped_assignments}
              onCheckAccess={refreshAssessorAccess}
              onAccessRevoked={leaveAssessorWorkspace}
            />,
          )}
        />
        <Route
          path="/assessor/review"
          element={guard(
            assessorAccess,
            <AssessorReviewQueue
              assignments={user.scoped_assignments}
              onCheckAccess={refreshAssessorAccess}
              onAccessRevoked={leaveAssessorWorkspace}
            />,
          )}
        />
        <Route path="/admin" element={guard(user.role === 'admin', <AdminWorkspace section="overview" />)} />
        <Route path="/admin/users" element={guard(user.role === 'admin', <AdminWorkspace section="users" />)} />
        <Route path="/admin/courses" element={guard(user.role === 'admin', <AdminWorkspace section="courses" />)} />
        <Route path="/admin/settings" element={guard(user.role === 'admin', <AdminWorkspace section="settings" />)} />
        <Route path="*" element={<NotFound homeTo={homePath(user.role)} />} />
      </Route>
    </Routes>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}

export default App
