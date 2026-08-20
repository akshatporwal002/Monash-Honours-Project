import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { Tabs } from './Tabs'

function Harness() {
  const [value, setValue] = useState('evidence')
  return (
    <Tabs
      label="Progress areas"
      value={value}
      onValueChange={setValue}
      tabs={[
        { value: 'evidence', label: 'Evidence', content: <p>Evidence list</p> },
        { value: 'results', label: 'Formal results', content: <p>Results list</p> },
      ]}
    />
  )
}

describe('Tabs', () => {
  it('renders a labelled tablist and switches panels', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    expect(screen.getByRole('tablist', { name: 'Progress areas' })).toBeInTheDocument()
    expect(screen.getByText('Evidence list')).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: 'Formal results' }))
    expect(screen.getByText('Results list')).toBeInTheDocument()
  })
})
