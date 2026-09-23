from copy import deepcopy
from datetime import date
import pytest
from backend.data_loader import DatasetError, parse_dataset, read_json, read_history
from backend.domain import apply_gains, build_context, effective_skills, trajectory


def row(data, eid='EV_SYS', date_value='2026-09-20', status='completed'):
    return {'record_id':'RNEW','employee_id':'E0001','event_id':eid,'date':date_value,
            'due_date':'','status':status,'completion_pct':'100' if status=='completed' else '30',
            'score':'','feedback_rating':'','assigned_by':'self'}

@pytest.mark.parametrize('before,gain,cap,expected',[(2,1,4,3),(3,2,4,4),(5,1,3,5),(0,1,4,1)])
def test_growth_never_reduces(before,gain,cap,expected):
    event={'develops_skills':[{'skill_id':'x','gain':gain,'max_level':cap}]}
    original={'x':before}
    result,changes=apply_gains(original,event)
    assert result['x']==expected and original['x']==before
    assert changes[0].delta==expected-before


def test_replay_only_completed_after_review(dataset):
    dataset.history += [row(dataset,date_value='2026-08-10'), row(dataset),
                        {**row(dataset,date_value='2026-09-25',status='in_progress'),'record_id':'OTHER'}]
    assert effective_skills(dataset,'E0001')['SK_SYSTEM_DESIGN']==3
    assert effective_skills(dataset,'E0001')['SK_SYSTEM_DESIGN']==3  # No mutation / second credit.
    assert dataset.employees['E0001']['skills']['SK_SYSTEM_DESIGN']==2


def test_same_day_assessment_not_replayed(dataset):
    dataset.history += [row(dataset,date_value='2026-09-01')]
    assert effective_skills(dataset,'E0001')['SK_SYSTEM_DESIGN']==2


def test_completed_event_excluded(dataset):
    dataset.history += [row(dataset,date_value='2026-08-01')]
    ctx=build_context(dataset,'E0001')
    assert 'EV_SYS' not in {c.event_id for c in ctx.candidates}


def test_recurring_club_can_repeat(dataset):
    dataset.history += [row(dataset,eid='EV_036',date_value='2026-08-01')]
    assert 'EV_036' in {c.event_id for c in build_context(dataset,'E0001').candidates}

@pytest.mark.parametrize('mutation,reason',[
    ({'mandatory':True},'MANDATORY_NOT_A_RECOMMENDATION'),
    ({'target_roles':['Other']},'ROLE_NOT_ELIGIBLE'),
    ({'target_grades':['Lead']},'GRADE_NOT_ELIGIBLE'),
    ({'prerequisites':{'SK_SYSTEM_DESIGN':3}},'PREREQUISITES_NOT_MET'),
    ({'format':'online','upcoming_sessions':['2026-09-30']},'NO_UPCOMING_SESSION'),
])
def test_eligibility(dataset,mutation,reason):
    dataset.events['EV_SYS'].update(mutation)
    assert reason in [e.reason for e in build_context(dataset,'E0001').excluded if e.event_id=='EV_SYS']


def test_as_of_is_dataset_not_wall_clock(dataset):
    ctx=build_context(dataset,'E0001')
    assert ctx.as_of_date==date(2026,10,1)
    assert next(c for c in ctx.candidates if c.event_id=='EV_TALK').next_session==date(2026,10,8)


def test_no_future_grade_invented(dataset):
    e=dataset.employees['E0001'];e['grade']='Lead'
    dataset.role_profiles[('Backend Engineer','Lead')]={
        'required_skills':{'SK_SYSTEM_DESIGN':5},'critical_skills':['SK_SYSTEM_DESIGN']}
    t=trajectory(dataset,e,e['skills'])
    assert t.target_grade=='Lead' and t.target_source=='current_grade'


def test_cross_role_goal_used_but_access_not_bypassed(dataset):
    dataset.role_profiles[('Data Analyst','Junior')]={
        'required_skills':{'SK_SYSTEM_DESIGN':4},'critical_skills':[]}
    dataset.employees['E0001']['career_goal']={'target_role':'Data Analyst','target_grade':'Junior'}
    ctx=build_context(dataset,'E0001')
    assert ctx.trajectory.target_role=='Data Analyst'
    assert ctx.trajectory.target_source=='career_goal'


def test_missing_skill_zero(dataset):
    del dataset.employees['E0001']['skills']['SK_SYSTEM_DESIGN']
    assert next(g for g in build_context(dataset,'E0001').trajectory.gaps
                if g.skill_id=='SK_SYSTEM_DESIGN').current==0


def test_snapshot_validation(documents):
    documents['employees']['employees'][0]['skills']['SK_SYSTEM_DESIGN']=9
    with pytest.raises(DatasetError):
        parse_dataset(documents['employees'],documents['events'],documents['skills'],documents['history'])


def test_orphan_history_rejected(documents):
    documents['history'][0]['event_id']='UNKNOWN'
    with pytest.raises(DatasetError):
        parse_dataset(documents['employees'],documents['events'],documents['skills'],documents['history'])


def test_bom_json_and_csv():
    assert read_json(b'\xef\xbb\xbf{"employees":[]}')=={'employees':[]}
    with pytest.raises(DatasetError): read_history(b'wrong,columns\n1,2\n')
