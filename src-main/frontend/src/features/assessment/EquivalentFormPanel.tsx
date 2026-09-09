import { useState } from 'react'
import type { ApiSchemas } from '../../api/generated'
import { request } from '../../app/api'
import { Button, Field, Select, Textarea } from '../../components/ui'

export function EquivalentFormPanel({
  setup,
  onPublished,
}: {
  setup: ApiSchemas['ReassessmentSetup']
  onPublished: () => void
}) {
  const [taskId, setTaskId] = useState('')
  const [templateId, setTemplateId] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const task = setup.fresh_tasks.find((item) => item.task_id === taskId)
  async function publish() {
    if (!task) return
    setBusy(true)
    setError('')
    try {
      await request(
        `/assessment/definitions/${encodeURIComponent(setup.definition_version_id)}/equivalent-forms`,
        {
          method: 'POST',
          body: JSON.stringify({
            task_id: task.task_id,
            revision_id: task.revision_id,
            template_form_id: templateId,
            reason,
          }),
        },
      )
      onPublished()
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'The equivalent form could not be approved.',
      )
    } finally {
      setBusy(false)
    }
  }
  return (
    <details>
      <summary>Approve an additional equivalent form</summary>
      <p>
        Review the teaching task before approving equivalence. The new form
        inherits the selected form’s assessment conditions and preserves the
        outcome, Bloom target and criteria.
      </p>
      {error && <p role="alert">{error}</p>}
      {!setup.fresh_tasks.length ? (
        <p>
          Create and approve a fresh teaching task in the course editor first.
        </p>
      ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault()
            void publish()
          }}
        >
          <Field label="Reviewed fresh teaching task" required>
            <Select
              value={taskId || undefined}
              onValueChange={setTaskId}
              options={setup.fresh_tasks.map((item) => ({
                value: item.task_id,
                label: item.title,
              }))}
              disabled={busy}
            />
          </Field>
          {task && (
            <blockquote>
              <p>{task.prompt}</p>
              <p>{task.instructions}</p>
            </blockquote>
          )}
          <Field label="Approved form with equivalent conditions" required>
            <Select
              value={templateId || undefined}
              onValueChange={setTemplateId}
              options={setup.policy_forms.map((item) => ({
                value: item.id,
                label: item.task_title,
              }))}
              disabled={busy}
            />
          </Field>
          <Field label="Equivalence approval reason" required>
            <Textarea
              value={reason}
              maxLength={2000}
              onChange={(event) => setReason(event.target.value)}
              disabled={busy}
              required
            />
          </Field>
          <Button
            type="submit"
            disabled={busy || !task || !templateId || !reason.trim()}
          >
            Approve equivalent form
          </Button>
        </form>
      )}
    </details>
  )
}
