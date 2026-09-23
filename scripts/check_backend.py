"""API smoke scenario on local seed + regression profiles, using an isolated temporary DB."""
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from backend.data_loader import load_dataset
from backend.domain import build_context
from backend.main import ROOT, create_app


def main():
    load_dotenv(ROOT / '.env', override=False)
    folder = Path(os.getenv('DATA_DIR', 'docs'))
    if not folder.is_absolute():
        folder = ROOT / folder
    paths = [folder / name for name in ('employees.json', 'events.json', 'skills.json', 'activity_history.csv')]
    original = {p: sha256(p.read_bytes()).hexdigest() for p in paths}
    seed = load_dataset(folder)
    # This script checks the backend only. Never contact a provider or print local tokens.
    os.environ['AI_ENABLED'] = 'false'
    os.environ['HR_TOKEN'] = secrets.token_urlsafe(32)
    os.environ['EMPLOYEE_TOKEN'] = secrets.token_urlsafe(32)
    headers = {'Authorization': 'Bearer ' + os.environ['HR_TOKEN']}
    employee_id, event_id = next((eid, c.event_id) for eid in seed.employees
        for c in build_context(seed, eid).candidates if c.format == 'self_paced')
    payload = {'event_id': event_id, 'idempotency_key': 'backend-smoke-completion', 'expected_data_version': seed.version}
    files = {field: (name, (ROOT / 'docs' / 'jury_examples' / name).read_bytes(), mime)
        for field, name, mime in [('employees', 'employees.json', 'application/json'),
                                  ('history', 'activity_history.csv', 'text/csv')]}
    with TemporaryDirectory(prefix='career-quest-check-') as folder_name:
        db = Path(folder_name) / 'runtime.sqlite3'
        with TestClient(create_app(seed, db)) as client:
            url = f'/api/employees/{employee_id}'
            before = client.get(url, headers=headers).json()
            recommendations = client.get(url + '/recommendations', headers=headers)
            assert recommendations.status_code == 200 and recommendations.json()['mode'] == 'fallback'
            completed = client.post(url + '/complete', headers=headers, json=payload)
            assert completed.status_code == 200, completed.text
            assert completed.json()['trajectory']['progress_pct'] > before['trajectory']['progress_pct']
            retry = client.post(url + '/complete', headers=headers, json=payload)
            assert retry.status_code == 200 and retry.json()['already_applied']
            imported = client.post('/api/admin/import', headers=headers, files=files)
            assert imported.status_code == 200, imported.text
            assert imported.json()['employees_added'] == 3 and imported.json()['history_added'] == 3
            repeated = client.post('/api/admin/import', headers=headers, files=files)
            assert repeated.status_code == 200 and repeated.json()['data_version'] == imported.json()['data_version']
            for eid in ('TEST_CQ_001', 'TEST_CQ_002', 'TEST_CQ_003'):
                response = client.get(f'/api/employees/{eid}/recommendations', headers=headers)
                assert response.status_code == 200, response.text
                if eid == 'TEST_CQ_003':
                    assert response.json()['steps'] == [] and response.json()['no_step_reason']
            report = client.get('/api/hr/overview', headers=headers)
            assert report.status_code == 200 and report.json()['employees_count'] == len(seed.employees) + 3
            expected_profile = client.get(url, headers=headers).json()
        with TestClient(create_app(seed, db)) as restarted:
            assert restarted.get(url, headers=headers).json() == expected_profile
            retry = restarted.post(url + '/complete', headers=headers, json=payload)
            assert retry.status_code == 200 and retry.json()['already_applied']
            assert restarted.get('/api/employees/TEST_CQ_001', headers=headers).status_code == 200
    assert all(sha256(p.read_bytes()).hexdigest() == digest for p, digest in original.items())
    print(json.dumps({'status': 'ok', 'seed_employees': len(seed.employees),
        'imported_employees': 3, 'imported_history': 3, 'completion': 'applied_once',
        'restart': 'preserved', 'seed_files': 'unchanged', 'ai_mode': 'fallback',
        'progress_before_pct': before['trajectory']['progress_pct'],
        'progress_after_pct': expected_profile['trajectory']['progress_pct']}, indent=2))


if __name__ == '__main__':
    main()
