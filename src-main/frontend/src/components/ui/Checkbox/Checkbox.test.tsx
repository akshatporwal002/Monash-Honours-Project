import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Checkbox } from './Checkbox'

describe('Checkbox', () => {
  it('is labelled and toggles', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Checkbox label="I verified the Bloom process" onChange={onChange} />)
    const box = screen.getByRole('checkbox', { name: 'I verified the Bloom process' })
    await user.click(box)
    expect(onChange).toHaveBeenCalledOnce()
  })
})
