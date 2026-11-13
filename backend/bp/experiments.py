"""Battery profiles, experiment execution, characterization and persistence. Every run gets an experiment ID and is
labelled SIMULATED with the model ID that produced it. I > 0 = discharge (cell-level inside the engine)."""
import uuid
import numpy as np
from . import generators as gen
from .model import load_model, nicd_provisional, with_changes, simulate
from .constraints import LIMITS, monitor, run_moderated
from .charging import adaptive, cccv, nicd_charge
from .db import connect, dumps, now, rows

CHEM = {
    "li-ion-nmc": {"model": None, "status": "VALIDATED (CALCE drive cycles, 25 C)",
                   "charging": "CC-CV", "limits": "li-ion-nmc"},
    "li-ion-lfp": {"model": None, "status": "NOT SUPPORTED: no reliable LFP data or verified parameters", "limits": None},
    "li-ion-nca": {"model": None, "status": "NOT SUPPORTED: Panasonic NCR18650B data lacks current/temperature; "
                   "no calibrated NCA model", "limits": None},
    "ni-cd": {"model": "NICD_GENERIC_PROVISIONAL", "status": "PROVISIONAL - NOT VALIDATED (no real Ni-Cd data)",
              "charging": "CC with -dV/dT-dt/charge-input/timer termination", "limits": "ni-cd"},
}

DEFAULT_PROFILES = [
    {"id": "INR18650-20R", "name": "CALCE INR18650-20R (1S1P)", "chemistry": "li-ion-nmc", "manufacturer": "UNVERIFIED",
     "model": "INR18650-20R", "n_series": 1, "n_parallel": 1, "V_nom": 3.6, "V_min": 2.5, "V_max": 4.2,
     "capacity_Ah": 2.0, "reference_capacity_Ah": 2.06689334569, "I_chg_max": 2.2, "I_dis_max": 4.0,
     "T_max": 45.0, "initial_soc": 0.8, "T_init": 25.0, "T_amb": 25.0, "health": {"capacity_factor": 1.0, "r0_factor": 1.0},
     "provenance": {"capacity_Ah": "CALCE data page (manufacturer rating as published)",
                    "reference_capacity_Ah": "ESTIMATED by fitting (model v2)", "V_min/V_max": "CALCE test procedure",
                    "I_chg_max/I_dis_max": "validated data envelope, datasheet UNVERIFIED", "V_nom": "UNVERIFIED (typical)"}},
    {"id": "NICD-GENERIC-1S", "name": "Generic Ni-Cd cell (PROVISIONAL)", "chemistry": "ni-cd", "manufacturer": "UNKNOWN",
     "model": "UNKNOWN", "n_series": 1, "n_parallel": 1, "V_nom": 1.2, "V_min": 1.0, "V_max": 1.55, "capacity_Ah": 1.0,
     "reference_capacity_Ah": 1.0, "I_chg_max": 1.0, "I_dis_max": 2.0, "T_max": 45.0, "initial_soc": 0.0,
     "T_init": 25.0, "T_amb": 25.0, "health": {"capacity_factor": 1.0, "r0_factor": 1.0},
     "provenance": {"all": "USER-CONFIGURED PLACEHOLDER: no Ni-Cd datasheet or measurements available"}},
]


def validate_profile(p):
    err = []
    if p.get("chemistry") not in CHEM:
        err.append(f"unknown chemistry {p.get('chemistry')!r}")
    elif CHEM[p["chemistry"]]["status"].startswith("NOT SUPPORTED"):
        err.append(CHEM[p["chemistry"]]["status"])
    for k in ("n_series", "n_parallel"):
        if not isinstance(p.get(k), int) or p[k] < 1:
            err.append(f"{k} must be an integer >= 1")
    if not (0 < p.get("V_min", 0) < p.get("V_nom", 0) < p.get("V_max", 0)):
        err.append("need 0 < V_min < V_nom < V_max (per cell)")
    for k in ("capacity_Ah", "I_chg_max", "I_dis_max"):
        if not p.get(k, 0) > 0:
            err.append(f"{k} must be > 0")
    if not 0 <= p.get("initial_soc", -1) <= 1:
        err.append("initial_soc must be in [0, 1]")
    lim = LIMITS.get(CHEM.get(p.get("chemistry"), {}).get("limits") or "", {})
    if lim and (p.get("V_max", 0) > lim["V_crit_hi"] or p.get("V_min", 9) < lim["V_crit_lo"]):
        err.append(f"voltage limits must stay inside the chemistry's critical limits {lim['V_crit_lo']}-{lim['V_crit_hi']} V")
    return err


