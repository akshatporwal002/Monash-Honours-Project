import { useEffect, useState } from 'react'
import type { ApiSchemas } from '../../api/generated'
import { ApiError, request } from '../../app/api'
import { Button, Card, Field, Select, Textarea } from '../../components/ui'
import { EquivalentFormPanel } from './EquivalentFormPanel'

type Setup = ApiSchemas['ReassessmentSetup']
type Rule = ApiSchemas['OutcomePolicyWrite']['selection_rule']
const rules: { value: Rule; label: string }[] = [
  { value: 'LATEST_VALID', label: 'Latest valid authorised evidence' },
  { value: 'ANY_VALID_PASS', label: 'Any valid PASS' },
  { value: 'ALL_REQUIRED_FORMS', label: 'PASS on every required form' },
]

export function ReassessmentPanel({
  decisionId,
  revision,
}: {
  decisionId: string
  revision: number
}) {
  const [setup, setSetup] = useState<Setup | null>(null)
  const [refresh, setRefresh] = useState(0)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [rule, setRule] = useState<Rule>('LATEST_VALID')
  const [requiredForms, setRequiredForms] = useState<string[]>([])
  const [formId, setFormId] = useState('')
  const [policyReason, setPolicyReason] = useState('')
  const [reason, setReason] = useState('')
  const [notice, setNotice] = useState('')
  const path = `/assessment/decisions/${encodeURIComponent(decisionId)}/reassessment`

  useEffect(() => {
    const controller = new AbortController()
    request<Setup>(path, { signal: controller.signal })
      .then((value) => {
        if (
          !Array.isArray(value.forms) ||
          !Array.isArray(value.policy_forms) ||
          !Array.isArray(value.fresh_tasks)
        )
          throw new Error('Reassessment could not be loaded. Please refresh.')
        if (!controller.signal.aborted) setSetup(value)
      })
      .catch((caught) => {
        if (!controller.signal.aborted) {
          setSetup(null)
          setError(
            caught instanceof Error
              ? caught.message
              : 'Reassessment could not be loaded.',
          )
        }
      })
    return () => controller.abort()
  }, [path, refresh, revision])

  async function save(policy: boolean) {
    if (!setup) return
    setBusy(true)
    setError('')
    try {
      await request(
        policy
          ? `/assessment/definitions/${encodeURIComponent(setup.definition_version_id)}/outcome-policy`
          : path,
        {
          method: 'POST',
          body: JSON.stringify(
            policy
              ? {
                  selection_rule: rule,
                  required_form_ids:
                    rule === 'ALL_REQUIRED_FORMS' ? requiredForms : [],
                  reason: policyReason,
                }
              : {
                  task_form_version_id: formId,
                  expected_decision_revision: revision,
                  reason,
                  learner_notice: notice,
                },
          ),
        },
      )
      setRefresh((value) => value + 1)
    } catch (caught) {
      if (caught instanceof ApiError && [401, 403, 404].includes(caught.status))
        setSetup(null)
      setError(
        caught instanceof Error
          ? caught.message
          : 'The change could not be saved. Your text is retained.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card
      heading="Reassessment and outcome rule"
      aria-label="Reassessment and outcome rule"
    >
      {error && <p role="alert">{error}</p>}
      <Button
        variant="secondary"
        disabled={busy}
        onClick={() => {
          setError('')
          setRefresh((value) => value + 1)
        }}
      >
        Reload reassessment
      </Button>
      {setup && (
        <>
          <EquivalentFormPanel
            setup={setup}
            onPublished={() => setRefresh((value) => value + 1)}
          />
          <p>
            Earlier decisions remain available. A fresh form must preserve the
            approved standard and be unused by this learner.
          </p>
          {setup.policy ? (
            <p>
              Published outcome rule:{' '}
              {
                rules.find(
                  (item) => item.value === setup.policy?.selection_rule,
                )?.label
              }
              . {setup.policy.reason}
            </p>
          ) : (
            <form
              onSubmit={(event) => {
                event.preventDefault()
                void save(true)
              }}
            >
              <Field label="Outcome selection rule" required>
                <Select
                  value={rule}
                  options={rules}
                  onValueChange={(value) => {
                    if (rules.some((item) => item.value === value))
                      setRule(value as Rule)
                  }}
                  disabled={busy}
                />
              </Field>
              <p>
                A valid PASS remains until an assessor changes or voids it.
                Partial criteria across attempts are never combined. Publishing
                fixes this rule for the standard version.
              </p>
              {rule === 'ALL_REQUIRED_FORMS' && (
                <fieldset disabled={busy}>
                  <legend>Required forms</legend>
                  {setup.policy_forms.map((form) => (
                    <label key={form.id}>
                      <input
                        type="checkbox"
                        checked={requiredForms.includes(form.id)}
                        onChange={(event) =>
                          setRequiredForms((current) =>
                            event.target.checked
                              ? [...current, form.id]
                              : current.filter((id) => id !== form.id),
                          )
                        }
                      />
                      {form.task_title}
                    </label>
                  ))}
                </fieldset>
              )}
              <Field label="Policy approval reason" required>
                <Textarea
                  value={policyReason}
                  maxLength={2000}
                  onChange={(event) => setPolicyReason(event.target.value)}
                  disabled={busy}
                  required
                />
              </Field>
              <Button
                type="submit"
                disabled={
                  busy ||
                  !policyReason.trim() ||
                  (rule === 'ALL_REQUIRED_FORMS' && !requiredForms.length)
                }
              >
                Publish outcome rule
              </Button>
            </form>
          )}
          {setup.authorisation && (
            <p role="status">
              Reassessment authorised: {setup.authorisation.task_title}.{' '}
              {setup.authorisation.learner_notice}{' '}
              {!setup.authorisation.available &&
                'This authorisation is no longer available for new work.'}
            </p>
          )}
          {setup.policy &&
            !setup.authorisation?.available &&
            !setup.authorisation?.replacement_response_id && (
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  void save(false)
                }}
              >
                {!setup.forms.length && (
                  <p>
                    No fresh equivalent form is currently published for this
                    standard. Publish an equivalent form before authorising
                    reassessment.
                  </p>
                )}
                <Field label="Fresh equivalent form" required>
                  <Select
                    value={formId || undefined}
                    options={setup.forms.map((form) => ({
                      value: form.id,
                      label: form.task_title,
                    }))}
                    onValueChange={setFormId}
                    disabled={busy || !setup.forms.length}
                  />
                </Field>
                <Field label="Private reassessment reason" required>
                  <Textarea
                    value={reason}
                    maxLength={2000}
                    onChange={(event) => setReason(event.target.value)}
                    disabled={busy}
                    required
                  />
                </Field>
                <Field label="Reassessment notice to learner" required>
                  <Textarea
                    value={notice}
                    maxLength={2000}
                    onChange={(event) => setNotice(event.target.value)}
                    disabled={busy}
                    required
                  />
                </Field>
                <Button
                  type="submit"
                  disabled={busy || !formId || !reason.trim() || !notice.trim()}
                >
                  Authorise reassessment
                </Button>
              </form>
            )}
        </>
      )}
    </Card>
  )
}
