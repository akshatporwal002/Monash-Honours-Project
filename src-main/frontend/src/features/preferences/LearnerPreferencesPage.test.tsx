import { render, screen } from '@testing-library/react'
import { api } from '../../app/api'
import { LearnerPreferencesPage } from './LearnerPreferencesPage'

it('announces a failed preference load instead of an endless loading message', async () => {
  vi.spyOn(api.preferences, 'read').mockRejectedValue(new Error('offline'))
  render(<LearnerPreferencesPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Preferences could not be loaded.')
  expect(screen.queryByText(/Loading learning preferences/)).not.toBeInTheDocument()
})
