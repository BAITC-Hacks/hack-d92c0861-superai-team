import asyncio
import pytest
from ai import provider
from ai.engine import recommend
from backend.domain import build_context


def test_multifactor_trap_prefers_critical_not_minimum(dataset,monkeypatch):
    monkeypatch.setenv('AI_ENABLED','false')
    response=asyncio.run(recommend(build_context(dataset,'E0001')))
    assert response.steps[0].event_id=='EV_SYS'
    assert response.mode=='fallback'
    assert {'grade_goal','skill_gap','history'}.issubset({f.code for f in response.steps[0].factors})

@pytest.mark.parametrize('value',[{'event_ids':['NOT_REAL']},{'event_ids':['EV_SYS','EV_SYS']},{'event_ids':[]}])
def test_reject_invalid_llm_selection(dataset,value):
    with pytest.raises(ValueError): provider.validate_selection(value,build_context(dataset,'E0001'))


def enable(monkeypatch):
    for k,v in {'AI_ENABLED':'true','LLM_BASE_URL':'https://example.invalid/v1',
                'LLM_API_KEY':'test-key','LLM_MODEL':'test-model'}.items(): monkeypatch.setenv(k,v)


def test_llm_selection_actually_controls_ranking(dataset,monkeypatch):
    enable(monkeypatch)
    async def select(context): return ['EV_TALK']
    monkeypatch.setattr(provider,'select_events',select)
    result=asyncio.run(recommend(build_context(dataset,'E0001')))
    assert result.mode=='llm' and [s.event_id for s in result.steps]==['EV_TALK']


def test_timeout_falls_back(dataset,monkeypatch):
    enable(monkeypatch)
    async def select(context): raise asyncio.TimeoutError()
    monkeypatch.setattr(provider,'select_events',select)
    result=asyncio.run(recommend(build_context(dataset,'E0001')))
    assert result.mode=='fallback' and result.fallback_reason=='AI_TIMEOUT'


def test_no_gain_means_honest_empty(dataset,monkeypatch):
    monkeypatch.setenv('AI_ENABLED','false')
    dataset.employees['E0001']['skills']={'SK_SYSTEM_DESIGN':5,'SK_PUBLIC_SPEAKING':5}
    response=asyncio.run(recommend(build_context(dataset,'E0001')))
    assert response.steps==[] and response.no_step_reason