def cell_model(p):
    """Model for one cell of the profile. Rating/health changes are user scenarios layered on the validated model."""
    h = p.get("health", {})
    if p["chemistry"] == "ni-cd":
        m = nicd_provisional(p["capacity_Ah"])
    else:
        m = load_model()   # newest APPROVED Li-ion model
        m = with_changes(m, Q=p.get("reference_capacity_Ah", m["Q"]))
    m = with_changes(m, Q=m["Q"] * h.get("capacity_factor", 1.0), R0=m["R0"] * h.get("r0_factor", 1.0))
    if "rth_factor" in h:
        m = with_changes(m, thermal={**m["thermal"], "Rth": m["thermal"]["Rth"] * h["rth_factor"]})
    return m


def limits_for(p):
    L = dict(LIMITS[CHEM[p["chemistry"]]["limits"]])
    L["V_crit_hi"], L["V_crit_lo"] = min(L["V_crit_hi"], p["V_max"]), max(L["V_crit_lo"], p["V_min"])
    L["V_warn_hi"], L["V_warn_lo"] = min(L["V_warn_hi"], L["V_crit_hi"]), max(L["V_warn_lo"], L["V_crit_lo"])
    L["T_crit"] = min(L["T_crit"], p.get("T_max", L["T_crit"]) + 15); L["T_warn"] = min(L["T_warn"], p.get("T_max", 45))
    return L


# ---------------------------------------------------------------- characterization

def characterize(t, V, I, T, z, Q_ref_Ah=None, ripple=None):
    """Electrical, thermal, capacity and dynamic features (cell level). Windows: the whole run unless stated."""
    t = np.asarray(t, float); dt = np.diff(t, append=t[-1])
    P = V * I
    dVdt = np.gradient(V, t); dIdt = np.gradient(I, t); dTdt = np.gradient(T, t) * 60
    f = {"V_avg": float(V.mean()), "V_max": float(V.max()), "V_min": float(V.min()),
         "I_avg": float(I.mean()), "I_max": float(np.abs(I).max()), "I_rms": float(np.sqrt(np.mean(I ** 2))),
         "P_avg_W": float(P.mean()), "energy_out_Wh": float(np.sum(np.clip(P, 0, None) * dt) / 3600),
         "energy_in_Wh": float(np.sum(np.clip(-P, 0, None) * dt) / 3600),
         "dVdt_max_V_per_s": float(np.abs(dVdt).max()), "dIdt_max_A_per_s": float(np.abs(dIdt).max()),
         "T_avg": float(T.mean()), "T_max": float(T.max()), "T_rise": float(T.max() - T[0]),
         "dTdt_max_C_per_min": float(dTdt.max()),
         "Q_dis_Ah": float(np.sum(np.clip(I, 0, None) * dt) / 3600), "Q_chg_Ah": float(np.sum(np.clip(-I, 0, None) * dt) / 3600),
         "duration_s": float(t[-1] - t[0]), "soc_start": float(z[0]), "soc_end": float(z[-1])}
    steps = np.where(np.abs(np.diff(I)) > 0.05)[0]
    if steps.size:
        k = steps[np.argmax(np.abs(np.diff(I))[steps])]
        f["R_app_ohm"] = float(abs((V[k + 1] - V[k]) / (I[k + 1] - I[k])))
        f["R_app_note"] = "apparent resistance |dV/dI| over one sample at the largest current step (not pure ohmic)"
        f["voltage_sag_V"] = float(V[k] - V[k + 1]) if I[k + 1] > I[k] else float(V[k + 1] - V[k])
        rec = V[k + 1:]
        if rec.size > 2:
            j = np.argmax(np.abs(rec - rec[-1]) < 0.001) if np.any(np.abs(rec - rec[-1]) < 0.001) else len(rec) - 1
            f["voltage_recovery_time_s"] = float(t[k + 1 + j] - t[k + 1])
    if ripple:
        w = (t >= ripple.get("start_s", 0)) & (t < ripple.get("stop_s", np.inf))
        if w.any():
            f["I_ripple_rms_A"] = float(np.sqrt(np.mean((I[w] - I[w].mean()) ** 2)))
            f["V_ripple_rms_V"] = float(np.sqrt(np.mean((V[w] - V[w].mean()) ** 2)))
            f["ripple_sensitivity_ohm"] = f["V_ripple_rms_V"] / max(f["I_ripple_rms_A"], 1e-12)
    if Q_ref_Ah and f["soc_end"] <= 0.02 and f["soc_start"] >= 0.98:
        f["SOH_capacity_pct"] = 100 * f["Q_dis_Ah"] / Q_ref_Ah
    return f


