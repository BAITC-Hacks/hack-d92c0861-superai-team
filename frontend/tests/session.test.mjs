import test from 'node:test'
import assert from 'node:assert/strict'
import { toRaw } from 'vue'
import { createCareerSession } from '../src/session.js'
import { ApiError } from '../src/api.js'

// Synthetic contract-shaped responses; no source dataset is bundled in these tests.
const firstId = 'TEST_PERSON_A'
const secondId = 'TEST_PERSON_B'
const eventId = 'TEST_EVENT'
const trajectory = (progress = 31.25) => ({
  target_role: 'Test role', target_grade: 'Middle', target_source: 'next_grade',
  progress_pct: progress, remaining_gap: 3, critical_gaps: 1, gaps: [], note: '',
})
const profile = (id = firstId, version = 1, progress = 31.25) => ({
  employee: { employee_id: id, full_name: `Person ${id}`, skills: { TEST_SKILL: 0 } },
  effective_skills: { TEST_SKILL: version }, trajectory: trajectory(progress),
  history: [], as_of_date: '2026-10-01', data_version: version,
})
const recommendations = (id = firstId, version = 1) => ({
  employee_id: id, as_of_date: '2026-10-01', data_version: version,
  mode: 'fallback', fallback_reason: 'AI disabled in test', trajectory: trajectory(),
  steps: [{ event_id: eventId, title: 'Synthetic activity', factors: [], skill_deltas: [] }],
  excluded: [], no_step_reason: null,
})
const hr = (version = 1) => ({
  as_of_date: '2026-10-01', data_version: version, employees_count: 2,
  skill_gaps: [], employees_without_step: [], participation: [],
})
const completionResult = (id = firstId, version = 2) => ({
  employee_id: id, event_id: eventId, already_applied: false, data_version: version,
  skill_deltas: [], trajectory: trajectory(99),
})
const importResult = (version = 2) => ({
  employees_added: 1, employees_updated: 0, history_added: 0, history_unchanged: 0,
  data_version: version, warnings: [],
})
function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
function setup(role = 'employee') {
  const calls = [], tokens = [], handlers = {}
  let uuidCalls = 0
  const defaults = {
    me: () => ({ role, employee_id: role === 'employee' ? firstId : null }),
    employees: () => [firstId, secondId].map(employee_id => ({ employee_id })),
    events: () => [{ event_id: eventId }], skills: () => ({ skills: [], role_profiles: [] }),
    profile: id => profile(id), recommendations: id => recommendations(id),
    hrOverview: () => hr(), complete: id => completionResult(id), importFiles: () => importResult(),
  }
  const api = Object.fromEntries(Object.keys(defaults).map(name => [name, async (...args) => {
    calls.push({ name, args: args.map(argument => structuredClone(toRaw(argument))) })
    return (handlers[name] || defaults[name])(...args)
  }]))
  const session = createCareerSession(api, value => tokens.push(value), () => `test-uuid-${++uuidCalls}`)
  return { ...session, handlers, calls, tokens, uuidCalls: () => uuidCalls,
    called: name => calls.filter(call => call.name === name) }
}

test('Employee uses only its authenticated ID and cannot load the directory or HR', async () => {
  const app = setup()
  await app.login('in-memory-demo-token')
  assert.equal(app.state.employeeId, firstId)
  assert.equal(app.state.profile.employee.employee_id, firstId)
  await app.selectEmployee(secondId)
  await app.loadDirectory()
  await app.loadHR()
  await app.importFiles({ employees: { name: 'test.json' } })
  assert.equal(app.called('employees').length, 0)
  assert.equal(app.called('hrOverview').length, 0)
  assert.equal(app.called('importFiles').length, 0)
  assert.deepEqual(app.called('profile').map(call => call.args[0]), [firstId])
  assert.deepEqual(app.called('recommendations').map(call => call.args[0]), [firstId])
  assert.deepEqual(app.tokens, ['', 'in-memory-demo-token'])
})

test('HR loads directory and can select arbitrary imported IDs', async () => {
  const app = setup('hr')
  await app.login('in-memory-demo-token')
  const importedId = 'JURY/EXTERNAL ID'
  await app.selectEmployee(importedId)
  assert.equal(app.called('employees').length, 1)
  assert.equal(app.state.profile.employee.employee_id, importedId)
  assert.equal(app.state.recommendations.employee_id, importedId)
  await app.loadHR()
  assert.equal(app.state.hr.employees_count, 2)
})

