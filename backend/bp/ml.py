"""Machine learning on EXPERIMENTAL data only, with a versioned registry and an explicit acceptance rule.

Task A  SOC estimation (regression) from causal features of measured V and I (CALCE INR18650-20R, SP2).
        Split by FILE: train = DST 50/80, validation = FUDS 50/80 (model selection), test = US06 + BJDST 50/80 (once).
        Target = reference SOC by coulomb counting of the measured current from the full CC-CV charge
        (not an independent SOC measurement). Features use only past samples (no leakage from the future).
Task B  Anomaly screening of the 92 Panasonic NCR18650B cells (Isolation Forest on OCV and pulse features).
        Unsupervised: reports which cells stand out and why; no accuracy is claimed (there are no labels)."""
import json, time
from pathlib import Path
import numpy as np
import scipy.io as sio
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor, IsolationForest
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import joblib
from .data import ROOT, drive_cycle, scored
from .bms import coulomb_count

REG = ROOT / "DATA" / "MODELS" / "ml"
SPLIT = {"train": ["DST_50SOC", "DST_80SOC"], "val": ["FUDS_50SOC", "FUDS_80SOC"],
         "test": ["US06_50SOC", "US06_80SOC", "BJDST_50SOC", "BJDST_80SOC"]}
FEATURES = ["V", "I", "I_mean10", "I_mean60", "I_mean300", "V_mean60", "V_min300", "V_max300", "dV10"]


def _trailing(x, t, w):
    """Mean / min / max of x over the trailing window of w seconds (only past samples)."""
    c = np.concatenate([[0.0], np.cumsum(x)])
    j = np.searchsorted(t, t - w)
    mean = (c[1:] - c[j]) / (np.arange(1, len(x) + 1) - j)
    return mean, j


def features(t, V, I):
    m10, _ = _trailing(I, t, 10); m60, _ = _trailing(I, t, 60); m300, j300 = _trailing(I, t, 300)
    v60, _ = _trailing(V, t, 60)
    vmin = np.array([V[a:k + 1].min() for k, a in enumerate(j300)])
    vmax = np.array([V[a:k + 1].max() for k, a in enumerate(j300)])
    j10 = np.searchsorted(t, t - 10)
    return np.column_stack([V, I, m10, m60, m300, v60, vmin, vmax, V - V[j10]])


def dataset(names, every=5):
    X, y, g = [], [], []
    for n in names:
        d = drive_cycle(n); I = -d["I_chg"]
        z = coulomb_count(d["t"], I, 1.0, 2.06689334569)   # capacity of the approved v2 model
        F = features(d["t"], d["V"], I)
        k = np.where(scored(d))[0][::every]
        X.append(F[k]); y.append(z[k]); g += [n] * len(k)
    return np.vstack(X), np.concatenate(y), np.array(g)


def _rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def train_soc(threshold_rmse=0.05, seed=0):
    Xtr, ytr, _ = dataset(SPLIT["train"]); Xva, yva, _ = dataset(SPLIT["val"])
    cands = {"ridge (baseline)": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
             "random forest": RandomForestRegressor(n_estimators=200, min_samples_leaf=5, n_jobs=-1, random_state=seed),
             "gradient boosting": HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=seed)}
    res = {}
    for name, mdl in cands.items():
        mdl.fit(Xtr, ytr); res[name] = {"model": mdl, "val_rmse": _rmse(mdl.predict(Xva), yva)}
    best = min(res, key=lambda k: res[k]["val_rmse"])
    Xte, yte, gte = dataset(SPLIT["test"])
    p = res[best]["model"].predict(Xte)
    per_file = {n: {"RMSE": _rmse(p[gte == n], yte[gte == n]), "MaxAE": float(np.max(np.abs(p[gte == n] - yte[gte == n])))}
                for n in SPLIT["test"]}
    test_rmse = _rmse(p, yte)
    prev = latest("soc_regressor")
    better = prev is None or res[best]["val_rmse"] <= prev["val_rmse"] + 1e-4
    approval = "APPROVED" if (better and test_rmse <= threshold_rmse) else "REJECTED"
    version = 1 + max([r["version"] for r in [latest("soc_regressor", approved_only=False)] if r] or [0])
    rec = {"task": "soc_regressor", "version": version, "algorithm": best, "features": FEATURES,
           "candidates_val_rmse": {k: v["val_rmse"] for k, v in res.items()}, "val_rmse": res[best]["val_rmse"],
           "test_rmse": test_rmse, "test_per_file": per_file, "split": SPLIT, "split_unit": "file (drive-cycle test)",
           "data": "MEASURED: CALCE INR18650-20R SP2 25 C drive cycles", "target": "coulomb-counted reference SOC",
           "n_train": int(len(ytr)), "n_val": int(len(yva)), "n_test": int(len(yte)),
           "acceptance": f"val RMSE not worse than previous approved and test RMSE <= {threshold_rmse}",
           "approval": approval, "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"), "source_type": "experimental"}
    REG.mkdir(parents=True, exist_ok=True)
    stem = REG / f"soc_regressor_v{version}"
    if approval == "APPROVED":
        joblib.dump(res[best]["model"], stem.with_suffix(".joblib"))
    stem.with_suffix(".json").write_text(json.dumps(rec, indent=2))
    return rec


