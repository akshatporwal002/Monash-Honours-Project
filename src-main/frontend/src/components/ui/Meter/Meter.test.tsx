import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Meter } from './Meter'

describe('Meter', () => {
  it('exposes a labelled meter with count-based value text', () => {
    render(<Meter value={3} max={8} label="Tasks completed" />)
    const meter = screen.getByRole('meter', { name: 'Tasks completed' })
    expect(meter).toHaveAttribute('aria-valuenow', '3')
    expect(meter).toHaveAttribute('aria-valuetext', '3 of 8')
    expect(screen.getByText('3 of 8')).toBeInTheDocument()
  })

  it('clamps out-of-range values', () => {
    render(<Meter value={12} max={8} label="Steps" />)
    expect(screen.getByRole('meter')).toHaveAttribute('aria-valuenow', '8')
  })
})
