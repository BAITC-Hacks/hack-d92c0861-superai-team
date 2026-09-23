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


def test_write_and_hr_routes_explicitly_not_implemented(client):
    payload={'event_id':'EV_SYS','idempotency_key':'test-key-123','expected_data_version':1}
    assert client.post('/api/employees/E0001/complete',json=payload,headers=EMP).status_code==501
    assert client.post('/api/admin/import',headers=HR).status_code==501
    assert client.get('/api/hr/overview',headers=HR).status_code==501


def test_client_cannot_inject_skill_levels(client):
    payload={'event_id':'EV_SYS','idempotency_key':'test-key-123','expected_data_version':1,'gain':5}
    assert client.post('/api/employees/E0001/complete',json=payload,headers=EMP).status_code==422