# ---------------------------------------------------------------- execution

def sample_step(cfg):
    """Simulation step: the requested dt (default 1 s), reduced to <= 1/(20 f) when ripple is enabled so the ripple is
    resolved (at dt = 1 s a 0.5 Hz sine would be sampled only at its zero crossings)."""
    dt = cfg.get("dt_s", 1.0)
    r = cfg.get("load", {}).get("ripple")
    if r and r.get("enabled", True) and r.get("freq_Hz", 0) > 0:
        dt = min(dt, 1.0 / (20.0 * r["freq_Hz"]))
    return dt


def _profile_current(cfg, p):
    """Cell-level current profile from the experiment config (pack currents are divided by n_parallel)."""
    load = cfg.get("load", {})
    base = {**load, "pulse": ({**load["pulse"], "pulse_A": load["pulse"]["base_A"]} if load.get("pulse") else None)}
    offset = 0.0
    if cfg.get("charging", {}).get("enabled") and cfg["charging"].get("mode") == "constant":
        offset -= cfg["charging"]["current_A"]
    if cfg.get("discharging", {}).get("enabled"):
        offset += cfg["discharging"]["current_A"]
    grid = {"duration_s": cfg["duration_s"], "dt_s": sample_step(cfg)}
    t, I = gen.build({**load, **grid})
    keep = gen.build({**base, **grid})[1]   # everything except the pulse excess: kept by the moderator if safe
    return t, (I + offset) / p["n_parallel"], (keep + offset) / p["n_parallel"]


