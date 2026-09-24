"""Numerical helpers copied into each report project; no model/API calls."""
from __future__ import annotations
import math
from pathlib import Path
from statistics import mean, stdev

from reportlib import read_json, write_json, sha256, validate_data, validate_results, inside, number


def load_data(project=".", *, allow_incomplete=False):
    check = validate_data(project, allow_incomplete=allow_incomplete)
    if not check["valid"]:
        raise ValueError("\n".join(check["errors"]))
    return read_json(Path(project) / "data.json")


def columns(data, table_id):
    table = next(t for t in data["tables"] if t["id"] == table_id)
    return {c["key"]: [row["values"][c["key"]] for row in table["rows"]]
            for c in table["columns"]}


def linear_fit(x, y):
    """Unweighted OLS y=a*x+b, including residual-derived standard errors."""
    x, y = list(x), list(y)
    if len(x) != len(y) or len(x) < 3 or not all(number(v) for v in x + y):
        raise ValueError("OLS needs at least 3 paired finite points")
    xm, ym = mean(x), mean(y)
    sxx = sum((v - xm)**2 for v in x)
    if sxx <= 0:
        raise ValueError("Constant x cannot be fitted")
    slope = sum((a-xm)*(b-ym) for a,b in zip(x,y)) / sxx
    intercept = ym - slope*xm
    residuals = [b-slope*a-intercept for a,b in zip(x,y)]
    sse = sum(v*v for v in residuals)
    variance = sse/(len(x)-2)
    syy = sum((v-ym)**2 for v in y)
    return {"slope": slope, "intercept": intercept,
            "slope_stderr": math.sqrt(variance/sxx),
            "intercept_stderr": math.sqrt(variance*(1/len(x)+xm*xm/sxx)),
            "r_squared": 1-sse/syy if syy > 0 else None,
            "residuals": residuals, "n": len(x)}


def mean_uncertainty(values, *, instrument_limit=None):
    """u_A of the mean; optional independent rectangular +/- limit for u_B."""
    values = list(values)
    if not values or not all(number(v) for v in values):
        raise ValueError("At least one finite reading required")
    ua = stdev(values)/math.sqrt(len(values)) if len(values) > 1 else None
    if instrument_limit is not None and (not number(instrument_limit) or instrument_limit < 0):
        raise ValueError("Instrument limit must be finite and nonnegative")
    ub = instrument_limit/math.sqrt(3) if instrument_limit is not None else None
    uc = math.hypot(ua, ub) if ua is not None and ub is not None else None
    return {"mean": mean(values), "n": len(values), "u_a": ua, "u_b": ub, "u_c": uc}


def propagate(gradient, covariance):
    """First-order propagation u^2 = J Sigma J^T; keep shared errors correlated."""
    g = list(gradient)
    if len(covariance) != len(g) or any(len(row) != len(g) for row in covariance):
        raise ValueError("Covariance shape differs from gradient")
    if not all(number(x) for x in g) or not all(number(x) for row in covariance for x in row):
        raise ValueError("Finite gradient and covariance required")
    import numpy as np
    cov = np.asarray(covariance, dtype=float)
    if not np.allclose(cov, cov.T, rtol=1e-9, atol=1e-15):
        raise ValueError("Covariance must be symmetric")
    scale = max(float(np.max(np.abs(cov))), 1e-300)
    if float(np.linalg.eigvalsh(cov).min()) < -1e-12*scale:
        raise ValueError("Covariance must be positive semidefinite")
    var = sum(g[i]*cov[i,j]*g[j] for i in range(len(g)) for j in range(len(g)))
    return math.sqrt(max(0, var))


def angular_difference(a, b):
    """Signed shortest difference a-b in degrees, in [-180,180)."""
    return (a-b+180) % 360 - 180


def configure_plots():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    candidates = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "WenQuanYi Micro Hei"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((x for x in candidates if x in available), None)
    plt.rcParams.update({"font.family": chosen or "DejaVu Sans", "axes.unicode_minus": False,
                         "font.size": 10, "figure.dpi": 120, "savefig.dpi": 200})
    return plt


def save_results(project, *, quantities=(), tables=(), figures=(), notes=(), allow_incomplete=False):
    project = Path(project).resolve()
    data = load_data(project, allow_incomplete=allow_incomplete)
    result = {"schema_version": 1, "experiment_id": data["experiment_id"],
              "data_policy": "partial" if allow_incomplete else "complete",
              "data_sha256": sha256(project/"data.json"),
              "analysis_sha256": sha256(project/"analyze.py"),
              "support_sha256": {name: sha256(project/name) for name in ("physics.py", "reportlib.py")},
              "quantities": list(quantities), "tables": list(tables),
              "figures": [dict(f, sha256=sha256(inside(project, f["path"]))) for f in figures],
              "notes": list(notes)}
    write_json(project/"results.json", result)
    check = validate_results(project)
    if not check["valid"]:
        raise ValueError("\n".join(check["errors"]))
    return result
