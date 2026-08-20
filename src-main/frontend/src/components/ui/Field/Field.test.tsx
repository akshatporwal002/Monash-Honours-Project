import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Field } from './Field'
import { Input } from '../Input/Input'

describe('Field', () => {
  it('wires the label to its control', () => {
    render(
      <Field label="Outcome wording">
        <Input />
      </Field>,
    )
    expect(screen.getByLabelText('Outcome wording')).toBeInTheDocument()
  })

  it('wires help and error into aria-describedby and sets aria-invalid', () => {
    render(
      <Field label="Claim" help="What the learner will show." error="Claim is needed before approval.">
        <Input />
      </Field>,
    )
    const input = screen.getByLabelText(/Claim/)
    const describedBy = input.getAttribute('aria-describedby') ?? ''
    expect(describedBy.split(' ')).toHaveLength(2)
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText('What the learner will show.')).toBeInTheDocument()
    expect(screen.getByText('Claim is needed before approval.')).toBeInTheDocument()
  })

  it('marks required fields accessibly and in the visible label', () => {
    render(
      <Field label="Pass rule" required>
        <Input />
      </Field>,
    )
    const input = screen.getByLabelText(/Pass rule/)
    expect(input).toHaveAttribute('aria-required', 'true')
    expect(screen.getByText('(required)')).toBeInTheDocument()
  })
})
