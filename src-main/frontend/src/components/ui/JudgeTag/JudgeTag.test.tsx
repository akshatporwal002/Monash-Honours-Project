import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { JudgeTag } from './JudgeTag'
import type { QualityReviewDecision } from '../../../features/assessment/types'

describe('JudgeTag', () => {
  it('names the judge namespace explicitly so it cannot read as a learner result (AT20)', () => {
    render(<JudgeTag decision="REJECTED" />)
    expect(screen.getByText('Quality review: rejected')).toBeInTheDocument()
  })

  it('accepts only judge-namespace values', () => {
    // @ts-expect-error — PASS is a learner result, not a judge decision (D3 §5.2)
    const invalid: QualityReviewDecision = 'PASS'
    void invalid
  })
})
