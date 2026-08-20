import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { Tooltip } from './Tooltip'
import { Button } from '../Button/Button'

describe('Tooltip', () => {
  it('shows its content on focus', async () => {
    const user = userEvent.setup()
    render(
      <Tooltip content="Opens the review queue">
        <Button>Review</Button>
      </Tooltip>,
    )
    await user.tab()
    expect(await screen.findByRole('tooltip')).toBeInTheDocument()
  })
})
