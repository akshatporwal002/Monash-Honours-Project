import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Input } from './Input'

describe('Input', () => {
  it('renders a textbox and forwards native props', () => {
    render(<Input aria-label="Course title" placeholder="e.g. Quantum foundations" />)
    expect(screen.getByRole('textbox', { name: 'Course title' })).toHaveAttribute(
      'placeholder',
      'e.g. Quantum foundations',
    )
  })
})
