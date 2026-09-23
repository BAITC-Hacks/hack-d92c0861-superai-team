# Отчёт проверки стартового архива

Проверена именно эта сгенерированная основа, НЕ уже существующий GitHub-репозиторий команды.
Среда: Python 3.13.5, Linux; Node.js 22.16.0, npm 10.9.2.

| Проверка | Результат |
|---|---|
| python -m pytest -q | PASS: 34 tests, 0.72 s в первоначальном полном прогоне |
| python scripts/check_dataset.py | PASS: все 200 профилей, 40 events, 60 skills, 32 role profiles, 2743 history |
| Детерминированный проход по 200 профилям | 0.849 s в одном прогоне этой среды; не обещание пользовательской задержки |
| Число допустимых вариантов всего | 474 при задокументированных starter-политиках |
| Нет gap-reducing доступного события | 34 из 200; это результат выбранных политик, не разметка организаторов |
| Примеры нового импорта | PASS: схема объединённого набора и три собственных regression-сценария |
| Python compileall | PASS |
| Node syntax check api.js / vite.config.js | PASS |
| OpenAPI генерация | PASS: docs/openapi.json |
| npm install / Vue build | NOT VERIFIED: npm registry DNS EAI_AGAIN; зависимости не установились |
| Браузерный end-to-end | NOT VERIFIED |
| Реальный LLM API | NOT VERIFIED: нет выбранного endpoint/ключа; только mocked unit tests |
| Completion / Import / HR API | NOT IMPLEMENTED: явные 501-заглушки, tests это подтверждают |
| Durable state / restart / cache | NOT IMPLEMENTED |

34 теста проверяют стартовые инварианты, а не все must-have готового продукта.
После реализации трёх маршрутов заменить проверку 501 acceptance-тестами, не оставлять ложный «зелёный» статус.
На машине команды выполнить npm install, npm run build, зафиксировать package-lock.json, пройти живой
UI→API→LLM сценарий, импорт, completion, повторный клик и restart. Это остаётся обязательной проверкой.

Реальная ошибка npm в среде подготовки: getaddrinfo EAI_AGAIN registry.npmjs.org.
В архив не включены .env, секреты, raw official dataset, node_modules, .venv или runtime-state.
