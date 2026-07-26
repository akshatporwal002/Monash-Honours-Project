import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { isAbsolute, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const isWindows = process.platform === 'win32'
const root = fileURLToPath(new URL('..', import.meta.url))
const backendRoot = resolve(root, '../backend')
const viteEntry = fileURLToPath(
  new URL('../node_modules/vite/bin/vite.js', import.meta.url),
)
const playwrightEntry = fileURLToPath(
  new URL('../node_modules/@playwright/test/cli.js', import.meta.url),
)
const services = []

function start(command, arguments_, cwd = root) {
  const child = spawn(command, arguments_, {
    cwd,
    detached: !isWindows,
    stdio: 'inherit',
  })
  services.push(child)
  return child
}

function stop(child) {
  if (child.exitCode !== null || child.killed) return
  if (isWindows) {
    child.kill()
    return
  }
  try {
    process.kill(-child.pid, 'SIGTERM')
  } catch {
    child.kill('SIGTERM')
  }
}

function runCommand(command, arguments_, cwd = root) {
  const child = spawn(command, arguments_, { cwd, stdio: 'inherit' })
  return new Promise((resolveCommand, reject) => {
    child.once('error', reject)
    child.once('exit', (code, signal) => {
      if (signal !== null) {
        reject(new Error(`Command exited after signal ${signal}.`))
        return
      }
      if (code !== 0) {
        reject(new Error(`Command exited with status ${code ?? 1}.`))
        return
      }
      resolveCommand()
    })
  })
}

function backendPython() {
  const configured = process.env.QUANTUMLEARN_BACKEND_PYTHON
  if (configured) {
    return isAbsolute(configured) ? configured : resolve(root, configured)
  }
  const candidates = isWindows
    ? [join(backendRoot, '.venv', 'Scripts', 'python.exe')]
    : [join(backendRoot, '.venv', 'bin', 'python')]
  const discovered = candidates.find((candidate) => existsSync(candidate))
  if (!discovered) {
    throw new Error(
      'The locked backend environment is missing. Run `uv sync --frozen --extra dev` in src-main/backend.',
    )
  }
  return discovered
}

async function waitUntilReady(urls) {
  for (let attempt = 0; attempt < 240; attempt += 1) {
    if (services.some((service) => service.exitCode !== null)) {
      throw new Error('An E2E support server exited before becoming ready.')
    }
    const checks = await Promise.all(
      urls.map(async (url) => {
        try {
          return (await fetch(url)).ok
        } catch {
          return false
        }
      }),
    )
    if (checks.every(Boolean)) return
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  throw new Error('Timed out waiting for the E2E support servers.')
}

async function run() {
  await runCommand(process.execPath, [
    viteEntry,
    'build',
    '--config',
    'vite.e2e.config.ts',
  ])
  start(
    backendPython(),
    ['tests/browser_e2e_server.py'],
    backendRoot,
  )
  start(process.execPath, [
    viteEntry,
    'preview',
    '--config',
    'vite.e2e.config.ts',
  ])
  await waitUntilReady([
    'http://127.0.0.1:4180/api/v1/health',
    'http://127.0.0.1:4173/e2e.html',
  ])

  const runner = spawn(
    process.execPath,
    [playwrightEntry, 'test', ...process.argv.slice(2)],
    {
      cwd: root,
      stdio: 'inherit',
    },
  )
  return await new Promise((resolve, reject) => {
    runner.once('error', reject)
    runner.once('exit', (code, signal) => {
      if (signal !== null) {
        reject(new Error(`Playwright exited after signal ${signal}.`))
        return
      }
      resolve(code ?? 1)
    })
  })
}

let exitCode = 1
try {
  exitCode = await run()
} finally {
  for (const service of services.reverse()) stop(service)
}
process.exitCode = exitCode
