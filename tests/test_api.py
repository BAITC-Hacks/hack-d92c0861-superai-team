from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import csv
import io
import json

import pytest
from fastapi.testclient import TestClient

from backend.data_loader import CSV_COLUMNS
from backend.main import create_app

HR={'Authorization':'Bearer test-hr-token'}
EMP={'Authorization':'Bearer test-employee-token'}


def test_health(client):
    assert client.get('/api/health').json()['as_of_date']=='2026-10-01'


def test_authentication_required(client):
    assert client.get('/api/employees').status_code==401


def test_employee_cannot_read_hr_or_other_employee(client):
    assert client.get('/api/employees',headers=EMP).status_code==403
    assert client.get('/api/hr/overview',headers=EMP).status_code==403
    assert client.get('/api/employees/E0002',headers=EMP).status_code==403
    assert client.get('/api/employees/E0002/recommendations',headers=EMP).status_code==403
    assert client.get('/api/employees/E0001',headers=EMP).status_code==200


def test_hr_can_inspect_arbitrary_profile(client):
    assert len(client.get('/api/employees',headers=HR).json())==2
    assert client.get('/api/employees/E0002',headers=HR).status_code==200
    assert client.get('/api/employees/NONEXISTENT',headers=HR).status_code==404


def test_recommendations_schema(client):
    response=client.get('/api/employees/E0001/recommendations',headers=EMP)
    assert response.status_code==200
    assert len(response.json()['steps'])<=3
    assert response.json()['mode']=='fallback'


def completion(client, event='EV_SYS', key='test-key-123', version=1, **extra):
    return client.post('/api/employees/E0001/complete', headers=EMP, json={
        'event_id': event, 'idempotency_key': key, 'expected_data_version': version, **extra})


def get_profile(client, eid='E0001'):
    response = client.get(f'/api/employees/{eid}', headers=HR)
    assert response.status_code == 200
    return response.json()


def history_csv(rows):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=sorted(CSV_COLUMNS))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode('utf-8-sig')


def upload(client, employees=None, history=None):
    files = {}
    if employees is not None:
        files['employees'] = ('employees.json', json.dumps(employees).encode('utf-8-sig'), 'application/json')
    if history is not None:
        files['history'] = ('activity_history.csv', history_csv(history), 'text/csv')
    return client.post('/api/admin/import', headers=HR, files=files)


def new_employee(documents, eid='JURY-NEW'):
    employee = deepcopy(documents['employees']['employees'][0])
    employee['employee_id'] = eid
    employee['manager_id'] = 'E0002'
    return {'meta': documents['employees']['meta'], 'employees': [employee]}


def participation(rid='RNEW', event='EV_SYS', eid='E0001', date='2026-08-01', status='in_progress'):
    return {'record_id': rid, 'employee_id': eid, 'event_id': event, 'date': date,
        'due_date': '', 'status': status, 'completion_pct': '100' if status == 'completed' else '30',
        'score': '', 'feedback_rating': '', 'assigned_by': 'self'}


def test_complete_retry_and_new_key_do_not_duplicate_gain(client):
    first = completion(client)
    assert first.status_code == 200
    assert first.json()['skill_deltas'][0]['delta'] == 1
    assert first.json()['data_version'] == 2
    assert first.json()['trajectory']['progress_pct'] == 60
    retry = completion(client)
    assert retry.status_code == 200 and retry.json()['already_applied'] is True
    assert retry.json() == {**first.json(), 'already_applied': True}
    again = completion(client, key='another-key', version=2)
    assert again.status_code == 200 and again.json()['already_applied'] is True
    assert again.json()['skill_deltas'] == [] and again.json()['data_version'] == 2
    profile = get_profile(client)
    assert profile['effective_skills']['SK_SYSTEM_DESIGN'] == 3
    assert profile['employee']['skills']['SK_SYSTEM_DESIGN'] == 2
    assert len([r for r in profile['history'] if r['event_id'] == 'EV_SYS']) == 1


