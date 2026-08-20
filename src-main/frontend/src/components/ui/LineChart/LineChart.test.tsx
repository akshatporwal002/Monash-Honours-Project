import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { LineChart } from './LineChart'

describe('LineChart', () => {
  it('renders a table equivalent carrying the same series values', () => {
    render(
      <LineChart
        title="Weekly engagement"
        labels={['Mon', 'Tue', 'Wed']}
        series={[
          { label: 'Active students', values: [3, 5, 2] },
          { label: 'Submissions', values: [1, 4, 0] },
        ]}
      />,
    )
    const table = screen.getByRole('table', { name: 'Weekly engagement' })
    expect(within(table).getByRole('columnheader', { name: 'Active students' })).toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: 'Submissions' })).toBeInTheDocument()
    const tuesday = within(table).getByRole('row', { name: /Tue/ })
    const cells = within(tuesday).getAllByRole('cell')
    expect(cells.map((cell) => cell.textContent)).toEqual(['5', '4'])
    expect(within(table).getAllByRole('row')).toHaveLength(4)
  })

  it('renders a single data point without NaN coordinates', () => {
    const { container } = render(
      <LineChart
        title="One week"
        labels={['Week 1']}
        series={[{ label: 'Submissions', values: [7] }]}
      />,
    )
    const polyline = container.querySelector('polyline')
    expect(polyline?.getAttribute('points')).not.toMatch(/NaN/)
    expect(container.innerHTML).not.toContain('NaN')
  })

  it('renders an all-zero series without NaN coordinates', () => {
    const { container } = render(
      <LineChart
        title="Quiet fortnight"
        labels={['Week 1', 'Week 2']}
        series={[
          { label: 'Active students', values: [0, 0] },
          { label: 'Submissions', values: [0, 0] },
        ]}
      />,
    )
    for (const polyline of container.querySelectorAll('polyline')) {
      expect(polyline.getAttribute('points')).not.toMatch(/NaN/)
    }
    const table = screen.getByRole('table', { name: 'Quiet fortnight' })
    expect(within(table).getAllByRole('cell').map((cell) => cell.textContent)).toEqual([
      '0',
      '0',
      '0',
      '0',
    ])
  })
})
