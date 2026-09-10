import { randomUUID } from 'node:crypto'

import AxeBuilder from '@axe-core/playwright'
import { expect, test, type APIRequestContext } from '@playwright/test'

import { apiUrl, webUrl } from './urls'

type CircuitTask = {
  id: string
  course_id: string
  task_type: string
  position: number
  access_status: string
  attempt_count: number
}

async function loginDemo(request: APIRequestContext, role: 'admin' | 'educator' | 'student') {
  const response = await request.post(`${apiUrl}/api/v1/auth/login`, {
    data: { email: `${role}@quantumlearn.demo`, password: 'quantumlearn-demo' },
  })
  expect(response.status()).toBe(200)
  expect((await response.json()).role).toBe(role === 'admin' ? 'administrator' : role)
  const csrf = (await request.storageState()).cookies.find(cookie => cookie.name === 'ql_csrf')?.value
  expect(csrf).toBeTruthy()
  return { Origin: webUrl, 'X-CSRF-Token': csrf! }
}

async function demoProgress(request: APIRequestContext) {
  await loginDemo(request, 'student')
  const response = await request.get(`${apiUrl}/api/v1/students/me/dashboard`)
  expect(response.ok()).toBeTruthy()
  const { tasks }: { tasks: CircuitTask[] } = await response.json()
  const circuit = tasks.find(task => task.task_type === 'quantum_circuit')!
  expect(circuit).toBeTruthy()
  return {
    courseId: circuit.course_id,
    tasks: tasks.map(({ id, access_status, attempt_count }) => ({ id, access_status, attempt_count })),
  }
}

