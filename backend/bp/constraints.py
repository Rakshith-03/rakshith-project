"""Chemistry-specific limits, offline constraint monitor, and the predictive moderator (requested vs permitted current).

The moderator runs in the backend (never in n8n). Every intervention is logged with reason, prediction and time."""
import numpy as np
from .model import simulate

LIMITS = {
    "li-ion-nmc": {
        "V_warn_hi": 4.18, "V_crit_hi": 4.20, "V_warn_lo": 2.80, "V_crit_lo": 2.50,
        "I_dis_warn": 4.0, "I_dis_crit": np.inf, "I_chg_warn": 2.2, "I_chg_crit": np.inf,
        "T_warn": 45.0, "T_crit": 60.0, "dTdt_warn": 10.0, "dTdt_crit": 60.0,
        "soc_warn_lo": 0.10, "soc_crit_lo": 0.0, "soc_warn_hi": 0.95, "soc_crit_hi": 1.0,
        "source": {
            "V": "4.20 / 2.50 V: CALCE test-procedure cutoffs; warning margins ASSUMED",
            "I": "4 A discharge / 2.2 A charge: validated data envelope (WARNING = model extrapolating); datasheet maxima UNVERIFIED",
            "T": "ASSUMED generic Li-ion limits, UNVERIFIED for this cell; thermal model PROVISIONAL",
            "dTdt": "degC/min, ASSUMED", "soc": "10 %: model accuracy degrades below 10 % SOC (validation run)"}},
    "ni-cd": {
        "V_warn_hi": 1.50, "V_crit_hi": 1.55, "V_warn_lo": 1.00, "V_crit_lo": 0.90,
        "I_dis_warn": np.inf, "I_dis_crit": np.inf, "I_chg_warn": np.inf, "I_chg_crit": np.inf,
        "T_warn": 45.0, "T_crit": 55.0, "dTdt_warn": 1.0, "dTdt_crit": 2.0,
        "soc_warn_lo": 0.05, "soc_crit_lo": 0.0, "soc_warn_hi": 1.2, "soc_crit_hi": 1.6,
        "source": {"all": "PROVISIONAL generic Ni-Cd per-cell values, UNVERIFIED (no real Ni-Cd data or datasheet)"}},
}


def monitor(t, V, I, T, z, L):
    """Offline check. Returns (rows, overall). dV/dt and dI/dt are reported elsewhere, not used as damage limits."""
    t = np.asarray(t, float)
    dTdt = 60 * np.gradient(np.asarray(T, float), t) if len(t) > 1 else np.zeros_like(t)
    checks = [("overvoltage", V, "V_warn_hi", "V_crit_hi", 1), ("undervoltage", V, "V_warn_lo", "V_crit_lo", -1),
              ("discharge current", I, "I_dis_warn", "I_dis_crit", 1),
              ("charge current", -np.asarray(I), "I_chg_warn", "I_chg_crit", 1),
              ("overtemperature", T, "T_warn", "T_crit", 1), ("temperature rate", dTdt, "dTdt_warn", "dTdt_crit", 1),
              ("low SOC", z, "soc_warn_lo", "soc_crit_lo", -1), ("high SOC", z, "soc_warn_hi", "soc_crit_hi", 1)]
    rows, lev = [], ["NORMAL", "WARNING", "CRITICAL"]
    for name, x, kw, kc, s in checks:
        x = np.asarray(x, float)
        if np.all(np.isnan(x)):
            rows.append({"constraint": name, "severity": "NOT MONITORED"}); continue
        bw, bc = s * x > s * L[kw], s * x > s * L[kc]
        rows.append({"constraint": name, "severity": lev[int(bw.any()) + int(bc.any())],
                     "n_warning": int(bw.sum()), "n_critical": int(bc.sum()),
                     "first_warning_s": float(t[bw.argmax()]) if bw.any() else None,
                     "first_critical_s": float(t[bc.argmax()]) if bc.any() else None,
                     "worst": float(np.nanmax(x) if s > 0 else np.nanmin(x)),
                     "warn_limit": L[kw], "crit_limit": L[kc]})
    sev = [r["severity"] for r in rows]
    overall = next((l for l in reversed(lev) if l in sev), "NORMAL")
    return rows, overall


def _violates(y, L, margin):
    """First predicted violation of a hard (CRITICAL) limit with a safety margin, or None."""
    tests = [("overvoltage", y["V"] > L["V_crit_hi"] - margin["V"]), ("undervoltage", y["V"] < L["V_crit_lo"] + margin["V"]),
             ("overtemperature", y["T"] > L["T_crit"] - margin["T"]), ("SOC below 0", y["z"] < L["soc_crit_lo"]),
             ("SOC above 1", y["z"] > L["soc_crit_hi"])]
    for name, b in tests:
        if np.any(b):
            k = int(np.argmax(b))
            return {"constraint": name, "t_s": float(y["t"][k] - y["t"][0]), "V": float(y["V"][k]), "T": float(y["T"][k])}
    return None


