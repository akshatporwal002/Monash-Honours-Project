import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { LifecycleTag } from './LifecycleTag'

describe('LifecycleTag', () => {
  it('renders each lifecycle state as plain text', () => {
    render(<LifecycleTag lifecycle="OVERRIDDEN" />)
    expect(screen.getByText('Overridden')).toBeInTheDocument()
  })
})
