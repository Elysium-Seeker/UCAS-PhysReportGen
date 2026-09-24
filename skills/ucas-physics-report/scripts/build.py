"""Render, compile and visually inspect a report project using one data source."""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from reportlib import read_json, write_json, sha256, inside, validate_data, validate_results

SKILL = Path(__file__).resolve().parents[1]


def tex(text):
    escapes = {"\\":r"\textbackslash{}", "&":r"\&", "%":r"\%", "$":r"\$",
               "#":r"\#", "_":r"\_", "{":r"\{", "}":r"\}", "~":r"\textasciitilde{}",
               "^":r"\textasciicircum{}"}
    return "".join(escapes.get(c,c) for c in str(text))


def numeric(value, digits=6):
    s = format(value, f".{digits}g")
    if "e" in s:
        a,b = s.split("e")
        return rf"\ensuremath{{{a}\times 10^{{{int(b)}}}}}"
    return s


def cell(row, col):
    value = row["values"][col["key"]]
    if value is None:
        return r"\textemdash{}"
    if col.get("kind","number")=="text":
        return tex(value)
    raw = row.get("raw",{}).get(col["key"])
    if isinstance(raw,str) and re.fullmatch(r"[+-]?\d+(?:\.\d+)?",raw) and float(raw)==value:
        return tex(raw)
    return numeric(value,col.get("digits",6))


def table_tex(table):
    cols=table["columns"]
    align="".join("l" if c.get("kind")=="text" else "r" for c in cols)
    header=" & ".join(tex(c["label"])+(rf" / {tex(c['unit'])}" if c["unit"] else "") for c in cols)+r" \\"
    rows=[" & ".join(cell(row,c) for c in cols)+r" \\" for row in table["rows"]]
    # Keep a short table together; long tables retain repeating page headers.
    if len(rows) <= 12:
        return "\n".join([r"\begingroup\small",r"\begin{table}[H]",r"\centering",
            rf"\caption{{{tex(table['title'])}}}\label{{tab:{table['id']}}}",
            rf"\begin{{tabular}}{{{align}}}",r"\toprule",header,r"\midrule",
            *rows,r"\bottomrule",r"\end{tabular}",r"\end{table}",r"\endgroup",""])
    out=[r"\begingroup\small",rf"\begin{{longtable}}{{{align}}}",
         rf"\caption{{{tex(table['title'])}}}\label{{tab:{table['id']}}}\\",
         r"\toprule",header,r"\midrule",r"\endfirsthead",
         rf"\multicolumn{{{len(cols)}}}{{c}}{{{tex(table['title'])}（续）}}\\",
         r"\toprule",header,r"\midrule",r"\endhead",
         r"\bottomrule\endfoot"]
    out += rows
    return "\n".join(out+[r"\end{longtable}",r"\endgroup",""])


