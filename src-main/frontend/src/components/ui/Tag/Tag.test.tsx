import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Tag } from './Tag'

describe('Tag', () => {
  it('renders its text', () => {
    render(<Tag>AI-generated</Tag>)
    expect(screen.getByText('AI-generated')).toBeInTheDocument()
  })
})
