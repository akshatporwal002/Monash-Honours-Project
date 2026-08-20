import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { Dialog } from './Dialog'
import { Button } from '../Button/Button'

function Harness() {
  const [open, setOpen] = useState(false)
  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      trigger={<Button>Open dialog</Button>}
      title="Edit outcome"
      description="Update the wording."
    >
      <p>Body content</p>
    </Dialog>
  )
}

describe('Dialog', () => {
  it('opens as an accessible dialog, closes on Escape, and returns focus to the trigger', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const trigger = screen.getByRole('button', { name: 'Open dialog' })
    await user.click(trigger)
    expect(screen.getByRole('dialog', { name: 'Edit outcome' })).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await waitFor(() => expect(trigger).toHaveFocus())
  })

  it('has a labelled close control', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole('button', { name: 'Open dialog' }))
    await user.click(screen.getByRole('button', { name: 'Close dialog' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
