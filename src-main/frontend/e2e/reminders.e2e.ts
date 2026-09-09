import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

async function signIn(
  page: Page,
  role: 'Student' | 'Educator',
  email: string,
  password: string,
) {
  await page.goto('/login')
  await page.getByRole('radio', { name: role, exact: true }).check()
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).not.toHaveURL(/\/login$/)
}

test('reminder opt-out survives reload and leaves task access available', async ({
  page,
  request,
}) => {
  const response = await request.post(
    'http://127.0.0.1:4180/e2e/human-workflows-fixture',
  )
  expect(response.ok()).toBeTruthy()
  const fixture = await response.json()
  await signIn(page, 'Student', fixture.student_email, fixture.student_password)
  await page.goto('/student/preferences')
  const settings = page.getByRole('region', {
    name: 'Task reminders',
    exact: true,
  })
  await settings
    .getByRole('checkbox', { name: 'Receive task reminders' })
    .uncheck()
  await settings.getByRole('button', { name: 'Save reminder settings' }).click()
  await expect(settings).toContainText('Reminder settings saved.')
  await page.reload()
  await expect(settings.getByRole('checkbox')).not.toBeChecked()
  expect(
    (await new AxeBuilder({ page }).include('main').analyze()).violations,
  ).toEqual([])
  await page.goto(`/student/tasks/${fixture.fresh_task_id}`)
  await expect(
    page.getByRole('button', { name: 'Submit activity', exact: true }),
  ).toBeVisible()
})

test('educator extension persists and learner sees only the public notice in course time', async ({
  page,
  browser,
  request,
}) => {
  test.setTimeout(90_000)
  const response = await request.post(
    'http://127.0.0.1:4180/e2e/human-workflows-fixture',
  )
  expect(response.ok()).toBeTruthy()
  const fixture = await response.json()
  await signIn(
    page,
    'Educator',
    fixture.educator_email,
    fixture.educator_password,
  )
  await page.goto('/educator/courses')
  await page.getByRole('combobox', { name: 'Choose a course to edit' }).click()
  await page
    .getByRole('option')
    .filter({ hasNotText: 'New course' })
    .first()
    .click()
  const code = page.getByLabel('Course code', { exact: true })
  await code.fill((await code.inputValue()).toUpperCase())
  await page
    .getByLabel('Course time zone', { exact: true })
    .fill('Australia/Sydney')
  await page
    .getByLabel('Description', { exact: true })
    .fill('Quantum evidence and individual learning arrangements.')
  await page.getByRole('button', { name: 'Save and add materials' }).click()
  await expect(
    page.getByRole('heading', { name: 'Learning materials', exact: true }),
  ).toBeVisible()
  await page
    .getByRole('button', { name: 'Manage individual deadlines' })
    .click()
  const panel = page.getByRole('region', {
    name: 'Individual deadlines',
    exact: true,
  })
  await panel.getByRole('combobox', { name: 'Learner', exact: true }).click()
  await page.getByRole('option').first().click()
  await panel.getByRole('combobox', { name: 'Task', exact: true }).click()
  await page
    .getByRole('option', {
      name: 'Fresh interference explanation',
      exact: true,
    })
    .click()
  await panel
    .getByLabel('Extended deadline (Australia/Sydney)', { exact: true })
    .fill('2035-01-05T17:00')
  await panel
    .getByLabel('Private staff reason', { exact: true })
    .fill('PRIVATE scheduling review')
  await panel
    .getByLabel('Notice shown to the learner', { exact: true })
    .fill('Your extended deadline is approved.')
  await panel
    .getByRole('button', { name: 'Save arrangement', exact: true })
    .click()
  await expect(panel).toContainText('Arrangement saved.')
  await panel
    .getByRole('button', { name: 'Reload arrangement history' })
    .click()
  await expect(panel).toContainText('Revision 1')
  await page.setViewportSize({ width: 320, height: 900 })
  expect(
    (await new AxeBuilder({ page }).include('main').analyze()).violations,
  ).toEqual([])
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
      ),
    )
    .toBeLessThanOrEqual(0)
  const context = await browser.newContext()
  try {
    const learner = await context.newPage()
    await signIn(
      learner,
      'Student',
      fixture.student_email,
      fixture.student_password,
    )
    await learner.goto(`/student/tasks/${fixture.fresh_task_id}`)
    const deadline = learner.getByRole('region', {
      name: 'Your deadline',
      exact: true,
    })
    await expect(deadline).toContainText('Your extended deadline is approved.')
    await expect(deadline).toContainText('5 Jan 2035')
    await expect(deadline).toContainText('5:00 pm')
    await expect(learner.locator('main')).not.toContainText(
      'PRIVATE scheduling review',
    )
    await learner.reload()
    await expect(deadline).toContainText('Your extended deadline is approved.')
  } finally {
    await context.close()
  }
})
