import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { SearchInput } from './SearchInput'

describe('SearchInput', () => {
  it('renders a labelled search box', () => {
    render(<SearchInput label="Search students" placeholder="Name or email" />)
    expect(screen.getByRole('searchbox', { name: 'Search students' })).toBeInTheDocument()
  })
})