def run_experiment(cfg, profile, c=None, idempotency_key=None, campaign_id=None):
    """cfg: duration_s, mode (manual|auto|adaptive), load {...generators...}, charging {...}, discharging {...},
    initial_soc, T_amb, compare_healthy (bool). Returns the stored experiment summary."""
    c = c or connect()
    if idempotency_key:
        ex = rows(c, "SELECT id FROM experiments WHERE idempotency_key=?", idempotency_key)
        if ex:
            return get_experiment(ex[0]["id"], c) | {"idempotent_replay": True}
    errs = validate_profile(profile)
    if errs:
        raise ValueError("; ".join(errs))
    eid = "EXP_" + now().replace("-", "").replace(":", "").replace("T", "_") + "_" + uuid.uuid4().hex[:6]
    m = cell_model(profile); L = limits_for(profile)
    z0 = cfg.get("initial_soc", profile["initial_soc"]); Tamb = cfg.get("T_amb", profile["T_amb"])
    T0 = cfg.get("T_init", profile["T_init"]); h0 = cfg.get("h0", -1.0)
    mode = cfg.get("mode", "manual"); label = "SIMULATED (" + m["id"] + ")"
    c.execute("INSERT INTO experiments VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              (eid, campaign_id, profile["id"], profile.get("version", 1), profile["chemistry"], cfg.get("type", "custom"),
               mode, "RUNNING", label, now(), None, idempotency_key))
    c.execute("INSERT INTO experiment_configurations VALUES (?,?)", (eid, dumps({"cfg": cfg, "profile": profile})))
    out = {"id": eid, "label": label, "mode": mode, "model_id": m["id"], "chemistry_status": CHEM[profile["chemistry"]]["status"],
           "dt_s": sample_step(cfg),
           "notes": ["Configuration applies to this run; mid-run changes go through a live session at step boundaries."]}
    try:
        if mode == "adaptive":
            ch = cfg["adaptive"]
            r = adaptive(m, z0, ch["target_soc"], ch.get("target_time_s"), L, L["V_crit_hi"],
                         profile["I_chg_max"] / profile["n_parallel"], T0=T0, Tamb=Tamb, h0=h0)
            s = r.pop("series"); t = np.array(s["t"]); I = np.array(s["I"]); I_req = I.copy()
            y = simulate(m, t, I, z0=z0, h0=h0, T0=T0, Tamb=Tamb); log = []
            c.execute("INSERT INTO charging_optimizations (experiment_id,payload,created_at) VALUES (?,?,?)", (eid, dumps(r), now()))
            out["charging"] = r
        elif profile["chemistry"] == "ni-cd" and cfg.get("charging", {}).get("strategy") == "nicd":
            r = nicd_charge(m, z0, cfg["charging"]["current_A"] / profile["n_parallel"], profile["capacity_Ah"], T0=T0, Tamb=Tamb)
            s = r.pop("series"); t = np.array(s["t"]); I = np.array(s["I"]); I_req = I.copy()
            y = simulate(m, t, I, z0=z0, h0=0.0, T0=T0, Tamb=Tamb); log = []; out["charging"] = r
        elif cfg.get("charging", {}).get("enabled") and cfg["charging"].get("mode") == "cccv":
            ch = cfg["charging"]
            r = cccv(m, z0, ch.get("target_soc", 1.0), ch["current_A"] / profile["n_parallel"],
                     min(ch.get("V_max", L["V_crit_hi"]), L["V_crit_hi"]), T0=T0, Tamb=Tamb, h0=h0,
                     t_max_s=cfg["duration_s"])
            s = r.pop("series"); t = np.array(s["t"]); I = np.array(s["I"]); I_req = I.copy()
            y = simulate(m, t, I, z0=z0, h0=h0, T0=T0, Tamb=Tamb); log = []; out["charging"] = r
        else:
            t, I_req, keep = _profile_current(cfg, profile)
            if mode == "auto":
                y, I, log = run_moderated(m, t, I_req, L, z0=z0, h0=h0, T0=T0, Tamb=Tamb, I_keep=keep,
                                          horizon_s=cfg.get("horizon_s", 30.0), step_s=cfg.get("ctrl_step_s", 10.0))
            else:
                I = I_req; y = simulate(m, t, I, z0=z0, h0=h0, T0=T0, Tamb=Tamb); log = []
        rows_c, overall = monitor(t, y["V"], y["I"], y["T"], y["z"], L)
        feats = characterize(t, y["V"], y["I"], y["T"], y["z"], m["Q"], cfg.get("load", {}).get("ripple"))
        _store_run(c, eid, "main", t, I_req, y, label)
        c.execute("INSERT INTO extracted_features VALUES (?,?,?,?)", (eid, "main", dumps(feats), now()))
        for r in rows_c:
            if r["severity"] not in ("NORMAL", "NOT MONITORED"):
                c.execute("INSERT INTO constraint_events (experiment_id,run,constraint_name,severity,payload,created_at) "
                          "VALUES (?,?,?,?,?,?)", (eid, "main", r["constraint"], r["severity"], dumps(r), now()))
        for e in log:
            c.execute("INSERT INTO moderation_events (experiment_id,t,requested_A,permitted_A,reason,payload,created_at) "
                      "VALUES (?,?,?,?,?,?,?)", (eid, e["t_s"], e["requested_A"], e["permitted_A"], e["reason"], dumps(e), now()))
        out |= {"constraints": rows_c, "overall_severity": overall, "features": feats, "moderation_events": len(log),
                "pack": {"V_max": feats["V_max"] * profile["n_series"], "V_min": feats["V_min"] * profile["n_series"],
                         "I_max": feats["I_max"] * profile["n_parallel"]}}
        if cfg.get("compare_healthy") and profile.get("health", {}) not in ({}, {"capacity_factor": 1.0, "r0_factor": 1.0}):
            hp = {**profile, "health": {"capacity_factor": 1.0, "r0_factor": 1.0}}
            hm = cell_model(hp); yh = simulate(hm, t, I, z0=z0, h0=h0, T0=T0, Tamb=Tamb)
            fh = characterize(t, yh["V"], yh["I"], yh["T"], yh["z"], hm["Q"], cfg.get("load", {}).get("ripple"))
            _store_run(c, eid, "healthy_reference", t, I, yh, "SIMULATED healthy reference (same current profile)")
            out["healthy_comparison"] = {"healthy": fh, "degraded": feats,
                                         "delta": {k: feats[k] - fh[k] for k in fh if isinstance(fh[k], float) and k in feats}}
        c.execute("INSERT INTO simulation_runs (experiment_id,engine,model_id,label,payload,created_at) VALUES (?,?,?,?,?,?)",
                  (eid, "python port of MATLAB bp_ecm_sim (equivalence-tested)", m["id"], label, dumps({"overall": overall}), now()))
        c.execute("UPDATE experiments SET status='COMPLETED', finished_at=? WHERE id=?", (now(), eid))
    except Exception as e:
        c.execute("UPDATE experiments SET status='FAILED', finished_at=? WHERE id=?", (now(), eid))
        c.execute("INSERT INTO diagnostic_events (experiment_id,severity,constraint_name,payload,created_at) VALUES (?,?,?,?,?)",
                  (eid, "ERROR", "execution", dumps({"error": str(e)}), now()))
        c.commit(); raise
    c.commit()
    return out


