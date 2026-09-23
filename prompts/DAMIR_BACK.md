# Задание Codex: Дамир / backend

Ты работаешь в существующем Career Quest, ветка damir-back. Прочитай AGENTS.md, CONTEXT.md,
README.md, docs/API_CONTRACT.md, shared/contracts.py и docs/DATASET_README.md.
Сначала git status и осмотр уже написанного кода. Не перезаписывай чужую реализацию.
Не меняй Vue, ai/**, URL и публичные JSON-схемы. Общие изменения сначала явно предложи команде.

Твоя цель — завершить backend для сквозного MVP. Каркас уже умеет загрузку исходного датасета,
эффективные навыки, trajectory, eligibility, профиль, demo-авторизацию и вызов ai.engine.recommend.
Не реализуй их с нуля и не дублируй формулы во frontend/AI.

## Приоритет 1: состояние и завершение
Реализуй /api/employees/{id}/complete вместо 501. Используй SQLite (stdlib sqlite3) для простого
транзакционного runtime-store, одного backend worker достаточно. Seed JSON/CSV остаются read-only.
Сохраняй imports/current snapshot, revision и runtime completion/idempotency ledger так, чтобы
после restart результат сохранялся. Разделяй assessed skills и рассчитанные effective skills.
Для runtime completion используй отдельное completed_at: в seed CSV нет точного completion_at.
Повторный клик/retry не увеличивает навыки повторно. Точная идемпотентная повторная операция должна
успешно возвращаться даже со старым expected_data_version; изменённый payload с тем же ключом => 409.
С новым ключом уже завершённый обычный event тоже не даёт gain. Исключение EV_036 требует нового участия.
Применяй текущую серверную авторизацию, проверку допустимости и общую apply_gains, не клиентские числа.
Выполнение future scheduled-сессии не симулировать молча; демонстрацию строим на self_paced.

## Приоритет 2: обязательный импорт жюри
Реализуй /api/admin/import с отдельными employees JSON и history CSV.
Импорт — атомарный merge согласно API_CONTRACT, не replace и не «только исходные 200 IDs».
Проверяй объединённый snapshot, ссылки и диапазоны; UTF-8 BOM; size limit при чтении.
На невалидном файле ничего не сохраняй. Не потеряй текущую историю и runtime-завершения.
Не создавай загрузчик произвольного ZIP в HTTP: отдельные JSON/CSV достаточны и проще.

## Приоритет 3: HR и кэш
Реализуй /api/hr/overview: разрывы по целям/critical, нет доступных шагов с причиной,
счётчики участия по статусам. Не вызывай LLM 200 раз. Используй локальные расчёты.
Добавь кеш рекомендаций по employee_id + data_version + model configuration, с инвалидированием.
Ошибки provider остаются fallback в AI; 401/403 и конфликты — ошибки API, их нельзя превращать в успех.

## Тесты и готовность
Заменяй starter-тест ожидания 501 acceptance-тестами ПО МЕРЕ реализации маршрутов.
Добавь: повтор completion; другой key для уже completed; session uniqueness EV_036; restart;
новый профиль+история через multipart; повторный импорт no-op; invalid import rollback;
manager/reference validation; employee→HR/другой employee = 403; новая версия после изменения.
Проверки: python -m pytest -q; python scripts/check_dataset.py.
Напиши короткий отчёт: что готово, какие файлы изменены, реальные команды/результаты тестов,
что ещё не готово, есть ли потребность менять общий контракт. Не делай merge/push самостоятельно.
