"""Create a fresh local .env with distinct random demo credentials; never overwrite one."""
from pathlib import Path
import secrets
root = Path(__file__).resolve().parents[1]
path = root/".env"
if path.exists(): raise SystemExit(".env already exists; preserve its contents and merge .env.example manually.")
text = (root/".env.example").read_text(encoding="utf-8")
text = text.replace("HR_TOKEN=\n", "HR_TOKEN="+secrets.token_urlsafe(32)+"\n")
text = text.replace("EMPLOYEE_TOKEN=\n", "EMPLOYEE_TOKEN="+secrets.token_urlsafe(32)+"\n")
path.write_text(text, encoding="utf-8")
try: path.chmod(0o600)
except OSError: pass
print("Created local .env. Read tokens locally; do not paste them into chat, screenshots or commits.")