def _store_run(c, eid, run, t, I_req, y, label, max_points=3000):
    k = np.unique(np.linspace(0, len(t) - 1, min(len(t), max_points)).astype(int))
    c.executemany("INSERT INTO time_series_data VALUES (?,?,?,?,?,?,?,?,?,?)",
                  [(eid, run, float(t[i]), float(I_req[i]), float(y["I"][i]), float(y["V"][i]), float(y["z"][i]),
                    float(y["T"][i]), float(y["h"][i]), label) for i in k])


def get_experiment(eid, c=None):
    c = c or connect()
    e = rows(c, "SELECT * FROM experiments WHERE id=?", eid)
    if not e:
        raise KeyError(eid)
    out = e[0]
    out["config"] = rows(c, "SELECT payload FROM experiment_configurations WHERE experiment_id=?", eid)[0]["payload"]
    out["features"] = {r["run"]: r["payload"] for r in rows(c, "SELECT run,payload FROM extracted_features WHERE experiment_id=?", eid)}
    out["constraint_events"] = rows(c, "SELECT constraint_name,severity,payload FROM constraint_events WHERE experiment_id=?", eid)
    out["moderation_events"] = rows(c, "SELECT t,requested_A,permitted_A,reason FROM moderation_events WHERE experiment_id=? ORDER BY t", eid)
    out["charging"] = [r["payload"] for r in rows(c, "SELECT payload FROM charging_optimizations WHERE experiment_id=?", eid)]
    return out


def timeseries(eid, run="main", c=None):
    c = c or connect()
    r = rows(c, "SELECT t_s,I_req,I,V,z,temp_C,h,source_type FROM time_series_data WHERE experiment_id=? AND run=? ORDER BY t_s", eid, run)
    if not r:
        return {}
    col = {"t": "t_s", "I_req": "I_req", "I": "I", "V": "V", "z": "z", "T": "temp_C", "h": "h"}   # SQLite names are case-insensitive
    a = {k: np.array([x[v] for x in r]) for k, v in col.items()}
    a["dVdt"] = np.gradient(a["V"], a["t"]) if len(a["t"]) > 1 else np.zeros(1)
    a["dIdt"] = np.gradient(a["I"], a["t"]) if len(a["t"]) > 1 else np.zeros(1)
    a["dTdt"] = 60 * np.gradient(a["T"], a["t"]) if len(a["t"]) > 1 else np.zeros(1)
    return {k: v.tolist() for k, v in a.items()} | {"label": r[0]["source_type"]}
