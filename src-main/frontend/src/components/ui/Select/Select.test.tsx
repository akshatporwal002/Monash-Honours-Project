import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { Select } from './Select'

function Harness() {
  const [value, setValue] = useState<string | undefined>(undefined)
  return (
    <Select
      aria-label="Bloom process"
      placeholder="Choose a process"
      value={value}
      onValueChange={setValue}
      options={[
        { value: 'ANALYSE', label: 'Analyse' },
        { value: 'EVALUATE', label: 'Evaluate' },
      ]}
    />
  )
}

describe('Select', () => {
  it('is a labelled combobox that opens and selects with the keyboard', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const trigger = screen.getByRole('combobox', { name: 'Bloom process' })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    await user.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    await user.click(screen.getByRole('option', { name: 'Analyse' }))
    expect(trigger).toHaveTextContent('Analyse')
  })
})
