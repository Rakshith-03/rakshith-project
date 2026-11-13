"""HTTP API. Run: python -m uvicorn bp.api:app --port 8000 (from backend/). The frontend never runs MATLAB or arbitrary
code: it can only call these endpoints. Control-loop moderation happens here, never in n8n."""
import hashlib, json
from pathlib import Path
import numpy as np
from fastapi import FastAPI, HTTPException, Header, Body
from fastapi.responses import FileResponse, HTMLResponse
from .data import ROOT, calce, drive_cycle, scored
from .db import connect, dumps, now, rows
from .model import load_model, MODELS, metrics, simulate
from .experiments import (CHEM, DEFAULT_PROFILES, validate_profile, run_experiment, get_experiment, timeseries,
                          cell_model, limits_for)
from .constraints import moderate
from . import generators as gen
from .charging import cccv, fixed_current, adaptive, feasibility, nicd_charge
from .bms import ekf_soc, coulomb_count, soh_capacity, apparent_resistance, sop
from .pack import make_cells, run as pack_run
from . import ml, reports
from .live import LiveSession, SESSIONS

app = FastAPI(title="Battery characterization & software BMS platform")
STATIC = Path(__file__).resolve().parents[1] / "static"

DATASETS = [
    {"id": "NICD_SIM_READY", "name": "NiCd_Simulation_Ready.xlsx", "chemistry": "ni-cd", "format": "xlsx",
     "source_type": "SIMULATED (self-labelled; OCV endpoints claimed measured)", "path": "NiCd_Simulation_Ready.xlsx",
     "approval": "REJECTED as experimental reference", "report": "DATA/REPORTS/nicd_inspection.md"},
    {"id": "PANASONIC_NCR18650B", "name": "Panasonic_NCR18650B_Consolidated.mat", "chemistry": "li-ion (UNVERIFIED subtype)",
     "format": "mat", "source_type": "MEASURED (92 cells; no current/temperature)", "path": "Panasonic_NCR18650B_Consolidated.mat",
     "approval": "APPROVED (partial: OCV and pulse shape only)", "report": "DATA/REPORTS/liion_inspection.md"},
    {"id": "CALCE_SP1_LC_OCV", "name": "CALCE INR18650-20R SP1 C/20 OCV 25C", "chemistry": "li-ion-nmc", "format": "xlsx",
     "source_type": "MEASURED", "path": "DATA/RAW_REFERENCE/LITHIUM_ION/CALCE_INR18650-20R/zips/SP1_25C_LC_OCV_11_5_2015.zip",
     "approval": "APPROVED (OCV calibration)", "url": "https://web.calce.umd.edu/batteries/data/SP1_25C_LC_OCV_11_5_2015.zip"},
] + [{"id": f"CALCE_SP2_{n}", "name": f"CALCE INR18650-20R SP2 {n} 25C", "chemistry": "li-ion-nmc", "format": "xls(x)",
      "source_type": "MEASURED", "path": f"DATA/RAW_REFERENCE/LITHIUM_ION/CALCE_INR18650-20R/zips/SP2_25C_{n}.zip",
      "approval": {"DST": "APPROVED (calibration)", "FUDS": "APPROVED (model selection)", "US06": "APPROVED (independent test)",
                   "BJDST": "APPROVED (independent test)"}[n], "url": f"https://web.calce.umd.edu/batteries/data/SP2_25C_{n}.zip"}
     for n in ("DST", "FUDS", "US06", "BJDST")] + [
    {"id": "CALCE_SP3_LC_OCV", "name": "CALCE INR18650-20R SP3 C/20 OCV 25C", "chemistry": "li-ion-nmc", "format": "xls(x)",
     "source_type": "MEASURED", "path": "DATA/RAW_REFERENCE/LITHIUM_ION/CALCE_INR18650-20R/zips/SP3_25C_LC_OCV_11_16_2015.zip",
     "approval": "APPROVED (independent OCV check)", "url": "https://web.calce.umd.edu/batteries/data/SP3_25C_LC_OCV_11_16_2015.zip"}]
SOURCES_ALLOWLIST = ["https://web.calce.umd.edu/batteries/data/"]


