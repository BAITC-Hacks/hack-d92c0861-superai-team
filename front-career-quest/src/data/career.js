import skillData from './skills.json'
import employeeData from './employees.json'
import eventData from './events.json'
import historyData from './history.json'

const history = historyData.rows.map(row => Object.fromEntries(historyData.columns.map((key, index) => [key, row[index]])))

export const employees = employeeData.employees
export const events = eventData.events
export const skills = skillData.skills
export const profiles = skillData.role_profiles
export const snapshotDate = employeeData.meta.as_of_date
export { history }

export function requirementsFor(employee, role, grade) {
  const profile = profiles.find((item) => item.role === role && item.grade === grade)
  return Object.entries(profile?.required_skills ?? {}).map(([id, target]) => ({
    ...skills.find((skill) => skill.skill_id === id),
    current: employee.skills[id] ?? 0,
    target,
    critical: profile.critical_skills.includes(id),
  }))
}

export function progressFor(requirements) {
  const target = requirements.reduce((total, skill) => total + skill.target, 0)
  return target ? Math.round(requirements.reduce((total, skill) => total + Math.min(skill.current, skill.target), 0) / target * 100) : 0
}

export function eligibleFor(event, employee) {
  return event.target_roles.includes(employee.role)
    && event.target_grades.includes(employee.grade)
    && Object.entries(event.prerequisites).every(([id, level]) => (employee.skills[id] ?? 0) >= level)
}

export function completedBy(event, employee) {
  return history.some((row) => row.employee_id === employee.employee_id && row.event_id === event.event_id && row.status === 'completed')
}

export function recommendFor(employee, requirements) {
  return events.filter((event) => !event.mandatory && eligibleFor(event, employee)
    && (event.event_id === 'EV_036' || !completedBy(event, employee))
    && event.develops_skills.some((gain) => requirements.some((skill) => skill.skill_id === gain.skill_id
      && skill.current < skill.target && skill.current < gain.max_level)))
}
