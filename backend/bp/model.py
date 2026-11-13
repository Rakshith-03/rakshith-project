"""Li-ion ECM (2 RC + one-state hysteresis) with a PROVISIONAL lumped thermal model.

Python port of MATLAB bp_ecm_sim.m / MULTI_CHEMISTRY_BATTERY_LAB.slx (LiIon_ECM + Thermal_Model).
tests/test_equivalence.py requires this port to reproduce the MATLAB test metrics and OCV table.
Current convention: I > 0 = discharge (A). Exact zero-order hold per sample:
    v_i(k+1) = a_i v_i(k) + R_i (1 - a_i) I(k),  a_i = exp(-dt/tau_i)
    h(k+1)   = e h(k) - (1 - e) sign(I(k)),       e = exp(-|I| gamma dt / (3600 Q))
    V        = OCV(z) + M h - R0 I - v1 - v2
    T(k+1)   = Tamb + (T(k) - Tamb) b + R_th Q_gen(k) (1 - b),  b = exp(-dt / (R_th C_th)),  Q_gen = I (R0 I + v1 + v2)
"""
import json
from functools import lru_cache
import numpy as np
from .data import ROOT, calce

MODELS = ROOT / "DATA" / "MODELS"
THERMAL_PROVISIONAL = {"Rth": 10.0, "Cth": 45.0,
                       "status": "PROVISIONAL: C_th = 45 g (CALCE) x 1000 J/kg/K ASSUMED; R_th = 10 K/W ASSUMED"}


def pocv(d, dis_step, chg_step, rest_step=None):
    """Pseudo-OCV (mean of C/20 branches) on a 201-point SOC grid; same algorithm as MATLAB bp_pocv.m."""
    def seg(s):
        m = d["step"] == s
        t, i, v = d["t"][m], d["I_chg"][m], d["V"][m]
        ah = np.concatenate([[0.0], np.cumsum(np.diff(t) * (i[1:] + i[:-1]) / 2)]) / 3600
        return ah, v
    ahd, vd = seg(dis_step); ahc, vc = seg(chg_step)
    Q = -ahd[-1]
    g = np.linspace(0, 1, 201)

    def branch(s, v):
        s, idx = np.unique(s, return_index=True)
        return np.interp(g, s, v[idx], left=np.nan, right=np.nan)
    O = {"soc": g, "Q_Ah": Q, "V_dis": branch(1 + ahd / Q, vd), "V_chg": branch(ahc / Q, vc)}
    if rest_step is not None:
        O["V_rest_full"] = float(d["V"][d["step"] == rest_step][-1])
        ie = int(np.where(~np.isnan(O["V_chg"]))[0][-1])
        O["z_end"] = float(g[ie]); O["gap_end"] = float((O["V_chg"][ie] - O["V_dis"][ie]) / 2)
    return O


def ocv_table(O, M):
    """Anchored-top table (MATLAB bp_ocv_table.m): OCV(1) + M equals the measured rest after a full CC-CV charge."""
    ocv = (O["V_dis"] + O["V_chg"]) / 2
    top = O["soc"] > O["z_end"]
    off1 = O["V_rest_full"] - M - O["V_dis"][-1]
    ocv[top] = O["V_dis"][top] + O["gap_end"] + (off1 - O["gap_end"]) * (O["soc"][top] - O["z_end"]) / (1 - O["z_end"])
    return ocv


def approved_model_id():
    """Newest APPROVED Li-ion model in the registry (DATA/MODELS)."""
    ok = [json.loads(p.read_text()) for p in MODELS.glob("LIION_*.json")]
    ok = [r for r in ok if r["approval"].startswith("APPROVED")]
    if not ok:
        raise RuntimeError("no approved Li-ion model in DATA/MODELS")
    return max(ok, key=lambda r: r.get("version", 0))["id"]


def load_model(model_id=None):
    return _load(model_id or approved_model_id())


