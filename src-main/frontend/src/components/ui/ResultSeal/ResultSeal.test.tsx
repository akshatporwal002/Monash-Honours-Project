import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ResultSeal } from './ResultSeal'
import type { AssessmentResult } from '../../../features/assessment/types'

describe('ResultSeal', () => {
  it('renders PASS as text + icon, with the confirmed lifecycle line', () => {
    const { container } = render(<ResultSeal result="PASS" lifecycle="CONFIRMED" />)
    expect(screen.getByText('Pass')).toBeInTheDocument()
    expect(screen.getByText('Confirmed by assessor')).toBeInTheDocument()
    expect(container.querySelector('svg')).not.toBeNull()
  })

  it('renders INCOMPLETE without any failure framing (AT19)', () => {
    const { container } = render(<ResultSeal result="INCOMPLETE" lifecycle="PROVISIONAL" />)
    expect(screen.getByText('Incomplete')).toBeInTheDocument()
    expect(screen.getByText('Provisional — awaiting assessor review')).toBeInTheDocument()
    expect(container.textContent?.toLowerCase()).not.toContain('fail')
  })

  it('conveys meaning by text and icon, not colour alone (AT24)', () => {
    const { container } = render(<ResultSeal result="INCOMPLETE" lifecycle="CONFIRMED" />)
    expect(container.textContent).toContain('Incomplete')
    expect(container.querySelector('svg')).not.toBeNull()
  })

  it('throws in dev on any value outside PASS/INCOMPLETE (AC19)', () => {
    expect(() =>
      render(<ResultSeal result={'FAIL' as AssessmentResult} lifecycle="CONFIRMED" />),
    ).toThrowError(/non-learner result/)
  })
})
