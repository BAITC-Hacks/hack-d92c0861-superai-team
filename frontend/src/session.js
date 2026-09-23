import { reactive } from 'vue'
import { api, setToken, ApiError } from './api.js'

function initialState() {
  return {
    identity: null, employees: [], employeeId: '', profile: null, recommendations: null,
    events: [], skills: [], roleProfiles: [], hr: null,
    loginBusy: false, directoryBusy: false, catalogBusy: false, profileBusy: false,
    recommendationBusy: false, hrBusy: false, importing: false, refreshingAfterImport: false,
    loginError: null, directoryError: null, catalogError: null, profileError: null,
    recommendationError: null, hrError: null, importError: null, importResult: null,
    completion: { busy: false, pending: null, error: null, result: null },
  }
}
function errorInfo(error) {
  return { status: error.status || 0, message: error.message || 'Request failed', code: error.detail?.code || '' }
}

// Request counters belong to this authenticated session, not to individual page components.
// No credentials, profile data or completion payloads are persisted in the browser.
export function createCareerSession(client = api, saveToken = setToken, uuid = () => crypto.randomUUID()) {
  const state = reactive(initialState())
  let session = 0, profileRequest = 0, directoryRequest = 0, catalogRequest = 0, hrRequest = 0
  const current = (ticket) => ticket === session && Boolean(state.identity)

  function logout() {
    session++; profileRequest++; directoryRequest++; catalogRequest++; hrRequest++
    saveToken('')
    Object.assign(state, initialState())
  }
  function failure(error, ticket) {
    if (ticket !== session) return null
    const info = errorInfo(error)
    if (info.status === 401) { logout(); state.loginError = info; return null }
    return info
  }

  async function login(token) {
    if (state.loginBusy) return
    logout()
    const ticket = session
    state.loginBusy = true
    saveToken(token)
    try {
      const identity = await client.me()
      if (ticket !== session) return
      if (!['employee', 'hr'].includes(identity.role) || (identity.role === 'employee' && !identity.employee_id)) {
        throw new ApiError(403, 'Unsupported identity', null)
      }
      state.identity = identity
      if (identity.role === 'employee') state.employeeId = identity.employee_id
      await Promise.allSettled([loadCatalog(), identity.role === 'hr' ? loadDirectory() : refreshEmployee()])
    } catch (error) {
      if (ticket !== session) return
      const info = errorInfo(error)
      logout()
      state.loginError = info
    } finally { if (ticket === session) state.loginBusy = false }
  }

  async function loadDirectory(loadProfile = true) {
    if (state.identity?.role !== 'hr') return
    const ticket = session, request = ++directoryRequest
    state.directoryBusy = true; state.directoryError = null
    try {
      const employees = await client.employees()
      if (!current(ticket) || request !== directoryRequest) return
      state.employees = employees
      if (!employees.some(person => person.employee_id === state.employeeId)) {
        state.employeeId = employees[0]?.employee_id || ''
        state.profile = null; state.recommendations = null
      }
      if (loadProfile && state.employeeId) await refreshEmployee()
    } catch (error) {
      if (current(ticket) && request === directoryRequest) state.directoryError = failure(error, ticket)
    } finally { if (current(ticket) && request === directoryRequest) state.directoryBusy = false }
  }

  async function loadCatalog() {
    const ticket = session, request = ++catalogRequest
    if (!current(ticket)) return
    state.catalogBusy = true; state.catalogError = null
    const results = await Promise.allSettled([client.events(), client.skills()])
    if (!current(ticket) || request !== catalogRequest) return
    const rejected = results.find(result => result.status === 'rejected' && result.reason.status === 401)
      || results.find(result => result.status === 'rejected')
    if (rejected) state.catalogError = failure(rejected.reason, ticket)
    if (!current(ticket)) return
    if (results[0].status === 'fulfilled') state.events = results[0].value
    if (results[1].status === 'fulfilled') {
      state.skills = results[1].value.skills
      state.roleProfiles = results[1].value.role_profiles
    }
    state.catalogBusy = false
  }

  async function selectEmployee(id) {
    if (!state.identity || state.completion.busy || state.completion.pending || state.importing) return
    if (state.identity.role !== 'hr' && id !== state.identity.employee_id) return
    state.employeeId = id
    state.profile = null; state.recommendations = null
    state.completion = { busy: false, pending: null, error: null, result: null }
    await refreshEmployee()
  }

  async function refreshEmployee(attempt = 0, minVersion = 0) {
    const ticket = session, request = ++profileRequest, id = state.employeeId
    if (!current(ticket) || !id) return
    state.profileBusy = true; state.recommendationBusy = true
    state.profileError = null; state.recommendationError = null; state.recommendations = null
    const valid = () => current(ticket) && request === profileRequest && id === state.employeeId
    try {
      const profile = await client.profile(id)
      if (!valid()) return
      if (profile.employee.employee_id !== id || profile.data_version < minVersion) throw new ApiError(409, 'Profile data is outdated. Refresh to continue.', null)
      state.profile = profile
      state.profileBusy = false
      try {
        const recommendations = await client.recommendations(id)
        if (!valid()) return
        if (recommendations.employee_id !== id || recommendations.data_version !== profile.data_version) {
          if (attempt === 0) { await refreshEmployee(1, Math.max(minVersion, profile.data_version, recommendations.data_version)); return }
          throw new ApiError(409, 'Data changed during the request. Refresh recommendations.', null)
        }
        state.recommendations = recommendations
      } catch (error) { if (valid()) state.recommendationError = failure(error, ticket) }
    } catch (error) {
      if (valid()) { state.profile = null; state.profileError = failure(error, ticket) }
    } finally {
      if (valid()) { state.profileBusy = false; state.recommendationBusy = false }
    }
  }

  async function loadHR(minVersion = 0) {
    if (state.identity?.role !== 'hr') return
    const ticket = session, request = ++hrRequest
    state.hrBusy = true; state.hrError = null
    try {
      const hr = await client.hrOverview()
      if (!current(ticket) || request !== hrRequest) return
      if (hr.data_version < minVersion) throw new ApiError(409, 'HR data is outdated. Refresh to continue.', null)
      state.hr = hr
    } catch (error) {
      if (current(ticket) && request === hrRequest) { state.hr = null; state.hrError = failure(error, ticket) }
    } finally { if (current(ticket) && request === hrRequest) state.hrBusy = false }
  }

  async function complete(input) {
    if (state.completion.busy || state.completion.pending || state.profileBusy || state.recommendationBusy || state.importing) return
    if (!state.profile || !state.recommendations || !state.recommendations.steps.some(step => step.event_id === input.event_id)) return
    if (state.profile.data_version !== state.recommendations.data_version) return
    state.completion.result = null
    state.completion.error = null
    try {
      state.completion.pending = {
        employeeId: state.employeeId, retryable: true,
        payload: { event_id: input.event_id, idempotency_key: uuid(), expected_data_version: state.profile.data_version,
          participation_record_id: input.participation_record_id || null, session_date: input.session_date || null },
      }
    } catch (error) { state.completion.error = errorInfo(error); return }
    await sendCompletion()
  }

  async function sendCompletion() {
    const pending = state.completion.pending, ticket = session
    if (!pending || !pending.retryable || state.completion.busy || pending.employeeId !== state.employeeId) return
    const completion = state.completion
    completion.busy = true; completion.error = null
    try {
      const result = await client.complete(pending.employeeId, pending.payload)
      if (!current(ticket) || completion !== state.completion || state.employeeId !== pending.employeeId) return
      completion.result = result; completion.pending = null
      state.hr = null; ++hrRequest
      await refreshEmployee(0, result.data_version)
      if (current(ticket) && state.identity.role === 'hr') await loadHR(result.data_version)
    } catch (error) {
      if (current(ticket) && completion === state.completion) {
        completion.error = failure(error, ticket)
        pending.retryable = ![401, 403, 404, 409, 422].includes(error.status)
      }
    } finally { if (current(ticket) && completion === state.completion) completion.busy = false }
  }

  async function discardCompletion() {
    if (state.completion.busy) return
    state.completion = { busy: false, pending: null, error: null, result: null }
    await refreshEmployee()
  }

  async function importFiles({ employees, history }) {
    if (state.identity?.role !== 'hr' || state.importing || state.completion.busy || state.completion.pending) return
    if (!employees && !history) return
    const ticket = session
    state.importing = true; state.importError = null; state.importResult = null
    try {
      const result = await client.importFiles(employees, history)
      if (!current(ticket)) return
      state.importResult = result; state.refreshingAfterImport = true
      ++profileRequest; ++hrRequest; ++directoryRequest
      state.profile = null; state.recommendations = null; state.hr = null; state.employees = []
      state.completion = { busy: false, pending: null, error: null, result: null }
      await Promise.allSettled([loadDirectory(false), loadHR(result.data_version)])
      if (current(ticket) && state.employeeId) await refreshEmployee(0, result.data_version)
    } catch (error) { if (current(ticket)) state.importError = failure(error, ticket) }
    finally { if (current(ticket)) { state.importing = false; state.refreshingAfterImport = false } }
  }

  return { state, login, logout, selectEmployee, loadDirectory, loadCatalog, refreshEmployee, loadHR,
    complete, retryCompletion: sendCompletion, discardCompletion, importFiles }
}