test('keyboard and drag place the same gates on q1 with named removal and preserved simulation', async ({ page, request }, testInfo) => {
  test.setTimeout(90_000)
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const demoBefore = await demoProgress(request)
  // Each project/retry gets a separate learner through the real account and
  // owning-educator enrolment routes. Shared demo progress stays untouched.
  const email = `circuit-${randomUUID()}@example.com`
  const password = randomUUID()
  const created = await request.post(`${apiUrl}/api/v1/admin/users`, {
    headers: await loginDemo(request, 'admin'),
    data: { email, password, full_name: 'Circuit browser learner', role: 'student' },
  })
  expect(created.status(), await created.text()).toBe(201)
  const learner = await created.json()
  const enrolled = await request.post(`${apiUrl}/api/v1/courses/${demoBefore.courseId}/enrollments`, {
    headers: await loginDemo(request, 'educator'), data: { student_id: learner.id },
  })
  expect(enrolled.status(), await enrolled.text()).toBe(201)
  await page.goto('/login')
  await page.getByRole('radio', { name: 'Student', exact: true }).check()
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).toHaveURL(/\/student$/)
  const dashboardResponse = await page.request.get('/api/v1/students/me/dashboard')
  expect(dashboardResponse.ok()).toBeTruthy()
  const dashboard = await dashboardResponse.json()
  const tasks: CircuitTask[] = dashboard.tasks
  expect(tasks.every(task => task.attempt_count === 0)).toBeTruthy()
  const circuit = tasks.find(task => task.task_type === 'quantum_circuit')!
  expect(circuit).toBeTruthy()
  expect(circuit.course_id).toBe(demoBefore.courseId)
  expect(circuit.access_status).toBe('locked')
  // Supported API submissions unlock the existing demo pathway; no fixture or
  // production access rule is overridden for this test's learner.
  const answers: Record<string, { answer: string; code?: string }> = {
    multiple_choice: { answer: 'b' },
    multiple_answer: { answer: '["a","c"]' },
    short_answer: { answer: 'A Hadamard gate creates a superposition.' },
    code_explanation: { answer: 'Hadamard creates superposition and measurement returns a classical result.' },
    code_completion: { answer: '', code: 'from qiskit import QuantumCircuit\ncircuit = QuantumCircuit(1, 1)\ncircuit.h(0)\ncircuit.measure(0, 0)' },
  }
  const csrf = (await page.context().cookies()).find(cookie => cookie.name === 'ql_csrf')!.value
  for (const task of tasks.filter(task => task.position < circuit.position).sort((a, b) => a.position - b.position)) {
    if (task.access_status === 'completed') continue
    const response = await page.request.post(`/api/v1/students/me/tasks/${task.id}/submissions`, {
      headers: { Origin: webUrl, 'X-CSRF-Token': csrf }, data: answers[task.task_type],
    })
    expect(response.status(), `Prerequisite ${task.task_type}: ${await response.text()}`).toBe(201)
  }
  const draftLoaded = page.waitForResponse(response => response.request().method() === 'GET' && response.url().endsWith(`/tasks/${circuit.id}/draft`))
  await page.goto(`/student/tasks/${circuit.id}`)
  await expect(page.getByRole('heading', { name: 'Build a superposition circuit' })).toBeVisible()
  expect((await draftLoaded).ok()).toBeTruthy()
  const clear = page.getByRole('button', { name: 'Clear', exact: true })
  const addH = page.getByRole('button', { name: 'Add H gate', exact: true })
  const wire1 = page.getByText('|0⟩ q1', { exact: true }).locator('..')
  await clear.click()
  const transfer = await page.evaluateHandle(() => new DataTransfer())
  await addH.dispatchEvent('dragstart', { dataTransfer: transfer })
  await wire1.dispatchEvent('drop', { dataTransfer: transfer })
  await transfer.dispose()
  async function save() {
    const receipt = page.waitForResponse(response => response.request().method() === 'PUT' && response.url().endsWith('/draft'))
    await page.getByRole('button', { name: 'Save draft', exact: true }).focus()
    await page.keyboard.press('Enter')
    const response = await receipt
    expect(response.ok()).toBeTruthy()
    return response.json()
  }
  const dragged = await save()
  expect(dragged.circuit.operations).toEqual([{ gate: 'h', targets: [1] }])
  await testInfo.attach('drag-q1-receipt', { body: JSON.stringify({ circuit: dragged.circuit }), contentType: 'application/json' })
  await clear.focus()
  await page.keyboard.press('Enter')
  const target = page.getByRole('combobox', { name: 'Target qubit for H and X' })
  if (await target.count()) {
    await target.focus()
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('Tab')
    await expect(target).toHaveValue('1')
    await expect(addH).toBeFocused()
  } else {
    // Baseline reproduction: the only keyboard add action defaults to q0.
    await addH.focus()
  }
  await page.keyboard.press('Enter')
  const keyboard = await save()
  await testInfo.attach('keyboard-receipt', { body: JSON.stringify({ circuit: keyboard.circuit }), contentType: 'application/json' })
  expect(keyboard.circuit).toEqual(dragged.circuit)
  await page.reload()
  await expect(page.getByRole('button', { name: 'Remove gate 1: H on qubit 1' })).toBeVisible()
  const run = page.getByRole('button', { name: 'Run 1,024 shots' })
  await run.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByText('Simulation completed and saved with 1,024 shots.')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('table', { name: 'Exact probabilities and sampled frequencies' })).toBeVisible()
  await page.getByRole('button', { name: 'Add CX gate', exact: true }).focus()
  await page.keyboard.press('Enter')
  expect((await save()).circuit.operations).toEqual([{ gate: 'h', targets: [1] }, { gate: 'cx', targets: [0, 1] }])
  await page.getByRole('button', { name: 'Remove gate 2: CX, control qubit 0, target qubit 1 (target on qubit 1)' }).focus()
  await page.keyboard.press('Enter')
  expect((await save()).circuit.operations).toEqual([{ gate: 'h', targets: [1] }])
  await clear.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByTitle('Remove gate', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Save draft', exact: true })).toBeDisabled()
  await expect(run).toBeDisabled()
  expect((await new AxeBuilder({ page }).include('main').withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze()).violations).toEqual([])
  await page.screenshot({ path: testInfo.outputPath('circuit-keyboard.png'), fullPage: true })
  expect(errors).toEqual([])
  expect((await demoProgress(request)).tasks).toEqual(demoBefore.tasks)
})
