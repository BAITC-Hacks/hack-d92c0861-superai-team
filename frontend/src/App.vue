<script setup>
// Integration shell only. Sayat replaces the JSON pane with the employee/HR screens.
import { ref, watch } from 'vue'
import { api, setToken } from './api'
const token = ref(''), identity = ref(null), employees = ref([]), employeeId = ref('')
const result = ref(null), error = ref(''), busy = ref(false)
watch(employeeId, () => { result.value = null; error.value = '' })
async function login() {
  busy.value = true; error.value = ''; result.value = null; identity.value = null; employees.value = []
  try {
    setToken(token.value)
    const user = await api.me()
    const options = user.role === 'hr' ? await api.employees()
      : [{employee_id: user.employee_id, full_name: 'Мой профиль'}]
    identity.value = user; employees.value = options; employeeId.value = options[0]?.employee_id || ''
    token.value = '' // Credential remains in memory in api.js, not in browser persistence.
  } catch (e) { setToken(''); error.value = e.message }
  finally { busy.value = false }
}
async function loadProfile() {
  busy.value = true; error.value = ''; result.value = null
  try { result.value = {profile: await api.profile(employeeId.value),
                         recommendations: await api.recommendations(employeeId.value)} }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
function logout() {
  setToken(''); identity.value = null; result.value = null; employees.value = []; employeeId.value = ''
}
</script>
<template>
  <main>
    <h1>Career Quest — стартовый каркас</h1>
    <p>Это проверка соединения Vue → API → AI-модуль, не финальный интерфейс.</p>
    <form v-if="!identity" @submit.prevent="login">
      <label>Локальный demo-токен из .env <input v-model="token" type="password" autocomplete="off" required></label>
      <button :disabled="busy">Войти</button>
    </form>
    <section v-else>
      <p>Роль: {{ identity.role }} <button @click="logout" :disabled="busy">Выйти</button></p>
      <label>Сотрудник <select v-model="employeeId" :disabled="busy">
        <option v-for="e in employees" :key="e.employee_id" :value="e.employee_id">{{e.employee_id}} — {{e.full_name}}</option>
      </select></label>
      <button @click="loadProfile" :disabled="busy || !employeeId">Загрузить профиль и шаги</button>
    </section>
    <p v-if="busy" role="status">Загрузка…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <section v-if="result">
      <h2>Режим рекомендации: {{ result.recommendations.mode }}</h2>
      <p v-if="result.recommendations.mode === 'fallback'">Резервный алгоритм: это не ответ LLM.</p>
      <pre>{{JSON.stringify(result, null, 2)}}</pre>
    </section>
  </main>
</template>
<style>
body {font-family:system-ui,sans-serif;margin:0}main {max-width:1000px;margin:32px auto;padding:0 24px}
input,select,button {font:inherit;padding:8px;margin:6px}pre {white-space:pre-wrap;overflow-wrap:anywhere}
button {cursor:pointer}button:disabled {cursor:wait}label {display:inline-block}
</style>
