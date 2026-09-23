"""One-command local launcher after dependency installation and dataset seeding."""
from pathlib import Path
import argparse
import shutil
import subprocess
import sys
import time

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--dev", action="store_true", help="Start both API and Vite with live reload")
args = parser.parse_args()
if not args.dev:
    if not (root/"frontend/dist/index.html").exists():
        raise SystemExit("First run: npm --prefix frontend run build. Or use python run.py --dev")
    raise SystemExit(subprocess.call([sys.executable, "-m", "uvicorn", "backend.main:app",
                        "--host", "127.0.0.1", "--port", "8000"], cwd=root))
npm = shutil.which("npm.cmd") or shutil.which("npm")
if npm is None: raise SystemExit("Node.js/npm required for --dev")
children = []
try:
    children.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app",
                     "--host", "127.0.0.1", "--port", "8000", "--reload"], cwd=root))
    children.append(subprocess.Popen([npm, "--prefix", "frontend", "run", "dev"], cwd=root))
    print("UI: http://127.0.0.1:5173 | API docs: http://127.0.0.1:8000/docs", flush=True)
    while all(child.poll() is None for child in children): time.sleep(0.3)
    failed = next((child.returncode for child in children if child.poll() is not None), 1)
    if failed: raise SystemExit(failed)
except KeyboardInterrupt:
    pass
finally:
    for child in children:
        if child.poll() is None: child.terminate()
    for child in children:
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired: child.kill()