def test_conflicting_key_and_stale_version(client):
    assert completion(client).status_code == 200
    assert completion(client, event='EV_TALK').status_code == 409
    assert completion(client, version=2).status_code == 409
    assert completion(client, key='new-stale-key').status_code == 409
    assert get_profile(client)['data_version'] == 2


def test_concurrent_retries_are_atomic(client):
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: completion(client), range(8)))
    assert all(r.status_code == 200 for r in responses)
    assert sum(not r.json()['already_applied'] for r in responses) == 1
    assert get_profile(client)['effective_skills']['SK_SYSTEM_DESIGN'] == 3


def test_missing_event_and_future_session(client):
    assert completion(client, event='UNKNOWN').status_code == 404
    assert completion(client, event='EV_TALK').status_code == 409
    assert completion(client, event='EV_TALK', session_date='2026-10-08').status_code == 409
    assert completion(client, event='EV_TALK', session_date='2026-09-20').status_code == 409
    assert completion(client, participation_record_id='R0').status_code == 422
    assert get_profile(client)['data_version'] == 1


@pytest.mark.parametrize('change', [
    {'mandatory': True}, {'target_roles': ['Other']}, {'target_grades': ['Lead']},
    {'prerequisites': {'SK_SYSTEM_DESIGN': 5}},
])
def test_completion_rechecks_eligibility(dataset, client, change):
    dataset.events['EV_SYS'].update(change)
    with TestClient(create_app(dataset)) as isolated:
        assert completion(isolated).status_code == 409
        assert get_profile(isolated)['data_version'] == 1


def test_old_participation_completed_now_counts_once_in_hr(client):
    row = participation()
    assert upload(client, history=[row]).status_code == 200
    before = client.get('/api/hr/overview', headers=HR).json()
    result = completion(client, version=2, participation_record_id='RNEW')
    assert result.status_code == 200
    profile = get_profile(client)
    assert profile['effective_skills']['SK_SYSTEM_DESIGN'] == 3
    record = next(r for r in profile['history'] if r['record_id'] == 'RNEW')
    assert record['date'] == '2026-08-01' and record['completed_at'].startswith('2026-10-01T')
    after = client.get('/api/hr/overview', headers=HR).json()
    event_before = next(e for e in before['participation'] if e['event_id'] == 'EV_SYS')
    event_after = next(e for e in after['participation'] if e['event_id'] == 'EV_SYS')
    assert event_before['total_records'] == event_after['total_records'] == 1
    assert event_after['by_status']['completed'] == 1
    assert event_after['by_status']['in_progress'] == 0
    # Re-uploading original source history is still a no-op, not a reset of the ledger.
    assert upload(client, history=[row]).json()['data_version'] == 3
    assert get_profile(client)['effective_skills']['SK_SYSTEM_DESIGN'] == 3


def test_recurring_club_requires_distinct_actual_participation(client):
    rows = [participation('CLUB1', 'EV_036', date='2026-09-20'),
            participation('CLUB2', 'EV_036', date='2026-09-25')]
    assert upload(client, history=rows).status_code == 200
    assert completion(client, event='EV_036', version=2).status_code == 422
    first = completion(client, event='EV_036', version=2, participation_record_id='CLUB1')
    assert first.status_code == 200 and first.json()['data_version'] == 3
    same = completion(client, event='EV_036', key='club-same-key', version=3, session_date='2026-09-20')
    assert same.status_code == 200 and same.json()['already_applied']
    second = completion(client, event='EV_036', key='club-next-key', version=3, session_date='2026-09-25')
    assert second.status_code == 200 and not second.json()['already_applied']
    profile = get_profile(client)
    assert profile['effective_skills']['SK_PUBLIC_SPEAKING'] == 2
    assert len([r for r in profile['history'] if r['event_id'] == 'EV_036']) == 2


def test_seed_completed_event_never_awards_second_gain(client):
    assert upload(client, history=[participation(status='completed')]).status_code == 200
    response = completion(client, version=2)
    assert response.status_code == 200 and response.json()['already_applied']
    assert get_profile(client)['effective_skills']['SK_SYSTEM_DESIGN'] == 2


