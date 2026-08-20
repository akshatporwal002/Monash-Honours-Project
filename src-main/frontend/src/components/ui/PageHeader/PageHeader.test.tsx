import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PageHeader } from './PageHeader'

describe('PageHeader', () => {
  it('renders the title as the page h1', () => {
    render(<PageHeader eyebrow="Assessment" title="Review queue" description="Records awaiting action" />)
    expect(screen.getByRole('heading', { level: 1, name: 'Review queue' })).toBeInTheDocument()
    expect(screen.getByText('Assessment')).toBeInTheDocument()
    expect(screen.getByText('Records awaiting action')).toBeInTheDocument()
  })
})
