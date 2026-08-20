import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ToastProvider } from './Toast'
import { useToast } from './toastContext'
import { Button } from '../Button/Button'

function Trigger() {
  const { toast } = useToast()
  return <Button onClick={() => toast('Changes saved')}>Save changes</Button>
}

describe('Toast', () => {
  it('announces a message after an action', async () => {
    const user = userEvent.setup()
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    )
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText('Changes saved')).toBeInTheDocument()
  })
})
