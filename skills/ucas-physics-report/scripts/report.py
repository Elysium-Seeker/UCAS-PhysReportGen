"""CLI for experiment lookup, project creation and checking."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from reportlib import read_json, write_json, sha256, validate_data, validate_results

SKILL = Path(__file__).resolve().parents[1]
CATALOG = SKILL/"references"/"experiments.json"
CONFIG = Path(os.environ.get("CODEX_HOME", str(Path.home()/".codex")))/"ucas-physics-report"/"config.json"


def catalog():
    return read_json(CATALOG)


def normalize(text):
    return "".join(c for c in text.lower() if c.isalnum())


def resolve(query):
    query = normalize(query)
    if not query:
        raise ValueError("Experiment name cannot be empty")
    entries = catalog()
    exact = [e for e in entries if query in [normalize(x) for x in [e["id"],e["title"],e["number"]]+e["aliases"]]]
    matches = exact or [e for e in entries if any(query in normalize(a) or normalize(a) in query
                                                 for a in [e["title"]]+e["aliases"])]
    if len(matches) != 1:
        names = ", ".join(e["title"] for e in matches)
        raise ValueError(f"Ambiguous or unknown experiment '{query}'. Candidates: {names or 'none'}; use catalog")
    return matches[0]


def source_inventory(experiment, library=None):
    config = read_json(CONFIG) if CONFIG.exists() else {}
    roots = [library] if library else config.get("library_roots", [])
    sources = []
    for root_value in roots:
        root = Path(root_value).expanduser().resolve()
        if not root.is_dir():
            continue
        for group in ("报告", "02_同学参考", "03_往届参考"):
            group_dir = root/group
            if not group_dir.is_dir():
                continue
            for p in group_dir.rglob("*"):
                if not p.is_file() or p.name.startswith("~$"):
                    continue
                if experiment["folder"] not in p.relative_to(group_dir).parts:
                    continue
                if p.suffix.lower() not in (".pdf",".docx",".tex",".txt",".csv",".xlsx",".py",".png",".jpg",".jpeg"):
                    continue
                guide = any(k in p.name for k in ("指导书","讲义","要求","1、傅里叶"))
                sources.append({"kind":"guide" if guide else "reference", "collection":group,
                                "path":str(p), "relative_path":str(p.relative_to(root)),
                                "bytes":p.stat().st_size})
    return sorted(sources, key=lambda x:(x["kind"]!="guide", x["collection"], x["path"]))


def init_project(args):
    exp = resolve(args.experiment)
    output = Path(args.output).expanduser().resolve()
    if output.exists():
        raise ValueError(f"Output already exists; select a new report directory: {output}")
    photos = []
    for role in ("records","preview","observations"):
        for value in getattr(args, role) or []:
            p = Path(value).expanduser().resolve()
            if not p.is_file() or p.suffix.lower() not in (".png",".jpg",".jpeg"):
                raise ValueError(f"Use existing PNG/JPEG photographs: {p}")
            photos.append((p, {"records":"record","preview":"preview","observations":"observation"}[role]))
    if not photos:
        raise ValueError("At least one record/observation photo is required")
    config = read_json(CONFIG) if CONFIG.exists() else {}
    output.mkdir(parents=True)
    (output/"photos").mkdir()
    (output/"figures").mkdir()
    images = []
    for i,(p,role) in enumerate(photos,1):
        relative = f"photos/photo-{i:03d}{p.suffix.lower()}"
        shutil.copy2(p, output/relative)
        images.append({"path":relative,"original_name":p.name,"role":role,"sha256":sha256(output/relative)})
    write_json(output/"inputs.json", {"schema_version":1,"experiment_id":exp["id"],"images":images})
    write_json(output/"data.json", {"schema_version":1,"experiment_id":exp["id"],
               "experiment_title":exp["title"],"metadata":config.get("profile",{}),
               "requirements":{"preview_required":True},"constants":{},
               "tables":[],"observations":[],"issues":[]})
    write_json(output/"sources.json", source_inventory(exp,args.library))
    for name in ("physics.py","reportlib.py"):
        shutil.copy2(SKILL/"scripts"/name, output/name)
    print(json.dumps({"project":str(output),"experiment":exp,"images":images,
                      "next":"Read recipe and relevant guides; inspect all photos; populate data.json, then write analyze.py and content.tex."},
                     ensure_ascii=False,indent=2))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("catalog"); p.add_argument("query",nargs="?")
    p=sub.add_parser("sources"); p.add_argument("experiment"); p.add_argument("--library")
    p=sub.add_parser("configure"); p.add_argument("--library"); p.add_argument("--profile")
    p=sub.add_parser("init")
    p.add_argument("--experiment",required=True); p.add_argument("--output",required=True)
    p.add_argument("--records",nargs="+"); p.add_argument("--preview",nargs="+")
    p.add_argument("--observations",nargs="+"); p.add_argument("--library")
    p=sub.add_parser("check"); p.add_argument("project"); p.add_argument("--results",action="store_true")
    p.add_argument("--allow-incomplete",action="store_true")
    p=sub.add_parser("analyze"); p.add_argument("project"); p.add_argument("--timeout",type=int,default=120)
    p.add_argument("--allow-incomplete",action="store_true")
    sub.add_parser("doctor")
    args=parser.parse_args()
    try:
        if args.command=="catalog":
            result=resolve(args.query) if args.query else catalog()
        elif args.command=="sources":
            result=source_inventory(resolve(args.experiment),args.library)
        elif args.command=="configure":
            result=read_json(CONFIG) if CONFIG.exists() else {}
            if args.library:
                library=Path(args.library).expanduser().resolve()
                if not library.is_dir(): raise ValueError(f"Library does not exist: {library}")
                result["library_roots"]=[str(library)]
            if args.profile:
                profile=read_json(args.profile)
                if not isinstance(profile,dict): raise ValueError("Profile must be a JSON object")
                result["profile"]=profile
            if not args.library and not args.profile: raise ValueError("Supply --library or --profile")
            result["python_executable"]=sys.executable
            if CONFIG.exists():
                import datetime
                backup=CONFIG.with_name("config.backup-"+datetime.datetime.now().strftime("%Y%m%dT%H%M%S%f")+".json")
                shutil.copy2(CONFIG,backup)
            write_json(CONFIG,result)
            result={"configured":str(CONFIG)}
        elif args.command=="init":
            init_project(args); return 0
        elif args.command=="check":
            result=validate_data(args.project, allow_incomplete=args.allow_incomplete)
            if args.results and result["valid"]:
                result["results"]=validate_results(args.project)
                result["valid"]=result["results"]["valid"]
            print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result["valid"] else 2
        elif args.command=="analyze":
            result=validate_data(args.project, allow_incomplete=args.allow_incomplete)
            if not result["valid"]: raise ValueError("\n".join(result["errors"]))
            project=Path(args.project).resolve()
            subprocess.run([sys.executable,str(project/"analyze.py")],cwd=project,check=True,timeout=args.timeout)
            result=validate_results(project)
            print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result["valid"] else 2
        else:
            modules=("numpy","scipy","matplotlib","pypdf","pypdfium2","PIL")
            result={"python":sys.executable,"xelatex":shutil.which("xelatex"),
                    "modules":{m:importlib.util.find_spec(m) is not None for m in modules},
                    "config":str(CONFIG) if CONFIG.exists() else None}
        print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
    except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr); return 2


if __name__=="__main__":
    raise SystemExit(main())
