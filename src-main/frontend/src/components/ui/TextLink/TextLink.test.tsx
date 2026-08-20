import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { TextLink } from './TextLink'

describe('TextLink', () => {
  it('renders a real anchor with its href', () => {
    render(<TextLink href="/student/progress">View progress</TextLink>)
    expect(screen.getByRole('link', { name: 'View progress' })).toHaveAttribute('href', '/student/progress')
  })
})
