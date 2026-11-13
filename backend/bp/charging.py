"""Chemistry-specific charging: conventional CC-CV (Li-ion), fixed current, adaptive receding-horizon charging, and
Ni-Cd CC charging with -dV / dT/dt / charge-input / timer termination (never CV). I > 0 = discharge, so charge I < 0.

Adaptive controller (every `ctrl_s` seconds):
    1. I_need = remaining charge / remaining time  (just enough to meet the target time, which limits heat and loss)
    2. I_max  = largest charge current whose predicted response over `horizon_s` keeps V <= V_max, T <= T_lim and
                stays inside the validated current envelope (bisection on the model)
    3. apply min(I_need * (1 + margin), I_max); hold V = V_max (CV) if the voltage limit binds within the step
Cost reported per profile: J = w_t * t_charge/t_target + w_T * max temperature rise + w_L * losses/energy + w_d * smoothness."""
import numpy as np
from .model import Stepper, simulate

W = {"time": 1.0, "thermal": 0.05, "loss": 2.0, "smooth": 0.2}


def _finish(name, log, m, z_target, t_target_s, Tamb):
    a = {k: np.array([r[k] for r in log]) for k in log[0]} if log else {}
    if not log:
        return {"strategy": name, "reached": False}
    dt = np.diff(a["t"], append=a["t"][-1] + (a["t"][-1] - a["t"][-2] if len(a["t"]) > 1 else 1))
    reached = bool(a["z"][-1] >= z_target - 1e-4)
    t_ch = float(a["t"][-1]) if reached else None
    E_in = float(np.sum(-a["I"] * a["V"] * dt) / 3600)          # Wh delivered to the cell terminals
    loss = float(np.sum(a["q"] * dt) / 3600)                     # Wh dissipated (modelled ohmic + polarisation)
    smooth = float(np.mean(np.abs(np.diff(a["I"])))) if len(a["I"]) > 1 else 0.0
    J = None if t_ch is None or not t_target_s else (W["time"] * t_ch / t_target_s + W["thermal"] * (a["T"].max() - Tamb)
                                                     + W["loss"] * loss / max(E_in, 1e-9) + W["smooth"] * smooth)
    return {"strategy": name, "reached": reached, "t_charge_s": t_ch, "final_soc": float(a["z"][-1]),
            "energy_in_Wh": E_in, "losses_Wh": loss, "T_max_C": float(a["T"].max()), "V_max_V": float(a["V"].max()),
            "I_max_A": float(-a["I"].min()), "cost_J": J, "series": {k: a[k].tolist() for k in ("t", "I", "V", "z", "T")}}


def cccv(m, z0, z_target, I_cc, V_max, I_term=0.02, t_max_s=6 * 3600, dt=1.0, T0=25.0, Tamb=25.0, h0=-1.0,
         t_target_s=None, name="conventional CC-CV"):
    s = Stepper(m, z0, h0, T0, Tamb); log = []; t = 0.0
    while t <= t_max_s and s.z < z_target:
        I = max(-I_cc, s.current_for_voltage(V_max))            # CV: never let V exceed V_max
        if -I < I_term:
            break
        V, q = s.step(I, dt); log.append({"t": t, "I": I, "V": V, "z": s.z, "T": s.T, "q": q}); t += dt
    return _finish(name, log, m, z_target, t_target_s, Tamb)


def fixed_current(m, z0, z_target, I, t_max_s=6 * 3600, dt=1.0, T0=25.0, Tamb=25.0, h0=-1.0, t_target_s=None):
    """Constant current with no voltage control: limit crossings are reported by the monitor, not prevented."""
    s = Stepper(m, z0, h0, T0, Tamb); log = []; t = 0.0
    while t <= t_max_s and s.z < z_target:
        V, q = s.step(-I, dt); log.append({"t": t, "I": -I, "V": V, "z": s.z, "T": s.T, "q": q}); t += dt
    return _finish("fixed current", log, m, z_target, t_target_s, Tamb)


def _max_safe_charge(m, st, L, I_cap, horizon_s, Tamb, V_max):
    t = np.arange(0.0, horizon_s + 1e-9, 1.0)
    def ok(Ic):
        y = simulate(m, t, np.full_like(t, -Ic), z0=st["z"], h0=st["h"], v0=st["v"], T0=st["T"], Tamb=Tamb)
        return y["T"].max() <= L["T_warn"]
    if ok(I_cap):
        return I_cap
    lo, hi = 0.0, I_cap
    while hi - lo > 1e-3:
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    return lo


