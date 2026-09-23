"""Copy ONLY named dataset members from the supplied ZIP, never extract arbitrary paths."""
from pathlib import Path
from zipfile import ZipFile
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("archive", type=Path)
parser.add_argument("--out", type=Path, default=Path("docs"))
args = parser.parse_args()
files = {"employees.json": "employees.json", "events.json": "events.json",
         "skills.json": "skills.json", "activity_history.csv": "activity_history.csv",
         "README.md": "DATASET_README.md"}
# Do not overwrite existing files; reconcile existing repo manually.
for target in files.values():
    if (args.out/target).exists():
        raise SystemExit(f"Refusing to overwrite {args.out/target}. Use existing DATA_DIR or a new --out.")
with ZipFile(args.archive) as archive:
    content = {}
    for name, target in files.items():
        matches = [i for i in archive.infolist()
                   if Path(i.filename).name == name and "__MACOSX" not in i.filename]
        if len(matches) != 1: raise SystemExit(f"Expected one {name}, got {len(matches)}")
        if matches[0].file_size > 10*1024*1024: raise SystemExit("Dataset member too large")
        content[target] = archive.read(matches[0])
args.out.mkdir(parents=True, exist_ok=True)
for name, raw in content.items(): (args.out/name).write_bytes(raw)
print(f"Imported {len(content)} files into {args.out}. Seed files must remain unchanged.")
