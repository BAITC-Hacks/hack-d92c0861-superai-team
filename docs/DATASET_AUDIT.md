# Разбор фактически приложенного датасета

Источник: career_quest_dataset.zip, папка case_1/career_quest_dataset/.
Проверены README.md, employees.json, events.json, skills.json, activity_history.csv.
README.ru.md/README.kz.md как содержательных файлов в архиве нет: присутствуют только служебные
AppleDouble __MACOSX/._README.ru.md и __MACOSX/._README.kz.md. Их нельзя принимать за переводы.
Фактические поля названий/описаний в приложенном наборе — английские; локализация UI отдельно.

| Набор | Фактический объём |
|---|---:|
| employees | 200 |
| events | 40 |
| skills | 60 |
| role_profiles | 32 (8 ролей × 4 грейда) |
| activity_history | 2743 записей |
| completed после last_review_date | 318 записей |
| career_goal с другой ролью | 28 сотрудников |
| career_goal=null | 66 сотрудников |

Snapshot: 2026-10-01. История: 2024-10-01–2026-09-30.
Это модельная дата из набора, хотя дата работы над архитектурой — 23 сентября 2026 года.
История: completed 2178, declined 104, dropped 160, no_show 195, overdue 90, in_progress 16.

Важные schema-детали: JSON — objects с meta и именованными массивами, не списки в корне.
У events есть prerequisites, target_roles/grades, mandatory, format, upcoming_sessions,
развиваемые навыки с gain/max_level. EV_036 допускает повторное участие после completed.
У role_profiles — required_skills и critical_skills. У employee — last_review_date и career_goal.
Нельзя считать старую историю повторно поверх skill assessment. Missing skill = 0.
Дедлайн due_date относится к mandatory; «добровольное обучение выполнено в срок» из этих полей не следует.

## Наши решения, не новые требования источника
Приоритет валидного career_goal; Lead без цели сверяется с текущей матрицей; строгий текущий
role/grade access при ротации; формула процента по сумме покрытых требований; similar history по
типу ИЛИ общему навыку; веса fallback — наши стартовые политики и требуют проверки качества.
Seed CSV.date используется как доступная временная отметка для сравнения с last_review_date,
хотя для self_paced это начало/назначение. Точное окончание source не даёт; его нельзя выдумывать.
Новые runtime-завершения проектируются с отдельным completed_at.

## Контроль целостности исходных файлов (SHA-256)
- `README.md`: `cd4a190009c6bb40c8f339b48da251af63adb2a50329b3ec77e8711315d8d96f`
- `employees.json`: `bcf366fc3cecde04401200e7ea192ae5b008fa5de8b13b246ef98b1ba65945de`
- `events.json`: `e82f08dfd947b0f4bfda2d984d7e2adcdb1e2b96f239223cf4ad14dd05c1b14b`
- `skills.json`: `12d99e52b5ed7e95d9d817380b774145e53d65a2b6c961f3c57e9f09a021edee`
- `activity_history.csv`: `daaec3190b7d3d37f6a820a4c2926fd3a94a4e7dc22ea8f00b350a008d11993b`
