"""Autonomous learning loop for the physics model: analyse errors -> recalibrate on TRAIN files only -> evaluate on
VALIDATION files -> accept only if strictly better and physically plausible -> score TEST files once -> register.
Approved models are never replaced silently; every candidate (approved or rejected) is kept in DATA/MODELS.
Same split and scoring as the MATLAB validation (train DST, select FUDS, test US06 + BJDST; drive-cycle steps, V > 3 V)."""
import json, time
import numpy as np
from scipy.optimize import least_squares
from .data import drive_cycle, scored
from .model import MODELS, load_model, simulate, metrics, ocv_table, pocv, approved_model_id, _load
from .data import calce
from .ml import SPLIT

BOUNDS = {"R0_ohm": (0.005, 0.2), "Q_Ah": (1.8, 2.4), "R1_ohm": (0.001, 0.2), "tau1_s": (1, 50), "R2_ohm": (0.001, 0.2),
          "tau2_s": (50, 5000), "M_V": (0, 0.1), "gamma": (1, 2000)}
KEYS = list(BOUNDS)


def registry():
    return sorted((json.loads(p.read_text()) for p in MODELS.glob("LIION_*.json")), key=lambda r: r.get("version", 0))


def approved_id():
    return approved_model_id()


KNOTS = [0.0, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9, 1.0]


def _model_from(p, O):
    m = dict(load_model(approved_id()))
    delta = np.interp(O["soc"], KNOTS, p[8:]) if len(p) > 8 else 0.0
    m.update(R0=p[0], Q=p[1], R1=p[2], tau1=p[3], R2=p[4], tau2=p[5], M=p[6], gam=p[7], ocv=ocv_table(O, p[6]) + delta)
    return m


def _rmse_files(m, names):
    out = {}
    for n in names:
        d = drive_cycle(n); y = simulate(m, d["t"], -d["I_chg"]); k = scored(d)
        out[n] = metrics(1000 * d["V"][k], 1000 * y["V"][k])
    return out


def error_analysis(model_id=None, names=None):
    """Where does the model fail? Errors by SOC band, current magnitude, direction; systematic vs random."""
    m = load_model(model_id or approved_id()); names = names or SPLIT["val"]
    E, Z, I = [], [], []
    for n in names:
        d = drive_cycle(n); y = simulate(m, d["t"], -d["I_chg"]); k = scored(d)
        E.append(1000 * (y["V"][k] - d["V"][k])); Z.append(y["z"][k]); I.append(-d["I_chg"][k])
    e, z, i = (np.concatenate(x) for x in (E, Z, I))
    band = lambda msk: {"n": int(msk.sum()), "RMSE_mV": float(np.sqrt(np.mean(e[msk] ** 2))) if msk.any() else None,
                        "bias_mV": float(np.mean(e[msk])) if msk.any() else None}
    res = {"files": names, "overall": band(np.ones_like(e, bool)),
           "soc_bands": {f"{a:.1f}-{b:.1f}": band((z >= a) & (z < b)) for a, b in ((0, .1), (.1, .2), (.2, .5), (.5, .8), (.8, 1.01))},
           "current": {"|I|<1A": band(np.abs(i) < 1), "1-2.5A": band((np.abs(i) >= 1) & (np.abs(i) < 2.5)), "|I|>=2.5A": band(np.abs(i) >= 2.5)},
           "direction": {"discharge": band(i > 0.05), "charge (regen)": band(i < -0.05), "rest": band(np.abs(i) <= 0.05)}}
    ov = res["overall"]
    res["systematic"] = abs(ov["bias_mV"]) > 0.3 * ov["RMSE_mV"]
    weak = [(k, v) for k, v in res["soc_bands"].items() if v["RMSE_mV"] and v["RMSE_mV"] > 1.5 * ov["RMSE_mV"]]
    weak += [(k, v) for k, v in res["current"].items() if v["RMSE_mV"] and v["RMSE_mV"] > 1.5 * ov["RMSE_mV"]]
    res["weak_regions"] = [{"region": k, **v} for k, v in weak]
    rec = []
    for k, _ in weak:
        if k.startswith("0.0"):
            rec.append("low-SOC (0-10 %) pulse and relaxation tests; an OCV table measured on the same cell")
        elif "A" in k:
            rec.append(f"more data at {k}: pulse tests at that current to identify current-dependent resistance")
        else:
            rec.append(f"more measurements in SOC band {k}")
    rec += ["drive cycles at 0 C and 45 C (CALCE files available, not yet used) to cover temperature",
            "tests with a logged cell temperature, so the PROVISIONAL thermal model can be calibrated"]
    res["recommended_experiments"] = rec
    return res


