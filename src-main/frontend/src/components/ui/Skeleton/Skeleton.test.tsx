import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Skeleton } from './Skeleton'

describe('Skeleton', () => {
  it('is hidden from assistive technology', () => {
    const { container } = render(<Skeleton width="10rem" />)
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true')
  })
})
