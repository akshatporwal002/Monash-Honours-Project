import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Stepper } from './Stepper'

describe('Stepper', () => {
  it('marks the current step with aria-current', () => {
    render(<Stepper steps={[{ label: 'Details' }, { label: 'Materials' }, { label: 'Publish' }]} current={1} />)
    const items = screen.getAllByRole('listitem')
    expect(items[1]).toHaveAttribute('aria-current', 'step')
    expect(items[0]).not.toHaveAttribute('aria-current')
  })
})
