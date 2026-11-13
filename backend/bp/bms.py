"""Software BMS: SOC (coulomb counting, EKF on the validated ECM), capacity-based SOH, resistance indicator, SOP.
I > 0 = discharge. Nothing here is a certified safety function."""
import numpy as np
from .model import ocv_at, simulate


def coulomb_count(t, I, z0, Q_Ah, eta_chg=1.0):
    """SOC by integrating current. Charging efficiency eta_chg applies to charge current (I < 0)."""
    dt = np.diff(t, prepend=t[0])
    Ieff = np.where(I < 0, eta_chg * I, I)
    return z0 - np.cumsum(np.concatenate([[0.0], Ieff[:-1] * dt[1:]])) / (3600 * Q_Ah)


def ekf_soc(m, t, I, V, z0=0.5, P0=0.04, sigma_I=0.02, sigma_V=0.015, h0=0.0):
    """Extended Kalman filter, state x = [z, v1, v2, h]; measurement V = OCV(z) + M h - R0 I - v1 - v2.
    sigma_V reflects the validated model error (about 15 mV RMSE), sigma_I the current-sensor noise."""
    n = len(t); dt = np.diff(t, append=t[-1])
    x = np.array([z0, 0.0, 0.0, h0]); P = np.diag([P0, 1e-4, 1e-4, 0.25])
    dz = np.gradient(m["ocv"], m["soc_bp"])
    out = np.empty((n, 4)); Pz = np.empty(n)
    Rm = sigma_V ** 2
    for k in range(n):
        # update with measurement k
        Hm = np.array([np.interp(np.clip(x[0], 0, 1), m["soc_bp"], dz), -1.0, -1.0, m["M"]])
        Vp = ocv_at(m, x[0]) + m["M"] * x[3] - m["R0"] * I[k] - x[1] - x[2]
        S = Hm @ P @ Hm + Rm; K = P @ Hm / S
        x = x + K * (V[k] - Vp); P = P - np.outer(K, Hm) @ P
        out[k] = x; Pz[k] = P[0, 0]
        # predict to k+1
        a1 = np.exp(-dt[k] / m["tau1"]); a2 = np.exp(-dt[k] / m["tau2"])
        e = np.exp(-abs(I[k]) * m["gam"] * dt[k] / (3600 * m["Q"]))
        A = np.diag([1.0, a1, a2, e])
        x = A @ x + np.array([-I[k] * dt[k] / (3600 * m["Q"]), m["R1"] * (1 - a1) * I[k], m["R2"] * (1 - a2) * I[k],
                              -(1 - e) * np.sign(I[k])])
        G = np.array([-dt[k] / (3600 * m["Q"]), m["R1"] * (1 - a1), m["R2"] * (1 - a2), 0.0])
        P = A @ P @ A.T + np.outer(G, G) * sigma_I ** 2 + np.diag([1e-10, 1e-8, 1e-8, 1e-6])
    return {"z": out[:, 0], "v1": out[:, 1], "v2": out[:, 2], "h": out[:, 3], "z_std": np.sqrt(Pz)}


def soh_capacity(Q_measured_Ah, Q_reference_Ah):
    """Capacity-based SOH (%). Reported separately from resistance indicators; no combined index is validated."""
    return 100.0 * Q_measured_Ah / Q_reference_Ah


def apparent_resistance(t, V, I, min_step_A=1.0, max_dt_s=1.5):
    """|dV/dI| across single-sample current steps >= min_step_A (an apparent ~1 s resistance, NOT pure ohmic R0)."""
    dI = np.diff(I); dV = np.diff(V); dt = np.diff(t)
    k = (np.abs(dI) >= min_step_A) & (dt <= max_dt_s)
    r = np.abs(dV[k] / dI[k])
    return {"R_app_median_ohm": float(np.median(r)) if r.size else None, "n_steps": int(k.sum()),
            "R_app_p10_p90": [float(np.percentile(r, 10)), float(np.percentile(r, 90))] if r.size else None}


def sop(m, state, L, horizon_s=10.0, I_max_dis=4.0, I_max_chg=2.2, Tamb=25.0):
    """State of power over horizon_s: largest constant discharge / charge current (bounded by the validated envelope)
    that keeps the predicted voltage and SOC inside the CRITICAL limits, and the corresponding power."""
    t = np.arange(0.0, horizon_s + 1e-9, 1.0)
    def ok(Ic):
        y = simulate(m, t, np.full_like(t, Ic), z0=state["z"], h0=state["h"], v0=state["v"], T0=state["T"], Tamb=Tamb)
        good = (y["V"] >= L["V_crit_lo"]).all() and (y["V"] <= L["V_crit_hi"]).all() and (y["z"] >= 0).all() \
            and (y["z"] <= 1).all() and (y["T"] <= L["T_crit"]).all()
        return good, y
    res = {}
    for name, sgn, cap in (("discharge", 1, I_max_dis), ("charge", -1, I_max_chg)):
        lo, hi = 0.0, cap
        if ok(sgn * hi)[0]:
            lo = hi
        while hi - lo > 1e-3:
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if ok(sgn * mid)[0] else (lo, mid)
        y = ok(sgn * lo)[1]
        res[name] = {"I_A": lo, "P_W": float(lo * (y["V"].min() if sgn > 0 else y["V"].max())),
                     "limited_by": "validated current envelope" if lo >= cap - 1e-6 else "voltage/SOC/temperature limit"}
    res["assumptions"] = f"{horizon_s:.0f} s constant current from the present state; current capped at the validated envelope"
    return res
