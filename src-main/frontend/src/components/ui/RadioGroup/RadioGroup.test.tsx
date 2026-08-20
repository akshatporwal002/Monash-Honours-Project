import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { RadioGroup } from './RadioGroup'

describe('RadioGroup', () => {
  it('renders a fieldset with legend and selects by click', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <RadioGroup
        legend="Response format"
        name="format"
        value="text"
        onChange={onChange}
        options={[
          { value: 'text', label: 'Written response' },
          { value: 'circuit', label: 'Circuit' },
        ]}
      />,
    )
    expect(screen.getByRole('group', { name: 'Response format' })).toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: 'Circuit' }))
    expect(onChange).toHaveBeenCalledWith('circuit')
  })
})
