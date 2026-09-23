import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'

process.chdir(fileURLToPath(new URL('.', import.meta.url)))
import fs from 'node:fs'
import { createServer } from 'vite'
import { createSSRApp, nextTick } from 'vue'
import { renderToString } from '@vue/server-renderer'
const store = new Map()
globalThis.localStorage = { getItem: key => store.get(key) ?? null, setItem: (key, value) => store.set(key, value) }
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
try {
  const { default: ProfilePage } = await server.ssrLoadModule('/src/components/ProfilePage.vue')
  const { default: App } = await server.ssrLoadModule('/src/App.vue')
  const { default: Workspace } = await server.ssrLoadModule('/src/components/CareerWorkspace.vue')
  const { default: i18n } = await server.ssrLoadModule('/src/i18n.js')
  const data = await server.ssrLoadModule('/src/data/career.js')
  const { employees, events, requirementsFor, progressFor, recommendFor, eligibleFor, completedBy } = data
  const defaultEmployee = employees.find(person => person.employee_id === 'E0017')
  const flatten = (object, prefix = '') => Object.entries(object).flatMap(([key, value]) => typeof value === 'object' ? flatten(value, `${prefix}${key}.`) : [`${prefix}${key}`]).sort()
  const baseline = flatten(i18n.global.messages.value.en)
  for (const locale of ['ru', 'kk', 'en']) {
    assert.deepEqual(flatten(i18n.global.messages.value[locale]), baseline)
    i18n.global.locale.value = locale
    await nextTick()
    const profileHtml = await renderToString(createSSRApp(ProfilePage, { employee: defaultEmployee }).use(i18n))
    assert.ok(profileHtml.includes(defaultEmployee.full_name))
    assert.ok(profileHtml.includes(i18n.global.t('design.profile')))
    assert.ok(!/>design\./.test(profileHtml))
    globalThis.location = { hash: '#profile' }
    const shellHtml = await renderToString(createSSRApp(App).use(i18n))
    assert.ok(/href="#profile"[^>]*class="profile-trigger"/.test(shellHtml))
    assert.ok(/href="#settings"[^>]*class="top-settings"/.test(shellHtml))
    assert.ok(shellHtml.includes('profile-hero'))
    for (const page of ['overview', 'path', 'catalog', 'team', 'settings', 'help']) {
      const app = createSSRApp(Workspace, { page, employee: defaultEmployee }).use(i18n)
      const html = await renderToString(app)
      assert.ok(/<h1(?:\s[^>]*)?>/.test(html), `${page}: missing heading`)
      assert.ok(!html.includes('NaN'), `${page}: NaN`)
      assert.ok(!/>pages\./.test(html), `${page}: untranslated key`)
      if (page === 'catalog') assert.equal((html.match(/class="activity-card"/g) || []).length, 40)
      if (page === 'team') assert.equal((html.match(/<small(?:\s[^>]*)?>E\d{4}<\/small>/g) || []).length, 200)
    }
  }
  const noGoal = employees.find(person => person.career_goal === null)
  const html = await renderToString(createSSRApp(Workspace, { page: 'path', employee: noGoal }).use(i18n))
  assert.ok(html.includes('No career goal is set'))
  assert.equal(progressFor([]), 0)
  assert.equal(progressFor([{current: 5, target: 4}, {current: 2, target: 4}]), 75)
  for (const employee of employees) {
    const reqs = requirementsFor(employee, employee.career_goal?.target_role || employee.role, employee.career_goal?.target_grade || employee.grade)
    assert.ok(reqs.length > 0)
    assert.ok(progressFor(reqs) >= 0 && progressFor(reqs) <= 100)
    for (const event of recommendFor(employee, reqs)) {
      assert.ok(!event.mandatory && eligibleFor(event, employee))
      assert.ok(event.event_id === 'EV_036' || !completedBy(event, employee))
    }
  }
  const sources = ['src/App.vue', 'src/components/CareerWorkspace.vue', 'src/components/EventCard.vue', 'src/components/ProfilePage.vue'].map(file => fs.readFileSync(file, 'utf8')).join('\n')
  for (const [, key] of sources.matchAll(/\bt\('([^']+)'/g)) assert.ok(baseline.includes(key), key)
  console.log('PASS: 18 workspace + 3 profile + 3 shell renders, catalog and team counts, missing goal, key parity, progress and recommendation rules for 200 profiles.')
} finally { await server.close() }
