import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Button } from './Button'

describe('Button', () => {
  it('renders an accessible button with its label', () => {
    render(<Button variant="primary">Save changes</Button>)
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeInTheDocument()
  })

  it('defaults to type="button" so it cannot submit forms accidentally', () => {
    render(<Button>Open</Button>)
    expect(screen.getByRole('button')).toHaveAttribute('type', 'button')
  })

  it('loading disables the button and sets aria-busy', () => {
    const onClick = vi.fn()
    render(
      <Button loading onClick={onClick}>
        Publishing
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Publishing' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
  })

  it('fires onClick when enabled', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(<Button onClick={onClick}>Go</Button>)
    await user.click(screen.getByRole('button', { name: 'Go' }))
    expect(onClick).toHaveBeenCalledOnce()
  })
})
