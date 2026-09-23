import test from 'node:test'
import assert from 'node:assert/strict'
import { api, setToken, ApiError } from '../src/api.js'

function intercept(t, handler = () => Response.json({ ok: true })) {
  const calls = []
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ url, options })
    return handler(url, options)
  })
  t.after(() => setToken(''))
  return calls
}

test('Bearer credential stays in memory and clearing it removes Authorization', async t => {
  const calls = intercept(t)
  // Any attempted browser persistence is an error, not a hidden fixture fallback.
  const storage = { getItem() { throw new Error('Must not read persisted tokens') },
    setItem() { throw new Error('Must not persist tokens') } }
  const oldLocal = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
  const oldSession = Object.getOwnPropertyDescriptor(globalThis, 'sessionStorage')
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: storage })
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: storage })
  t.after(() => {
    if (oldLocal) Object.defineProperty(globalThis, 'localStorage', oldLocal)
    else delete globalThis.localStorage
    if (oldSession) Object.defineProperty(globalThis, 'sessionStorage', oldSession)
    else delete globalThis.sessionStorage
  })
  setToken('  synthetic-test-token  ')
  await api.me()
  assert.equal(calls[0].url, '/api/auth/me')
  assert.equal(calls[0].options.headers.get('Authorization'), 'Bearer synthetic-test-token')
  setToken('')
  await api.events()
  assert.equal(calls[1].options.headers.has('Authorization'), false)
})

test('all employee paths encode IDs without interpreting slashes, spaces or query syntax', async t => {
  const calls = intercept(t)
  const id = 'JURY/тест ?role=hr'
  const encoded = encodeURIComponent(id)
  await api.profile(id)
  await api.recommendations(id)
  await api.complete(id, { event_id: 'TEST_EVENT', idempotency_key: 'synthetic-uuid', expected_data_version: 1 })
  assert.deepEqual(calls.map(call => call.url), [
    `/api/employees/${encoded}`, `/api/employees/${encoded}/recommendations`, `/api/employees/${encoded}/complete`,
  ])
})

test('completion posts the complete JSON contract unchanged', async t => {
  const calls = intercept(t)
  const payload = { event_id: 'TEST_EVENT', idempotency_key: 'synthetic-uuid', expected_data_version: 7,
    participation_record_id: 'TEST_RECORD', session_date: '2026-10-01' }
  await api.complete('TEST_PERSON', payload)
  assert.equal(calls[0].options.method, 'POST')
  assert.equal(calls[0].options.headers.get('Content-Type'), 'application/json')
  assert.deepEqual(JSON.parse(calls[0].options.body), payload)
})

test('imports use FormData with either file and let browser provide its multipart boundary', async t => {
  const calls = intercept(t)
  const employees = new Blob(['{"employees":[]}'], { type: 'application/json' })
  const history = new Blob(['record_id,employee_id\n'], { type: 'text/csv' })
  await api.importFiles(employees, null)
  await api.importFiles(null, history)
  await api.importFiles(employees, history)
  assert.deepEqual(calls.map(call => [...call.options.body.keys()]), [['employees'], ['history'], ['employees', 'history']])
  for (const { url, options } of calls) {
    assert.equal(url, '/api/admin/import')
    assert.equal(options.method, 'POST')
    assert.ok(options.body instanceof FormData)
    assert.equal(options.headers.has('Content-Type'), false)
  }
  assert.equal(await calls[0].options.body.get('employees').text(), '{"employees":[]}')
  assert.equal(await calls[1].options.body.get('history').text(), 'record_id,employee_id\n')
})

test('directory, catalog, health and HR use the established API paths', async t => {
  const calls = intercept(t)
  await api.health()
  await api.employees()
  await api.events()
  await api.skills()
  await api.hrOverview()
  assert.deepEqual(calls.map(call => call.url), ['/api/health', '/api/employees', '/api/events', '/api/skills', '/api/hr/overview'])
})

test('structured application errors retain status, message and code', async t => {
  intercept(t, () => Response.json({ detail: { code: 'stale_version', message: 'Refresh profile' } }, { status: 409 }))
  await assert.rejects(api.profile('TEST_PERSON'), error => {
    assert.ok(error instanceof ApiError)
    assert.equal(error.status, 409)
    assert.equal(error.message, 'Refresh profile')
    assert.deepEqual(error.detail, { code: 'stale_version', message: 'Refresh profile' })
    return true
  })
})

test('FastAPI validation arrays become safe HTTP error text', async t => {
  const detail = [{ loc: ['body', 'expected_data_version'], msg: 'Field required', type: 'missing' }]
  intercept(t, () => Response.json({ detail }, { status: 422 }))
  await assert.rejects(api.complete('TEST_PERSON', {}), error => {
    assert.equal(error.status, 422)
    assert.equal(error.message, 'HTTP 422')
    assert.deepEqual(error.detail, detail)
    return true
  })
})

test('plain-text upstream failures become HTTP errors instead of JSON parse failures', async t => {
  intercept(t, () => new Response('<html>Unavailable</html>', { status: 503 }))
  await assert.rejects(api.hrOverview(), error => {
    assert.ok(error instanceof ApiError)
    assert.equal(error.status, 503)
    assert.equal(error.message, 'HTTP 503')
    return true
  })
})

test('request timeout aborts fetch, exposes status 408 and clears its timer', async t => {
  let clearCount = 0
  t.mock.method(globalThis, 'setTimeout', (callback, delay) => {
    assert.equal(delay, 12000)
    queueMicrotask(callback)
    return 12345
  })
  t.mock.method(globalThis, 'clearTimeout', timer => { assert.equal(timer, 12345); clearCount++ })
  intercept(t, (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true })
  }))
  await assert.rejects(api.events(), error => {
    assert.ok(error instanceof ApiError)
    assert.equal(error.status, 408)
    return true
  })
  assert.equal(clearCount, 1)
})
