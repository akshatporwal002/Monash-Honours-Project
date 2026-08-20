import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Prose } from './Prose'

describe('Prose', () => {
  it('renders its children', () => {
    render(
      <Prose>
        <p>Feedback body</p>
      </Prose>,
    )
    expect(screen.getByText('Feedback body')).toBeInTheDocument()
  })
})
