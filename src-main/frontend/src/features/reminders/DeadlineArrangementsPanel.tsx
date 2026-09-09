import { useEffect, useRef, useState } from 'react'
import type { ApiSchemas } from '../../api/generated'
import { ApiError, api } from '../../app/api'
import {
  Button,
  Card,
  Field,
  Input,
  Select,
  Textarea,
} from '../../components/ui'
import { formatDeadline } from './deadlineTime'
import styles from './reminders.module.css'

type Arrangement = ApiSchemas['DeadlineArrangementRead']

export function DeadlineArrangementsPanel({
  courseId,
  timeZone,
}: {
  courseId: string
  timeZone: string
}) {
  const [participants, setParticipants] = useState<
    ApiSchemas['EnrollmentRead'][]
  >([])
  const [tasks, setTasks] = useState<ApiSchemas['TaskRead'][]>([])
  const [student, setStudent] = useState('')
  const [task, setTask] = useState('')
  const [status, setStatus] = useState('Loading course participants and tasks…')
  const [reload, setReload] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    void Promise.all([
      api.reminders.participants(courseId, controller.signal),
      api.taskReview.tasks(courseId, controller.signal),
    ])
      .then(([people, work]) => {
        if (controller.signal.aborted) return
        setParticipants(people)
        setTasks(work)
        setStatus('')
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setStatus('Course participants and tasks could not be loaded.')
      })
    return () => controller.abort()
  }, [courseId, reload])
  return (
    <Card
      heading="Individual deadlines"
      aria-label="Individual deadlines"
      eyebrow="Learner access"
    >
      <p>
        Record an extension or access arrangement in {timeZone}. Assessment
        requirements and results stay the same.
      </p>
      {status && (
        <>
          <p role="status">{status}</p>
          <Button
            variant="quiet"
            onClick={() => setReload((value) => value + 1)}
          >
            Reload participants and tasks
          </Button>
        </>
      )}
      <Field label="Learner">
        <Select
          value={student}
          onValueChange={setStudent}
          placeholder="Select a learner"
          options={participants.map((person) => ({
            value: String(person.student_id),
            label: person.student_name,
          }))}
        />
      </Field>
      <Field label="Task">
        <Select
          value={task}
          onValueChange={setTask}
          placeholder="Select a task"
          options={tasks.map((item) => ({ value: item.id, label: item.title }))}
        />
      </Field>
      {student && task && (
        <ArrangementEditor
          key={`${student}-${task}`}
          taskId={task}
          studentId={Number(student)}
          timeZone={timeZone}
        />
      )}
    </Card>
  )
}

