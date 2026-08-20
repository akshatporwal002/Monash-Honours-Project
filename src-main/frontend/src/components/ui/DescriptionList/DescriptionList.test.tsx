import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DescriptionList } from './DescriptionList'

describe('DescriptionList', () => {
  it('renders terms and descriptions as a definition list', () => {
    render(
      <DescriptionList
        items={[
          { term: 'Purpose', description: 'Summative' },
          { term: 'Target', description: 'Analyse' },
        ]}
      />,
    )
    expect(screen.getByText('Purpose')).toBeInTheDocument()
    expect(screen.getByText('Summative')).toBeInTheDocument()
  })

  it('renders long values in full — no truncation', () => {
    const long = 'Identify the incorrect measurement assumption in the presented circuit and explain, '.repeat(4)
    render(<DescriptionList items={[{ term: 'Criterion', description: long }]} />)
    expect(screen.getByText(long.trim(), { exact: false })).toBeInTheDocument()
  })
})
