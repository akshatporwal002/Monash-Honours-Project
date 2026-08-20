import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { BarList } from './BarList'

describe('BarList', () => {
  it('renders every label with its visible value', () => {
    render(
      <BarList
        max={100}
        items={[
          { label: 'On track', value: 60, display: '12 (60%)' },
          { label: 'At risk', value: 25, display: '5 (25%)' },
        ]}
      />,
    )
    expect(screen.getByText('On track')).toBeInTheDocument()
    expect(screen.getByText('12 (60%)')).toBeInTheDocument()
    expect(screen.getByText('At risk')).toBeInTheDocument()
    expect(screen.getByText('5 (25%)')).toBeInTheDocument()
  })

  it('renders an all-zero series without NaN widths', () => {
    const { container } = render(
      <BarList
        items={[
          { label: 'Quizzes', value: 0 },
          { label: 'Circuits', value: 0 },
        ]}
      />,
    )
    expect(container.innerHTML).not.toContain('NaN')
    expect(screen.getAllByText('0')).toHaveLength(2)
  })
})
