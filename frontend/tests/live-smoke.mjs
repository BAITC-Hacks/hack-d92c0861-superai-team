// Opt-in live smoke: actual frontend API/session -> launcher -> FastAPI -> runtime store.
// Uses a temporary DB and generated in-memory credentials. Never alters the seed dataset.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { randomUUID } from 'node:crypto'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'node:net'
import { api, setToken } from '../src/api.js'
import { createCareerSession } from '../src/session.js'

const root = fileURLToPath(new URL('../../', import.meta.url))
assert.ok(process.env.DATA_DIR, 'Set DATA_DIR to the local official dataset folder')
const python = process.env.CQ_PYTHON || 'python3'
const directory = await mkdtemp(join(tmpdir(), 'career-quest-ui-smoke-'))
const hrToken = randomUUID(), employeeToken = randomUUID()
const env = { ...process.env, DATA_DIR: resolve(process.env.DATA_DIR), STATE_PATH: join(directory, 'runtime.sqlite3'),
  HR_TOKEN: hrToken, EMPLOYEE_TOKEN: employeeToken, EMPLOYEE_ID: 'E0001', AI_ENABLED: 'false' }
const fetchOriginal = globalThis.fetch
let server, output = '', sentCompletion
const base = 'http://127.0.0.1:8000'
globalThis.fetch = (url, options) => {
  if (String(url).endsWith('/complete') && options?.body) sentCompletion = JSON.parse(options.body)
  return fetchOriginal(new URL(url, base), options)
}
async function stop() {
  const child = server
  server = null
  if (!child || child.exitCode !== null || child.signalCode !== null) return
  const closed = once(child, 'exit')
  if (process.platform !== 'win32') process.kill(-child.pid, 'SIGTERM')
  else child.kill('SIGTERM')
  await closed
  for (let tries = 0; tries < 50; tries++) {
    try { await fetchOriginal(`${base}/api/health`); await new Promise(accept => setTimeout(accept, 100)) }
    catch { break }
  }
}
async function start() {
  // Refuse to attach to, or stop, another developer's running service.
  const probe = createServer()
  await new Promise((accept, reject) => { probe.once('error', reject); probe.listen(8000, '127.0.0.1', accept) })
  await new Promise(accept => probe.close(accept))
  output = ''
  server = spawn(python, ['run.py'], { cwd: root, env, detached: process.platform !== 'win32', stdio: ['ignore', 'pipe', 'pipe'] })
  server.stdout.on('data', chunk => { output += chunk })
  server.stderr.on('data', chunk => { output += chunk })
  for (let tries = 0; tries < 100; tries++) {
    if (server.exitCode !== null) throw Error(`Launcher exited: ${output.slice(-2000)}`)
    try { const response = await fetchOriginal(`${base}/api/health`); if (response.ok) return } catch { /* Wait for our process. */ }
    await new Promise(accept => setTimeout(accept, 100))
  }
  throw Error('Launcher did not become ready')
}
try {
  await start()
  const page = await fetchOriginal(base)
  assert.equal(page.status, 200)
  const html = await page.text()
  const asset = html.match(/src="([^"]+\.js)"/)[1]
  assert.equal((await fetchOriginal(new URL(asset, base))).status, 200)
  const session = createCareerSession()
  await session.login(hrToken)
  assert.equal(session.state.identity.role, 'hr')
  assert.ok(session.state.events.length && session.state.skills.length && session.state.employees.length)
  let selected
  for (const person of session.state.employees) {
    if (session.state.employeeId !== person.employee_id) await session.selectEmployee(person.employee_id)
    selected = session.state.recommendations?.steps.find(step => step.format === 'self_paced')
    if (selected) break
  }
  assert.ok(selected, 'At least one employee should have a self-paced recommendation')
  assert.equal(session.state.recommendations.mode, 'fallback')
  const employeeId = session.state.employeeId
  const before = session.state.profile.trajectory.progress_pct
  const participation = session.state.profile.history.find(row => row.event_id === selected.event_id && row.status === 'in_progress')
  await session.complete({ event_id: selected.event_id, participation_record_id: participation?.record_id || null })
  assert.ok(session.state.completion.result, JSON.stringify(session.state.completion.error))
  const result = session.state.completion.result
  assert.ok(result.trajectory.progress_pct > before)
  assert.equal(session.state.profile.trajectory.progress_pct, result.trajectory.progress_pct)
  assert.equal(session.state.recommendations.data_version, result.data_version)
  const sameRequest = structuredClone(sentCompletion)
  const duplicate = await api.complete(employeeId, sameRequest)
  assert.equal(duplicate.already_applied, true)
  assert.equal(duplicate.data_version, result.data_version)

  const employeeFile = new File([await readFile(join(root, 'docs/jury_examples/employees.json'))], 'employees.json', { type: 'application/json' })
  const historyFile = new File([await readFile(join(root, 'docs/jury_examples/activity_history.csv'))], 'activity_history.csv', { type: 'text/csv' })
  await session.importFiles({ employees: employeeFile, history: historyFile })
  assert.ok(session.state.importResult, JSON.stringify(session.state.importError))
  assert.ok(session.state.employees.some(person => person.employee_id === 'TEST_CQ_003'))
  assert.equal(session.state.hr.data_version, session.state.importResult.data_version)
  await session.selectEmployee('TEST_CQ_003')
  assert.equal(session.state.recommendations.steps.length, 0)
  assert.ok(session.state.recommendations.no_step_reason)
  const version = session.state.profile.data_version
  await session.importFiles({ employees: new File(['{invalid'], 'employees.json'), history: null })
  assert.equal(session.state.importError.status, 422)
  assert.equal((await api.health()).data_version, version)

  session.logout()
  await session.login(employeeToken)
  assert.equal(session.state.identity.role, 'employee')
  assert.equal(session.state.employeeId, 'E0001')
  assert.equal(session.state.employees.length, 0)
  await assert.rejects(api.employees(), error => error.status === 403)
  await assert.rejects(api.hrOverview(), error => error.status === 403)
  await assert.rejects(api.profile('TEST_CQ_003'), error => error.status === 403)
  await assert.rejects(api.importFiles(employeeFile, null), error => error.status === 403)
  session.logout()
  await stop()
  await start()
  await session.login(hrToken)
  await session.selectEmployee(employeeId)
  assert.equal(session.state.profile.trajectory.progress_pct, result.trajectory.progress_pct)
  assert.ok(session.state.employees.some(person => person.employee_id === 'TEST_CQ_003'))
  session.logout()
  console.log(`PASS: one-command launcher + built UI; real API Employee/HR; completion ${before} -> ${result.trajectory.progress_pct}; same-key retry; import/new ID; rejected invalid import; access control; persistence after restart; explicit fallback.`)
} finally {
  setToken('')
  globalThis.fetch = fetchOriginal
  await stop()
  await rm(directory, { recursive: true, force: true })
}
