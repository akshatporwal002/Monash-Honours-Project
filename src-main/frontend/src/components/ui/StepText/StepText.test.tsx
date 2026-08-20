import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StepText } from './StepText'
import { submissionStateValues } from '../../../features/assessment/types'

describe('StepText', () => {
  it('renders every submission state as quiet workflow narration', () => {
    for (const state of submissionStateValues) {
      const { unmount, container } = render(<StepText state={state} />)
      expect(container.textContent).not.toBe('')
      unmount()
    }
  })

  it('never words a workflow state as an outcome', () => {
    for (const state of submissionStateValues) {
      const { unmount, container } = render(<StepText state={state} />)
      expect(container.textContent?.toLowerCase()).not.toMatch(/pass|incomplete|fail/)
      unmount()
    }
  })
})
