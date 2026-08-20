import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ErrorState } from './ErrorState'

describe('ErrorState', () => {
  it('renders as an alert and retries', async () => {
    const onRetry = vi.fn()
    const user = userEvent.setup()
    render(<ErrorState title="The queue did not load" description="Check your connection." onRetry={onRetry} />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })
})