@lru_cache(maxsize=8)
def _load(model_id):
    meta = json.loads((MODELS / f"{model_id}.json").read_text())
    if not meta["approval"].startswith("APPROVED"):
        raise ValueError(f"{model_id} is not approved: {meta['approval']}")
    O = pocv(calce("*SP20-1.xlsx"), 3, 5, rest_step=2)
    p = meta["params"]
    return {"id": model_id, "meta": meta, "R0": p["R0_ohm"], "Q": p["Q_Ah"], "R1": p["R1_ohm"], "tau1": p["tau1_s"],
            "R2": p["R2_ohm"], "tau2": p["tau2_s"], "M": p["M_V"], "gam": p["gamma"],
            "soc_bp": O["soc"], "ocv": ocv_table(O, p["M_V"]) + ocv_delta(meta, O["soc"]), "thermal": dict(THERMAL_PROVISIONAL)}


def ocv_delta(meta, soc):
    """Optional learned OCV correction (piecewise linear in SOC), fitted on training files only. Zero when absent."""
    d = meta.get("ocv_delta")
    return np.interp(soc, d["knots"], d["values_V"]) if d else np.zeros_like(soc)


def nicd_provisional(Q_Ah):
    """PROVISIONAL single-cell Ni-Cd model: NOT VALIDATED (no real Ni-Cd measurements exist in this project).
    OCV: linear between 1.206 V and 1.369 V, the endpoints NiCd_Simulation_Ready.xlsx labels as measured (unverified).
    R0 = 0.03 Ohm: taken from that SIMULATED file. Rated capacity: user-configured (UNKNOWN in the file).
    eta_chg = 0.8, thermal parameters: ASSUMED generic values. Overcharge physics (-dV signature) is NOT modelled."""
    g = np.linspace(0, 1, 201)
    return {"id": "NICD_GENERIC_PROVISIONAL", "R0": 0.03, "Q": float(Q_Ah), "R1": 1e-6, "tau1": 1.0, "R2": 1e-6,
            "tau2": 1.0, "M": 0.0, "gam": 1.0, "soc_bp": g, "ocv": 1.206 + (1.369 - 1.206) * g, "eta_chg": 0.8,
            "thermal": {"Rth": 12.0, "Cth": 30.0, "status": "ASSUMED"},
            "meta": {"approval": "PROVISIONAL - NOT VALIDATED", "chemistry": "Ni-Cd"}}


def with_changes(m, **kw):
    """Copy of a model with some parameters replaced (ratings, degradation scenarios). Unknown keys raise."""
    bad = set(kw) - set(m)
    if bad:
        raise KeyError(f"unknown model parameters: {sorted(bad)}")
    return {**m, **kw}


def ocv_at(m, z):
    return np.interp(np.clip(z, 0, 1), m["soc_bp"], m["ocv"])


