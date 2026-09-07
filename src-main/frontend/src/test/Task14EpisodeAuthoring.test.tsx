import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { EpisodePlanEditor } from '../components/EpisodePlanEditor'

function Editor({ initial = {}, changed }: { initial?: Record<string, unknown>; changed: (value: Record<string, unknown>) => void }) {
  const [value, setValue] = useState(initial)
  return <EpisodePlanEditor value={value} disabled={false} onChange={(next) => { setValue(next); changed(next) }} />
}

describe('reviewed episode authoring', () => {
  it('offers keyboard controls and saves separate fresh content, support, and private guidance', async () => {
    const user = userEvent.setup()
    const changed = vi.fn()
    render(<Editor initial={{ required_keywords: ['Hadamard'] }} changed={changed} />)
    await user.tab()
    expect(screen.getByRole('checkbox', { name: 'Include a separate unaided transfer stage' })).toHaveFocus()
    await user.keyboard(' ')
    await user.type(screen.getByLabelText('Fresh transfer prompt (required)'), 'Apply H to a fresh input.')
    await user.type(screen.getByLabelText('Fresh transfer starter code'), '  h(0)\n')
    await user.type(screen.getByLabelText('Approved conceptual hints'), 'Consider the input state.')
    await user.type(screen.getByLabelText('Accessibility support for both stages'), 'Circuit text')
    await user.type(screen.getByLabelText('Private transfer solution'), 'Reviewer-only guidance')
    await user.click(screen.getByRole('button', { name: 'Add transfer starter circuit' }))
    expect(changed.mock.lastCall?.[0]).toMatchObject({
      required_keywords: ['Hadamard'],
      episode_plan: {
        prediction_required: true, required_responses: ['prediction', 'explanation'],
        supported_hints: ['Consider the input state.'], accessibility_support: ['Circuit text'],
        transfer: { prompt: 'Apply H to a fresh input.', starter_code: '  h(0)\n',
          starter_circuit: { qubits: 1, operations: [] }, solution: { answer: 'Reviewer-only guidance' } },
      },
    })
  })

  it('preserves private code and circuit guidance during text edits, and removes only the chosen plan', async () => {
    const user = userEvent.setup()
    const changed = vi.fn()
    const solution = { answer: 'Old guidance', code: '  h(0)\n', circuit: { qubits: 1, operations: [] } }
    render(<Editor initial={{ required_keywords: ['H'], episode_plan: {
      transfer: { prompt: 'Fresh prompt', solution }, supported_hints: [], accessibility_support: [],
    } }} changed={changed} />)
    await user.type(screen.getByLabelText('Fresh transfer prompt (required)'), ' updated')
    expect(changed.mock.lastCall?.[0]).toMatchObject({ episode_plan: { transfer: { solution } } })
    await user.click(screen.getByRole('checkbox', { name: 'Include a separate unaided transfer stage' }))
    expect(changed.mock.lastCall?.[0]).toEqual({ required_keywords: ['H'] })
    expect(screen.queryByLabelText('Fresh transfer prompt (required)')).not.toBeInTheDocument()
  })
})