def test_import_new_ids_and_history_and_noop(client, documents):
    employees = new_employee(documents)
    rows = [participation(eid='JURY-NEW', date='2026-09-20', status='completed')]
    response = upload(client, employees, rows)
    assert response.status_code == 200
    assert response.json() == {'employees_added': 1, 'employees_updated': 0,
        'history_added': 1, 'history_unchanged': 0, 'data_version': 2, 'warnings': []}
    assert get_profile(client, 'JURY-NEW')['effective_skills']['SK_SYSTEM_DESIGN'] == 3
    assert client.get('/api/employees/JURY-NEW/recommendations', headers=HR).status_code == 200
    retry = upload(client, employees, rows).json()
    assert retry['employees_added'] == retry['employees_updated'] == retry['history_added'] == 0
    assert retry['history_unchanged'] == 1 and retry['data_version'] == 2
    assert len(client.get('/api/employees', headers=HR).json()) == 3


def test_profile_upsert_preserves_live_completion(client, documents):
    assert completion(client).status_code == 200
    employees = deepcopy(documents['employees'])
    employees['employees'][0]['full_name'] = 'Updated Profile'
    response = upload(client, employees)
    assert response.status_code == 200 and response.json()['employees_updated'] == 1
    assert get_profile(client)['effective_skills']['SK_SYSTEM_DESIGN'] == 3
    assert get_profile(client)['employee']['full_name'] == 'Updated Profile'


@pytest.mark.parametrize('change', [
    {'manager_id': 'MISSING'}, {'manager_id': []}, {'skills': {'UNKNOWN': 2}},
    {'skills': {'SK_SYSTEM_DESIGN': True}}, {'career_goal': {}},
    {'career_goal': {'target_role': 'Unknown', 'target_grade': 'Junior'}},
    {'last_review_date': '2026-10-02'}, {'hire_date': '2030-01-01'},
    {'full_name': None}, {'work_format': []}, {'skills': []},
])
def test_invalid_import_rolls_back_all_changes(client, documents, change):
    employees = new_employee(documents)
    employees['employees'][0].update(change)
    before = get_profile(client)
    response = upload(client, employees, [participation(eid='JURY-NEW')])
    assert response.status_code == 422
    assert get_profile(client) == before
    assert client.get('/api/employees/JURY-NEW', headers=HR).status_code == 404


def test_history_conflict_is_atomic(client, documents):
    conflicting = {**documents['history'][0], 'status': 'completed', 'completion_pct': '100'}
    response = upload(client, new_employee(documents), [conflicting])
    assert response.status_code == 422
    assert get_profile(client)['data_version'] == 1
    assert client.get('/api/employees/JURY-NEW', headers=HR).status_code == 404


@pytest.mark.parametrize('already_stored', [False, True])
@pytest.mark.parametrize('identical', [True, False])
def test_duplicate_record_ids_in_upload_reject_entire_import(client, documents, already_stored, identical):
    row = participation()
    if already_stored:
        assert upload(client, history=[row]).status_code == 200
    duplicate = dict(row) if identical else {**row, 'completion_pct': '40'}
    before = get_profile(client)
    response = upload(client, new_employee(documents), [row, duplicate])
    assert response.status_code == 422
    assert 'Duplicate record_id' in response.json()['detail']['message']
    assert get_profile(client) == before
    assert client.get('/api/employees/JURY-NEW', headers=HR).status_code == 404


def test_import_limits_metadata_and_malformed_files(client, documents):
    assert upload(client).status_code == 422
    employees = new_employee(documents)
    employees['meta'] = {'as_of_date': '2026-10-02'}
    assert upload(client, employees).status_code == 422
    for raw in (b'[]', b'{bad json', b'\xff', b' ' * (5 * 1024 * 1024 + 1)):
        response = client.post('/api/admin/import', headers=HR,
            files={'employees': ('employees.json', raw, 'application/json')})
        assert response.status_code == 422
    for raw in (b'wrong,header\n', history_csv([participation()]) + b'incomplete\n', b' ' * (5 * 1024 * 1024 + 1)):
        response = client.post('/api/admin/import', headers=HR,
            files={'history': ('history.csv', raw, 'text/csv')})
        assert response.status_code == 422
    assert get_profile(client)['data_version'] == 1


