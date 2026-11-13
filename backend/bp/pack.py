"""Series pack of individually modelled cells with passive or active balancing. All outputs are SIMULATED.
Cell-to-cell differences are user-configured scenarios (capacity, R0, initial SOC, temperature); they are never
inferred from pack-level measurements.
    passive: cell k bleeds V_k / R_bleed while V_k - min(V) > threshold
    active : I_bal is moved from the highest-SOC cell to the lowest while the SOC spread > threshold (efficiency eta)"""
import numpy as np
from .model import Stepper, with_changes


def make_cells(m, n, dQ=None, dR0=None, z0=None, T0=None):
    dQ = np.zeros(n) if dQ is None else np.asarray(dQ); dR0 = np.zeros(n) if dR0 is None else np.asarray(dR0)
    z0 = np.full(n, 0.5) if z0 is None else np.asarray(z0); T0 = np.full(n, 25.0) if T0 is None else np.asarray(T0)
    return [Stepper(with_changes(m, Q=m["Q"] * (1 + dQ[k]), R0=m["R0"] * (1 + dR0[k])), z0[k], -1.0, T0[k], 25.0)
            for k in range(n)]


def run(cells, I_pack, duration_s, mode="off", threshold=0.01, R_bleed=33.0, I_bal=0.2, eta=0.9, dt=1.0,
        V_cell_max=4.2, stop_at_vmax=True):
    """I_pack > 0 discharge. Stops a charge when any cell reaches V_cell_max (cell-level protection)."""
    n = len(cells); steps = int(duration_s / dt)
    out = {k: np.full((steps, n), np.nan) for k in ("V", "z", "I_bal")}
    E_bal = 0.0; t_bal = 0.0; stop = None
    for s in range(steps):
        V = np.array([c.voltage(I_pack) for c in cells]); z = np.array([c.z for c in cells])
        Ib = np.zeros(n)
        if mode == "passive":
            on = V - V.min() > threshold
            Ib[on] = V[on] / R_bleed
        elif mode == "active" and z.max() - z.min() > threshold:
            Ib[np.argmax(z)] = I_bal; Ib[np.argmin(z)] = -eta * I_bal
        if np.any(Ib != 0):
            t_bal += dt
            E_bal += (np.sum(Ib[Ib > 0] * V[Ib > 0]) - (np.sum(-Ib[Ib < 0] * V[Ib < 0]))) * dt / 3600  # Wh not returned
        for k, c in enumerate(cells):
            out["V"][s, k] = c.step(I_pack + Ib[k], dt)[0]
            out["z"][s, k] = c.z
        out["I_bal"][s] = Ib
        if stop_at_vmax and I_pack < 0 and np.max(out["V"][s]) >= V_cell_max:
            stop = s; break
    k = steps if stop is None else stop + 1
    V, z = out["V"][:k], out["z"][:k]
    return {"V": V, "z": z, "I_bal": out["I_bal"][:k], "t": np.arange(k) * dt, "stopped_at_s": None if stop is None else k * dt,
            "dV_final_mV": float(1000 * (V[-1].max() - V[-1].min())), "dSOC_final": float(z[-1].max() - z[-1].min()),
            "dSOC_initial": float(z[0].max() - z[0].min()), "balancing_energy_Wh": E_bal, "balancing_time_s": t_bal,
            "charge_in_Ah": float(-I_pack * k * dt / 3600) if I_pack < 0 else 0.0, "label": "SIMULATED"}
