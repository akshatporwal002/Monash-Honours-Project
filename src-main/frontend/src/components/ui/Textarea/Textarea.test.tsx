import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Textarea } from './Textarea'

describe('Textarea', () => {
  it('renders a multiline textbox', () => {
    render(<Textarea aria-label="Reason" />)
    expect(screen.getByRole('textbox', { name: 'Reason' }).tagName).toBe('TEXTAREA')
  })
})
