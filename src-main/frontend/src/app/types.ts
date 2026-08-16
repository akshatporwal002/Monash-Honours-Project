export type UserRole = 'student' | 'educator' | 'admin'

export interface AuthUser {
  id: number | string
  email: string
  full_name: string
  role: UserRole
  scoped_assignments: ScopedRoleAssignment[]
}

export interface ScopedRoleAssignment {
  id: string
  course_id: string
  role: 'assessor' | 'research'
  version: number
  valid_from: string
  valid_until: string | null
}

export type TaskType =
  | 'multiple_choice'
  | 'multiple_answer'
  | 'short_answer'
  | 'code_explanation'
  | 'code_completion'
  | 'quantum_circuit'
  | 'quiz'
  | 'code'
  | 'circuit'

export type LearningState = 'locked' | 'not_started' | 'draft' | 'in_progress' | 'submitted' | 'completed'

export interface LearningTask {
  id: string
  title: string
  module: string
  description: string
  instructions: string
  task_type: TaskType
  difficulty: string
  points: number
  position: number
  status: LearningState | null
  score: number | null
  starter_code?: string | null
  due_at?: string | null
  options?: Array<{ id: string; text: string }>
  correct_option?: number | null
  source_references?: string[]
  prerequisite_task_ids?: string[]
  attempt_count?: number
}

export interface Achievement {
  code: string
  name: string
  description: string
  icon: string
  earned_at: string | null
}

export interface StudentProgress {
  student_id: string
  display_name: string
  completed_tasks: number
  total_tasks: number
  completion_percent: number
  average_score: number
  points: number
  points_to_next_level?: number
  streak_days: number
  level: number
  level_progress: number
  achievements: Achievement[]
  module_progress: Record<string, number>
}

export interface Recommendation {
  task_id: string
  title: string
  reason: string
  priority: 'high' | 'medium' | 'low'
}

export interface LearningNotification {
  id: string
  kind: 'reminder' | 'achievement' | 'feedback'
  title: string
  message: string
  is_read: boolean
  created_at: string
}

export interface StudentDashboardData {
  progress: StudentProgress
  tasks: LearningTask[]
  recommendations: Recommendation[]
  notifications: LearningNotification[]
}

export interface TaskDraft {
  id: string
  task_id: string
  answer: string
  code: string | null
  circuit: {
    qubits: number
    operations: GateOperation[]
  } | null
  updated_at: string
}

export interface TaskSubmission {
  id?: string
  score: number
  feedback: string | null
  feedback_reference?: string | null
  status: LearningState
  answer?: string
  code?: string | null
  circuit?: {
    qubits: number
    operations: GateOperation[]
  } | null
  attempt_number?: number
  points_awarded?: number
  submitted_at?: string
}

export interface GateOperation {
  gate: 'h' | 'x' | 'cx'
  targets: number[]
}

export interface SimulationResult {
  counts: Record<string, number>
  circuit_text: string
  engine: string
}

export interface EngagementPoint {
  label: string
  active_students: number
  submissions: number
}

export interface ActivityItem {
  id: string
  actor: string
  action: string
  occurred_at: string
}

export interface CourseSummary {
  id: string
  code: string
  title: string
  description?: string
  status: 'draft' | 'published' | 'archived'
  enrollment_open: boolean
  enrolled_students?: number
  completion_percent?: number
  module_count?: number
}

export interface EducatorDashboardData {
  active_students: number
  average_completion: number
  submissions_this_week: number
  at_risk_count: number
  engagement: EngagementPoint[]
  at_risk_students: EducatorStudent[]
  recent_activity: ActivityItem[]
  courses: CourseSummary[]
  task_type_performance?: Array<{ label: string; score: number }>
  concept_mastery?: Array<{ label: string; score: number }>
  leaderboard?: Array<{
    student_id: string
    display_name: string
    points: number
    completed_tasks: number
  }>
}

export type StudentRisk = 'at_risk' | 'on_track' | 'not_started'

export interface EducatorStudent {
  student_id: string
  display_name: string
  email?: string
  course_id?: string
  course_title?: string
  completed_tasks: number
  total_tasks: number
  completion_percent: number
  average_score: number
  last_active: string | null
  risk?: StudentRisk
  overdue_tasks?: number
}

export interface CourseModule {
  id: string
  course_id: string
  title: string
  description?: string
  position: number
}

export interface LearningOutcome {
  id: string
  module_id: string
  title: string
  statement: string
  kind: 'weekly' | 'topic'
  week_number: number | null
  position: number
}

export interface GeneratedTaskPreview {
  id?: string
  title: string
  task_type: TaskType
  difficulty: string
  prompt: string
  learning_outcome?: string
  source_references?: string[]
  points?: number
}

export interface AdminUser {
  id: number | string
  full_name: string
  email: string
  role: UserRole
  is_active: boolean
  created_at?: string
}

export interface SystemSettings {
  llm_provider: string
  llm_model: string
  at_risk_threshold: number
  passing_score: number
  points_per_level: number
  reminders_enabled: boolean
}

export type AsyncState = 'idle' | 'loading' | 'success' | 'error'
