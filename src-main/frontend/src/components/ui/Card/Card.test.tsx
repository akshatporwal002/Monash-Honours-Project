import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Card } from './Card'

describe('Card', () => {
  it('renders eyebrow, heading, and children', () => {
    render(
      <Card eyebrow="Evidence" heading="Criterion decisions">
        <p>Body</p>
      </Card>,
    )
    expect(screen.getByText('Evidence')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Criterion decisions' })).toBeInTheDocument()
    expect(screen.getByText('Body')).toBeInTheDocument()
  })

  it('renders no header block when only children are given', () => {
    const { container } = render(<Card>plain</Card>)
    expect(container.querySelector('header')).toBeNull()
  })
})