def test_mutations_enforce_access(client, documents):
    payload = {'event_id': 'EV_SYS', 'idempotency_key': 'test-access-key', 'expected_data_version': 1}
    assert client.post('/api/employees/E0002/complete', headers=EMP, json=payload).status_code == 403
    assert client.post('/api/employees/E0001/complete', json=payload).status_code == 401
    assert client.post('/api/admin/import', headers=EMP).status_code == 403
    assert client.get('/api/hr/overview', headers={**EMP, 'X-Role': 'hr'}).status_code == 403


def test_restart_persists_import_completion_and_idempotency(dataset, client, documents, tmp_path):
    path = tmp_path / 'runtime.sqlite3'
    with TestClient(create_app(dataset, path)) as first:
        assert completion(first).status_code == 200
        assert upload(first, new_employee(documents)).status_code == 200
        expected = get_profile(first)
    with TestClient(create_app(dataset, path)) as restarted:
        assert get_profile(restarted) == expected
        assert get_profile(restarted, 'JURY-NEW')['data_version'] == 3
        retry = completion(restarted)
        assert retry.status_code == 200 and retry.json()['already_applied']
        assert retry.json()['data_version'] == 2  # Original committed response.
        assert completion(restarted, event='EV_TALK').status_code == 409
        assert get_profile(restarted) == expected


@pytest.mark.parametrize('configuration', ['default', 'relative', 'absolute'])
def test_state_path_configuration_persists_across_restart(dataset, client, monkeypatch, tmp_path, configuration):
    monkeypatch.setattr('backend.main.ROOT', tmp_path)
    monkeypatch.setattr('backend.main.load_dataset', lambda folder: dataset)
    monkeypatch.delenv('STATE_PATH', raising=False)
    if configuration == 'default':
        expected_path = tmp_path / '.local' / 'career_quest.sqlite3'
    elif configuration == 'relative':
        monkeypatch.setenv('STATE_PATH', 'custom/state.sqlite3')
        expected_path = tmp_path / 'custom' / 'state.sqlite3'
    else:
        expected_path = tmp_path / 'absolute.sqlite3'
        monkeypatch.setenv('STATE_PATH', str(expected_path))
    with TestClient(create_app()) as first:
        assert completion(first).status_code == 200
        expected = get_profile(first)
    assert expected_path.is_file()
    with TestClient(create_app()) as restarted:
        assert get_profile(restarted) == expected
        retry = completion(restarted)
        assert retry.status_code == 200 and retry.json()['already_applied']


def test_hr_denominators_and_no_llm(client, documents, monkeypatch):
    async def forbidden(context):
        raise AssertionError('HR must never call AI')
    monkeypatch.setattr('backend.main.recommend', forbidden)
    employees = deepcopy(documents['employees'])
    employees['employees'][1]['career_goal'] = {'target_role': 'Backend Engineer', 'target_grade': 'Middle'}
    assert upload(client, employees).status_code == 200
    response = client.get('/api/hr/overview', headers=HR)
    assert response.status_code == 200
    report = response.json()
    talk = next(g for g in report['skill_gaps'] if g['skill_id'] == 'SK_PUBLIC_SPEAKING')
    system = next(g for g in report['skill_gaps'] if g['skill_id'] == 'SK_SYSTEM_DESIGN')
    assert talk['employees_requiring_skill'] == 1 and talk['gap_rate'] == 1
    assert system['employees_requiring_skill'] == 2 and system['gap_rate'] == 0.5
    assert system['critical_employee_count'] == 1
    assert report['employees_without_step'] == [{'employee_id': 'E0002', 'reason': 'TARGET_REQUIREMENTS_MET'}]


