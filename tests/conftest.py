from copy import deepcopy
import pytest
from backend.data_loader import parse_dataset

@pytest.fixture
def documents():
    meta={"as_of_date":"2026-10-01", "dataset":"test", "version":"1.0"}
    def employee(eid):
        return {"employee_id":eid,"full_name":"Synthetic Test","department":"Engineering",
            "role":"Backend Engineer","grade":"Middle","manager_id":None,
            "hire_date":"2023-01-01","tenure_months":45,"work_format":"remote",
            "preferred_language":"ru","career_goal":None,
            "skills":{"SK_SYSTEM_DESIGN":2,"SK_PUBLIC_SPEAKING":0},"last_review_date":"2026-09-01"}
    skills={"meta":meta, "proficiency_scale":{}, "skills":[
        {"skill_id":"SK_SYSTEM_DESIGN","name":"System Design"},
        {"skill_id":"SK_PUBLIC_SPEAKING","name":"Public Speaking"}],"role_profiles":[
        {"role":"Backend Engineer","grade":"Middle","required_skills":{"SK_SYSTEM_DESIGN":2},
         "critical_skills":["SK_SYSTEM_DESIGN"]},
        {"role":"Backend Engineer","grade":"Senior",
         "required_skills":{"SK_SYSTEM_DESIGN":4,"SK_PUBLIC_SPEAKING":1},
         "critical_skills":["SK_SYSTEM_DESIGN"]}]}
    def event(eid,sid,kind='course',fmt='self_paced'):
        return {"event_id":eid,"title":eid,"description":"Test", "type":kind,"format":fmt,
            "duration_hours":2,"mandatory":False,"target_roles":["Backend Engineer"],
            "target_grades":["Middle","Senior"],"prerequisites":{},
            "develops_skills":[{"skill_id":sid,"gain":1,"max_level":4}],
            "upcoming_sessions":[] if fmt=='self_paced' else ['2026-10-08']}
    events=[event('EV_SYS','SK_SYSTEM_DESIGN'),event('EV_TALK','SK_PUBLIC_SPEAKING','meetup','offline'),
            event('EV_036','SK_PUBLIC_SPEAKING','meetup','offline')]
    history=[]
    for i in range(3):
        history.append({"record_id":f"R{i}","employee_id":"E0001","event_id":"EV_TALK",
            "date":f"2026-09-{10+i}","due_date":"","status":"no_show","completion_pct":"0",
            "score":"","feedback_rating":"","assigned_by":"self"})
    return {"employees":{"meta":meta,"employees":[employee('E0001'),employee('E0002')]},
            "events":{"meta":meta,"events":events},"skills":skills,"history":history}

@pytest.fixture
def dataset(documents):
    return parse_dataset(documents['employees'],documents['events'],documents['skills'],documents['history'])

@pytest.fixture
def client(dataset, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import create_app
    monkeypatch.setenv('HR_TOKEN','test-hr-token')
    monkeypatch.setenv('EMPLOYEE_TOKEN','test-employee-token')
    monkeypatch.setenv('EMPLOYEE_ID','E0001')
    monkeypatch.setenv('AI_ENABLED','false')
    with TestClient(create_app(dataset)) as client:
        yield client