def render(project):
    project=Path(project).resolve()
    result=read_json(project/"results.json")
    check=validate_data(project, allow_incomplete=result.get("data_policy")=="partial")
    if result.get("data_policy")=="partial":
        check["warnings"].append("Partial-data draft: review results.notes for omitted calculations")
    if not check["valid"]: raise ValueError("\n".join(check["errors"]))
    result_check=validate_results(project)
    if not result_check["valid"]: raise ValueError("\n".join(result_check["errors"]))
    data=read_json(project/"data.json")
    content=(project/"content.tex").read_text(encoding="utf-8")
    # Ignore comments when checking references; a commented input does not render a table.
    active=re.sub(r"(?<!\\)%[^\n]*","",content)
    allowed_inputs={f"generated/tables/{t['id']}.tex" for t in data["tables"]+result["tables"]}
    allowed_inputs.update(f"generated/figures/{f['id']}.tex" for f in result["figures"])
    for path in re.findall(r"\\input\{(generated/(?:tables|figures)/[^}]+)\}", active):
        if path not in allowed_inputs:
            raise ValueError(f"Unknown or stale generated input: {path}")
    generated=project/"generated"
    (generated/"tables").mkdir(parents=True,exist_ok=True)
    (generated/"figures").mkdir(parents=True,exist_ok=True)
    for table in data["tables"]+result["tables"]:
        rel=f"generated/tables/{table['id']}.tex"
        if rf"\input{{{rel}}}" not in active:
            raise ValueError(f"content.tex must include table: {rel}")
        (project/rel).write_text(table_tex(table),encoding="utf-8")
    quantities={q["id"]:q for q in result["quantities"]}
    values=[]
    for key,q in quantities.items():
        values.append(rf"\expandafter\def\csname result@{key}\endcsname{{{numeric(q['value'],q.get('digits',6))}}}")
        if "uncertainty" in q:
            values.append(rf"\expandafter\def\csname uncertainty@{key}\endcsname{{{numeric(q['uncertainty'],q.get('uncertainty_digits',2))}}}")
    for command,qid in re.findall(r"\\(Result|ResultUncertainty)\{([^}]+)\}",active):
        if qid not in quantities or (command=="ResultUncertainty" and "uncertainty" not in quantities[qid]):
            raise ValueError(f"Undefined result reference: {command}{{{qid}}}")
    (generated/"values.tex").write_text("\n".join(values)+"\n",encoding="utf-8")
    for fig in result["figures"]:
        rel=f"generated/figures/{fig['id']}.tex"
        if rf"\input{{{rel}}}" not in active:
            raise ValueError(f"content.tex must include figure: {rel}")
        # detokenize handles underscores and spaces; braces and % are not valid asset names.
        if any(c in fig["path"] for c in "{}%\n\r"):
            raise ValueError("Rename figure to a simple path before including it")
        body="\n".join([r"\begin{figure}[H]",r"\centering",
             rf"\includegraphics[width=0.86\textwidth,height=0.42\textheight,keepaspectratio]{{\detokenize{{{fig['path']}}}}}",
             rf"\caption{{{tex(fig['caption'])}}}\label{{fig:{fig['id']}}}",
             r"\end{figure}",""])
        (project/rel).write_text(body,encoding="utf-8")
    appendix=[r"\section{原始记录与预习报告}"]
    images=read_json(project/"inputs.json")["images"]
    for i,item in enumerate(images):
        if i: appendix.append(r"\clearpage")
        label={"record":"原始数据记录","preview":"预习报告","observation":"实验现象照片"}[item["role"]]
        appendix += [rf"\subsection*{{{label} {i+1}}}",r"\begin{center}",
                     rf"\includegraphics[width=\textwidth,height=0.84\textheight,keepaspectratio]{{{item['path']}}}",
                     r"\end{center}"]
    (generated/"appendix.tex").write_text("\n".join(appendix)+"\n",encoding="utf-8")
    template=(SKILL/"assets"/"report.tex").read_text(encoding="utf-8")
    fields={"EXPERIMENT":data.get("experiment_title",data["experiment_id"])}
    fields.update({k.upper():v for k,v in data.get("metadata",{}).items()})
    for key in re.findall(r"@@([A-Z_]+)@@",template):
        if key=="STATUS": continue
        template=template.replace("@@"+key+"@@",tex(fields.get(key) or "待补充"))
    status=r"\begin{center}\small 本稿尚有待补充信息，详见随附检查记录。\end{center}" if check["warnings"] else ""
    template=template.replace("@@STATUS@@",status)
    (project/"report.tex").write_text(template,encoding="utf-8")
    write_json(project/"checks.json",check)
    return check


def dependencies(project):
    project=Path(project)
    paths=[project/x for x in ("data.json","inputs.json","results.json","analyze.py","content.tex","report.tex")]
    paths.extend((project/"generated").rglob("*.tex"))
    paths.extend(inside(project,f["path"]) for f in read_json(project/"results.json")["figures"])
    paths.extend(inside(project,f["path"]) for f in read_json(project/"inputs.json")["images"])
    return {str(p.relative_to(project)).replace("\\","/"):sha256(p) for p in sorted(set(paths))}


def compile_report(project, engine="xelatex", timeout=120):
    project=Path(project).resolve()
    # Invalidate success BEFORE rendering; failures cannot report an older PDF as new.
    write_json(project/"build.json",{"compiled":False,"reason":"Build in progress or failed"})
    render(project)
    executable=shutil.which(engine)
    if not executable: raise ValueError(f"XeLaTeX not found: {engine}")
    build=project/".build"/uuid.uuid4().hex
    build.mkdir(parents=True)
    command=[executable,"-interaction=nonstopmode","-halt-on-error","-file-line-error",
             "-no-shell-escape",f"-output-directory={build}","report.tex"]
    for attempt in range(2):
        run=subprocess.run(command,cwd=project,capture_output=True,text=True,encoding="utf-8",
                           errors="replace",timeout=timeout)
        (build/f"pass-{attempt+1}.txt").write_text(run.stdout+"\n"+run.stderr,encoding="utf-8")
        if run.returncode:
            raise ValueError(f"XeLaTeX pass {attempt+1} failed (exit {run.returncode}); see {build}")
    pdf=build/"report.pdf"
    if not pdf.is_file() or pdf.stat().st_size<100:
        raise ValueError("This build did not produce a valid PDF")
    from pypdf import PdfReader
    page_count=len(PdfReader(pdf).pages)
    log=(build/"report.log").read_text(encoding="utf-8",errors="replace")
    errors=re.findall(r"^.*(?:Missing character:|Undefined control sequence|undefined references|Reference .* undefined).*$",
                      log,re.MULTILINE)
    if errors: raise ValueError("LaTeX content errors: "+"\n".join(errors[:15]))
    warnings=re.findall(r"^.*(?:Overfull \\[hv]box|LaTeX Warning:|Package .* Warning:).*$",log,re.MULTILINE)
    shutil.copy2(pdf,project/"report.pdf")
    result={"compiled":True,"pages":page_count,"pdf_sha256":sha256(project/"report.pdf"),
            "dependencies":dependencies(project),"warnings":warnings,"log_directory":str(build)}
    write_json(project/"build.json",result)
    return result