test('switching employee clears previous profile, recommendations and completion feedback immediately', async () => {
  const app = setup('hr')
  await app.login('in-memory-demo-token')
  app.state.completion.result = completionResult()
  app.state.completion.error = { status: 422, message: 'Previous error' }
  app.state.profileError = { status: 404, message: 'Previous error' }
  const pending = deferred()
  app.handlers.profile = () => pending.promise
  const loading = app.selectEmployee(secondId)
  assert.equal(app.state.profile, null)
  assert.equal(app.state.recommendations, null)
  assert.equal(app.state.completion.result, null)
  assert.equal(app.state.completion.error, null)
  assert.equal(app.state.profileError, null)
  pending.resolve(profile(secondId))
  await loading
})

test('late profile response from previous employee cannot overwrite the selected profile', async () => {
  const app = setup('hr')
  await app.login('in-memory-demo-token')
  const late = deferred()
  app.handlers.profile = id => id === secondId ? late.promise : profile(id)
  const oldRequest = app.selectEmployee(secondId)
  await app.selectEmployee('TEST_PERSON_C')
  late.resolve(profile(secondId))
  await oldRequest
  assert.equal(app.state.profile.employee.employee_id, 'TEST_PERSON_C')
  assert.equal(app.state.recommendations.employee_id, 'TEST_PERSON_C')
  assert.equal(app.called('recommendations').filter(call => call.args[0] === secondId).length, 0)
})

test('late recommendations from previous employee cannot overwrite a newer selection', async () => {
  const app = setup('hr')
  await app.login('in-memory-demo-token')
  const late = deferred(), started = deferred()
  app.handlers.recommendations = id => {
    if (id === secondId) { started.resolve(); return late.promise }
    return recommendations(id)
  }
  const oldRequest = app.selectEmployee(secondId)
  await started.promise
  await app.selectEmployee('TEST_PERSON_C')
  late.resolve(recommendations(secondId))
  await oldRequest
  assert.equal(app.state.recommendations.employee_id, 'TEST_PERSON_C')
  assert.equal(app.state.recommendationBusy, false)
})

test('logout clears credentials and all private state, ignoring late requests', async () => {
  const app = setup('hr')
  await app.login('in-memory-demo-token')
  const late = deferred()
  app.handlers.profile = () => late.promise
  const loading = app.refreshEmployee()
  app.logout()
  late.resolve(profile(firstId, 3))
  await loading
  assert.equal(app.tokens.at(-1), '')
  assert.equal(app.state.identity, null)
  assert.equal(app.state.employeeId, '')
  assert.deepEqual(app.state.employees, [])
  assert.deepEqual(app.state.events, [])
  assert.equal(app.state.profile, null)
  assert.equal(app.state.recommendations, null)
  assert.equal(app.state.hr, null)
  assert.equal(app.state.profileBusy, false)
})

test('a late login response does not restore a logged out session', async () => {
  const app = setup()
  const late = deferred()
  app.handlers.me = () => late.promise
  const login = app.login('in-memory-demo-token')
  app.logout()
  late.resolve({ role: 'employee', employee_id: firstId })
  await login
  assert.equal(app.state.identity, null)
  assert.equal(app.tokens.at(-1), '')
  assert.equal(app.called('profile').length, 0)
})

test('mismatching recommendation version refreshes profile once before accepting new recommendations', async () => {
  const app = setup()
  let count = 0
  app.handlers.profile = id => profile(id, ++count === 1 ? 1 : 2)
  app.handlers.recommendations = id => recommendations(id, 2)
  await app.login('in-memory-demo-token')
  assert.equal(app.called('profile').length, 2)
  assert.equal(app.state.profile.data_version, 2)
  assert.equal(app.state.recommendations.data_version, 2)
  assert.equal(app.state.recommendationError, null)
})

test('repeatedly mismatching versions are rejected without an endless refresh or stale steps', async () => {
  const app = setup()
  let version = 0
  app.handlers.profile = id => profile(id, ++version)
  app.handlers.recommendations = id => recommendations(id, version + 1)
  await app.login('in-memory-demo-token')
  assert.equal(app.called('profile').length, 2)
  assert.equal(app.state.recommendations, null)
  assert.equal(app.state.recommendationError.status, 409)
  assert.equal(app.state.recommendationBusy, false)
})

