import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { IconButton } from './IconButton'

describe('IconButton', () => {
  it('exposes its accessible name via the required label prop', () => {
    render(<IconButton label="Close panel">×</IconButton>)
    expect(screen.getByRole('button', { name: 'Close panel' })).toBeInTheDocument()
  })

  it('hides the glyph from assistive technology', () => {
    render(<IconButton label="Close">×</IconButton>)
    const glyphWrapper = screen.getByRole('button').querySelector('[aria-hidden="true"]')
    expect(glyphWrapper).not.toBeNull()
  })
})
