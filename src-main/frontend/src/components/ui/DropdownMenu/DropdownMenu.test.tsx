import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { DropdownMenu } from './DropdownMenu'
import { Button } from '../Button/Button'

describe('DropdownMenu', () => {
  it('opens from its trigger and fires the item action', async () => {
    const onSelect = vi.fn()
    const user = userEvent.setup()
    render(
      <DropdownMenu
        trigger={<Button>Actions</Button>}
        items={[{ label: 'Archive course', onSelect, danger: true }]}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Actions' }))
    await user.click(screen.getByRole('menuitem', { name: 'Archive course' }))
    expect(onSelect).toHaveBeenCalledOnce()
  })
})
