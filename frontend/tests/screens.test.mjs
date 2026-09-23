import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
import { createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'

const root = fileURLToPath(new URL('../', import.meta.url))
const fixture = async name => JSON.parse(await readFile(new URL(`../../docs/examples/${name}.json`, import.meta.url), 'utf8'))
const leaves = (object, prefix = '') => Object.entries(object).flatMap(([key, value]) => typeof value === 'object' ? leaves(value, `${prefix}${key}.`) : [`${prefix}${key}`]).sort()

test('translated API screens render real contract shapes; completion controls respect explicit session inputs', async () => {
  const server = await createServer({ root, configFile: `${root}/vite.config.js`, server: { middlewareMode: true }, appType: 'custom' })
  try {
    const { default: i18n } = await server.ssrLoadModule('/src/i18n.js')
    const { default: Employee } = await server.ssrLoadModule('/src/components/EmployeeView.vue')
    const { default: Hr } = await server.ssrLoadModule('/src/components/HrView.vue')
    const { default: Card } = await server.ssrLoadModule('/src/components/RecommendationCard.vue')
    const { default: App } = await server.ssrLoadModule('/src/App.vue')
    const profile = await fixture('profile'), recommendations = await fixture('recommendations'), overview = await fixture('hr')
    const render = (component, props) => renderToString(createSSRApp(component, props).use(i18n))
    const keys = leaves(i18n.global.messages.value.ru)
    for (const locale of ['ru', 'kk', 'en']) {
      assert.deepEqual(leaves(i18n.global.messages.value[locale]), keys)
      i18n.global.locale.value = locale
      const employee = await render(Employee, { profile, recommendations })
      assert.ok(employee.includes(profile.employee.full_name))
      assert.ok(employee.includes(i18n.global.t('employee.coverage')))
      assert.ok(employee.includes(i18n.global.t('employee.fallback')))
      for (const factor of recommendations.steps[0].factors) assert.ok(employee.includes(factor.text))
      const hr = await render(Hr, { overview })
      assert.ok(hr.includes('hr-employees-file') && hr.includes('hr-history-file'))
      assert.ok(hr.includes('100'))
      const login = await render(App)
      assert.ok(login.includes('type="password"'))
      assert.ok(!login.includes('hr-import-title'))
      for (const html of [employee, hr, login]) assert.ok(!/>\s*(employee|hr|integration)\./.test(html))
    }
    const source = { step: recommendations.steps[0], asOfDate: profile.as_of_date, history: profile.history }
    const enabled = await render(Card, source)
    assert.ok(/<button[^>]*type="submit"(?![^>]*disabled)/.test(enabled))
    const disabled = await render(Card, { ...source, disabled: true })
    assert.ok(/<button[^>]*type="submit"[^>]*disabled/.test(disabled))
    const future = await render(Card, { step: recommendations.steps[1], asOfDate: profile.as_of_date, event: { upcoming_sessions: ['2026-10-08'] } })
    assert.ok(/<button[^>]*type="submit"[^>]*disabled/.test(future))
    const priorParticipation = await render(Card, { step: recommendations.steps[1], asOfDate: profile.as_of_date, history: [{event_id:'EV_036',record_id:'R_TEST',date:'2026-09-20',status:'in_progress'}] })
    assert.ok(/<button[^>]*type="submit"(?![^>]*disabled)/.test(priorParticipation))
    const noSteps = await render(Employee, { profile, recommendations: {...recommendations,steps:[],no_step_reason:'No eligible step'} })
    assert.ok(noSteps.includes('No eligible step'))
    const error = await render(Employee, { profile, recommendationError: {status:501,message:'Not implemented'}, completion: {busy:false,pending:{retryable:true},error:{status:501,message:'Not implemented'},result:null} })
    assert.ok(error.includes('Not implemented'))
    assert.ok(!error.includes('completion-success'))
  } finally { await server.close() }
})
