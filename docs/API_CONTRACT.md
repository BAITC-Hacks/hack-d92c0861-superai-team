# API v1 — граница трёх веток

Авторитетные Pydantic-схемы: shared/contracts.py. OpenAPI: GET /openapi.json; Swagger: /docs.
В .env на сервере HR_TOKEN, EMPLOYEE_TOKEN, EMPLOYEE_ID. В HTTP: Authorization: Bearer <token>.
Токены не публикуются в документации и не возвращаются /api/auth/me.

| Метод | Путь | Доступ | Статус starter |
|---|---|---|---|
| GET | /api/health | Без токена | Работает |
| GET | /api/auth/me | Employee/HR | Работает |
| GET | /api/employees | HR | Работает, список кратких профилей |
| GET | /api/employees/{id} | Свой/HR | Работает, ProfileResponse |
| GET | /api/employees/{id}/recommendations | Свой/HR | Работает, RecommendationResponse |
| GET | /api/events | Employee/HR | Работает, каталог |
| GET | /api/skills | Employee/HR | Работает, skills + role_profiles |
| POST | /api/employees/{id}/complete | Свой/HR | 501, реализует Дамир |
| POST | /api/admin/import | HR | 501, реализует Дамир |
| GET | /api/hr/overview | HR | 501, реализует Дамир |

## Python boundary
```python
from shared.contracts import RecommendationContext, RecommendationResponse
async def recommend(context: RecommendationContext) -> RecommendationResponse:
    ...
```
Backend вызывает await recommend(build_context(dataset, employee_id)). AI не читает файлы и не хранит state.
Frontend не вычисляет уровни/прогресс и не пытается самостоятельно выбирать следующие события.

## Completion
JSON:
```json
{"event_id":"EV_SYS","idempotency_key":"<UUID>","expected_data_version":1,
 "participation_record_id":null,"session_date":null}
```
UUID создаётся один раз на пользовательское действие, а не заново при сетевом retry.
Сервер проверяет автора, существование события, допустимость участия и expected_data_version.
Одинаковый ключ + тот же запрос: вернуть сохранённый результат без повторного начисления.
Одинаковый ключ + другой запрос: 409. Idempotency lookup выполняется до отказа по устаревшей версии
для точного повторного запроса. Ключ привязан к актору/сотруднику, хранится вместе с результатом.
У обычной активности уже completed в seed или runtime: повторный прирост запрещён даже с новым ключом.
EV_036 повторяется только как другое реальное участие/сессия, не повторным кликом.
Все новые completed_at относятся к модельной шкале времени. Не отмечать будущую scheduled-сессию
фактически пройденной сегодня. Для демонстрации выбрать доступную self_paced-активность либо начатое участие.
Новое завершение сохранять в отдельном runtime-ledger с completed_at. Не пересчитывать поверх уже
материализованных effective_skills: база оценки + послеревью seed-completed + новые runtime-completed.
Когда есть participation_record_id, HR-view должен учитывать обновлённое состояние одного участия,
а не дублировать запись in_progress и её завершение как двух участников.
В ответе CompletionResponse: skill_deltas и новая trajectory; UI затем перезапрашивает profile/recommendations.

## Import — must-have, не замена каталога
multipart/form-data: поле employees = JSON с meta/employees; поле history = CSV исходной схемы.
Можно загрузить оба файла или один, но не пустой запрос. Максимум 5 MiB на файл (проверить фактическое чтение).
Поддержать дополнительные ID, не ограничивать E0001..E0200 и не требовать ровно 200 записей.
Все операции сначала собираются во временный snapshot с текущими справочниками.
Employee upsert по employee_id; новые добавляются, существующие профили заменяются целиком по схеме.
History merge по record_id: точная копия — no-op; тот же ID с отличающимся содержимым — 422 conflict,
вместо тихого overwrite. Нельзя потерять старую историю или live-completions.
Проверить manager_id относительно объединённого набора; события/навыки/цели должны существовать.
Проверить метадату as_of_date, типы, диапазоны, даты и ссылки. Ошибка => весь импорт отклоняется.
Сохранение и увеличение data_version — атомарно; повторный полностью идентичный импорт ничего не меняет.
После успешного изменения сбросить recommendation-cache и перечитать HR/profile, без рестарта сервера.
Загрузка событий/навыков через UI не обязательна: в ТЗ для защиты требуются дополнительные профили и история.

## HR
Не делать LLM-запросы на каждого сотрудника. Агрегировать effective_skills и build_context локально.
Для gap_rate знаменатель — сотрудники, у которых конкретный навык входит в требования их цели,
не все сотрудники банка. Значение 0..1, фронт показывает проценты.
Отсутствие шага — нет допустимого события, реально уменьшающего target gap; не означает отсутствие потенциала.
participation: счётчики всех исходных статусов, без выдуманного поля «пройдено в срок» для добровольных
событий: due_date в исходном CSV предусмотрен только для обязательных.
Личный рейтинг сотрудников не создавать. Персональные исключения видны только HR.

## Ошибки и state
401 — нет/невалиден токен; 403 — нет прав; 404 — объект не найден; 409 — конфликт версии/операции;
422 — невалидный ввод; 501 — только временные starter-заглушки.
Прикладная ошибка: {"detail":{"code":"...","message":"..."}}.
Стандартная FastAPI validation-ошибка может иметь detail как массив; api.js уже обрабатывает её безопасно.
Рекомендация содержит data_version. Cache-key включает employee_id, data_version, конфигурацию модели.
Не отдавать кэш другого сотрудника; завершение/импорт инвалидируют его.