def moderate(m, state, t, I_req, L, margin=None, Tamb=25.0, tol=1e-3, I_keep=None):
    """Predict the response to the requested current over the horizon t (from `state`). If a CRITICAL limit would be
    crossed, reduce the command by bisection to the largest safe s in [0, 1]:
        I_perm = I_keep + s (I_req - I_keep)
    I_keep (e.g. the base current of a pulse train) is kept if it is itself safe; otherwise the whole command is scaled.
    Returns dict with requested/permitted profiles, scale, prediction, severity and reason."""
    margin = margin or {"V": 0.0, "T": 0.0}
    sim = lambda I: simulate(m, t, I, z0=state["z"], h0=state["h"], v0=state["v"], T0=state["T"], Tamb=Tamb)
    y = sim(I_req)
    v = _violates(y, L, margin)
    out = {"requested_peak_A": float(np.max(np.abs(I_req))), "predicted_V_min": float(y["V"].min()),
           "predicted_V_max": float(y["V"].max()), "predicted_T_max": float(y["T"].max())}
    if v is None:
        return out | {"scale": 1.0, "I_perm": I_req, "permitted_peak_A": out["requested_peak_A"], "severity": "NORMAL",
                      "action": "none", "reason": "no limit predicted to be crossed over the horizon"}
    keep = np.zeros_like(I_req) if I_keep is None else np.asarray(I_keep, float)
    mode = "pulse reduced, base kept"
    if _violates(sim(keep), L, margin) is not None:
        keep = np.zeros_like(I_req); mode = "whole command scaled"
    cmd = lambda s: keep + s * (I_req - keep)
    lo, hi = 0.0, 1.0
    if _violates(sim(cmd(0.0)), L, margin) is not None:
        lo = hi = 0.0   # even zero current violates (e.g. already beyond a limit): stop
    while hi - lo > tol:
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if _violates(sim(cmd(mid)), L, margin) is None else (lo, mid)
    Ip = cmd(lo); yp = sim(Ip)
    return out | {"scale": lo, "I_perm": Ip, "permitted_peak_A": float(np.max(np.abs(Ip))), "mode": mode,
                  "severity": "CRITICAL", "action": "reduced" if np.any(Ip != 0) else "stopped",
                  "reason": f"predicted {v['constraint']} at +{v['t_s']:.0f} s (V {v['V']:.3f} V, T {v['T']:.1f} degC)",
                  "permitted_V_min": float(yp["V"].min()), "permitted_V_max": float(yp["V"].max()),
                  "permitted_T_max": float(yp["T"].max())}


def run_moderated(m, t, I_req, L, horizon_s=30.0, step_s=10.0, z0=1.0, h0=1.0, T0=25.0, Tamb=25.0, margin=None,
                  I_keep=None):
    """Closed loop: every step_s, predict horizon_s ahead and apply the permitted command for the next step_s.
    Returns the applied current, the full simulated response and the intervention log."""
    t = np.asarray(t, float); I_req = np.asarray(I_req, float)
    I_keep = np.zeros_like(I_req) if I_keep is None else np.asarray(I_keep, float)
    dt = t[1] - t[0]
    I_app = I_req.copy(); log = []
    state = {"z": z0, "h": h0, "v": (0.0, 0.0), "T": T0}
    k = 0; n_step = max(1, int(round(step_s / dt))); n_hor = max(n_step, int(round(horizon_s / dt)))
    while k < len(t):
        sl = slice(k, min(k + n_hor, len(t)))
        r = moderate(m, state, t[sl], I_req[sl], L, margin, Tamb, I_keep=I_keep[sl])
        e = min(k + n_step, len(t))
        I_app[k:e] = r["I_perm"][: e - k]
        if r["action"] != "none" and np.any(I_app[k:e] != I_req[k:e]):   # log only windows whose applied current changed
            log.append({"t_s": float(t[k]), "requested_A": float(np.max(np.abs(I_req[k:e]))),
                        "permitted_A": float(np.max(np.abs(I_app[k:e]))), "scale": r["scale"], "reason": r["reason"],
                        "predicted_V_min": r["predicted_V_min"], "predicted_V_max": r["predicted_V_max"],
                        "predicted_T_max": r["predicted_T_max"]})
        seg = simulate(m, t[k:e + 1] if e < len(t) else t[k:e], I_app[k:e + 1] if e < len(t) else I_app[k:e],
                       z0=state["z"], h0=state["h"], v0=state["v"], T0=state["T"], Tamb=Tamb)
        i_last = e - k if e < len(t) else e - k - 1
        state = {"z": float(seg["z"][i_last]), "h": float(seg["h"][i_last]),
                 "v": (float(seg["v1"][i_last]), float(seg["v2"][i_last])), "T": float(seg["T"][i_last])}
        k = e
    y = simulate(m, t, I_app, z0=z0, h0=h0, T0=T0, Tamb=Tamb)
    return y, I_app, log