def recalibrate(min_improvement_mV=0.01, test_limit_mV=25.0, structure="params"):
    """Fit a candidate on TRAIN files, compare with the approved model on VALIDATION files, then score TEST once.
    structure: "params" (8 ECM parameters) or "params+ocv_delta" (plus a bounded +/-50 mV piecewise-linear OCV
    correction at KNOTS, addressing the cell-to-cell OCV mismatch found by error_analysis)."""
    base = load_model(approved_id())
    O = pocv(calce("*SP20-1.xlsx"), 3, 5, rest_step=2)
    train = [drive_cycle(n) for n in SPLIT["train"]]
    lo = [BOUNDS[k][0] for k in KEYS]; hi = [BOUNDS[k][1] for k in KEYS]
    x0 = list(np.clip([base["R0"], base["Q"], base["R1"], base["tau1"], base["R2"], base["tau2"], base["M"], base["gam"]],
                      np.array(lo) + 1e-9, np.array(hi) - 1e-9))
    if structure == "params+ocv_delta":
        lo += [-0.05] * len(KNOTS); hi += [0.05] * len(KNOTS); x0 += [0.0] * len(KNOTS)
    fixed = None
    if structure == "ocv_delta_only":
        # dynamics stay at the approved values; the correction is bounded by the measured cell-to-cell OCV spread
        # (SP3 vs SP1 pseudo-OCV max 25.7 mV in the region both measured) -> +/-30 mV
        # only knots the training data actually covers are free (>= 500 scored samples within +/-0.05 SOC)
        zs = np.concatenate([simulate(base, d["t"], -d["I_chg"])["z"][scored(d)] for d in train])
        free = np.array([np.sum(np.abs(zs - k) <= 0.05) >= 500 for k in KNOTS])
        fixed = np.array(x0)
        lo = [-0.03 if f else -1e-9 for f in free]; hi = [0.03 if f else 1e-9 for f in free]; x0 = [0.0] * len(KNOTS)

    full = (lambda p: np.concatenate([fixed, p])) if fixed is not None else (lambda p: p)

    def resid(p):
        m = _model_from(full(p), O)
        return np.concatenate([(simulate(m, d["t"], -d["I_chg"])["V"] - d["V"])[scored(d)] for d in train])
    fit = least_squares(resid, x0, bounds=(lo, hi), x_scale="jac", max_nfev=200)
    names = (KEYS if fixed is None else []) + ([f"dOCV@{z}" for z in KNOTS] if structure != "params" else [])
    at_bound = [k for k, x, a, b in zip(names, fit.x, lo, hi) if b - a > 1e-6 and min(x - a, b - x) < 1e-3 * (b - a)]
    fit.x = full(fit.x)
    cand = _model_from(fit.x, O)
    v_new = _rmse_files(cand, SPLIT["val"]); v_old = _rmse_files(base, SPLIT["val"])
    mean = lambda r: float(np.mean([x["RMSE"] for x in r.values()]))
    plausible = not at_bound and cand["R0"] > 0 and cand["tau1"] < cand["tau2"]
    improved = mean(v_new) < mean(v_old) - min_improvement_mV
    test = _rmse_files(cand, SPLIT["test"]) if improved and plausible else None
    passes_test = test is not None and max(x["RMSE"] for x in test.values()) <= test_limit_mV
    approval = "APPROVED" if improved and plausible and passes_test else "REJECTED"
    reason = ("candidate better on validation, plausible, within test limit" if approval == "APPROVED" else
              "not better on validation data" if not improved else
              f"physically implausible (at bound: {at_bound})" if not plausible else "test error above limit")
    version = 1 + max([r.get("version", 0) for r in registry()] or [2])
    rec = {**json.loads((MODELS / f"{base['id']}.json").read_text()),
           "id": f"LIION_INR18650-20R_ECM_2RC_H_v{version}", "version": version,
           "params": dict(zip(KEYS, map(float, fit.x[:8]))), "parent": base["id"], "structure": structure,
           "ocv_delta": {"knots": KNOTS, "values_V": [float(v) for v in fit.x[8:]],
                         "note": "fitted on TRAIN files only (SP2 DST); corrects SP1-vs-SP2 OCV mismatch; knots without training coverage held at 0"} if len(fit.x) > 8 else None,
           "approval": f"{approval} - {reason}; val RMSE {mean(v_new):.3f} mV vs approved {mean(v_old):.3f} mV",
           "status": "VALIDATED" if approval == "APPROVED" else "NOT APPROVED",
           "calibration": "python least_squares on SP2 DST 50/80 % (train only)", "source_run": "python recalibration",
           "simulink_equivalence": "pending: export ocv table to MATLAB and rerun RUN_SIMULINK_EQUIVALENCE",
           "validation_rmse_mV": {k: v["RMSE"] for k, v in v_new.items()},
           "test_rmse_mV": {k: v["RMSE"] for k, v in test.items()} if test else None,
           "created_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    rec.pop("matlab_test_metrics_mV", None)
    (MODELS / f"{rec['id']}.json").write_text(json.dumps(rec, indent=2))
    _load.cache_clear()
    return rec


def rollback():
    """Withdraw the newest approved model; the previous approved version becomes active again."""
    ok = [r for r in registry() if r["approval"].startswith("APPROVED")]
    if len(ok) < 2:
        raise RuntimeError("nothing to roll back to")
    newest = max(ok, key=lambda r: r.get("version", 0))
    newest["approval"] = "ROLLED BACK - " + newest["approval"]
    (MODELS / f"{newest['id']}.json").write_text(json.dumps(newest, indent=2))
    _load.cache_clear()
    return {"rolled_back": newest["id"], "active": approved_id()}
