import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { SystemTag } from './SystemTag'

describe('SystemTag', () => {
  it('renders execution outcomes in the system namespace', () => {
    render(<SystemTag outcome="FAILED" />)
    expect(screen.getByText('failed')).toBeInTheDocument()
  })
})
