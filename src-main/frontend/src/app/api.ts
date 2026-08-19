import type {
  AdminUser,
  AuthUser,
  CourseModule,
  CourseSummary,
  EducatorDashboardData,
  EducatorStudent,
  GateOperation,
  AssessmentConditions,
  GeneratedTaskPreview,
  LearningOutcome,
  LearningState,
  LearningTask,
  SimulationResult,
  StudentDashboardData,
  SystemSettings,
  TaskDraft,
  TaskSubmission,
  TaskType,
  UserRole,
} from './types'
import type { ApiSchemas } from '../api/generated'

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api/v1').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

type JsonBody = object

export function csrfToken(): string | null {
  if (typeof document === 'undefined') return null
  const entry = document.cookie
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith('ql_csrf='))
  if (!entry) return null
  try {
    return decodeURIComponent(entry.slice('ql_csrf='.length))
  } catch {
    return null
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (!(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const method = (init.method ?? 'GET').toUpperCase()
  const csrf = !['GET', 'HEAD'].includes(method) ? csrfToken() : null
  if (csrf) headers.set('X-CSRF-Token', csrf)

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: 'include',
    headers,
  })

  if (!response.ok) {
    let detail = 'The request could not be completed.'
    try {
      const payload = (await response.json()) as { detail?: string | Array<{ msg?: string }> }
      if (typeof payload.detail === 'string') detail = payload.detail
      if (Array.isArray(payload.detail)) {
        detail = payload.detail.map((item) => item.msg).filter(Boolean).join(' ') || detail
      }
    } catch {
      // Reduce non-JSON failures to a safe message without exposing server internals.
    }
    throw new ApiError(detail, response.status)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

function json(method: string, body?: JsonBody): RequestInit {
  return {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  }
}

interface RawTask {
  id: string
  title: string
  prompt: string
  instructions: string
  task_type: TaskType
  difficulty: string
  points: number
  position: number
  starter_code?: string | null
  due_at?: string | null
  course_id: string
  module_id: string
  module_title?: string
  learning_outcome_id: string
  source_references?: string[]
  prerequisite_task_ids?: string[]
  choices?: Array<{ id: string; text: string }>
  access_status?: 'locked' | 'available' | 'in_progress' | 'completed'
  attempt_count?: number
  latest_score?: number | null
  assessment?: AssessmentConditions | null
}

interface RawStudentDashboard {
  student: { id: string; display_name: string }
  summary: {
    completed_tasks: number
    total_tasks: number
    completion_percentage: number
    average_score: number
    points: number
    level: number
    next_level_points: number
  }
  tasks: RawTask[]
  recommendations: Array<{ task_id: string; title: string; reason: string }>
  reminders: Array<{
    id: string
    title: string
    message: string
    is_read: boolean
    created_at: string
  }>
  achievements: Array<{
    code: string
    name: string
    description: string
    icon: string
    earned_at: string | null
  }>
}

interface RawCourse {
  id: string
  code?: string
  title: string
  description: string
  state: 'draft' | 'published' | 'archived'
  enrollment_open: boolean
  module_count?: number
  student_count?: number
  enrolled_students?: number
  progress_percentage?: number
}

interface RawEducatorDashboard {
  courses: RawCourse[]
  total_students: number
  at_risk_students: number
  completion_percentage: number
  weekly_engagement: EducatorDashboardData['engagement']
  task_type_performance: NonNullable<EducatorDashboardData['task_type_performance']>
  concept_mastery: NonNullable<EducatorDashboardData['concept_mastery']>
  leaderboard: NonNullable<EducatorDashboardData['leaderboard']>
  recent_activity: Array<{
    student_name: string
    task_title: string
    score: number
    occurred_at: string
  }>
}

interface RawEducatorStudent {
  student_id: string
  display_name: string
  email: string
  course_id: string
  course_title: string
  completed_tasks: number
  total_tasks: number
  completion_percentage: number
  average_score: number
  last_active: string | null
  at_risk: boolean
  overdue_tasks: number
}

interface RawSubmission {
  id?: string
  score?: number | null
  feedback?: string | null
  feedback_reference?: string | null
  status?: string
  answer?: string
  code?: string | null
  circuit?: TaskDraft['circuit']
  attempt_number?: number
  points_awarded?: number
  submitted_at?: string
}

interface RawDraft {
  id: string
  task_id: string
  answer: string
  code: string | null
  circuit: TaskDraft['circuit']
  updated_at: string
}

interface RawMaterial {
  id: string
  original_filename: string | null
  source_url: string | null
  indexing_status: string
}

interface RawSettings {
  llm_provider?: string
  llm_model?: string
  at_risk_threshold: number
  reminders_enabled?: boolean
  passing_score?: number
  points_per_level?: number
}

interface RawAuthUser {
  id: number | string
  email: string
  full_name: string
  role: 'student' | 'educator' | 'administrator'
  scoped_assignments?: AuthUser['scoped_assignments']
}

interface RawAdminUser extends Omit<AdminUser, 'role'> {
  role: 'student' | 'educator' | 'administrator'
}

function normalizeRole(role: RawAuthUser['role']): UserRole {
  return role === 'administrator' ? 'admin' : role
}

function normalizeAuthUser(user: RawAuthUser): AuthUser {
  return { ...user, role: normalizeRole(user.role), scoped_assignments: user.scoped_assignments ?? [] }
}

function normalizeAdminUser(user: RawAdminUser): AdminUser {
  return { ...user, role: normalizeRole(user.role) }
}

function learningState(status: RawTask['access_status']): LearningState {
  if (status === 'available') return 'not_started'
  return status ?? 'not_started'
}

function normalizeTask(task: RawTask): LearningTask {
  return {
    id: task.id,
    title: task.title,
    module: task.module_title ?? 'Course module',
    description: task.prompt,
    instructions: task.instructions,
    task_type: task.task_type,
    difficulty: task.difficulty,
    points: task.points,
    position: task.position,
    status: learningState(task.access_status),
    score: task.latest_score ?? null,
    starter_code: task.starter_code,
    due_at: task.due_at,
    options: task.choices ?? [],
    source_references: task.source_references ?? [],
    prerequisite_task_ids: task.prerequisite_task_ids ?? [],
    attempt_count: task.attempt_count ?? 0,
    assessment: task.assessment ?? null,
  }
}

function normalizeStudentDashboard(raw: RawStudentDashboard): StudentDashboardData {
  const tasks = raw.tasks.map(normalizeTask)
  const moduleTasks = new Map<string, RawTask[]>()
  raw.tasks.forEach((task) => {
    moduleTasks.set(task.module_id, [...(moduleTasks.get(task.module_id) ?? []), task])
  })
  const moduleProgress: Record<string, number> = {}
  Array.from(moduleTasks.values()).forEach((items, index) => {
    const complete = items.filter((task) => task.access_status === 'completed').length
    const label = items[0]?.module_title ?? `Module ${index + 1}`
    moduleProgress[label] = Math.round(complete / items.length * 100)
  })
  const pointsPerLevel = Math.max(1, (raw.summary.points + raw.summary.next_level_points) / raw.summary.level)
  const pointsWithinLevel = Math.max(0, pointsPerLevel - raw.summary.next_level_points)

  return {
    progress: {
      student_id: raw.student.id,
      display_name: raw.student.display_name,
      completed_tasks: raw.summary.completed_tasks,
      total_tasks: raw.summary.total_tasks,
      completion_percent: raw.summary.completion_percentage,
      average_score: raw.summary.average_score,
      points: raw.summary.points,
      points_to_next_level: raw.summary.next_level_points,
      streak_days: 0,
      level: raw.summary.level,
      level_progress: Math.min(100, Math.round(pointsWithinLevel / pointsPerLevel * 100)),
      achievements: raw.achievements,
      module_progress: moduleProgress,
    },
    tasks,
    recommendations: raw.recommendations.map((item, index) => ({
      ...item,
      priority: index === 0 ? 'high' : index === 1 ? 'medium' : 'low',
    })),
    notifications: raw.reminders.map((item) => ({ ...item, kind: 'reminder' })),
  }
}

function courseCode(course: Pick<RawCourse, 'title' | 'id' | 'code'>): string {
  if ('code' in course && course.code) return course.code
  const initials = course.title.split(/\s+/).map((part) => part[0]).join('').slice(0, 5).toUpperCase()
  return initials || course.id.slice(0, 6).toUpperCase()
}

function normalizeCourse(course: RawCourse): CourseSummary {
  return {
    id: course.id,
    code: courseCode(course),
    title: course.title,
    description: course.description,
    status: course.state,
    enrollment_open: course.enrollment_open ?? false,
    enrolled_students: course.student_count ?? course.enrolled_students ?? 0,
    completion_percent: course.progress_percentage ?? 0,
    module_count: course.module_count ?? 0,
  }
}

function normalizeStudent(student: RawEducatorStudent): EducatorStudent {
  return {
    student_id: student.student_id,
    display_name: student.display_name,
    email: student.email,
    course_id: student.course_id,
    course_title: student.course_title,
    completed_tasks: student.completed_tasks,
    total_tasks: student.total_tasks,
    completion_percent: student.completion_percentage,
    average_score: student.average_score,
    last_active: student.last_active,
    risk: student.completed_tasks === 0 ? 'not_started' : student.at_risk ? 'at_risk' : 'on_track',
    overdue_tasks: student.overdue_tasks,
  }
}

function normalizeSubmission(raw: RawSubmission): TaskSubmission {
  return {
    id: raw.id,
    score: raw.score ?? null,
    feedback: raw.feedback ?? null,
    feedback_reference: raw.feedback_reference ?? null,
    status: (raw.status as LearningState | undefined) ?? 'draft',
    answer: raw.answer,
    code: raw.code,
    circuit: raw.circuit,
    attempt_number: raw.attempt_number,
    points_awarded: raw.points_awarded,
    submitted_at: raw.submitted_at,
  }
}

function normalizeMaterial(raw: RawMaterial): { id: string; filename: string; status: string } {
  return {
    id: raw.id,
    filename: raw.original_filename ?? raw.source_url ?? 'Linked learning source',
    status: raw.indexing_status,
  }
}

function normalizeSettings(raw: RawSettings): SystemSettings {
  return {
    llm_provider: raw.llm_provider ?? '',
    llm_model: raw.llm_model ?? '',
    at_risk_threshold: raw.at_risk_threshold,
    passing_score: raw.passing_score ?? 70,
    points_per_level: raw.points_per_level ?? 500,
    reminders_enabled: raw.reminders_enabled ?? true,
  }
}

export const api = {
  auth: {
    me: async (signal?: AbortSignal) =>
      normalizeAuthUser(await request<RawAuthUser>('/auth/me', { signal })),
    login: async (email: string, password: string) =>
      normalizeAuthUser(await request<RawAuthUser>('/auth/login', json('POST', { email, password }))),
    logout: () => request<void>('/auth/logout', { method: 'POST' }),
  },
  assessment: {
    createDefinition: (
      courseId: string,
      outcomeId: string,
      payload: ApiSchemas['AssessmentDefinitionDraftCreate'],
    ) => request<ApiSchemas['AssessmentDefinitionRead']>(
      `/assessment/courses/${encodeURIComponent(courseId)}/outcomes/${encodeURIComponent(outcomeId)}/definitions`,
      json('POST', payload),
    ),
    updateDefinition: (
      courseId: string,
      outcomeId: string,
      assessmentDefinitionId: string,
      payload: ApiSchemas['AssessmentDefinitionDraftUpdate'],
    ) => request<ApiSchemas['AssessmentDefinitionRead']>(
      `/assessment/courses/${encodeURIComponent(courseId)}/outcomes/${encodeURIComponent(outcomeId)}/definitions/${encodeURIComponent(assessmentDefinitionId)}`,
      json('PUT', payload),
    ),
    history: (courseId: string, assessmentDefinitionId: string) =>
      request<ApiSchemas['AssessmentDefinitionRead'][]>(
        `/assessment/courses/${encodeURIComponent(courseId)}/definitions/${encodeURIComponent(assessmentDefinitionId)}/history`,
      ),
    publish: (
      courseId: string,
      assessmentDefinitionId: string,
      payload: ApiSchemas['AssessmentDefinitionApproval'],
    ) => request<ApiSchemas['AssessmentDefinitionRead']>(
      `/assessment/courses/${encodeURIComponent(courseId)}/definitions/${encodeURIComponent(assessmentDefinitionId)}/publish`,
      json('POST', payload),
    ),
    reviewQueue: (
      courseId: string,
      filters: {
        outcome_id?: string
        result?: ApiSchemas['AssessmentResult']
        result_state?: ApiSchemas['ResultState']
        review_flag?: string
        minimum_age_hours?: number
      } = {},
    ) => {
      const query = new URLSearchParams()
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== '') query.set(key, String(value))
      })
      const suffix = query.size ? `?${query.toString()}` : ''
      return request<ApiSchemas['AssessmentReviewDetailRead'][]>(
        `/assessment/courses/${encodeURIComponent(courseId)}/review-queue${suffix}`,
      )
    },
    reviewDetail: (decisionId: string) => request<ApiSchemas['AssessmentReviewDetailRead']>(
      `/assessment/decisions/${encodeURIComponent(decisionId)}/review`,
    ),
    reviewAction: (decisionId: string, payload: ApiSchemas['AssessmentReviewActionCreate']) =>
      request<ApiSchemas['AssessmentReviewActionRead']>(
        `/assessment/decisions/${encodeURIComponent(decisionId)}/review`,
        json('POST', payload),
      ),
  },
  student: {
    dashboard: async (signal?: AbortSignal) =>
      normalizeStudentDashboard(await request<RawStudentDashboard>('/students/me/dashboard', { signal })),
    task: async (taskId: string, signal?: AbortSignal) =>
      normalizeTask(await request<RawTask>(`/students/me/tasks/${encodeURIComponent(taskId)}`, { signal })),
    draft: (taskId: string, signal?: AbortSignal) =>
      request<RawDraft | null>(
        `/students/me/tasks/${encodeURIComponent(taskId)}/draft`,
        { signal },
      ),
    saveDraft: (
      taskId: string,
      payload: {
        answer: string
        code?: string
        circuit?: { qubits: number; operations: GateOperation[] }
      },
    ) => request<RawDraft>(
      `/students/me/tasks/${encodeURIComponent(taskId)}/draft`,
      json('PUT', payload),
    ),
    submit: async (
      taskId: string,
      payload: {
        answer: string
        code?: string
        circuit?: { qubits: number; operations: GateOperation[] }
        idempotency_key?: string
      },
    ) => normalizeSubmission(await request<RawSubmission>(
      `/students/me/tasks/${encodeURIComponent(taskId)}/submissions`,
      json('POST', payload),
    )),
    attempts: async (taskId: string, signal?: AbortSignal) =>
      (await request<RawSubmission[]>(
        `/students/me/tasks/${encodeURIComponent(taskId)}/submissions`,
        { signal },
      )).map(normalizeSubmission),
    simulate: (operations: GateOperation[]) =>
      request<SimulationResult>(
        '/students/me/simulate',
        json('POST', { qubits: 2, operations, shots: 1024 }),
      ),
    markNotificationRead: (notificationId: string) =>
      request<void>(
        `/students/me/reminders/${encodeURIComponent(notificationId)}/read`,
        { method: 'PATCH' },
      ),
  },
  educator: {
    dashboard: async (signal?: AbortSignal): Promise<EducatorDashboardData> => {
      const raw = await request<RawEducatorDashboard>('/educator/dashboard', { signal })
      return {
        active_students: raw.total_students,
        average_completion: raw.completion_percentage,
        submissions_this_week: raw.weekly_engagement.reduce((total, item) => total + item.submissions, 0),
        at_risk_count: raw.at_risk_students,
        engagement: raw.weekly_engagement,
        at_risk_students: [],
        recent_activity: raw.recent_activity.map((item, index) => ({
          id: `${item.student_name}-${item.occurred_at}-${index}`,
          actor: item.student_name,
          action: `${item.task_title} · ${item.score}%`,
          occurred_at: item.occurred_at,
        })),
        courses: raw.courses.map(normalizeCourse),
        task_type_performance: raw.task_type_performance,
        concept_mastery: raw.concept_mastery,
        leaderboard: raw.leaderboard,
      }
    },
    students: async (signal?: AbortSignal) =>
      (await request<RawEducatorStudent[]>('/educator/students', { signal })).map(normalizeStudent),
    notifyStudents: async (studentIds: string[], message: string) => {
      const response = await request<unknown[]>('/educator/students/notifications', json('POST', {
        student_ids: studentIds,
        message,
      }))
      return { sent: Array.isArray(response) ? response.length : studentIds.length }
    },
  },
  courses: {
    list: async (signal?: AbortSignal) =>
      (await request<RawCourse[]>('/courses', { signal })).map(normalizeCourse),
    create: async (payload: {
      code: string
      title: string
      description: string
      enrollment_open: boolean
    }) =>
      normalizeCourse(await request<RawCourse>('/courses', json('POST', {
        code: payload.code,
        title: payload.title,
        description: payload.description,
        enrollment_open: payload.enrollment_open,
      }))),
    update: async (
      courseId: string,
      payload: Partial<
        Pick<CourseSummary, 'code' | 'title' | 'description' | 'status' | 'enrollment_open'>
      >,
    ) => normalizeCourse(await request<RawCourse>(`/courses/${encodeURIComponent(courseId)}`, json('PATCH', {
      code: payload.code,
      title: payload.title,
      description: payload.description,
      enrollment_open: payload.enrollment_open,
    }))),
    publish: async (courseId: string) =>
      normalizeCourse(await request<RawCourse>(`/courses/${encodeURIComponent(courseId)}/publish`, { method: 'POST' })),
    archive: async (courseId: string) =>
      normalizeCourse(await request<RawCourse>(`/courses/${encodeURIComponent(courseId)}/archive`, { method: 'POST' })),
    createModule: (
      courseId: string,
      payload: { title: string; description: string; position?: number },
    ) =>
      request<CourseModule>(
        `/courses/${encodeURIComponent(courseId)}/modules`,
        json('POST', { ...payload, position: payload.position ?? 1 }),
      ),
    listModules: (courseId: string) =>
      request<CourseModule[]>(`/courses/${encodeURIComponent(courseId)}/modules`),
    updateModule: (
      moduleId: string,
      payload: { title: string; description: string; position: number },
    ) => request<CourseModule>(
      `/modules/${encodeURIComponent(moduleId)}`,
      json('PATCH', payload),
    ),
    deleteModule: (moduleId: string) =>
      request<void>(`/modules/${encodeURIComponent(moduleId)}`, { method: 'DELETE' }),
    createOutcome: (
      moduleId: string,
      payload: {
        title: string
        statement: string
        kind: 'weekly' | 'topic'
        week_number: number | null
        position: number
      },
    ) =>
      request<LearningOutcome>(
        `/modules/${encodeURIComponent(moduleId)}/outcomes`,
        json('POST', payload),
      ),
    listOutcomes: (moduleId: string) =>
      request<LearningOutcome[]>(`/modules/${encodeURIComponent(moduleId)}/outcomes`),
    updateOutcome: (
      outcomeId: string,
      payload: {
        title: string
        statement: string
        kind: 'weekly' | 'topic'
        week_number: number | null
        position: number
      },
    ) => request<LearningOutcome>(
      `/outcomes/${encodeURIComponent(outcomeId)}`,
      json('PATCH', payload),
    ),
    deleteOutcome: (outcomeId: string) =>
      request<void>(`/outcomes/${encodeURIComponent(outcomeId)}`, { method: 'DELETE' }),
    uploadMaterial: async (courseId: string, file: File) => {
      const form = new FormData()
      form.append('file', file)
      return normalizeMaterial(await request<RawMaterial>(
        `/courses/${encodeURIComponent(courseId)}/materials/upload`,
        { method: 'POST', body: form },
      ))
    },
    linkMaterial: async (courseId: string, url: string) => {
      const registered = await request<RawMaterial>(
        `/courses/${encodeURIComponent(courseId)}/materials/links`,
        json('POST', { source_url: url }),
      )
      const processed = await request<{ material: RawMaterial }>(
        `/courses/${encodeURIComponent(courseId)}/materials/${encodeURIComponent(registered.id)}/process`,
        { method: 'POST' },
      )
      return normalizeMaterial(processed.material)
    },
    listMaterials: async (courseId: string) =>
      (await request<RawMaterial[]>(`/courses/${encodeURIComponent(courseId)}/materials/list`)).map(normalizeMaterial),
    generateTasks: async (
      courseId: string,
      payload: { module_id: string; learning_outcome_ids: string[]; count: number },
    ): Promise<GeneratedTaskPreview[]> => {
      const tasks = await request<RawTask[]>(
        `/courses/${encodeURIComponent(courseId)}/generate-tasks`,
        json('POST', {
          learning_outcome_id: payload.learning_outcome_ids[0],
          task_count: Math.max(3, payload.count),
          task_types: ['multiple_choice', 'code_explanation', 'quantum_circuit'],
        }),
      )
      return tasks.map((task) => ({
        id: task.id,
        title: task.title,
        task_type: task.task_type,
        difficulty: task.difficulty,
        prompt: task.prompt,
        source_references: task.source_references,
        points: task.points,
      }))
    },
  },
  admin: {
    bootstrapDemo: () => request<unknown>('/admin/bootstrap-demo', { method: 'POST' }),
    users: async (signal?: AbortSignal) =>
      (await request<RawAdminUser[]>('/admin/users', { signal })).map(normalizeAdminUser),
    createUser: async (payload: { full_name: string; email: string; role: UserRole; password: string }) =>
      normalizeAdminUser(await request<RawAdminUser>('/admin/users', json('POST', {
        ...payload,
        role: payload.role === 'admin' ? 'administrator' : payload.role,
      }))),
    updateUser: async (userId: AdminUser['id'], payload: { role: UserRole }) =>
      normalizeAdminUser(await request<RawAdminUser>(
        `/admin/users/${encodeURIComponent(String(userId))}`,
        json('PATCH', {
          role: payload.role === 'admin' ? 'administrator' : payload.role,
        }),
      )),
    setUserActive: async (userId: AdminUser['id'], active: boolean) =>
      normalizeAdminUser(await request<RawAdminUser>(
        `/admin/users/${encodeURIComponent(String(userId))}/${active ? 'reactivate' : 'deactivate'}`,
        { method: 'POST' },
      )),
    settings: async (signal?: AbortSignal) =>
      normalizeSettings(await request<RawSettings>('/admin/settings', { signal })),
    updateSettings: async (payload: SystemSettings) =>
      normalizeSettings(await request<RawSettings>('/admin/settings', json('PUT', payload))),
    archiveCourse: async (courseId: string) =>
      normalizeCourse(await request<RawCourse>(
        `/admin/courses/${encodeURIComponent(courseId)}/archive`,
        { method: 'POST' },
      )),
  },
}
