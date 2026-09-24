"""Install only the maintained skill package; never copy private report libraries."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import sys

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home",default=os.environ.get("CODEX_HOME",str(Path.home()/".codex")))
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1]
    source=repo/"skills"/"ucas-physics-report"
    codex=Path(args.codex_home).expanduser().resolve()
    target=(codex/"skills"/"ucas-physics-report").resolve()
    if not target.is_relative_to(codex) or target==source.resolve():
        raise ValueError("Invalid install target")
    backup=None
    if target.exists():
        backup=codex/"skill-backups"/("ucas-physics-report-"+datetime.datetime.now().strftime("%Y%m%dT%H%M%S%f"))
        shutil.copytree(target,backup)
    shutil.copytree(source,target,dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__","*.pyc",".DS_Store"))
    print(json.dumps({"installed":str(target),"backup":str(backup) if backup else None},ensure_ascii=False))

if __name__=="__main__":
    main()