def feasibility(m, z0, z_target, t_target_s, L, V_max, I_cap, T0=25.0, Tamb=25.0, h0=-1.0):
    """Fastest charge allowed by the constraints (CC at the current cap, CV at V_max, thermal derating) and the verdict."""
    fast = adaptive(m, z0, z_target, None, L, V_max, I_cap, T0=T0, Tamb=Tamb, h0=h0, fastest=True)
    I_avg = (z_target - z0) * m["Q"] * 3600 / t_target_s
    if not fast["reached"]:
        return {"feasible": False, "t_min_s": None, "reason": "target SOC not reachable within the limits"}
    ok = fast["t_charge_s"] <= t_target_s
    if ok:
        why = "achievable within all constraints"
    elif I_avg > I_cap:
        why = (f"needs an average of {I_avg:.2f} A, above the {I_cap:.2f} A charge-current cap "
               f"(validated envelope; datasheet maximum UNVERIFIED)")
    else:
        why = (f"fastest constrained charge takes {fast['t_charge_s'] / 60:.1f} min: the {V_max:.2f} V limit "
               f"forces CV taper and/or thermal derating")
    return {"feasible": ok, "t_min_s": fast["t_charge_s"], "I_avg_needed_A": I_avg, "reason": why}


def adaptive(m, z0, z_target, t_target_s, L, V_max, I_cap, ctrl_s=10.0, horizon_s=60.0, margin=0.03, dt=1.0,
             T0=25.0, Tamb=25.0, h0=-1.0, t_max_s=6 * 3600, fastest=False):
    s = Stepper(m, z0, h0, T0, Tamb); log = []; t = 0.0; I_cmd = 0.0
    while t <= t_max_s and s.z < z_target:
        if int(round(t / dt)) % int(round(ctrl_s / dt)) == 0:
            I_max = _max_safe_charge(m, s.state(), L, I_cap, horizon_s, Tamb, V_max)
            if fastest or t_target_s is None:
                I_cmd = I_max
            else:
                left = max(t_target_s - t, ctrl_s)
                I_need = (z_target - s.z) * m["Q"] * 3600 / left
                I_cmd = min(I_need * (1 + margin), I_max)
        I = max(-I_cmd, s.current_for_voltage(V_max))
        if -I < 1e-3:
            break
        V, q = s.step(I, dt); log.append({"t": t, "I": I, "V": V, "z": s.z, "T": s.T, "q": q}); t += dt
    return _finish("adaptive (receding horizon)" if not fastest else "fastest constrained", log, m, z_target,
                   t_target_s, Tamb)


def nicd_charge(m, z0, I_cc, Q_rated_Ah, dV_term=0.010, dTdt_term=1.0, input_frac=1.5, t_max_s=None, dt=1.0,
                T0=25.0, Tamb=25.0):
    """Ni-Cd constant-current charge. Terminates on the first of: -dV (V drops dV_term below its peak),
    dT/dt > dTdt_term degC/min, charge input > input_frac x rated capacity, timer. No CV phase."""
    t_max_s = t_max_s or 1.2 * input_frac * Q_rated_Ah / I_cc * 3600
    s = Stepper(m, z0, 0.0, T0, Tamb); log = []; t = 0.0; Vpk = -np.inf; Ah = 0.0; reason = "timer"
    while t <= t_max_s:
        T_prev = s.T
        V, q = s.step(-I_cc, dt); Ah += I_cc * dt / 3600; Vpk = max(Vpk, V)
        log.append({"t": t, "I": -I_cc, "V": V, "z": s.z, "T": s.T, "q": q}); t += dt
        if V < Vpk - dV_term:
            reason = "-dV"; break
        if (s.T - T_prev) / dt * 60 > dTdt_term:
            reason = "dT/dt"; break
        if Ah >= input_frac * Q_rated_Ah:
            reason = "charge input limit"; break
    out = _finish("Ni-Cd CC with -dV/dT/dt/input/timer termination", log, m, 1.0, None, Tamb)
    return out | {"termination": reason, "charge_input_Ah": Ah}