def _db():
    c = connect()
    if not rows(c, "SELECT id FROM battery_profiles LIMIT 1"):
        for p in DEFAULT_PROFILES:
            c.execute("INSERT INTO battery_profiles VALUES (?,?,?,?,?,?)", (p["id"], p["name"], p["chemistry"],
                      CHEM[p["chemistry"]]["status"], 1, now()))
            c.execute("INSERT INTO battery_parameter_versions VALUES (?,?,?,?)", (p["id"], 1, dumps(p | {"version": 1}), now()))
        for k, v in CHEM.items():
            c.execute("INSERT OR REPLACE INTO chemistry_profiles VALUES (?,?,?)", (k, dumps(v), now()))
        for d in DATASETS:
            f = ROOT / d["path"]
            sha = hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None
            c.execute("INSERT OR REPLACE INTO datasets VALUES (?,?,?,?,?,?,?,?,?,?)", (d["id"], d["name"], d["chemistry"],
                      d["format"], d["source_type"], d["path"], sha, d["approval"], dumps(d), now()))
            if d.get("url"):
                c.execute("INSERT INTO dataset_sources (dataset_id,url,licence_note,retrieved_at) VALUES (?,?,?,?)",
                          (d["id"], d["url"], "openly accessible per CALCE; cite CALCE", "2026-11-12"))
        c.commit()
    return c


def _profile(c, pid, version=None):
    r = rows(c, "SELECT payload FROM battery_parameter_versions WHERE profile_id=? ORDER BY version DESC", pid)
    if version:
        r = [x for x in r if x["payload"]["version"] == version]
    if not r:
        raise HTTPException(404, f"profile {pid} not found")
    return r[0]["payload"]


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    return o


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health():
    m = load_model()
    return {"status": "ok", "model": m["id"], "approval": m["meta"]["approval"], "time": now()}


# ---------------- profiles
@app.get("/api/chemistries")
def chemistries():
    return CHEM


@app.get("/api/profiles")
def list_profiles():
    c = _db()
    return [r | {"latest": _profile(c, r["id"])} for r in rows(c, "SELECT * FROM battery_profiles ORDER BY id")]


@app.get("/api/profiles/{pid}/versions")
def profile_versions(pid: str):
    return rows(_db(), "SELECT version, created_at, payload FROM battery_parameter_versions WHERE profile_id=? ORDER BY version", pid)


@app.post("/api/profiles")
def create_profile(p: dict = Body(...)):
    c = _db()
    errs = validate_profile(p)
    if errs:
        raise HTTPException(422, errs)
    if rows(c, "SELECT id FROM battery_profiles WHERE id=?", p["id"]):
        raise HTTPException(409, "profile id exists; use PUT to create a new version")
    p = p | {"version": 1}
    c.execute("INSERT INTO battery_profiles VALUES (?,?,?,?,?,?)", (p["id"], p.get("name", p["id"]), p["chemistry"],
              CHEM[p["chemistry"]]["status"], 1, now()))
    c.execute("INSERT INTO battery_parameter_versions VALUES (?,?,?,?)", (p["id"], 1, dumps(p), now())); c.commit()
    return p | {"constraints": limits_for(p)}


@app.put("/api/profiles/{pid}")
def update_profile(pid: str, changes: dict = Body(...)):
    c = _db(); old = _profile(c, pid)
    new = {**old, **changes, "id": pid, "version": old["version"] + 1}
    if "health" in changes:
        new["health"] = {**old.get("health", {}), **changes["health"]}
    errs = validate_profile(new)
    if errs:
        raise HTTPException(422, errs)
    c.execute("INSERT INTO battery_parameter_versions VALUES (?,?,?,?)", (pid, new["version"], dumps(new), now()))
    c.execute("UPDATE battery_profiles SET current_version=?, chemistry=? WHERE id=?", (new["version"], new["chemistry"], pid))
    c.commit()
    return new | {"constraints": _clean(limits_for(new))}


@app.post("/api/profiles/{pid}/duplicate")
def duplicate_profile(pid: str, body: dict = Body(...)):
    p = _profile(_db(), pid)
    return create_profile({**p, "id": body["new_id"], "name": body.get("name", body["new_id"])})


# ---------------- datasets & validation
@app.get("/api/datasets")
def datasets():
    c = _db()
    return [r | {"sources": rows(c, "SELECT url,licence_note,retrieved_at FROM dataset_sources WHERE dataset_id=?", r["id"]),
                 "cleaning_log": rows(c, "SELECT step,detail,created_at FROM dataset_cleaning_logs WHERE dataset_id=?", r["id"])}
            for r in rows(c, "SELECT * FROM datasets")]