test('profile still older than recommendation version is rejected on refresh', async () => {
  const app = setup()
  app.handlers.recommendations = id => recommendations(id, 2)
  await app.login('in-memory-demo-token')
  assert.equal(app.state.profile, null)
  assert.equal(app.state.recommendations, null)
  assert.equal(app.state.profileError.status, 409)
  assert.equal(app.called('recommendations').length, 1)
})

test('a profile for a different employee is rejected', async () => {
  const app = setup()
  app.handlers.profile = () => profile(secondId)
  await app.login('in-memory-demo-token')
  assert.equal(app.state.profile, null)
  assert.equal(app.state.profileError.status, 409)
  assert.equal(app.called('recommendations').length, 0)
})

test('recommendations for a different employee are never shown', async () => {
  const app = setup()
  app.handlers.recommendations = () => recommendations(secondId)
  await app.login('in-memory-demo-token')
  assert.equal(app.state.recommendations, null)
  assert.equal(app.state.recommendationError.status, 409)
})

test('completion blocks duplicate clicks and refreshes effective skills and progress from server', async () => {
  const app = setup()
  await app.login('in-memory-demo-token')
  const pending = deferred()
  app.handlers.complete = () => pending.promise
  const sending = app.complete({ event_id: eventId })
  assert.equal(app.state.completion.busy, true)
  await app.complete({ event_id: eventId })
  await app.retryCompletion()
  assert.equal(app.called('complete').length, 1)
  assert.equal(app.uuidCalls(), 1)
  app.handlers.profile = id => profile(id, 2, 67.5)
  app.handlers.recommendations = id => recommendations(id, 2)
  pending.resolve(completionResult())
  await sending
  assert.equal(app.state.profile.trajectory.progress_pct, 67.5)
  assert.equal(app.state.profile.effective_skills.TEST_SKILL, 2)
  assert.equal(app.state.profile.employee.skills.TEST_SKILL, 0)
  assert.equal(app.state.recommendations.data_version, 2)
  assert.equal(app.called('profile').length, 2)
  assert.equal(app.called('recommendations').length, 2)
  assert.equal(app.state.completion.pending, null)
  assert.equal(app.state.completion.busy, false)
})

test('uncertain completion network failure retries the exact same UUID and request body', async () => {
  const app = setup('hr')
  await app.login('in-memory-demo-token')
  app.handlers.complete = () => { throw new TypeError('Connection lost') }
  const input = { event_id: eventId, participation_record_id: 'TEST_RECORD', session_date: '2026-10-01' }
  await app.complete(input)
  const sent = app.called('complete')[0].args
  assert.equal(app.state.completion.pending.retryable, true)
  assert.equal(app.state.completion.result, null)
  await app.selectEmployee(secondId)
  assert.equal(app.state.employeeId, firstId)
  app.handlers.profile = id => profile(id, 2)
  app.handlers.recommendations = id => recommendations(id, 2)
  await app.refreshEmployee()
  await app.complete(input)
  assert.equal(app.called('complete').length, 1)
  app.handlers.complete = id => completionResult(id)
  app.handlers.hrOverview = () => hr(2)
  await app.retryCompletion()
  assert.deepEqual(app.called('complete')[1].args, sent)
  assert.equal(sent[1].expected_data_version, 1)
  assert.equal(app.uuidCalls(), 1)
  assert.equal(app.state.hr.data_version, 2)
})

test('completion never sends an activity missing from server recommendations', async () => {
  const app = setup()
  await app.login('in-memory-demo-token')
  await app.complete({ event_id: 'NOT_RECOMMENDED' })
  assert.equal(app.called('complete').length, 0)
  assert.equal(app.uuidCalls(), 0)
})

for (const status of [403, 409, 422, 501]) {
  test(`completion HTTP ${status} is exposed without invented success`, async () => {
    const app = setup()
    await app.login('in-memory-demo-token')
    app.handlers.complete = () => { throw new ApiError(status, `Server error ${status}`, { code: 'test_failure' }) }
    await app.complete({ event_id: eventId })
    assert.equal(app.state.completion.error.status, status)
    assert.equal(app.state.completion.error.code, 'test_failure')
    assert.equal(app.state.completion.result, null)
    assert.equal(app.state.profile.data_version, 1)
    assert.equal(app.called('profile').length, 1)
    assert.equal(app.state.completion.busy, false)
    if (status !== 501) {
      await app.retryCompletion()
      assert.equal(app.called('complete').length, 1)
    }
    await app.discardCompletion()
    assert.equal(app.state.completion.pending, null)
    assert.equal(app.state.completion.error, null)
  })
}

