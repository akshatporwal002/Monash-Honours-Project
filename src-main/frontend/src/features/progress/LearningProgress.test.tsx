import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import type { ApiSchemas } from '../../api/generated'
import { LearningEvidenceDetail } from './LearningEvidenceDetail'
import { LearningProgress } from './LearningProgress'
import { ProgressRecordList } from './ProgressRecordList'

const cases = [
  ['audit date (standard time)', '2026-09-10T03:33:21.486860Z', '10/09/2026, 13:33:21'],
  ['summer', '2026-01-15T03:33:21+00:00', '15/01/2026, 14:33:21'],
  ['next local day', '2026-09-10T14:30:00Z', '11/09/2026, 00:30:00'],
  ['next local year', '2026-12-31T13:30:00Z', '01/01/2027, 00:30:00'],
  ['before spring jump', '2026-10-03T15:59:59Z', '04/10/2026, 01:59:59'],
  ['after spring jump', '2026-10-03T16:00:00Z', '04/10/2026, 03:00:00'],
  ['before autumn repeat', '2026-04-04T15:59:59Z', '05/04/2026, 02:59:59'],
  ['after autumn repeat', '2026-04-04T16:00:00Z', '05/04/2026, 02:00:00'],
  ['explicit non-UTC offset', '2026-09-10T13:33:21.486860+10:00', '10/09/2026, 13:33:21'],
]

beforeEach(() => {
  // Supply a deterministic viewer locale/zone while retaining real Date parsing
  // and ICU conversion. Do not change the host zone or shared Vitest settings.
  const format = Date.prototype.toLocaleString
  vi.spyOn(Date.prototype, 'toLocaleString').mockImplementation(function (this: Date) {
    return format.call(this, 'en-AU', {
      timeZone: 'Australia/Sydney',
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
    })
  })
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function observation(stamp: string): ApiSchemas['ProgressObservation'] {
  return {
    evidence_id: 'evidence', task_id: 'task', response_id: 'response',
    kind: 'RESPONSE', support_level: 0, occurred_at: stamp, confidence: null,
  }
}

function progress(stamp: string): ApiSchemas['LearningProgressPage'] {
  return {
    course_id: 'course', course_title: 'Quantum', generated_at: stamp,
    cohort_observations: { RESPONSE: 1 }, cohort_weekly_observations: {},
    cohort_weekly_trends: {}, next_offset: null, history_limit: 20,
    items: [{
      learner_id: 1, learner_name: 'Learner', outcome_id: 'outcome', outcome_title: 'Measurement',
      observations: { RESPONSE: 1 }, weekly_observations: {}, independent_responses: 1,
      supported_responses: 0, recent_evidence: [observation(stamp)],
      estimates: [{
        snapshot_id: 'snapshot', prior_snapshot_id: null, estimate_id: 'estimate',
        dimension: 'CONCEPT', status: 'UNCERTAIN', uncertainty: 1,
        reason: 'More evidence needed', occurred_at: stamp,
        evidence: [{ evidence_id: 'evidence', relation: 'SUPPORTS' }],
      }],
      results: [{
        response_id: 'response', task_id: 'task', result: null,
        status: 'pending', occurred_at: stamp,
      }],
      adaptations: [{
        workflow_id: 'workflow', state: 'suggested', reason: 'Try a fresh activity',
        uncertainty: 1, snapshot_id: 'snapshot', evidence_ids: ['evidence'], occurred_at: stamp,
        choices: [{
          version: 1, action: 'defer', task_id: null, reason: 'Revisit later',
          educator: false, created_at: stamp,
        }],
      }],
      outcome_results: [], misconception_ids: [],
    }],
  }
}

describe.each(['student', 'educator'] as const)('%s progress in Sydney', role => {
  test.each(cases)('%s', async (_name, stamp, expected) => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async input =>
      Response.json(String(input).endsWith('/courses')
        ? [{ id: 'course', title: 'Quantum' }]
        : progress(stamp)),
    )
    render(<MemoryRouter initialEntries={['/?course=course']}>
      <LearningProgress role={role} />
    </MemoryRouter>)
    expect(await screen.findByText(/Result not released: pending/)).toHaveTextContent(expected)
    // Observations, estimates, results, adaptations and nested choices all use
    // the recorded instant. Hidden detail sections are also rendered and checked.
    expect(screen.getAllByText(text => text.includes(expected))).toHaveLength(5)
    expect(screen.queryByText('PASS', { exact: true })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Inspect this response and its evidence' }))
      .toHaveAttribute('href', `/${role}/progress/records?course=course&kind=result&response_id=response&learner_id=1&outcome_id=outcome`)
  })
})

test.each(cases)('contributing record and evidence detail: %s', async (_name, stamp, expected) => {
  const records: ApiSchemas['ProgressTrendPage'] = {
    items: [{
      id: 'record', learner_id: 1, learner_name: 'Learner', outcome_id: 'outcome',
      occurred_at: stamp, kind: 'observation:RESPONSE', evidence_id: 'evidence', task_id: 'task',
      response_id: 'response', workflow_id: null, estimate_id: null, uncertainty: null,
      reason: null, evidence_ids: ['evidence'],
    }],
    next_offset: null,
  }
  const detail: ApiSchemas['ProgressEvidenceDetail'] = {
    ...observation(stamp), course_id: 'course', learner_id: 1, outcome_id: 'outcome',
    status: 'Saved observation', fields: [{ label: 'Answer', text: 'Preserved reasoning' }],
    related_evidence_ids: [],
  }
  vi.spyOn(globalThis, 'fetch').mockImplementation(async input =>
    Response.json(String(input).includes('/records?') ? records : detail),
  )
  const view = render(<MemoryRouter initialEntries={['/?course=course&kind=observation:RESPONSE']}>
    <ProgressRecordList role="student" />
  </MemoryRouter>)
  expect(await screen.findByText(text => text.includes(expected))).toBeVisible()
  view.unmount()
  render(<MemoryRouter initialEntries={['/evidence/evidence?course=course']}>
    <Routes><Route path="/evidence/:evidenceId" element={<LearningEvidenceDetail role="student" />} /></Routes>
  </MemoryRouter>)
  expect(await screen.findByText(/^Recorded /)).toHaveTextContent(expected)
  expect(screen.getByText('Preserved reasoning')).toBeVisible()
})
