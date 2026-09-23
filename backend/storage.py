"""Single-worker SQLite state. Publish immutable snapshots only after commit."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import uuid4

from backend.data_loader import Dataset, DatasetError, index_unique, parse_dataset, read_history, read_json
from backend.domain import REPEATABLE_EVENTS, apply_gains, effective_skills, trajectory
from shared.contracts import CompletionRequest, CompletionResponse, ImportResponse


class OperationError(ValueError):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code = status, code


def encode(data: Dataset) -> str:
    value = asdict(data)
    value['as_of_date'] = data.as_of_date.isoformat()
    value['role_profiles'] = list(data.role_profiles.values())
    return json.dumps(value, ensure_ascii=False)


def decode(raw: str) -> Dataset:
    value = json.loads(raw)
    value['as_of_date'] = date.fromisoformat(value['as_of_date'])
    value['role_profiles'] = {(p['role'], p['grade']): p for p in value['role_profiles']}
    return Dataset(**value)


class RuntimeStore:
    def __init__(self, seed: Dataset, path: str | Path):
        if str(path) != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        self.connection.execute('PRAGMA synchronous = FULL')
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS snapshot (
                id INTEGER PRIMARY KEY CHECK(id = 1), payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS idempotency (
                actor TEXT NOT NULL, employee_id TEXT NOT NULL, key TEXT NOT NULL,
                request TEXT NOT NULL, response TEXT NOT NULL,
                PRIMARY KEY(actor, employee_id, key));
        ''')
        with self.connection:
            self.connection.execute('INSERT OR IGNORE INTO snapshot VALUES (1, ?)', (encode(seed),))
        self.data = decode(self.connection.execute('SELECT payload FROM snapshot WHERE id=1').fetchone()[0])

    def close(self):
        self.connection.close()

    @contextmanager
    def transaction(self):
        with self.lock:
            self.connection.execute('BEGIN IMMEDIATE')
            try:
                yield
                self.connection.commit()
                self.data = decode(self.connection.execute('SELECT payload FROM snapshot WHERE id=1').fetchone()[0])
            except BaseException:
                self.connection.rollback()
                raise

    def save(self, candidate: Dataset):
        self.connection.execute('UPDATE snapshot SET payload=? WHERE id=1', (encode(candidate),))

    def complete(self, employee_id: str, body: CompletionRequest, user: dict) -> CompletionResponse:
        actor = user['role'] + ':' + (user['employee_id'] or 'hr')
        payload = body.model_dump_json()
        scope = (actor, employee_id, body.idempotency_key)
        with self.transaction():
            existing = self.connection.execute(
                'SELECT request, response FROM idempotency WHERE actor=? AND employee_id=? AND key=?',
                scope).fetchone()
            if existing:
                if existing[0] != payload:
                    raise OperationError(409, 'IDEMPOTENCY_CONFLICT', 'Key already used for another request')
                return CompletionResponse.model_validate_json(existing[1]).model_copy(update={'already_applied': True})
            data = self.data
            if body.expected_data_version != data.version:
                raise OperationError(409, 'VERSION_CONFLICT', 'Reload the profile before completing an activity')
            if body.event_id not in data.events:
                raise OperationError(404, 'NOT_FOUND', 'Event not found')
            event = data.events[body.event_id]
            employee = data.employees[employee_id]
            rows = [r for r in data.employee_history(employee_id) if r['event_id'] == body.event_id]
            participation = None
            if body.participation_record_id is not None:
                participation = next((r for r in rows if r['record_id'] == body.participation_record_id), None)
                if participation is None:
                    raise OperationError(422, 'INVALID_PARTICIPATION', 'Participation does not belong to this employee/event')
            repeatable = body.event_id in REPEATABLE_EVENTS
            if repeatable and participation is None and body.session_date is None:
                raise OperationError(422, 'PARTICIPATION_REQUIRED', 'Recurring events require a participation or session date')
            if participation and body.session_date and body.session_date.isoformat() != participation['date']:
                raise OperationError(422, 'SESSION_MISMATCH', 'Session does not match participation')
            session = body.session_date.isoformat() if body.session_date else (participation['date'] if participation else None)
            already = any(r['status'] == 'completed' and (
                not repeatable or r['date'] == session) for r in rows)
            current = effective_skills(data, employee_id)
            candidate = data
            deltas = []
            if not already:
                if event['mandatory'] or employee['role'] not in event['target_roles'] or employee['grade'] not in event['target_grades']:
                    raise OperationError(409, 'NOT_ELIGIBLE', 'Activity is not available for this role/grade')
                if any(current.get(sid, 0) < need for sid, need in event['prerequisites'].items()):
                    raise OperationError(409, 'PREREQUISITES_NOT_MET', 'Activity prerequisites are not met')
                if participation is None and repeatable and session:
                    same_session = [r for r in rows if r['date'] == session]
                    if len(same_session) > 1:
                        raise OperationError(422, 'PARTICIPATION_REQUIRED', 'Choose the participation to complete')
                    participation = same_session[0] if same_session else None
                if participation is None and not repeatable:
                    ongoing = [r for r in rows if r['status'] == 'in_progress']
                    if len(ongoing) > 1:
                        raise OperationError(422, 'PARTICIPATION_REQUIRED', 'Choose the participation to complete')
                    participation = ongoing[0] if ongoing else None
                    if participation:
                        if session and session != participation['date']:
                            raise OperationError(422, 'SESSION_MISMATCH', 'Session does not match participation')
                        session = participation['date']
                if participation and participation['status'] != 'in_progress':
                    raise OperationError(409, 'INVALID_PARTICIPATION_STATE', 'Only an ongoing participation can be completed')
                if session and session > data.as_of_date.isoformat():
                    raise OperationError(409, 'FUTURE_SESSION', 'A future session cannot be completed')
                if event['format'] != 'self_paced' and participation is None:
                    if session is None or session not in event['upcoming_sessions']:
                        raise OperationError(409, 'SESSION_REQUIRED', 'Choose an actual available session')
                if event['format'] == 'self_paced' and participation is None and session not in (None, data.as_of_date.isoformat()):
                    raise OperationError(422, 'INVALID_SESSION', 'New self-paced completion uses the snapshot date')
                candidate = deepcopy(data)
                candidate.runtime_completions.append({
                    'record_id': 'LIVE_' + uuid4().hex, 'employee_id': employee_id,
                    'event_id': body.event_id, 'completed_at': (datetime.combine(data.as_of_date, time(12))
                        + timedelta(microseconds=len(data.runtime_completions))).isoformat(timespec='microseconds'),
                    'session_date': session or data.as_of_date.isoformat(),
                    'participation_record_id': participation['record_id'] if participation else '',
                    'assigned_by': 'hr' if user['role'] == 'hr' else 'self',
                })
                candidate.version += 1
                _, deltas = apply_gains(current, event)
                self.save(candidate)
            response = CompletionResponse(employee_id=employee_id, event_id=body.event_id,
                already_applied=already, data_version=candidate.version, skill_deltas=deltas,
                trajectory=trajectory(candidate, employee, effective_skills(candidate, employee_id)))
            self.connection.execute('INSERT INTO idempotency VALUES (?, ?, ?, ?, ?)',
                                    (*scope, payload, response.model_dump_json()))
        return response

    def import_files(self, employees_raw: bytes | None, history_raw: bytes | None) -> ImportResponse:
        if employees_raw is None and history_raw is None:
            raise DatasetError('Upload employees and/or history')
        with self.transaction():
            data = self.data
            employees = deepcopy(data.employees)
            history = {r['record_id']: r for r in data.history}
            added = updated = history_added = unchanged = 0
            if employees_raw is not None:
                doc = read_json(employees_raw)
                if not isinstance(doc.get('meta'), dict) or doc['meta'].get('as_of_date') != data.as_of_date.isoformat():
                    raise DatasetError('as_of_date must match the current snapshot')
                for eid, employee in index_unique(doc.get('employees'), 'employee_id').items():
                    if eid not in employees:
                        added += 1
                    elif employees[eid] != employee:
                        updated += 1
                    employees[eid] = employee
            if history_raw is not None:
                imported = read_history(history_raw)
                # Validate the upload itself before merging it with stored records.
                # An identical row already in storage is a no-op; duplicate IDs
                # inside one uploaded file are invalid even when rows match.
                index_unique(imported, 'record_id')
                live_ids = {r['record_id'] for r in data.runtime_completions}
                for row in imported:
                    rid = row['record_id']
                    if rid in live_ids:
                        raise DatasetError(f'History record conflicts with runtime completion: {rid}')
                    if rid in history:
                        if history[rid] != row:
                            raise DatasetError(f'Conflicting history record: {rid}')
                        unchanged += 1
                    else:
                        if row['status'] == 'completed' and any(
                            c['employee_id'] == row['employee_id'] and c['event_id'] == row['event_id']
                            and (row['event_id'] not in REPEATABLE_EVENTS or c['session_date'] == row['date'])
                            for c in data.runtime_completions):
                            raise DatasetError(f'Completion overlaps the runtime ledger: {rid}')
                        history[rid] = row
                        history_added += 1
            meta = {'as_of_date': data.as_of_date.isoformat()}
            candidate = parse_dataset({'meta': meta, 'employees': list(employees.values())},
                {'meta': meta, 'events': list(data.events.values())},
                {'meta': meta, 'skills': list(data.skills.values()), 'role_profiles': list(data.role_profiles.values())},
                list(history.values()))
            candidate.runtime_completions = deepcopy(data.runtime_completions)
            candidate.version = data.version + int(bool(added or updated or history_added))
            if candidate.version != data.version:
                self.save(candidate)
            response = ImportResponse(employees_added=added, employees_updated=updated,
                history_added=history_added, history_unchanged=unchanged,
                data_version=candidate.version, warnings=[])
        return response
