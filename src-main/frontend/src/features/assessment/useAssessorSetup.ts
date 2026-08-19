import { useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from '../../app/api'
import type { ScopedRoleAssignment } from '../../app/types'
import { assessmentApi } from './api'
import type { AssessmentDefinition } from './api'
import {
  buildAssessmentDraft,
  initialSetupValues,
  missingSetupFields,
} from './assessmentDraft'
import type { SetupValues } from './assessmentDraft'

function safeError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return 'The assessment service could not be reached. Your draft remains in this form.'
  }
  if (error.status === 403) return 'Your assessor permission no longer allows this action.'
  if (error.status === 404) {
    return 'This assessment record is no longer available in the assigned course.'
  }
  if (error.status === 409) {
    return 'This assessment changed elsewhere. Your local values are still available below.'
  }
  if (error.status === 422) {
    return 'The assessment could not be approved. Check the required fields and current publication policy.'
  }
  return 'The assessment service could not complete the request. Your draft remains in this form.'
}

const bloomVerificationInputs = new Set<keyof SetupValues>([
  'courseId',
  'outcomeId',
  'outcome',
  'source',
  'sourceVersion',
  'sourceDigest',
  'bloomProcess',
  'knowledgeDimension',
  'purpose',
  'claim',
  'evidence',
  'criterion',
  'taskId',
  'taskFamily',
  'tools',
  'support',
  'transfer',
])
const accessVerificationInputs = new Set<keyof SetupValues>([
  ...bloomVerificationInputs,
  'access',
])

export function useAssessorSetup({
  assignments,
  onCheckAccess,
  onAccessRevoked,
}: {
  assignments: ScopedRoleAssignment[]
  onCheckAccess: (courseId: string) => Promise<boolean>
  onAccessRevoked: () => void
}) {
  const assessorAssignments = assignments.filter((assignment) => assignment.role === 'assessor')
  const [values, setValues] = useState<SetupValues>({
    ...initialSetupValues,
    courseId: assessorAssignments[0]?.course_id ?? '',
  })
  const [definition, setDefinition] = useState<AssessmentDefinition | null>(null)
  const [history, setHistory] = useState<AssessmentDefinition[]>([])
  const [faults, setFaults] = useState<string[]>([])
  const [status, setStatus] = useState('')
  const [serverError, setServerError] = useState('')
  const [stale, setStale] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState<'save' | 'publish' | 'history' | 'access' | null>(null)
  const editRevision = useRef(0)
  const requiredFields = useMemo(() => missingSetupFields(values), [values])

  const update = <Key extends keyof SetupValues>(key: Key, value: SetupValues[Key]) => {
    setValues((current) => {
      const changed = current[key] !== value
      const next: SetupValues = { ...current, [key]: value }
      if (changed && accessVerificationInputs.has(key)) next.accessVerified = false
      if (changed && bloomVerificationInputs.has(key)) next.bloomVerified = false
      return next
    })
    if (key !== 'approvalReason') {
      editRevision.current += 1
      if (definition) setDirty(true)
    }
    setFaults([])
    setStatus('')
    setServerError('')
  }

  const saveDraft = async (event: FormEvent) => {
    event.preventDefault()
    if (requiredFields.length) {
      setFaults(requiredFields)
      setStatus('Complete every required field before saving this assessment draft.')
      return
    }
    setBusy('save')
    setServerError('')
    const savingRevision = editRevision.current
    try {
      const saved = definition
        ? await assessmentApi.updateDraft(
          values.courseId,
          values.outcomeId.trim(),
          definition.assessment_definition_id,
          definition.version,
          buildAssessmentDraft(values),
        )
        : await assessmentApi.createDraft(
          values.courseId,
          values.outcomeId.trim(),
          buildAssessmentDraft(values),
        )
      setDefinition(saved)
      setHistory((current) => [
        ...current.filter((item) => item.id !== saved.id),
        saved,
      ])
      const changedDuringSave = editRevision.current !== savingRevision
      setDirty(changedDuringSave)
      setStale(false)
      setStatus(
        changedDuringSave
          ? 'Draft saved, but newer local changes still need saving.'
          : definition
          ? 'Draft revision saved. Review the new version before approval.'
          : 'Draft saved. Review the pass rule, then approve when ready.',
      )
    } catch (error) {
      setServerError(safeError(error))
      setStale(error instanceof ApiError && error.status === 409)
    } finally {
      setBusy(null)
    }
  }

  const loadHistory = async () => {
    if (!definition) return
    setBusy('history')
    setServerError('')
    try {
      const records = await assessmentApi.history(
        values.courseId,
        definition.assessment_definition_id,
      )
      setHistory(records)
      setStale(false)
      setStatus('Server history reloaded. Your local form values were not changed.')
    } catch (error) {
      setServerError(safeError(error))
    } finally {
      setBusy(null)
    }
  }

  const publish = async () => {
    if (!definition) return
    if (dirty) {
      setStatus('Save the current changes before publishing.')
      return
    }
    const approvalFaults = [
      ...requiredFields,
      ...(!values.approvalReason.trim() ? ['approval reason'] : []),
    ]
    if (approvalFaults.length) {
      setFaults(approvalFaults)
      setStatus('Complete every required field and record an approval reason before publishing.')
      return
    }
    setBusy('publish')
    setServerError('')
    try {
      const approved = await assessmentApi.publish(
        values.courseId,
        definition.assessment_definition_id,
        definition.version,
        values.approvalReason.trim(),
      )
      setDefinition(approved)
      setHistory((current) => [
        ...current.filter((item) => item.id !== approved.id),
        approved,
      ])
      setStale(false)
      setStatus('Assessment approved and published.')
    } catch (error) {
      setServerError(safeError(error))
      setStale(error instanceof ApiError && error.status === 409)
    } finally {
      setBusy(null)
    }
  }

  const checkAccess = async () => {
    setBusy('access')
    try {
      const active = await onCheckAccess(values.courseId)
      if (active) setStatus('Assessor access is still active for this course.')
      else onAccessRevoked()
    } catch {
      setServerError('Assessor access could not be refreshed. Existing controls have not changed.')
    } finally {
      setBusy(null)
    }
  }

  return {
    assessorAssignments,
    values,
    definition,
    history,
    faults,
    status,
    serverError,
    stale,
    dirty,
    busy,
    update,
    saveDraft,
    loadHistory,
    publish,
    checkAccess,
  }
}
