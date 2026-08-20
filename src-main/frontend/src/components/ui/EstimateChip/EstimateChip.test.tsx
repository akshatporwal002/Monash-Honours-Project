import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { EstimateChip } from './EstimateChip'

describe('EstimateChip', () => {
  it('always shows the estimate with its uncertainty (NFR27)', () => {
    render(<EstimateChip uncertainty="Low confidence — 2 observations">Developing</EstimateChip>)
    expect(screen.getByText('Developing')).toBeInTheDocument()
    expect(screen.getByText('Low confidence — 2 observations')).toBeInTheDocument()
  })

  it('cannot be rendered without uncertainty wording', () => {
    // @ts-expect-error — uncertainty is a required prop by design
    void (<EstimateChip>Developing</EstimateChip>)
  })
})
