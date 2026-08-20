import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { EmptyState } from './EmptyState'

describe('EmptyState', () => {
  it('renders as a status region with title and description', () => {
    render(<EmptyState title="No records match" description="Clear a filter to see more." />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getByText('No records match')).toBeInTheDocument()
    expect(screen.getByText('Clear a filter to see more.')).toBeInTheDocument()
  })
})
