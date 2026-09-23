"""Cross-platform first-run setup and launcher: python start.py [--dataset archive.zip]."""
from pathlib import Path
import argparse
import hashlib
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def run(*args):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, help='Official career_quest_dataset.zip')
    parser.add_argument('--prepare-only', action='store_true', help='Prepare without starting server')
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        raise SystemExit('Python 3.11+ is required.')
    os.chdir(ROOT)
    npm = shutil.which('npm.cmd') or shutil.which('npm')
    node = shutil.which('node')
    if not npm or not node:
        raise SystemExit('Install Node.js 22.12+ (including npm), then retry.')
    version = subprocess.check_output([node, '--version'], text=True).strip().lstrip('v')
    if tuple(map(int, version.split('.')[:2])) < (22, 12):
        raise SystemExit('Node.js 22.12+ is required; installed: ' + version)
    python = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        run(sys.executable, '-m', 'venv', ROOT / '.venv')
    local = ROOT / '.local'
    local.mkdir(exist_ok=True)
    digest = hashlib.sha256((ROOT / 'requirements.txt').read_bytes()).hexdigest()
    marker = local / 'requirements.sha256'
    if not marker.exists() or marker.read_text() != digest:
        run(python, '-m', 'pip', 'install', '-r', 'requirements.txt')
        marker.write_text(digest)
    if not (ROOT / '.env').exists():
        run(python, 'scripts/setup_env.py')
    # dotenv parsing is delegated to the venv; no secrets are printed.
    folder = subprocess.check_output([str(python), '-c',
        "from dotenv import dotenv_values; import os; print(os.getenv('DATA_DIR') or dotenv_values('.env').get('DATA_DIR') or 'docs')"],
        cwd=ROOT, text=True).strip()
    data = Path(folder)
    if not data.is_absolute():
        data = ROOT / data
    required = ['employees.json', 'skills.json', 'events.json', 'activity_history.csv']
    if not all((data / name).exists() for name in required):
        archive = args.dataset
        if archive is None:
            archive = next((p for p in [ROOT / 'career_quest_dataset.zip', Path.home() / 'Downloads/career_quest_dataset.zip'] if p.exists()), None)
        if archive is None or not archive.is_file():
            raise SystemExit('Official dataset needed: python start.py --dataset "path/to/career_quest_dataset.zip"')
        run(python, 'scripts/seed_data.py', archive.resolve(), '--out', data)
    os.environ['DATA_DIR'] = str(data)
    run(python, 'scripts/check_dataset.py')
    lock_hash = hashlib.sha256((ROOT / 'frontend/package-lock.json').read_bytes()).hexdigest()
    npm_marker = local / 'frontend.sha256'
    if not (ROOT / 'frontend/node_modules').exists() or not npm_marker.exists() or npm_marker.read_text() != lock_hash:
        run(npm, '--prefix', 'frontend', 'ci')
        npm_marker.write_text(lock_hash)
    run(npm, '--prefix', 'frontend', 'run', 'build')
    print('\nCareer Quest: http://127.0.0.1:8000\nLogin: copy HR_TOKEN or EMPLOYEE_TOKEN from local .env.\nAPI key is NOT a login token.', flush=True)
    if not args.prepare_only:
        run(python, 'run.py')


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode)
    except KeyboardInterrupt:
        pass
