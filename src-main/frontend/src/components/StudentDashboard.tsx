import type { LearningNotification, LearningTask, StudentDashboardData } from '../app/types'
import { Icon, PageHeading, Panel, ProgressRing } from './ScreenPrimitives'

function taskState(task: LearningTask): 'locked' | 'in-progress' | 'completed' {
  if (task.status === 'completed') return 'completed'
  if (task.status === 'locked') return 'locked'
  return 'in-progress'
}

function taskKind(task: LearningTask): string {
  if (['multiple_choice', 'multiple_answer', 'quiz'].includes(task.task_type)) return 'Multiple choice'
  if (['code', 'code_explanation', 'code_completion'].includes(task.task_type)) return 'Qiskit activity'
  if (['circuit', 'quantum_circuit'].includes(task.task_type)) return 'Circuit builder'
  return 'Short answer'
}

export function StudentDashboard({
  data,
  onOpenTask,
  onReadNotification,
}: {
  data: StudentDashboardData
  onOpenTask: (task: LearningTask) => void
  onReadNotification: (notification: LearningNotification) => Promise<void>
}) {
  const { progress, tasks, recommendations, notifications } = data
  const firstName = progress.display_name.split(' ')[0]
  const nextRecommendation = recommendations[0]
  const nextTask = tasks.find((task) => task.id === nextRecommendation?.task_id)
  const earned = progress.achievements.filter((achievement) => achievement.earned_at)

  return (
    <div className="screen">
      <PageHeading
        eyebrow="Student dashboard"
        title={`Welcome back, ${firstName}`}
        description="Build momentum with one focused quantum concept at a time."
        actions={
          <div className="xp-card" aria-label={`${progress.points} experience points`}>
            <span><Icon name="spark" size={18} /> Level {progress.level}</span>
            <strong>{progress.points} XP</strong>
            <div className="meter"><i style={{ width: `${progress.level_progress}%` }} /></div>
            <small>{progress.points_to_next_level ?? 0} XP to your next level</small>
          </div>
        }
      />

      <section className="student-hero">
        <article className="continue-panel">
          <div>
            <p className="eyebrow">AI recommendation</p>
            <h2>{nextTask?.title ?? 'Your pathway is complete'}</h2>
            <p>{nextRecommendation?.reason ?? 'You have completed every available activity. Keep exploring your achievements.'}</p>
            {nextTask && (
              <button className="button button--light" onClick={() => onOpenTask(nextTask)}>
                Continue learning <Icon name="arrow" size={18} />
              </button>
            )}
          </div>
          <div className="hero-atom" aria-hidden="true"><i /><i /><i /><b /></div>
        </article>
        <article className="momentum-panel">
          <ProgressRing value={progress.completion_percent} />
          <div>
            <p className="eyebrow">Course momentum</p>
            <h2>{progress.completed_tasks} of {progress.total_tasks} activities</h2>
            <div className="compact-stats">
              <span><strong>{progress.average_score}%</strong> average</span>
              <span><strong>{progress.points_to_next_level ?? 0}</strong> XP to level up</span>
              <span><strong>{earned.length}</strong> achievements</span>
            </div>
          </div>
        </article>
      </section>

      <Panel
        eyebrow="Your pathway"
        title="Quantum foundations"
        className="pathway-panel"
        action={<span className="status-chip status-chip--cyan">{progress.completion_percent}% complete</span>}
      >
        {tasks.length === 0 ? (
          <div className="inline-empty"><Icon name="book" /><p>No activities are available yet. Your educator is preparing the pathway.</p></div>
        ) : (
          <ol className="module-path">
            {tasks.map((task, index) => {
              const state = taskState(task)
              return (
                <li key={task.id} className={`module-step module-step--${state}`}>
                  <span className="module-step__marker">
                    {state === 'completed' ? <Icon name="check" /> : state === 'locked' ? '—' : index + 1}
                  </span>
                  <div className="module-step__copy">
                    <div>
                      <span>{task.module}</span>
                      <span className={`status-chip status-chip--${state}`}>
                        {state === 'in-progress' ? 'In progress' : state}
                      </span>
                    </div>
                    <h3>{task.title}</h3>
                    <p>{taskKind(task)} · {task.difficulty} · {task.points} XP{task.attempt_count ? ` · ${task.attempt_count} attempt${task.attempt_count === 1 ? '' : 's'}` : ''}</p>
                  </div>
                  <button
                    className={state === 'locked' ? 'button button--ghost' : 'button button--secondary'}
                    disabled={state === 'locked'}
                    onClick={() => onOpenTask(task)}
                    aria-label={`${state === 'completed' ? 'Review' : 'Open'} ${task.title}`}
                  >
                    {state === 'locked' ? 'Locked' : state === 'completed' ? 'Review' : 'Open'}
                    {state !== 'locked' && <Icon name="arrow" size={16} />}
                  </button>
                </li>
              )
            })}
          </ol>
        )}
      </Panel>

      <div className="student-grid">
        <Panel eyebrow="Progress by module" title="Concept mastery">
          {Object.keys(progress.module_progress).length === 0 ? (
            <div className="inline-empty"><p>Complete an activity to see module mastery.</p></div>
          ) : (
            <div className="ring-grid">
              {Object.entries(progress.module_progress).slice(0, 4).map(([module, value]) => (
                <div key={module}>
                  <ProgressRing value={value} label="mastery" size="small" />
                  <strong>{module}</strong>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel eyebrow="Milestones" title="Achievements" action={<Icon name="trophy" />}>
          {progress.achievements.length === 0 ? (
            <div className="inline-empty"><Icon name="spark" /><p>Your first achievement is one activity away.</p></div>
          ) : (
            <div className="achievement-list">
              {progress.achievements.slice(0, 4).map((achievement) => (
                <article className={achievement.earned_at ? 'earned' : 'locked'} key={achievement.code}>
                  <span aria-hidden="true">{achievement.icon || '✦'}</span>
                  <div><strong>{achievement.name}</strong><p>{achievement.description}</p></div>
                </article>
              ))}
            </div>
          )}
        </Panel>

        <Panel eyebrow="Stay on track" title="Updates" action={<span className="status-chip">{notifications.filter((item) => !item.is_read).length} new</span>}>
          {notifications.length === 0 ? (
            <div className="inline-empty"><p>You are all caught up.</p></div>
          ) : (
            <div className="notification-list">
              {notifications.slice(0, 4).map((notification) => (
                <button
                  key={notification.id}
                  className={notification.is_read ? 'read' : ''}
                  onClick={() => void onReadNotification(notification)}
                >
                  <span className="notification-dot" />
                  <span><strong>{notification.title}</strong><small>{notification.message}</small></span>
                </button>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}