def current_build(project):
    project=Path(project).resolve()
    if not (project/"build.json").is_file(): return False
    build=read_json(project/"build.json")
    try:
        return bool(build.get("compiled") and build.get("pdf_sha256")==sha256(project/"report.pdf")
                    and build.get("dependencies")==dependencies(project))
    except (OSError,ValueError,KeyError): return False


def preview(project):
    project=Path(project).resolve()
    if not current_build(project): raise ValueError("Compile the current report before rendering previews")
    import pypdfium2 as pdfium
    from PIL import Image,ImageDraw
    output=project/".review"; output.mkdir(exist_ok=True)
    doc=pdfium.PdfDocument(project/"report.pdf")
    images=[]
    for i in range(len(doc)):
        page=doc[i]
        bitmap=page.render(scale=1.5)
        pic=bitmap.to_pil()
        path=output/f"page-{i+1:03d}.png"
        pic.save(path)
        images.append(path)
        pic.close(); bitmap.close(); page.close()
    doc.close()
    sheets=[]
    for batch in range(0,len(images),6):
        sheet=Image.new("RGB",(1280,2760),"#dddddd")
        draw=ImageDraw.Draw(sheet)
        for offset,path in enumerate(images[batch:batch+6]):
            with Image.open(path) as im:
                im.thumbnail((620,870))
                x=10+(offset%2)*640; y=30+(offset//2)*920
                sheet.paste(im,(x,y))
                draw.text((x,y-20),f"Page {batch+offset+1}",fill="black")
        path=output/f"overview-{batch//6+1:02d}.png"; sheet.save(path); sheets.append(str(path))
    write_json(output/"render.json",{"pdf_sha256":sha256(project/"report.pdf"),"pages":len(images)})
    return {"pages":[str(x) for x in images],"overviews":sheets}


def record_review(project,pages,note):
    project=Path(project).resolve()
    if not current_build(project): raise ValueError("Review does not apply to the current source/PDF")
    build=read_json(project/"build.json")
    rendered=read_json(project/".review"/"render.json")
    if rendered["pdf_sha256"]!=build["pdf_sha256"]: raise ValueError("Previews are stale")
    if sorted(set(pages))!=list(range(1,build["pages"]+1)):
        raise ValueError("Record all actual PDF pages inspected, including appendices")
    if not note.strip(): raise ValueError("Describe the visual review")
    review={"pdf_sha256":build["pdf_sha256"],"pages":sorted(set(pages)),"note":note}
    write_json(project/"review.json",review)
    return review


def status(project):
    project=Path(project).resolve()
    result=read_json(project/"results.json")
    data_check=validate_data(project, allow_incomplete=result.get("data_policy")=="partial")
    result_check=validate_results(project)
    current=current_build(project)
    review=read_json(project/"review.json") if (project/"review.json").is_file() else {}
    build=read_json(project/"build.json") if (project/"build.json").is_file() else {}
    reviewed=bool(current and review.get("pdf_sha256")==build.get("pdf_sha256")
                  and review.get("pages")==list(range(1,build.get("pages",0)+1)))
    return {"data":data_check,"results":result_check,"compiled_current":current,"visual_review_current":reviewed,
            "complete":bool(data_check["valid"] and not data_check["warnings"] and result_check["valid"]
                            and result.get("data_policy", "complete")=="complete"
                            and current and reviewed), "build_warnings":build.get("warnings",[])}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=("render","compile","preview","review","status"))
    p.add_argument("project")
    p.add_argument("--engine",default="xelatex"); p.add_argument("--timeout",type=int,default=120)
    p.add_argument("--pages",nargs="+",type=int); p.add_argument("--note",default="")
    args=p.parse_args()
    try:
        if args.command=="compile": result=compile_report(args.project,args.engine,args.timeout)
        elif args.command=="render": result=render(args.project)
        elif args.command=="preview": result=preview(args.project)
        elif args.command=="review": result=record_review(args.project,args.pages or [],args.note)
        else: result=status(args.project)
        print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
    except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr); return 2


if __name__=="__main__":
    raise SystemExit(main())
