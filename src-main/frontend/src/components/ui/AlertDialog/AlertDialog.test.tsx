import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { AlertDialog } from './AlertDialog'

describe('AlertDialog', () => {
  it('renders an alertdialog with confirm and cancel', () => {
    render(
      <AlertDialog
        open
        onOpenChange={() => {}}
        title="Archive course?"
        description="Learners keep read access."
        confirmLabel="Archive course"
        onConfirm={() => {}}
      />,
    )
    expect(screen.getByRole('alertdialog', { name: 'Archive course?' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Archive course' })).toBeEnabled()
  })

  it('keeps confirm disabled until a required reason has text, then passes it through (D2 §14.2)', async () => {
    const onConfirm = vi.fn()
    const user = userEvent.setup()
    render(
      <AlertDialog
        open
        onOpenChange={() => {}}
        title="Override result"
        tone="danger"
        confirmLabel="Override result"
        reasonLabel="Reason for override"
        onConfirm={onConfirm}
      />,
    )
    const confirm = screen.getByRole('button', { name: 'Override result' })
    expect(confirm).toBeDisabled()
    await user.type(screen.getByLabelText(/Reason for override/), 'Evidence shows the criterion was met.')
    expect(confirm).toBeEnabled()
    await user.click(confirm)
    expect(onConfirm).toHaveBeenCalledWith('Evidence shows the criterion was met.')
  })
})
