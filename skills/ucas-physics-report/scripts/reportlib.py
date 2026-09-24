"""Shared IO and checks for UCAS report projects. Python 3.10+; stdlib only."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

ID = re.compile(r"^[a-z][a-z0-9_-]*$")
REQUIRED_META = ("student_name", "student_id", "group", "seat", "date", "teacher", "room")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else _hash(stream)


def _hash(stream):
    result = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        result.update(block)
    return result.hexdigest()


def inside(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError(f"Path must be a file inside the project: {relative}")
    return path


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _check_tables(tables, errors, source_images=None, incomplete_warnings=None):
    seen = set()
    if not isinstance(tables, list):
        errors.append("tables must be a list")
        return
    for table in tables:
        tid = table.get("id", "")
        if not isinstance(tid, str) or not ID.fullmatch(tid) or tid in seen:
            errors.append(f"Invalid or duplicate table id: {tid}")
        seen.add(tid)
        columns = table.get("columns", [])
        keys = [col.get("key") for col in columns]
        if not columns or len(set(keys)) != len(keys):
            errors.append(f"{tid}: missing/duplicate columns")
        for col in columns:
            if not isinstance(col.get("key"), str) or not ID.fullmatch(col["key"]):
                errors.append(f"{tid}: invalid column key")
            if col.get("kind", "number") not in ("number", "text"):
                errors.append(f"{tid}: unsupported column kind")
            if not isinstance(col.get("unit"), str) or not col.get("label"):
                errors.append(f"{tid}: columns need label and unit (empty string for dimensionless)")
        if not table.get("title") or not table.get("rows"):
            errors.append(f"{tid}: title and nonempty rows required")
        for i, row in enumerate(table.get("rows", []), 1):
            values = row.get("values", {})
            if set(values) != set(keys):
                errors.append(f"{tid} row {i}: values must match column keys exactly")
            for col in columns:
                v = values.get(col.get("key"))
                if col.get("kind", "number") == "number" and v is None and incomplete_warnings is not None:
                    incomplete_warnings.append(f"Unreadable {tid} row {i} {col.get('key')}: retained as missing; excluded only with stated analysis rationale")
                elif col.get("kind", "number") == "number" and not number(v):
                    errors.append(f"{tid} row {i} {col.get('key')}: finite number required; resolve unreadable cells first")
                elif col.get("kind") == "text" and not isinstance(v, str):
                    errors.append(f"{tid} row {i} {col.get('key')}: text required")
            if source_images is not None:
                src = row.get("source", {})
                if src.get("image") not in source_images or not src.get("table") or not src.get("row"):
                    errors.append(f"{tid} row {i}: source needs manifest image, table, row")


def validate_data(project, allow_incomplete=False):
    project = Path(project).resolve()
    errors, warnings = [], []
    data = read_json(project / "data.json")
    manifest = read_json(project / "inputs.json")
    if data.get("schema_version") != 1:
        errors.append("Unsupported data schema_version")
    if data.get("experiment_id") != manifest.get("experiment_id"):
        errors.append("Experiment differs between data.json and inputs.json")
    image_paths = set()
    for item in manifest.get("images", []):
        rel = item.get("path", "")
        image_paths.add(rel)
        try:
            p = inside(project, rel)
            if not p.is_file() or sha256(p) != item.get("sha256"):
                errors.append(f"Input image missing or changed: {rel}")
        except ValueError as exc:
            errors.append(str(exc))
    _check_tables(data.get("tables", []), errors, image_paths, warnings if allow_incomplete else None)
    observations = data.get("observations", [])
    observation_ids = set()
    for obs in observations:
        oid = obs.get("id", "")
        if not isinstance(oid, str) or not ID.fullmatch(oid) or oid in observation_ids:
            errors.append("Observations need unique valid ids")
        observation_ids.add(oid)
        if not obs.get("text") or obs.get("source", {}).get("image") not in image_paths:
            errors.append("Observations need text and a manifest image source")
    if not data.get("tables") and not observations:
        errors.append("No transcribed tables or observed phenomena")
    for key, item in data.get("constants", {}).items():
        if not number(item.get("value")) or not isinstance(item.get("unit"), str) or not item.get("source"):
            errors.append(f"Constant {key}: value, unit and source required")
    for issue in data.get("issues", []):
        if issue.get("status") not in ("resolved", "unresolved"):
            errors.append("Issue status must be resolved or unresolved")
        elif issue["status"] == "resolved" and not issue.get("resolution"):
            errors.append(f"Resolved issue needs its resolution: {issue.get('id')}")
        elif issue["status"] == "unresolved":
            (errors if issue.get("blocking", True) and not allow_incomplete else warnings).append(
                f"Unresolved {issue.get('id', '')}: {issue.get('description', '')}")
    meta = data.get("metadata", {})
    for key in REQUIRED_META:
        if not str(meta.get(key) or "").strip():
            warnings.append(f"Missing metadata: {key}")
    if meta.get("date"):
        from datetime import date
        try:
            date.fromisoformat(meta["date"])
        except (ValueError, TypeError):
            errors.append("metadata.date must be an actual ISO date YYYY-MM-DD")
    if data.get("requirements", {}).get("preview_required", True):
        if not any(x.get("role") == "preview" for x in manifest.get("images", [])):
            warnings.append("Missing required preview-report photo")
    return {"valid": not errors, "errors": errors, "warnings": warnings,
            "data_sha256": sha256(project / "data.json")}


def validate_results(project):
    project = Path(project).resolve()
    errors = []
    data = read_json(project / "data.json")
    result = read_json(project / "results.json")
    if result.get("schema_version") != 1 or result.get("experiment_id") != data.get("experiment_id"):
        errors.append("Invalid results schema or experiment")
    if result.get("data_policy", "complete") not in ("complete", "partial"):
        errors.append("Unknown results data_policy")
    if result.get("data_policy") == "partial" and not result.get("notes"):
        errors.append("Partial analysis must explain missing/excluded data in notes")
    if result.get("data_sha256") != sha256(project / "data.json"):
        errors.append("Stale results: data.json changed; rerun analyze.py")
    script = project / "analyze.py"
    if not script.is_file() or result.get("analysis_sha256") != sha256(script):
        errors.append("Stale results: analyze.py changed; rerun analyze.py")
    for name in ("physics.py", "reportlib.py"):
        support = project / name
        if not support.is_file() or result.get("support_sha256", {}).get(name) != sha256(support):
            errors.append(f"Stale results: {name} changed; rerun analyze.py")
    source_ids = {t["id"] for t in data.get("tables", [])}
    observation_ids = {o["id"] for o in data.get("observations", [])}
    derived_ids = {t.get("id") for t in result.get("tables", [])}
    if source_ids & derived_ids:
        errors.append("Raw and derived table ids must be different")
    _check_tables(result.get("tables", []), errors)
    seen = set()
    for q in result.get("quantities", []):
        qid = q.get("id", "")
        if not isinstance(qid, str) or not ID.fullmatch(qid) or qid in seen or not number(q.get("value")):
            errors.append(f"Invalid/duplicate quantity: {qid}")
        seen.add(qid)
        if not isinstance(q.get("unit"), str) or not q.get("method") or not q.get("inputs"):
            errors.append(f"{qid}: unit, method and inputs required")
        if "uncertainty" in q and (not number(q["uncertainty"]) or q["uncertainty"] < 0):
            errors.append(f"{qid}: uncertainty must be nonnegative")
        if "digits" in q and (not isinstance(q["digits"], int) or not 1 <= q["digits"] <= 12):
            errors.append(f"{qid}: digits must be between 1 and 12")
    seen_figures = set()
    for fig in result.get("figures", []):
        fid = fig.get("id", "")
        if not isinstance(fid, str) or not ID.fullmatch(fid) or fid in seen_figures:
            errors.append(f"Invalid/duplicate figure id: {fid}")
        seen_figures.add(fid)
        if not fig.get("caption") or not (fig.get("table_ids") or fig.get("observation_ids")):
            errors.append(f"{fid}: caption and table_ids/observation_ids required")
        for oid in fig.get("observation_ids", []):
            if oid not in observation_ids:
                errors.append(f"{fid}: unknown observation id {oid}")
        for tid in fig.get("table_ids", []):
            if tid not in source_ids | derived_ids:
                errors.append(f"{fid}: unknown table id {tid}")
        try:
            path = inside(project, fig.get("path", ""))
            if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".pdf"):
                errors.append(f"{fid}: unsupported LaTeX image type")
            if not path.is_file() or sha256(path) != fig.get("sha256"):
                errors.append(f"{fid}: figure missing or changed; rerun analysis")
        except ValueError as exc:
            errors.append(str(exc))
    return {"valid": not errors, "errors": errors}