function ArrangementEditor({
  taskId,
  studentId,
  timeZone,
}: {
  taskId: string
  studentId: number
  timeZone: string
}) {
  const [history, setHistory] = useState<Arrangement[]>([])
  const [loaded, setLoaded] = useState(false)
  const [more, setMore] = useState(false)
  const [busy, setBusy] = useState(false)
  const [stale, setStale] = useState(false)
  const [reload, setReload] = useState(0)
  const [kind, setKind] = useState<'EXTENSION' | 'ACCESS_PLAN'>('EXTENSION')
  const [active, setActive] = useState(true)
  const [due, setDue] = useState('')
  const [fold, setFold] = useState('auto')
  const [paused, setPaused] = useState(false)
  const [reason, setReason] = useState('')
  const [notice, setNotice] = useState('')
  const [status, setStatus] = useState('Loading arrangement history…')
  const pending = useRef<{ body: string; key: string } | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    void api.reminders
      .history(taskId, studentId, 0, controller.signal)
      .then((records) => {
        if (controller.signal.aborted) return
        setHistory(records)
        setMore(records.length === 20)
        setLoaded(true)
        setStale(false)
        setStatus('')
        pending.current = null
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setStatus(
            'Arrangement history could not be loaded. Reload to try again.',
          )
      })
    return () => controller.abort()
  }, [taskId, studentId, reload])
  const save = async () => {
    setBusy(true)
    try {
      const payload: Omit<
        ApiSchemas['DeadlineArrangementWrite'],
        'idempotency_key'
      > = {
        expected_revision: history[0]?.revision ?? 0,
        kind,
        time_zone: timeZone,
        active,
        local_due_at: active && due ? `${due}:00` : null,
        fold: fold === 'auto' ? null : fold === 'first' ? 0 : 1,
        reminders_paused: active && kind === 'ACCESS_PLAN' && paused,
        reason,
        learner_notice: notice,
      }
      const body = JSON.stringify(payload)
      if (pending.current?.body !== body)
        pending.current = { body, key: crypto.randomUUID() }
      const receipt = await api.reminders.saveArrangement(taskId, studentId, {
        ...payload,
        idempotency_key: pending.current.key,
      })
      setHistory((records) => [
        receipt,
        ...records.filter((record) => record.id !== receipt.id),
      ])
      setReason('')
      setNotice('')
      pending.current = null
      setStatus('Arrangement saved.')
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) setStale(true)
      setStatus(
        error instanceof ApiError
          ? error.message
          : 'The arrangement could not be saved. Your draft is still here.',
      )
    } finally {
      setBusy(false)
    }
  }
  const loadMore = async () => {
    setBusy(true)
    try {
      const records = await api.reminders.history(
        taskId,
        studentId,
        history.length,
      )
      setHistory((current) => [
        ...current,
        ...records.filter(
          (record) => !current.some((item) => item.id === record.id),
        ),
      ])
      setMore(records.length === 20)
    } catch {
      setStatus('Older arrangements could not be loaded.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <section aria-label="Arrangement editor">
      <form
        onSubmit={(event) => {
          event.preventDefault()
          void save()
        }}
      >
        <fieldset className={styles.fields} disabled={!loaded || busy || stale}>
          <legend>Record an arrangement</legend>
          <Field label="Arrangement type">
            <Select
              value={kind}
              onValueChange={(value) =>
                setKind(value === 'ACCESS_PLAN' ? 'ACCESS_PLAN' : 'EXTENSION')
              }
              options={[
                { value: 'EXTENSION', label: 'Extension' },
                { value: 'ACCESS_PLAN', label: 'Access plan' },
              ]}
            />
          </Field>
          <label>
            <input
              type="checkbox"
              checked={!active}
              onChange={(event) => setActive(!event.target.checked)}
            />{' '}
            Revoke the current arrangement
          </label>
          {active && (
            <>
              <Field label={`Extended deadline (${timeZone})`}>
                <Input
                  type="datetime-local"
                  value={due}
                  onChange={(event) => setDue(event.target.value)}
                />
              </Field>
              <Field
                label="Repeated daylight-saving time"
                help="If the clock repeats this time, choose which occurrence applies."
              >
                <Select
                  value={fold}
                  onValueChange={setFold}
                  options={[
                    { value: 'auto', label: 'No repeated time' },
                    { value: 'first', label: 'First occurrence' },
                    { value: 'second', label: 'Second occurrence' },
                  ]}
                />
              </Field>
              {kind === 'ACCESS_PLAN' && (
                <label>
                  <input
                    type="checkbox"
                    checked={paused}
                    onChange={(event) => setPaused(event.target.checked)}
                  />{' '}
                  Pause this task's reminders until the arrangement is changed
                  or revoked
                </label>
              )}
            </>
          )}
          <Field
            label="Private staff reason"
            help="Record only the scheduling decision; avoid medical details."
          >
            <Textarea
              required
              maxLength={2000}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </Field>
          <Field label="Notice shown to the learner">
            <Textarea
              required
              maxLength={2000}
              value={notice}
              onChange={(event) => setNotice(event.target.value)}
            />
          </Field>
          <Button type="submit">Save arrangement</Button>
        </fieldset>
      </form>
      <p role="status">{status}</p>
      <Button
        variant="quiet"
        disabled={busy}
        onClick={() => {
          setLoaded(false)
          setReload((value) => value + 1)
        }}
      >
        Reload arrangement history
      </Button>
      <h3>Arrangement history</h3>
      {loaded && history.length === 0 && (
        <p>No individual arrangements recorded.</p>
      )}
      <ol className={styles.history}>
        {history.map((record) => (
          <li key={record.id}>
            <p>
              Revision {record.revision} ·{' '}
              {record.kind === 'ACCESS_PLAN' ? 'Access plan' : 'Extension'} ·{' '}
              {record.active ? 'Recorded' : 'Revoked'}
            </p>
            {record.due_at && (
              <p>
                Deadline: {formatDeadline(record.due_at, record.time_zone)} (
                {record.time_zone})
              </p>
            )}
            {record.reminders_paused && <p>Task reminders paused</p>}
            <p>Staff reason: {record.reason}</p>
            <p>Learner notice: {record.learner_notice}</p>
          </li>
        ))}
      </ol>
      {more && (
        <Button variant="quiet" disabled={busy} onClick={() => void loadMore()}>
          Load older arrangements
        </Button>
      )}
    </section>
  )
}