for (const endpoint of ['profile', 'recommendations', 'complete', 'hrOverview', 'importFiles']) {
  test(`HTTP 401 from ${endpoint} clears credentials and session data`, async () => {
    const app = setup('hr')
    await app.login('in-memory-demo-token')
    app.handlers[endpoint] = () => { throw new ApiError(401, 'Expired session', null) }
    if (endpoint === 'complete') await app.complete({ event_id: eventId })
    else if (endpoint === 'hrOverview') await app.loadHR()
    else if (endpoint === 'importFiles') await app.importFiles({ history: { name: 'test.csv' } })
    else await app.refreshEmployee()
    assert.equal(app.tokens.at(-1), '')
    assert.equal(app.state.identity, null)
    assert.equal(app.state.profile, null)
    assert.equal(app.state.recommendations, null)
    assert.equal(app.state.hr, null)
    assert.deepEqual(app.state.employees, [])
    assert.equal(app.state.completion.pending, null)
    assert.equal(app.state.loginError.status, 401)
  })
}

for (const files of [{ employees: { name: 'test.json' } }, { history: { name: 'test.csv' } },
  { employees: { name: 'test.json' }, history: { name: 'test.csv' } }]) {
  test(`import ${Object.keys(files).join(' + ')} refreshes directory, HR and current profile`, async () => {
    const app = setup('hr')
    await app.login('in-memory-demo-token')
    app.handlers.profile = id => profile(id, 2)
    app.handlers.recommendations = id => recommendations(id, 2)
    app.handlers.hrOverview = () => hr(2)
    await app.importFiles(files)
    assert.deepEqual(app.called('importFiles')[0].args, [files.employees, files.history])
    assert.equal(app.called('employees').length, 2)
    assert.equal(app.called('hrOverview').length, 1)
    assert.equal(app.called('profile').length, 2)
    assert.equal(app.state.profile.data_version, 2)
    assert.equal(app.state.recommendations.data_version, 2)
    assert.equal(app.state.hr.data_version, 2)
    assert.equal(app.state.importResult.employees_added, 1)
    assert.equal(app.state.importError, null)
    assert.equal(app.state.importing, false)
  })
}

test('empty import sends no request', async () => {
  const app = setup('hr')
  await app.login('in-memory-demo-token')
  await app.importFiles({})
  assert.equal(app.called('importFiles').length, 0)
})

test('failed import retains error details and the last valid server profile', async () => {
  const app = setup('hr')
  await app.login('in-memory-demo-token')
  app.handlers.importFiles = () => { throw new ApiError(422, 'History record conflict', { code: 'history_conflict' }) }
  await app.importFiles({ history: { name: 'test.csv' } })
  assert.equal(app.state.importError.status, 422)
  assert.equal(app.state.importError.code, 'history_conflict')
  assert.equal(app.state.importError.message, 'History record conflict')
  assert.equal(app.state.importResult, null)
  assert.equal(app.state.profile.data_version, 1)
  assert.equal(app.called('employees').length, 1)
  assert.equal(app.state.importing, false)
})

test('post-import refresh failures remain visible and outdated profile and HR data are rejected', async () => {
  const app = setup('hr')
  await app.login('in-memory-demo-token')
  await app.loadHR()
  app.handlers.employees = () => { throw new ApiError(503, 'Directory temporarily unavailable', null) }
  await app.importFiles({ employees: { name: 'test.json' } })
  assert.equal(app.state.importResult.data_version, 2)
  assert.equal(app.state.directoryError.status, 503)
  assert.equal(app.state.hrError.status, 409)
  assert.equal(app.state.profileError.status, 409)
  assert.equal(app.state.profile, null)
  assert.equal(app.state.recommendations, null)
  assert.equal(app.state.hr, null)
  assert.deepEqual(app.state.employees, [])
  assert.equal(app.state.importing, false)
  assert.equal(app.state.refreshingAfterImport, false)
})

test('catalog 401 clears credentials even when its other parallel request fails first', async () => {
  const app = setup()
  await app.login('in-memory-demo-token')
  app.handlers.events = () => { throw new ApiError(403, 'Catalog unavailable for this role', null) }
  app.handlers.skills = () => { throw new ApiError(401, 'Expired session', null) }
  await app.loadCatalog()
  assert.equal(app.state.identity, null)
  assert.equal(app.tokens.at(-1), '')
  assert.equal(app.state.loginError.status, 401)
})