def simulate(m, t, I, z0=1.0, h0=1.0, v0=(0.0, 0.0), T0=25.0, Tamb=25.0):
    """Run the ECM + thermal model on a current profile I(t) (A, discharge > 0, zero-order hold).
    Returns arrays V, z (SOC, unclamped), h, v1, v2, T (degC), Q (W heat), plus final state."""
    t = np.asarray(t, float); I = np.asarray(I, float); n = len(t)
    dt = np.diff(t, append=t[-1])
    a1 = np.exp(-dt / m["tau1"]); a2 = np.exp(-dt / m["tau2"])
    e = np.exp(-np.abs(I) * m["gam"] * dt / (3600 * m["Q"]))
    th = m["thermal"]; b = np.exp(-dt / (th["Rth"] * th["Cth"]))
    Ieff = np.where(I < 0, m.get("eta_chg", 1.0) * I, I)   # charge efficiency (1 for the Li-ion model)
    z = z0 - np.concatenate([[0.0], np.cumsum(Ieff[:-1] * dt[:-1])]) / (3600 * m["Q"])
    v1 = np.empty(n); v2 = np.empty(n); h = np.empty(n); T = np.empty(n); Qg = np.empty(n)
    x1, x2 = v0; hh = h0; TT = T0
    R0, R1, R2 = m["R0"], m["R1"], m["R2"]
    for k in range(n):
        v1[k] = x1; v2[k] = x2; h[k] = hh; T[k] = TT
        ik = I[k]
        q = ik * (R0 * ik + x1 + x2); Qg[k] = q
        x1 = a1[k] * x1 + R1 * (1 - a1[k]) * ik
        x2 = a2[k] * x2 + R2 * (1 - a2[k]) * ik
        if ik != 0.0:
            hh = e[k] * hh - (1 - e[k]) * np.sign(ik)
        TT = Tamb + (TT - Tamb) * b[k] + th["Rth"] * q * (1 - b[k])
    V = ocv_at(m, z) + m["M"] * h - R0 * I - v1 - v2
    return {"t": t, "I": I, "V": V, "z": z, "h": h, "v1": v1, "v2": v2, "T": T, "Q": Qg,
            "final": {"z": float(z[-1] - I[-1] * dt[-1] / (3600 * m["Q"])) if n else z0, "h": hh, "v": (x1, x2), "T": TT}}


class Stepper:
    """One-sample-at-a-time version of simulate() (same equations), for closed-loop control and live sessions."""

    def __init__(self, m, z0=1.0, h0=1.0, T0=25.0, Tamb=25.0):
        self.m, self.z, self.h, self.v1, self.v2, self.T, self.Tamb = m, z0, h0, 0.0, 0.0, T0, Tamb

    def voltage(self, I):
        m = self.m
        return float(ocv_at(m, self.z) + m["M"] * self.h - m["R0"] * I - self.v1 - self.v2)

    def current_for_voltage(self, V_target):
        """Current that makes the terminal voltage equal V_target right now (V is affine in I)."""
        m = self.m
        return (float(ocv_at(m, self.z)) + m["M"] * self.h - self.v1 - self.v2 - V_target) / m["R0"]

    def step(self, I, dt):
        """Apply current I for dt seconds. Returns (V at the start of the step, heat W)."""
        m = self.m; th = m["thermal"]
        V = self.voltage(I); q = I * (m["R0"] * I + self.v1 + self.v2)
        eta = m.get("eta_chg", 1.0) if I < 0 else 1.0
        a1 = np.exp(-dt / m["tau1"]); a2 = np.exp(-dt / m["tau2"])
        e = np.exp(-abs(I) * m["gam"] * dt / (3600 * m["Q"])); b = np.exp(-dt / (th["Rth"] * th["Cth"]))
        self.z -= eta * I * dt / (3600 * m["Q"])
        self.v1 = a1 * self.v1 + m["R1"] * (1 - a1) * I
        self.v2 = a2 * self.v2 + m["R2"] * (1 - a2) * I
        if I != 0:
            self.h = e * self.h - (1 - e) * np.sign(I)
        self.T = self.Tamb + (self.T - self.Tamb) * b + th["Rth"] * q * (1 - b)
        return V, q

    def state(self):
        return {"z": self.z, "h": self.h, "v": (self.v1, self.v2), "T": self.T}


def metrics(y, yhat):
    """MAE, RMSE, MaxAE, Bias, R2 of yhat against reference y (same units)."""
    e = np.asarray(yhat, float) - np.asarray(y, float)
    ok = ~np.isnan(e); e = e[ok]; y = np.asarray(y, float)[ok]
    return {"N": int(e.size), "MAE": float(np.mean(np.abs(e))), "RMSE": float(np.sqrt(np.mean(e ** 2))),
            "MaxAE": float(np.max(np.abs(e))), "Bias": float(np.mean(e)),
            "R2": float(1 - np.sum(e ** 2) / np.sum((y - y.mean()) ** 2))}