@app.get("/api/datasets/sources")
def dataset_sources():
    c = _db()
    return {"allowlist": SOURCES_ALLOWLIST, "known": [{"id": d["id"], "url": d.get("url"), "present": (ROOT / d["path"]).exists()}
                                                     for d in DATASETS],
            "policy": "download only allow-listed public sources; originals kept unchanged; operator approval for new sources"}


@app.post("/api/datasets/{did}/fetch")
def fetch_dataset(did: str):
    """Download a KNOWN dataset from its allow-listed public URL if it is missing locally (originals kept unchanged).
    Unknown sources are refused: adding a source needs an operator decision, not a workflow."""
    import urllib.request
    d = next((x for x in DATASETS if x["id"] == did), None)
    if not d or not d.get("url") or not any(d["url"].startswith(a) for a in SOURCES_ALLOWLIST):
        raise HTTPException(403, "dataset has no allow-listed source")
    f = ROOT / d["path"]
    if f.exists():
        return {"dataset": did, "status": "already present", "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
    f.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(d["url"], timeout=120) as r:
        f.write_bytes(r.read())
    sha = hashlib.sha256(f.read_bytes()).hexdigest()
    c = _db()
    c.execute("UPDATE datasets SET sha256=? WHERE id=?", (sha, did))
    c.execute("INSERT INTO dataset_cleaning_logs (dataset_id,step,detail,created_at) VALUES (?,?,?,?)",
              (did, "fetch", f"downloaded from {d['url']}", now())); c.commit()
    return {"dataset": did, "status": "downloaded", "sha256": sha}


@app.post("/api/datasets/{did}/clean")
def clean_dataset(did: str):
    """Quality checks on the parsed copy (raw file untouched). CALCE drive-cycle/OCV files only."""
    c = _db()
    pats = {"CALCE_SP1_LC_OCV": ["*SP20-1.xlsx"], "CALCE_SP3_LC_OCV": ["*SP20-3.xls"]}
    pats |= {f"CALCE_SP2_{n}": [f"*SP20-2_{n}_50SOC.xls", f"*SP20-2_{n}_80SOC.xls"] for n in ("DST", "FUDS", "US06", "BJDST")}
    if did not in pats:
        raise HTTPException(400, "automatic cleaning is implemented for the CALCE files; see the inspection reports for others")
    out = []
    for pat in pats[did]:
        d = calce(pat); dt = np.diff(d["t"])
        q = {"file": d["name"], "rows": int(len(d["t"])), "missing_V": int(np.isnan(d["V"]).sum()),
             "missing_I": int(np.isnan(d["I_chg"]).sum()), "duplicate_timestamps": int((dt == 0).sum()),
             "time_reversals": int((dt < 0).sum()), "dt_median_s": float(np.median(dt)),
             "V_out_of_range": int(((d["V"] < 2.0) | (d["V"] > 4.3)).sum()),
             "transients_preserved": "yes: no filtering or resampling is applied"}
        q["status"] = ("APPROVED" if q["missing_V"] == q["missing_I"] == q["time_reversals"] == q["V_out_of_range"] == 0
                       else "NEEDS REVIEW")
        out.append(q)
        c.execute("INSERT INTO dataset_quality_reports (dataset_id,payload,created_at) VALUES (?,?,?)", (did, dumps(q), now()))
        c.execute("INSERT INTO dataset_cleaning_logs (dataset_id,step,detail,created_at) VALUES (?,?,?,?)",
                  (did, "quality check", f"{q['file']}: {q['status']}", now()))
    c.commit()
    status = "APPROVED" if all(q["status"] == "APPROVED" for q in out) else "NEEDS REVIEW"
    return {"dataset": did, "status": status, "files": out}


@app.get("/api/validation")
def validation():
    m = load_model()
    return {"models": [json.loads(p.read_text()) for p in sorted(MODELS.glob("*.json"))],
            "approved": m["id"], "reports": sorted(str(p.relative_to(ROOT)) for p in (ROOT / "DATA" / "REPORTS").glob("*.md")),
            "statuses": ["NOT VALIDATED", "IN PROGRESS", "VALIDATED", "NEEDS IMPROVEMENT", "FAILED"]}


@app.get("/api/validation/overlay/{name}")
def validation_overlay(name: str, every: int = 5):
    """Measured vs simulated voltage for an unseen CALCE test file (US06_50SOC, US06_80SOC, BJDST_50SOC, BJDST_80SOC)."""
    if name not in ml.SPLIT["test"] + ml.SPLIT["val"] + ml.SPLIT["train"]:
        raise HTTPException(404, "unknown CALCE drive-cycle file")
    m = load_model(); d = drive_cycle(name); y = simulate(m, d["t"], -d["I_chg"]); k = scored(d)
    s = slice(None, None, every)
    return _clean({"file": name, "role": next(r for r, v in ml.SPLIT.items() if name in v),
                   "t": d["t"][s] - d["t"][0], "V_measured": d["V"][s], "V_simulated": y["V"][s], "I_measured": -d["I_chg"][s],
                   "metrics_mV": metrics(1000 * d["V"][k], 1000 * y["V"][k]), "scored_region": "drive-cycle steps, V > 3.0 V"})


# ---------------- experiments
@app.post("/api/experiments")
def create_experiment(body: dict = Body(...), idempotency_key: str | None = Header(default=None)):
    c = _db()
    p = _profile(c, body.get("profile_id", "INR18650-20R"), body.get("profile_version"))
    try:
        return _clean(run_experiment(body["config"], p, c, idempotency_key, body.get("campaign_id")))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/experiments")
def list_experiments(chemistry: str | None = None, profile_id: str | None = None, mode: str | None = None,
                     campaign_id: str | None = None, since: str | None = None, limit: int = 200):
    q, a = "SELECT * FROM experiments WHERE 1=1", []
    for col, v in (("chemistry", chemistry), ("profile_id", profile_id), ("mode", mode), ("campaign_id", campaign_id)):
        if v:
            q += f" AND {col}=?"; a.append(v)
    if since:
        q += " AND created_at>=?"; a.append(since)
    c = _db(); ex = rows(c, q + " ORDER BY created_at DESC, rowid DESC LIMIT ?", *a, limit)
    feats = {r["experiment_id"]: r["payload"] for r in rows(c, "SELECT experiment_id,payload FROM extracted_features WHERE run='main'")}
    return [e | {"features": feats.get(e["id"], {})} for e in ex]


@app.get("/api/experiments/{eid}")
def experiment(eid: str):
    try:
        return _clean(get_experiment(eid, _db()))
    except KeyError:
        raise HTTPException(404, eid)


@app.get("/api/experiments/{eid}/timeseries")
def experiment_ts(eid: str, run: str = "main"):
    return _clean(timeseries(eid, run, _db()))


@app.post("/api/experiments/{eid}/characterize")
def characterize_exp(eid: str):
    return experiment(eid)["features"]


@app.post("/api/experiments/{eid}/diagnostics")
def diagnostics(eid: str):
    """BMS diagnostics on a stored run: EKF SOC from its voltage/current, capacity SOH where valid, SOP at the end."""
    c = _db(); e = get_experiment(eid, c); ts = timeseries(eid, "main", c)
    p = e["config"]["profile"]; m = cell_model(p); L = limits_for(p)
    t, I, V = (np.array(ts[k]) for k in ("t", "I", "V"))
    est = ekf_soc(m, t, I, V, z0=float(ts["z"][0]))
    f = e["features"].get("main", {})
    out = {"soc_ekf_end": float(est["z"][-1]), "soc_model_end": float(ts["z"][-1]), "soc_ekf_std_end": float(est["z_std"][-1]),
           "soh_capacity_pct": f.get("SOH_capacity_pct"), "soh_note": "only for full 100->0 % discharges; otherwise not valid",
           "resistance_indicator": apparent_resistance(t, V, I, 0.3, 5.0),
           "sop": sop(m, {"z": float(ts["z"][-1]), "h": float(ts["h"][-1]), "v": (0.0, 0.0), "T": float(ts["T"][-1])}, L,
                      I_max_dis=p["I_dis_max"], I_max_chg=p["I_chg_max"]),
           "protection": [{"constraint": x["constraint_name"], "severity": x["severity"]} for x in e["constraint_events"]],
           "source_type": "estimated from SIMULATED signals"}
    c.execute("INSERT INTO bms_estimates (experiment_id,payload,created_at) VALUES (?,?,?)", (eid, dumps(out), now())); c.commit()
    return _clean(out)


@app.post("/api/experiments/{eid}/report")
def experiment_report(eid: str):
    return reports.experiment_report(eid)


@app.get("/api/files")
def get_file(path: str):
    f = (ROOT / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    allowed = (ROOT / "DATA" / "REPORTS").resolve()
    if allowed not in f.parents or not f.exists():
        raise HTTPException(404, "only generated reports can be downloaded")
    return FileResponse(f)


# ---------------- moderation, live
@app.post("/api/moderate")
def moderate_once(body: dict = Body(...)):
    """Evaluate one request: {profile_id, state:{soc,T}, request:{base_A, pulse_A, pulse_s, interval_s, horizon_s}}."""
    c = _db(); p = _profile(c, body.get("profile_id", "INR18650-20R")); m = cell_model(p); L = limits_for(p)
    r = body["request"]; st = body.get("state", {})
    t = gen.time_grid(r.get("horizon_s", 30.0))
    I = gen.pulse(t, r["base_A"], r["pulse_A"], r.get("pulse_s", 10.0), r.get("interval_s", 20.0)) / p["n_parallel"]
    keep = gen.pulse(t, r["base_A"], r["base_A"], r.get("pulse_s", 10.0), r.get("interval_s", 20.0)) / p["n_parallel"]
    res = moderate(m, {"z": st.get("soc", p["initial_soc"]), "h": -1.0, "v": (0.0, 0.0), "T": st.get("T", p["T_init"])},
                   t, I, L, I_keep=keep)
    res.pop("I_perm")
    res["requested_pulse_A"] = r["pulse_A"]
    res["permitted_pulse_A"] = r["base_A"] + res["scale"] * (r["pulse_A"] - r["base_A"]) if res.get("mode") != "whole command scaled" \
        else res["scale"] * r["pulse_A"]
    return _clean(res)


@app.post("/api/live")
def live_start(body: dict = Body(...)):
    c = _db(); p = _profile(c, body.get("profile_id", "INR18650-20R"))
    s = LiveSession(p, body.get("config", {})); SESSIONS[s.id] = s
    return {"session": s.id, "label": "SIMULATED (" + s.m["id"] + ")"}


@app.post("/api/live/{sid}/step")
def live_step(sid: str, seconds: float = 10.0):
    return _clean(_sess(sid).step(seconds))


@app.post("/api/live/{sid}/update")
def live_update(sid: str, changes: dict = Body(...)):
    return _sess(sid).update(changes)


@app.post("/api/live/{sid}/{action}")
def live_action(sid: str, action: str):
    s = _sess(sid)
    if action == "pause":
        s.state = "PAUSED"
    elif action == "resume":
        s.state = "RUNNING"
    elif action == "reset":
        s.reset()
    elif action == "stop":
        return _clean(s.stop())
    else:
        raise HTTPException(400, "action must be pause|resume|reset|stop")
    return {"state": s.state, "t": s.t}


def _sess(sid):
    if sid not in SESSIONS:
        raise HTTPException(404, "no such live session")
    return SESSIONS[sid]


# ---------------- charging, BMS, balancing
@app.post("/api/charging/optimize")
def charging_optimize(body: dict = Body(...)):
    c = _db(); p = _profile(c, body.get("profile_id", "INR18650-20R"))
    if body.get("health"):
        p = {**p, "health": {**p.get("health", {}), **body["health"]}}
    m = cell_model(p); L = limits_for(p)
    z0, zt = body["initial_soc"], body["target_soc"]; T0 = body.get("T_init", p["T_init"]); tt = body.get("target_time_s")
    if not 0 <= z0 < zt <= 1:
        raise HTTPException(422, "need 0 <= initial_soc < target_soc <= 1")
    Icap = p["I_chg_max"] / p["n_parallel"]
    if p["chemistry"] == "ni-cd":
        r = nicd_charge(m, z0, body.get("current_A", 0.5 * p["capacity_Ah"]) / p["n_parallel"], p["capacity_Ah"], T0=T0)
        return _clean({"chemistry": "ni-cd", "status": CHEM["ni-cd"]["status"], "strategy": r})
    feas = feasibility(m, z0, zt, tt, L, L["V_crit_hi"], Icap, T0=T0) if tt else None
    conv = cccv(m, z0, zt, min(1.0, Icap), L["V_crit_hi"], T0=T0, t_target_s=tt)
    fixed = fixed_current(m, z0, zt, min((zt - z0) * m["Q"] * 3600 / tt, Icap) if tt else Icap / 2, T0=T0, t_target_s=tt)
    ad = adaptive(m, z0, zt, tt, L, L["V_crit_hi"], Icap, T0=T0)
    out = {"feasibility": feas, "conventional": conv, "fixed": fixed, "adaptive": ad,
           "verdict": None if not feas else ("FEASIBLE" if feas["feasible"] else "INFEASIBLE"),
           "notes": ["constraints are never overridden to meet a time target",
                     "charge-current cap = validated data envelope (datasheet maximum UNVERIFIED)",
                     "temperature from the PROVISIONAL thermal model"]}
    c.execute("INSERT INTO charging_optimizations (experiment_id,payload,created_at) VALUES (?,?,?)",
              (None, dumps({k: v for k, v in out.items() if k in ("feasibility", "verdict")} | {"request": body}), now()))
    c.commit()
    return _clean(out)


@app.post("/api/bms/ekf_demo")
def ekf_demo(body: dict = Body(default={})):
    """EKF on a MEASURED CALCE test file, starting from a wrong SOC. Reference SOC = coulomb counting (not independent)."""
    name = body.get("file", "US06_80SOC"); err0 = body.get("initial_error", -0.3); bias = body.get("current_bias_A", 0.0)
    m = load_model(); d = drive_cycle(name); I = -d["I_chg"]
    z_ref = coulomb_count(d["t"], I, 1.0, m["Q"])
    k0 = int(np.argmax(d["step"] >= 7)); k1 = int(np.where(d["V"] > 3.0)[0][-1]); s = slice(k0, k1)
    est = ekf_soc(m, d["t"][s], I[s] + bias, d["V"][s], z0=z_ref[k0] + err0)
    cc = coulomb_count(d["t"][s], I[s] + bias, z_ref[k0], m["Q"])
    e = est["z"] - z_ref[s]; tt = d["t"][s] - d["t"][k0]
    every = 10
    return _clean({"file": name, "t": tt[::every], "soc_ref": z_ref[s][::every], "soc_ekf": est["z"][::every],
                   "soc_cc": cc[::every], "ekf_rmse_after_600s": float(np.sqrt(np.mean(e[tt > 600] ** 2))),
                   "data": "MEASURED V and I (CALCE); reference SOC from coulomb counting"})


@app.post("/api/pack/balance")
def pack_balance(body: dict = Body(...)):
    c = _db(); m = cell_model(_profile(c, body.get("profile_id", "INR18650-20R")))
    n = body.get("n_cells", 4)
    res = {}
    for mode in ("off", body.get("mode", "passive")):
        cells = make_cells(m, n, body.get("dQ"), body.get("dR0"), body.get("soc0"))
        r = pack_run(cells, body.get("I_pack_A", 0.0), body.get("duration_s", 3600), mode=mode,
                     threshold=body.get("threshold", 0.005), I_bal=body.get("I_bal_A", 0.2))
        every = max(1, len(r["t"]) // 400)
        res[mode] = {k: (v[::every] if isinstance(v, np.ndarray) else v) for k, v in r.items()}
    c.execute("INSERT INTO balancing_results (experiment_id,payload,created_at) VALUES (?,?,?)",
              (None, dumps({k: {kk: vv for kk, vv in v.items() if not isinstance(vv, np.ndarray)} for k, v in res.items()}), now()))
    c.commit()
    return _clean(res | {"label": "SIMULATED per-cell model; differences are user-configured scenarios"})


# ---------------- ML
@app.get("/api/ml/models")
def ml_models():
    reg = ml.REG
    return [json.loads(p.read_text()) for p in sorted(reg.glob("*.json"))] if reg.exists() else []


@app.post("/api/ml/train")
def ml_train(body: dict = Body(default={})):
    task = body.get("task", "soc_regressor")
    c = _db()
    r = ml.train_soc() if task == "soc_regressor" else ml.panasonic_anomalies()
    if task == "soc_regressor":
        mid = f"soc_regressor_v{r['version']}"
        c.execute("INSERT OR REPLACE INTO ml_models VALUES (?,?,?,?,?,?)", (mid, task, r["version"], r["approval"], dumps(r), now()))
        for split, val in (("val", r["val_rmse"]), ("test", r["test_rmse"])):
            c.execute("INSERT INTO ml_evaluation_metrics (model_id,split,metric,value) VALUES (?,?,?,?)", (mid, split, "RMSE_SOC", val))
        c.commit()
    return _clean(r)


# ---------------- campaigns, n8n, errors, reports
@app.post("/api/campaigns")
def campaign(body: dict = Body(...), idempotency_key: str | None = Header(default=None)):
    c = _db()
    if idempotency_key:
        ex = rows(c, "SELECT * FROM campaigns WHERE idempotency_key=?", idempotency_key)
        if ex:
            return ex[0] | {"idempotent_replay": True}
    cid = "CMP_" + now().replace("-", "").replace(":", "").replace("T", "_")
    c.execute("INSERT INTO campaigns VALUES (?,?,?,?,?,?)", (cid, body.get("name", cid), "RUNNING", dumps(body), now(), idempotency_key))
    c.commit()
    done, failed = [], []
    for i, exp in enumerate(body.get("experiments", [])):
        try:
            p = _profile(c, exp.get("profile_id", "INR18650-20R"))
            r = run_experiment(exp["config"], p, c, f"{idempotency_key}:{i}" if idempotency_key else None, cid)
            done.append(r["id"])
        except Exception as e:
            failed.append({"index": i, "error": str(e)})
    status = "COMPLETED" if not failed else ("PARTIAL" if done else "FAILED")
    c.execute("UPDATE campaigns SET status=? WHERE id=?", (status, cid)); c.commit()
    return {"id": cid, "status": status, "experiments": done, "failed": failed}


@app.get("/api/campaigns")
def campaigns():
    return rows(_db(), "SELECT id,name,status,created_at FROM campaigns ORDER BY created_at DESC")


@app.post("/api/n8n/executions")
def n8n_execution(body: dict = Body(...)):
    c = _db()
    c.execute("INSERT INTO n8n_workflow_executions (workflow,execution_id,idempotency_key,status,payload,created_at) "
              "VALUES (?,?,?,?,?,?)", (body.get("workflow"), body.get("execution_id"), body.get("idempotency_key"),
                                       body.get("status", "RECORDED"), dumps(body), now()))
    c.commit()
    return {"recorded": True}


@app.get("/api/n8n/executions")
def n8n_executions():
    return rows(_db(), "SELECT * FROM n8n_workflow_executions ORDER BY id DESC LIMIT 200")


@app.get("/api/errors")
def list_errors():
    return rows(_db(), "SELECT * FROM diagnostic_events WHERE severity='ERROR' ORDER BY id DESC LIMIT 200")


@app.post("/api/errors")
def record_error(body: dict = Body(...)):
    c = _db()
    eid = body.get("experiment_id")
    c.execute("INSERT INTO diagnostic_events (experiment_id,severity,constraint_name,payload,created_at) VALUES (?,?,?,?,?)",
              (eid, "ERROR", body.get("source", "workflow"), dumps(body), now()))
    retry = False
    if eid:
        st = rows(c, "SELECT status FROM experiments WHERE id=?", eid)
        retry = bool(st) and st[0]["status"] == "FAILED"   # completed experiments are never re-run
    c.commit()
    return {"recorded": True, "retry_allowed": retry}


@app.post("/api/reports/technical")
def tech_report():
    return reports.technical_report()


@app.get("/api/reports")
def list_reports():
    return rows(_db(), "SELECT * FROM reports ORDER BY created_at DESC")


# ---------------- autonomous learning (physics model)
from . import learning


@app.get("/api/learning/registry")
def learning_registry():
    return {"models": learning.registry(), "active": learning.approved_id()}


@app.get("/api/learning/error_analysis")
def learning_errors(model_id: str | None = None):
    return _clean(learning.error_analysis(model_id))


@app.post("/api/learning/recalibrate")
def learning_recalibrate(structure: str = "params"):
    """Long-running (minutes): calibrates on TRAIN files, validates, tests once, registers APPROVED or REJECTED.
    structure = params | params+ocv_delta"""
    if structure not in ("params", "params+ocv_delta", "ocv_delta_only"):
        raise HTTPException(422, "structure must be params, params+ocv_delta or ocv_delta_only")
    r = learning.recalibrate(structure=structure)
    c = _db()
    c.execute("INSERT INTO model_calibrations (model_id,payload,created_at) VALUES (?,?,?)", (r["id"], dumps(r), now()))
    c.execute("INSERT INTO model_validation_results (model_id,status,payload,created_at) VALUES (?,?,?,?)",
              (r["id"], r["approval"].split(" ")[0], dumps(r), now())); c.commit()
    return _clean(r)


@app.post("/api/learning/rollback")
def learning_rollback():
    try:
        return learning.rollback()
    except RuntimeError as e:
        raise HTTPException(409, str(e))