def test_recommendation_cache_configuration_and_writes(client, documents, monkeypatch):
    from ai.engine import recommend
    calls = []
    async def counted(context):
        calls.append((context.employee_id, context.data_version))
        return await recommend(context)
    monkeypatch.setattr('backend.main.recommend', counted)
    def fetch(eid='E0001'):
        return client.get(f'/api/employees/{eid}/recommendations', headers=HR)
    assert fetch().status_code == fetch().status_code == 200
    assert calls == [('E0001', 1)]
    assert fetch('E0002').json()['employee_id'] == 'E0002'
    monkeypatch.setenv('LLM_MODEL', 'changed-test-model')
    assert fetch().status_code == 200 and len(calls) == 3
    assert completion(client).status_code == 200
    assert fetch().json()['data_version'] == 2 and len(calls) == 4
    assert upload(client, new_employee(documents)).status_code == 200
    assert fetch().json()['data_version'] == 3 and len(calls) == 5


def test_failed_database_write_rolls_back_state_and_key(client, monkeypatch):
    import sqlite3
    store = client.app.state.store
    original_save = store.save
    before = get_profile(client)
    def fail_after_save(candidate):
        original_save(candidate)
        raise sqlite3.OperationalError('simulated disk failure')
    with monkeypatch.context() as patch:
        patch.setattr(store, 'save', fail_after_save)
        with pytest.raises(sqlite3.OperationalError):
            completion(client)
    assert get_profile(client) == before
    assert completion(client).status_code == 200
    assert get_profile(client)['effective_skills']['SK_SYSTEM_DESIGN'] == 3


def test_runtime_gain_on_assessment_day(client, documents):
    employees = deepcopy(documents['employees'])
    employees['employees'][0]['last_review_date'] = '2026-10-01'
    assert upload(client, employees).status_code == 200
    assert completion(client, version=2).status_code == 200
    assert get_profile(client)['effective_skills']['SK_SYSTEM_DESIGN'] == 3


def test_recurring_catalog_session_today_not_repeated(dataset, client):
    dataset.events['EV_036']['upcoming_sessions'].append('2026-10-01')
    with TestClient(create_app(dataset)) as isolated:
        first = completion(isolated, event='EV_036', session_date='2026-10-01')
        assert first.status_code == 200 and first.json()['data_version'] == 2
        again = completion(isolated, event='EV_036', version=2, key='second-session-key', session_date='2026-10-01')
        assert again.status_code == 200 and again.json()['already_applied']
        assert get_profile(isolated)['effective_skills']['SK_PUBLIC_SPEAKING'] == 1


def test_import_cannot_replay_runtime_completion_under_new_record(client):
    assert completion(client).status_code == 200
    response = upload(client, history=[participation(date='2026-10-01', status='completed')])
    assert response.status_code == 422
    assert get_profile(client)['effective_skills']['SK_SYSTEM_DESIGN'] == 3


def test_import_cannot_inject_runtime_timestamp(client):
    raw = history_csv([participation()]).decode('utf-8-sig').splitlines()
    malicious = '\n'.join([raw[0] + ',completed_at', raw[1] + ',2026-10-01T12:00:00'])
    response = client.post('/api/admin/import', headers=HR,
        files={'history': ('history.csv', malicious.encode(), 'text/csv')})
    assert response.status_code == 422
    assert get_profile(client)['data_version'] == 1


def test_cache_does_not_reinsert_old_result_after_write(client, monkeypatch):
    from ai.engine import recommend
    from shared.contracts import CompletionRequest
    async def overlapping(context):
        client.app.state.store.complete('E0001', CompletionRequest(event_id='EV_SYS',
            idempotency_key='overlapping-key', expected_data_version=1), {'role': 'hr', 'employee_id': None})
        return await recommend(context)
    monkeypatch.setattr('backend.main.recommend', overlapping)
    response = client.get('/api/employees/E0001/recommendations', headers=EMP)
    assert response.status_code == 200 and response.json()['data_version'] == 1
    assert get_profile(client)['data_version'] == 2
    assert not client.app.state.recommendation_cache


def test_client_cannot_inject_skill_levels(client):
    payload={'event_id':'EV_SYS','idempotency_key':'test-key-123','expected_data_version':1,'gain':5}
    assert client.post('/api/employees/E0001/complete',json=payload,headers=EMP).status_code==422
