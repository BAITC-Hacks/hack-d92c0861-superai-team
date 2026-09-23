# Career Quest — стартовая основа для команды из трёх человек

**Текущая работа команды в одной папке:** [что делать сейчас](docs/START_HERE.md). Ниже — описание первоначального каркаса; сведения о ветках и первоначальной проверке не являются статусом готового MVP.

**Это не готовый MVP.** Каркас создан для общей интеграционной базы и параллельной работы.
Старые версии AI и интерфейса есть в отдельных ветках репозитория; переносить их целиком поверх текущих файлов нельзя.

## Что работает, а что нужно завершить
Работает: загрузка реального датасета, проверки ссылок/диапазонов, effective skills после оценки,
целевая матрица, критические разрывы, eligibility, прогноз gain/max_level, профиль, каталог,
рекомендации с фактами, server-side demo-role access, fallback, интерфейс к configurable LLM.
Vue содержит только integration shell, а не конечные экраны.

**Три маршрута намеренно возвращают 501:** completion, admin/import, hr/overview.
Нет durable runtime-store, recommendation cache, финального UI и live-проверки провайдера.
Реализация этих частей распределена в prompts/. Не выдавать их за завершённые функции.
Живой AI проверяется с ключом команды; автоматически включён только явный fallback.
Результаты проверок в docs/VALIDATION.md.

## Структура
```text
backend/   main.py, data_loader.py, domain.py     — Дамир
ai/        engine.py, provider.py                — Михаил
frontend/  Vue, api.js                           — Саят
shared/    contracts.py                         — общий контракт
prompts/   три задания + архитектурный аудит
scripts/   безопасный seed, setup_env, проверка датасета
CONTEXT.md, AGENTS.md, docs/API_CONTRACT.md       — правила интеграции
```
Мы не сжимаем три независимые зоны в один app.py ради формального числа файлов.

## Первый запуск на Windows PowerShell
Требования этой основы: Python 3.11+, Node.js 22.12+ и npm. Официальный ZIP остаётся у команды локально.
Сначала перейти в папку основы/согласованного проекта. Команды выполняются по очереди; при ошибке остановиться.
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\seed_data.py "C:\путь\career_quest_dataset.zip"
.\.venv\Scripts\python.exe scripts\setup_env.py
npm --prefix frontend install
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\check_dataset.py
.\.venv\Scripts\python.exe run.py --dev
```
Не требуется активация venv или изменение ExecutionPolicy.
UI: http://127.0.0.1:5173; Swagger: http://127.0.0.1:8000/docs.
Войдите через HR_TOKEN или EMPLOYEE_TOKEN из локального .env. Не показывайте ключи на стриме/скриншотах.
HR выбирает произвольный профиль; employee-token привязан к EMPLOYEE_ID (по умолчанию E0001).

**Для уже существующего репозитория:** seed не перезаписывает файлы. Если четыре файла уже в docs/,
не запускайте seed заново. Укажите DATA_DIR в .env. setup_env также не перезаписывает существующий .env:
недостающие параметры нужно добавить вручную, сохранив существующие ключи и имена переменных.
Архив не включает сырые данные, .env, node_modules и .venv. Передать исходный ZIP участникам разрешённым способом.

## Запуск собранной версии одной командой
После установки зависимостей и seed:
```powershell
npm --prefix frontend run build
.\.venv\Scripts\python.exe run.py
```
Один backend на http://127.0.0.1:8000 отдаёт и API, и собранный Vue. Для dev используется один launcher
run.py --dev, запускающий API и Vite. Не включайте несколько API-workers с незавершённым in-memory state.

## Настройка LLM
В серверном .env заполнить LLM_BASE_URL, LLM_MODEL, LLM_API_KEY для одобренного endpoint,
затем AI_ENABLED=true. base URL содержит /v1, когда этого требует provider; код добавляет /chat/completions.
Модель должна поддерживать этот API и обычный JSON-ответ с event_ids. Провайдер-специфичные параметры
меняются только в ai/provider.py. Никакая конкретная модель не зафиксирована в проекте.
Проверить живой запрос: mode=llm, валидные IDs, осмысленный выбор, время меньше лимита ТЗ.
Нет ключа/сбой/таймаут/невалидный ответ => mode=fallback. В UI это явно показывается.
ТЗ разрешает облачные модели, но ограничивает вынос данных: заранее согласуйте допустимый сервис
и передавайте минимальный контекст. По умолчанию сетевые AI-запросы отключены.

## Разделение работы
Дамир: prompts/DAMIR_BACK.md — state, completion, импорт, HR, cache и API tests.
Саят: prompts/SAYAT_FRONT.md — профиль, карточки, completion flow, HR/upload и состояния.
Михаил: prompts/MIKHAIL_AI.md — живой provider, multi-factor качество, фактология, adversarial tests.
Общий план/merge: docs/TEAM_PLAN.md. Аудит: prompts/AUDIT.md.

## Существенные решения и ограничения
as_of_date берётся из meta: 2026-10-01, не системное «сегодня».
Дата seed CSV не всегда точная дата завершения; это отмечено в CONTEXT.md.
career_goal имеет приоритет над next_grade — продуктовое решение, не буквально заданный алгоритм ТЗ.
Cross-role goal не расширяет target_roles/target_grades мероприятия автоматически.
Часть сотрудников закономерно не имеет доступного gap-reducing события; это HR-сигнал, не баг само по себе.
Процент — покрытие матрицы навыков; повышение не обещается и не выполняется автоматически.
Аутентификация — demo Bearer credentials с проверками API, не production SSO и не полноценная IAM.
Не использовать реальные персональные данные и публичные рейтинги сотрудников.

## Источники
ТЗ из прикреплённого DOCX; README и четыре файла из предоставленного ZIP.
Технические справочники, сверенные при подготовке:
- FastAPI response model / upload: https://fastapi.tiangolo.com/tutorial/response-model/ и https://fastapi.tiangolo.com/tutorial/request-files/
- Vue quick start: https://vuejs.org/guide/quick-start.html
- Codex AGENTS.md: https://developers.openai.com/codex/guides/agents-md/
- Chat completions: https://developers.openai.com/api/reference/resources/chat
- Git merge: https://git-scm.com/docs/git-merge
