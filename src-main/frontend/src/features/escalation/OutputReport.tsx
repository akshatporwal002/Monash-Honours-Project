import { useEffect, useState } from 'react'
import type { ApiSchemas } from '../../api/generated'
import { request } from '../../app/api'
import { Button, Card, Field, Select, Textarea } from '../../components/ui'

export function OutputReport({ sourceId }: { sourceId: string }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [kind, setKind] = useState('ASSESSOR')
  const [severity, setSeverity] = useState('NORMAL')
  const [key, setKey] = useState(() => crypto.randomUUID())
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  async function submit() {
    setBusy(true)
    setError('')
    try {
      await request('/escalations/reports', {
        method: 'POST',
        body: JSON.stringify({
          source_kind: 'TUTOR',
          source_id: sourceId,
          queue_kind: kind,
          severity,
          reason,
          idempotency_key: key,
        }),
      })
      setStatus(
        'Your report is saved for human review. Follow its progress in Report updates below.',
      )
      setOpen(false)
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'The report could not be saved.',
      )
    } finally {
      setBusy(false)
    }
  }
  return (
    <div>
      {status ? (
        <p role="status">{status}</p>
      ) : (
        <Button
          variant="quiet"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          Report this reply
        </Button>
      )}
      {error && <p role="alert">{error}</p>}
      {open && (
        <form
          aria-label="Report tutor reply"
          onSubmit={(event) => {
            event.preventDefault()
            void submit()
          }}
        >
          <Field label="Concern type">
            <Select
              value={kind}
              onValueChange={(value) => {
                setKind(value)
                setKey(crypto.randomUUID())
              }}
              options={[
                { value: 'ASSESSOR', label: 'Explanation, evidence or safety' },
                { value: 'TECHNICAL', label: 'Technical problem' },
              ]}
              disabled={busy}
            />
          </Field>
          <Field label="Urgency">
            <Select
              value={severity}
              onValueChange={(value) => {
                setSeverity(value)
                setKey(crypto.randomUUID())
              }}
              options={[
                { value: 'NORMAL', label: 'Normal' },
                { value: 'HIGH', label: 'High' },
                { value: 'CRITICAL', label: 'Critical' },
              ]}
              disabled={busy}
            />
          </Field>
          <Field label="Describe the concern" required>
            <Textarea
              value={reason}
              maxLength={2000}
              disabled={busy}
              required
              onChange={(event) => {
                setReason(event.target.value)
                setKey(crypto.randomUUID())
              }}
            />
          </Field>
          <Button type="submit" disabled={busy || !reason.trim()}>
            Send reply report
          </Button>
        </form>
      )}
    </div>
  )
}

export function ReportNotices({ taskId }: { taskId: string }) {
  const [reports, setReports] = useState<ApiSchemas['EscalationRead'][]>([])
  const [refresh, setRefresh] = useState(0)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    request<ApiSchemas['EscalationRead'][]>(
      `/students/me/tasks/${encodeURIComponent(taskId)}/reports`,
      { signal: controller.signal },
    )
      .then((value) => {
        if (
          !Array.isArray(value) ||
          value.some((report) => !Array.isArray(report.notices))
        )
          throw new Error('Report updates could not be loaded. Please refresh.')
        if (!controller.signal.aborted) {
          setReports(value)
          setError('')
        }
      })
      .catch((caught) => {
        if (!controller.signal.aborted) {
          setReports([])
          setError(
            caught instanceof Error
              ? caught.message
              : 'Report updates could not be loaded.',
          )
        }
      })
    return () => controller.abort()
  }, [taskId, refresh])
  return (
    <Card heading="Report updates" aria-label="Report updates">
      <Button
        variant="secondary"
        onClick={() => setRefresh((value) => value + 1)}
      >
        Refresh reports
      </Button>
      {error && <p role="alert">{error}</p>}
      {!reports.length && !error && <p>No reports for this task.</p>}
      {reports.map((report) => (
        <section key={report.id} aria-label="Reported concern">
          <h3>
            {report.queue_kind === 'ASSESSOR' ? 'Assessor' : 'Technical'} review
            · {report.status.toLowerCase()}
          </h3>
          <p>Reported {new Date(report.created_at).toLocaleString()}</p>
          {report.resolution_due_at ? (
            <p>
              Resolution target:{' '}
              {new Date(report.resolution_due_at).toLocaleString()}
            </p>
          ) : (
            <p>Awaiting triage and a response target.</p>
          )}
          {report.notices.map((notice) => (
            <p key={notice.revision}>
              {notice.learner_notice} ·{' '}
              {new Date(notice.created_at).toLocaleString()}
            </p>
          ))}
        </section>
      ))}
    </Card>
  )
}
