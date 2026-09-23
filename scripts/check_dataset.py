"""Structural and deterministic smoke check over every official employee; no LLM requests."""
from pathlib import Path
import json
import os
import sys
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from backend.data_loader import load_dataset
from backend.domain import build_context
from ai.engine import baseline_score
root=Path(__file__).resolve().parents[1]
load_dotenv(root/'.env')
folder=Path(os.getenv('DATA_DIR','docs'))
if not folder.is_absolute(): folder=root/folder
start=perf_counter();data=load_dataset(folder)
empty=[];candidate_count=0
for eid in data.employees:
    ctx=build_context(data,eid)
    assert 0<=ctx.trajectory.progress_pct<=100
    if not ctx.candidates: empty.append(eid)
    candidate_count+=len(ctx.candidates)
    for c in ctx.candidates:
        assert c.target_gap_reduction>0
        assert c.progress_after_pct>=c.progress_before_pct
        assert all(0<=x.before<=x.after<=5 for x in c.skill_deltas)
print(json.dumps({'employees':len(data.employees),'events':len(data.events),'skills':len(data.skills),
    'role_profiles':len(data.role_profiles),'history_rows':len(data.history),
    'as_of_date':str(data.as_of_date),'candidate_options':candidate_count,
    'employees_with_no_eligible_gap_reducing_event':empty,
    'elapsed_seconds':round(perf_counter()-start,3)},ensure_ascii=False,indent=2))
