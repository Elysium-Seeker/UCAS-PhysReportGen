"""Build a reproducible ZIP containing only the distributable skill."""
import argparse
import hashlib
from pathlib import Path
import zipfile


def package(output):
    repo=Path(__file__).resolve().parents[1]
    source=repo/"skills"/"ucas-physics-report"
    output=Path(output).resolve()
    if output.is_relative_to(source.resolve()):
        raise ValueError("Package output must be outside the skill source")
    output.parent.mkdir(parents=True,exist_ok=True)
    files=[p for p in source.rglob("*") if p.is_file() and
           "__pycache__" not in p.parts and p.suffix not in (".pyc",".pyo")]
    with zipfile.ZipFile(output,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for file in sorted(files):
            name=source.name+"/"+file.relative_to(source).as_posix()
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            archive.writestr(info,file.read_bytes())
    checksum=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix+".sha256").write_text(checksum+"  "+output.name+"\n",encoding="ascii")
    return output,len(files),checksum


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",default=str(Path(__file__).resolve().parents[1]/"output"/"skill-packages"/"ucas-physics-report-0.1.0.zip"))
    args=parser.parse_args()
    path,count,digest=package(args.output)
    import json,sys
    if hasattr(sys.stdout,"reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps({"package":str(path),"files":count,"sha256":digest},ensure_ascii=False,indent=2))
