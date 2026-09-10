import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AdminWorkspace } from './AdminWorkspace'

const fetched = {
  llm_provider: 'compatible-provider', llm_model: '', points_per_level: 750,
  reminders_enabled: false, provider_timeout_seconds: 17, max_infrastructure_attempts: 2,
}
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
})

function mockApi(save?: (init?: RequestInit) => Promise<Response>, settings = fetched) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/admin/users') || url.endsWith('/courses')) return json([])
    if (url.endsWith('/admin/settings')) {
      if (init?.method === 'PUT') {
        if (save) return save(init)
        return json({ ...settings, ...JSON.parse(String(init.body)) })
      }
      return json(settings)
    }
    throw new Error(`Unexpected request: ${url}`)
  })
}
const timeout = () => screen.getByRole('spinbutton', { name: /Provider timeout/ })
const attempts = () => screen.getByRole('spinbutton', { name: /Infrastructure attempts/ })
const saveButton = () => screen.getByRole('button', { name: 'Save settings' })

afterEach(() => { cleanup(); vi.restoreAllMocks() })

test('shows fetched limits and accessible bounds, preserves unknown provider and saves only edits', async () => {
  const fetch = mockApi()
  render(<AdminWorkspace section="settings" />)
  await screen.findByRole('spinbutton', { name: /Provider timeout/ })
  expect(timeout()).toHaveValue(17)
  expect(attempts()).toHaveValue(2)
  expect(timeout()).toHaveAttribute('min', '1')
  expect(timeout()).toHaveAttribute('max', '60')
  expect(attempts()).toHaveAttribute('max', '3')
  expect(attempts()).toHaveAccessibleDescription(/including the first/)
  expect(screen.getByRole('combobox', { name: 'Provider' })).toHaveTextContent('compatible-provider')
  expect(screen.queryByRole('spinbutton', { name: /budget|billing|cost/i })).not.toBeInTheDocument()
  const user = userEvent.setup()
  await user.clear(timeout()); await user.type(timeout(), '9')
  await user.click(saveButton())
  expect(await screen.findByRole('status')).toHaveTextContent('System settings saved.')
  const writes = fetch.mock.calls.filter(([, init]) => init?.method === 'PUT')
  expect(writes).toHaveLength(1)
  expect(JSON.parse(String(writes[0][1]?.body))).toEqual({ provider_timeout_seconds: 9 })
  expect(attempts()).toHaveValue(2)
  expect(screen.getByRole('spinbutton', { name: 'Points required per level' })).toHaveValue(750)
  expect(screen.getByRole('checkbox', { name: /Automatic overdue reminders/ })).not.toBeChecked()
})

test.each(['', '0', '61', '1.5'])('rejects invalid timeout %j without writing', async (value) => {
  const fetch = mockApi()
  render(<AdminWorkspace section="settings" />)
  await screen.findByRole('spinbutton', { name: /Provider timeout/ })
  fireEvent.change(timeout(), { target: { value } })
  expect(timeout()).toHaveAttribute('aria-invalid', 'true')
  expect(timeout()).toHaveAccessibleDescription(/whole number from 1 to 60/)
  expect(saveButton()).toBeDisabled()
  fireEvent.submit(screen.getByRole('form', { name: 'System settings' }))
  expect(fetch.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(0)
})

test.each(['', '0', '4', '1.5'])('rejects invalid attempt count %j without writing', async (value) => {
  const fetch = mockApi()
  render(<AdminWorkspace section="settings" />)
  await screen.findByRole('spinbutton', { name: /Infrastructure attempts/ })
  fireEvent.change(attempts(), { target: { value } })
  expect(attempts()).toHaveAttribute('aria-invalid', 'true')
  expect(saveButton()).toBeDisabled()
  fireEvent.submit(screen.getByRole('form', { name: 'System settings' }))
  expect(fetch.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(0)
})

test('locks all fields while saving and keeps edits after a rejected save for retry', async () => {
  let finish: (value: Response) => void = () => { throw new Error('No pending save') }
  const write = vi.fn<(init?: RequestInit) => Promise<Response>>()
    .mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    .mockImplementation(async (init) => json({ ...fetched, ...JSON.parse(String(init?.body)) }))
  mockApi(write)
  render(<AdminWorkspace section="settings" />)
  await screen.findByRole('spinbutton', { name: /Infrastructure attempts/ })
  const user = userEvent.setup()
  await user.clear(attempts()); await user.type(attempts(), '1')
  await user.click(saveButton())
  await waitFor(() => expect(write).toHaveBeenCalledOnce())
  expect(screen.getByRole('form')).toHaveAttribute('aria-busy', 'true')
  expect(timeout()).toBeDisabled()
  expect(attempts()).toBeDisabled()
  expect(screen.getByRole('textbox', { name: 'Model' })).toBeDisabled()
  await act(async () => { finish(json({ detail: 'Synthetic save rejected' }, 503)) })
  expect(await screen.findByRole('alert')).toHaveTextContent('Synthetic save rejected')
  expect(attempts()).toHaveValue(1)
  expect(timeout()).toHaveValue(17)
  expect(saveButton()).toBeEnabled()
  await user.click(saveButton())
  expect(await screen.findByRole('status')).toHaveTextContent('System settings saved.')
  expect(write).toHaveBeenCalledTimes(2)
  expect(JSON.parse(String(write.mock.calls[1][0]?.body))).toEqual({ max_infrastructure_attempts: 1 })
})

test('missing runtime values fail visibly without inventing defaults or allowing saves', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) =>
    String(input).endsWith('/admin/settings') ? json({ llm_provider: 'local', llm_model: 'template' }) : json([]))
  render(<AdminWorkspace section="settings" />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Runtime settings could not be read')
  expect(screen.queryByRole('button', { name: 'Save settings' })).not.toBeInTheDocument()
  expect(fetch.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(0)
})
