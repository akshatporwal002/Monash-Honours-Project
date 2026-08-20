import { ArrowRight, Award, BellDot, BookOpen, Check, Lock, Trophy } from 'lucide-react'

import type { LearningNotification, LearningTask, StudentDashboardData } from '../app/types'
import { Button, Card, EmptyState, Meter, PageHeader, Tag, cx } from './ui'
import styles from './StudentDashboard.module.css'

type TaskState = 'locked' | 'in-progress' | 'completed'

function taskState(task: LearningTask): TaskState {
  if (task.status === 'completed') return 'completed'
  if (task.status === 'locked') return 'locked'
  return 'in-progress'
}

const stateLabel: Record<TaskState, string> = {
  completed: 'Completed',
  locked: 'Locked',
  'in-progress': 'In progress',
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
  const unread = notifications.filter((item) => !item.is_read).length

  return (
    <div className={styles.screen}>
      <PageHeader
        eyebrow="My learning"
        title={`Welcome back, ${firstName}`}
        description="Build momentum with one focused quantum concept at a time."
      />

      <div className={styles.hero}>
        <Card eyebrow="Continue" className={styles.continueCard}>
          {nextTask ? (
            <>
              <h2 className={styles.continueTitle}>{nextTask.title}</h2>
              <p className={styles.continueMeta}>
                <Tag>{taskKind(nextTask)}</Tag>
                <span>{nextTask.module}</span>
              </p>
              {nextRecommendation?.reason ? (
                <p className={styles.continueReason}>{nextRecommendation.reason}</p>
              ) : null}
              <div className={styles.continueAction}>
                <Button variant="primary" onClick={() => onOpenTask(nextTask)}>
                  Continue learning <ArrowRight size={16} aria-hidden="true" />
                </Button>
              </div>
            </>
          ) : (
            <>
              <h2 className={styles.continueTitle}>Your pathway is complete</h2>
              <p className={styles.continueReason}>
                You have completed every available activity. Review earlier work or explore your achievements.
              </p>
            </>
          )}
        </Card>
        <Card eyebrow="Course momentum" className={styles.momentumCard}>
          <Meter value={progress.completed_tasks} max={progress.total_tasks} label="Activities completed" />
          <p className={styles.momentumNote}>{earned.length} achievements earned</p>
        </Card>
      </div>

      <Card eyebrow="Your pathway" heading="Quantum foundations" className={styles.pathway}>
        {tasks.length === 0 ? (
          <EmptyState
            icon={<BookOpen size={20} />}
            title="No activities yet"
            description="Your educator is preparing the pathway. Check back soon."
          />
        ) : (
          <ol className={styles.path}>
            {tasks.map((task, index) => {
              const state = taskState(task)
              return (
                <li key={task.id} className={cx(styles.step, styles[`step-${state}`])}>
                  <span className={styles.marker} aria-hidden="true">
                    {state === 'completed' ? <Check size={14} /> : state === 'locked' ? <Lock size={12} /> : index + 1}
                  </span>
                  <div className={styles.stepBody}>
                    <p className={styles.stepMeta}>
                      <span>{task.module}</span>
                      <span className={styles.stepState}>{stateLabel[state]}</span>
                    </p>
                    <h3 className={styles.stepTitle}>{task.title}</h3>
                    <p className={styles.stepDetail}>
                      {taskKind(task)} · {task.difficulty}
                      {task.attempt_count
                        ? ` · ${task.attempt_count} attempt${task.attempt_count === 1 ? '' : 's'}`
                        : ''}
                    </p>
                  </div>
                  <Button
                    variant={state === 'in-progress' ? 'secondary' : 'quiet'}
                    disabled={state === 'locked'}
                    onClick={() => onOpenTask(task)}
                    aria-label={`${state === 'completed' ? 'Review' : 'Open'} ${task.title}`}
                  >
                    {state === 'locked' ? 'Locked' : state === 'completed' ? 'Review' : 'Open'}
                  </Button>
                </li>
              )
            })}
          </ol>
        )}
      </Card>

      <div className={styles.grid}>
        <Card eyebrow="Progress by module" heading="Module activity">
          {Object.keys(progress.module_progress).length === 0 ? (
            <EmptyState title="Nothing to show yet" description="Complete an activity to see module progress." />
          ) : (
            <div className={styles.modules}>
              {Object.entries(progress.module_progress)
                .slice(0, 4)
                .map(([module, value]) => (
                  <Meter key={module} value={Math.round(value)} max={100} label={module} />
                ))}
            </div>
          )}
        </Card>

        <Card eyebrow="Milestones" heading="Achievements">
          {progress.achievements.length === 0 ? (
            <EmptyState
              icon={<Award size={20} />}
              title="Your first achievement is one activity away"
              description="Finish an activity to earn it."
            />
          ) : (
            <ul className={styles.achievements}>
              {progress.achievements.slice(0, 4).map((achievement) => (
                <li key={achievement.code} className={cx(styles.achievement, !achievement.earned_at && styles.achievementLocked)}>
                  <span className={styles.achievementIcon} aria-hidden="true">
                    {achievement.earned_at ? <Trophy size={16} /> : <Award size={16} />}
                  </span>
                  <div>
                    <strong className={styles.achievementName}>{achievement.name}</strong>
                    <p className={styles.achievementText}>{achievement.description}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card eyebrow="Stay on track" heading="Updates" actions={unread ? <Tag tone="accent">{unread} new</Tag> : undefined}>
          {notifications.length === 0 ? (
            <EmptyState title="You are all caught up" description="New reminders will appear here." />
          ) : (
            <ul className={styles.notifications}>
              {notifications.slice(0, 4).map((notification) => (
                <li key={notification.id}>
                  <button
                    type="button"
                    className={cx(styles.notification, notification.is_read && styles.notificationRead)}
                    onClick={() => void onReadNotification(notification)}
                  >
                    <span className={styles.notificationIcon} aria-hidden="true">
                      <BellDot size={14} />
                    </span>
                    <span>
                      <strong className={styles.notificationTitle}>{notification.title}</strong>
                      <span className={styles.notificationText}>{notification.message}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* Gamification data retained pending the FR25 opt-in decision (plan 006 §8); deliberately quiet. */}
      <Card eyebrow="Optional points" className={styles.points}>
        <p className={styles.pointsText}>
          Level {progress.level} · {progress.points} points
          {progress.points_to_next_level ? ` · ${progress.points_to_next_level} to the next level` : ''}
          {progress.average_score ? ` · ${progress.average_score}% practice average` : ''}
        </p>
        <p className={styles.pointsNote}>Points come from practice activity only. They never affect a formal result.</p>
      </Card>
    </div>
  )
}
