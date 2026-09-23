"""Explicit live model check; uses local .env, never displays credentials or provider bodies."""
from pathlib import Path
import asyncio
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from ai.engine import recommend
from backend.data_loader import load_dataset
from backend.domain import build_context

root = Path(__file__).resolve().parents[1]
load_dotenv(root / '.env')
folder = Path(os.getenv('DATA_DIR', 'docs'))
if not folder.is_absolute():
    folder = root / folder
data = load_dataset(folder)
context = next((build_context(data, eid) for eid in data.employees
                if build_context(data, eid).candidates), None)
if context is None:
    raise SystemExit('No eligible candidates in this dataset.')
result = asyncio.run(recommend(context))
print(f'mode={result.mode}; reason={result.fallback_reason}; steps={len(result.steps)}; elapsed_ms={result.elapsed_ms}')
if result.mode != 'llm':
    raise SystemExit(1)
