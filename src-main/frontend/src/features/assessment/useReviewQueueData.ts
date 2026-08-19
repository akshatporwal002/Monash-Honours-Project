import { useCallback, useEffect, useMemo, useState } from 'react'

import { ApiError } from '../../app/api'
import { assessmentApi } from './api'
import type { AssessmentReviewDetail } from './api'
import type { ReviewFilters } from './AssessorReviewPanels'
import { resultStateValues } from './types'

export function reviewErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return 'The review service could not be reached. Your filters and typed reason remain available.'
  }
  if (error.status === 403) return 'Your assessor permission no longer allows this action.'
  if (error.status === 404) {
    return 'This review record is no longer available in your assigned course.'
  }
  if (error.status === 422) {
    return 'The review action could not be validated. Check the current record and reason.'
  }
  return 'The review service could not complete the request. Your filters and typed reason remain available.'
}

async function readAccess(
  check: (courseId: string) => Promise<boolean>,
  courseId: string,
): Promise<boolean | null> {
  try {
    return await check(courseId)
  } catch {
    return null
  }
}

function queueParameters(filters: ReviewFilters) {
  return {
    outcome_id: filters.outcomeId.trim() || undefined,
    result: filters.result || undefined,
    result_state: filters.resultState || undefined,
    review_flag: filters.reviewFlag.trim() || undefined,
    minimum_age_hours: filters.minimumAgeHours
      ? Number(filters.minimumAgeHours)
      : undefined,
  }
}

export function useReviewQueueData({
  initialCourseId,
  onCheckAccess,
  onAccessRevoked,
}: {
  initialCourseId: string
  onCheckAccess: (courseId: string) => Promise<boolean>
  onAccessRevoked: () => void
}) {
  const [filters, setFilters] = useState<ReviewFilters>({
    courseId: initialCourseId,
    outcomeId: '',
    result: '',
    resultState: '',
    reviewFlag: '',
    minimumAgeHours: '',
  })
  const [records, setRecords] = useState<AssessmentReviewDetail[]>([])
  const [selected, setSelected] = useState<AssessmentReviewDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [accessActive, setAccessActive] = useState(true)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')

  const clearForRevokedAccess = useCallback(() => {
    setAccessActive(false)
    setFilters((current) => ({ ...current, courseId: '' }))
    setRecords([])
    setSelected(null)
    setStatus('Assessor access has expired. Review action controls were removed.')
    onAccessRevoked()
  }, [onAccessRevoked])

  const checkAccess = useCallback(async (): Promise<boolean> => {
    const active = await readAccess(onCheckAccess, filters.courseId)
    if (active === null) {
      setError('Assessor access could not be refreshed. No review action was sent.')
      return false
    }
    setAccessActive(active)
    if (!active) clearForRevokedAccess()
    return active
  }, [clearForRevokedAccess, filters.courseId, onCheckAccess])

  const storeQueue = useCallback((queue: AssessmentReviewDetail[]) => {
    setRecords(queue)
    setSelected((current) => (
      queue.find((record) => record.decision_id === current?.decision_id)
      ?? queue[0]
      ?? null
    ))
    setStatus(`${queue.length} review record${queue.length === 1 ? '' : 's'} loaded.`)
  }, [])

  const refreshQueue = useCallback(async () => {
    if (!filters.courseId) {
      setRecords([])
      setSelected(null)
      setError('Select an assigned course before loading review records.')
      return
    }
    if (!(await checkAccess())) return
    setLoading(true)
    setError('')
    try {
      storeQueue(await assessmentApi.reviewQueue(filters.courseId, queueParameters(filters)))
    } catch (caught) {
      setError(reviewErrorMessage(caught))
    } finally {
      setLoading(false)
    }
  }, [checkAccess, filters, storeQueue])

  useEffect(() => {
    if (!filters.courseId) return
    let cancelled = false

    async function loadAssignedCourse() {
      const active = await readAccess(onCheckAccess, filters.courseId)
      if (cancelled) return
      if (active === null) {
        setError('Assessor access could not be refreshed. No review records were loaded.')
        return
      }
      setAccessActive(active)
      if (!active) {
        clearForRevokedAccess()
        return
      }
      setLoading(true)
      setError('')
      try {
        const queue = await assessmentApi.reviewQueue(filters.courseId, {})
        if (!cancelled) storeQueue(queue)
      } catch (caught) {
        if (!cancelled) setError(reviewErrorMessage(caught))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadAssignedCourse()
    return () => { cancelled = true }
  }, [clearForRevokedAccess, filters.courseId, onCheckAccess, storeQueue])

  const updateFilters = <Key extends keyof ReviewFilters>(
    key: Key,
    value: ReviewFilters[Key],
  ) => {
    setFilters((current) => ({ ...current, [key]: value }))
    setError('')
  }

  const reloadCurrentDetail = async (decisionId: string) => {
    const current = await assessmentApi.reviewDetail(decisionId)
    setSelected(current)
    setRecords((items) => items.map((item) => (
      item.decision_id === current.decision_id ? current : item
    )))
    return current
  }

  const summaries = useMemo(() => resultStateValues.map((state) => ({
    state,
    count: records.filter((record) => record.result_state === state).length,
  })), [records])

  return {
    filters,
    records,
    selected,
    loading,
    accessActive,
    error,
    status,
    summaries,
    setSelected,
    setError,
    setStatus,
    updateFilters,
    checkAccess,
    refreshQueue,
    reloadCurrentDetail,
  }
}
