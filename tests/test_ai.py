import asyncio
import pytest
import httpx
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


def test_admin_key_is_not_application_configuration(monkeypatch):
    enable(monkeypatch)
    monkeypatch.setenv('LLM_API_KEY', 'sk-admin-not-a-real-key')
    assert not provider.configured()


def test_provider_http_contract_and_minimized_payload(dataset, monkeypatch):
    import json
    enable(monkeypatch)
    context = build_context(dataset, 'E0001')
    original_client = httpx.AsyncClient
    def handle(request):
        body = json.loads(request.content)
        assert request.url.path == '/v1/chat/completions'
        assert body['response_format'] == {'type': 'json_object'}
        assert body['max_completion_tokens'] == 256
        payload = json.loads(body['messages'][1]['content'])
        assert 'employee_id' not in payload and 'excluded' not in payload
        assert all('similar_record_ids' not in c['history'] for c in payload['candidates'])
        return httpx.Response(200, json={'choices': [{'message': {'content': '{"event_ids":["EV_TALK"]}'}}]})
    monkeypatch.setattr(provider.httpx, 'AsyncClient', lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    result = asyncio.run(recommend(context))
    assert result.mode == 'llm'
    assert result.steps[0].event_id == 'EV_TALK'


def test_http_provider_failure_is_explicit_fallback(dataset, monkeypatch):
    enable(monkeypatch)
    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(429, json={'error': 'quota'}))
    monkeypatch.setattr(provider.httpx, 'AsyncClient', lambda **kwargs: original_client(transport=transport, **kwargs))
    result = asyncio.run(recommend(build_context(dataset, 'E0001')))
    assert result.mode == 'fallback' and result.fallback_reason == 'AI_PROVIDER_ERROR'