def latest(task, approved_only=True):
    recs = [json.loads(p.read_text()) for p in REG.glob(f"{task}_v*.json")] if REG.exists() else []
    recs = [r for r in recs if r["approval"] == "APPROVED" or not approved_only]
    return max(recs, key=lambda r: r["version"]) if recs else None


def predict_soc(t, V, I):
    rec = latest("soc_regressor")
    if rec is None:
        raise RuntimeError("no approved SOC regressor; train one first")
    mdl = joblib.load(REG / f"soc_regressor_v{rec['version']}.joblib")
    return mdl.predict(features(np.asarray(t, float), np.asarray(V, float), np.asarray(I, float))), rec


def panasonic_features(path=ROOT / "Panasonic_NCR18650B_Consolidated.mat"):
    M = sio.loadmat(path, squeeze_me=True)
    soc = M["POCV_SOC"]; i50 = int(np.argmin(abs(soc - 0.5)))
    rows = []
    for c in range(int(M["cell_count"])):
        r = {"cell": c + 1, "ocv50_chg": M["POCV_charge_V"][i50, c], "ocv50_dis": M["POCV_discharge_V"][i50, c]}
        r["hyst50_mV"] = 1000 * (r["ocv50_chg"] - r["ocv50_dis"])
        for s in ("positive", "negative"):
            t = M[f"Pulse_{s}_time_s"][:, c]; v = M[f"Pulse_{s}_voltage_V"][:, c]
            ok = v > 0; t, v = t[ok], v[ok]
            dv = np.diff(v); on = int(np.argmax(np.abs(dv[: np.searchsorted(t, 15)])))
            w = np.where((t[:-1] > t[on] + 2) & (t[:-1] < t[on] + 30))[0]; off = w[np.argmax(np.abs(dv[w]))]
            r[f"{s}_jump_on_mV"] = 1000 * dv[on]
            r[f"{s}_relax60_mV"] = 1000 * (v[np.searchsorted(t, t[off] + 60)] - v[off + 1])
            r[f"{s}_relax1800_mV"] = 1000 * (v[-1] - v[off + 1])
        rows.append(r)
    return rows


def panasonic_anomalies(contamination=0.05, seed=0):
    rows = panasonic_features()
    keys = [k for k in rows[0] if k != "cell"]
    X = np.array([[r[k] for k in keys] for r in rows])
    Z = (X - X.mean(0)) / X.std(0)
    iso = IsolationForest(contamination=contamination, random_state=seed).fit(Z)
    score = -iso.score_samples(Z); flag = iso.predict(Z) == -1
    out = []
    for i in np.argsort(-score):
        top = np.argsort(-np.abs(Z[i]))[:3]
        out.append({"cell": rows[i]["cell"], "anomaly_score": float(score[i]), "flagged": bool(flag[i]),
                    "most_unusual": {keys[j]: round(float(Z[i, j]), 2) for j in top}})
    rec = {"task": "panasonic_anomaly_screen", "algorithm": "IsolationForest", "contamination": contamination,
           "features": keys, "n_cells": len(rows), "n_flagged": int(flag.sum()), "ranking": out,
           "data": "MEASURED: Panasonic NCR18650B consolidated file (92 cells)",
           "note": "Unsupervised screen: flags statistical outliers, not confirmed faults. No accuracy claimed."}
    REG.mkdir(parents=True, exist_ok=True)
    (REG / "panasonic_anomaly_screen.json").write_text(json.dumps(rec, indent=2))
    return rec
