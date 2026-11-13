"""Current-profile generators (I > 0 = discharge, A). Same definitions as the Simulink Current_Generator:
    pulse : I = I_base + (I_pulse - I_base) P(t) inside [start, stop)   (I_pulse is the TOTAL current during a pulse)
    ripple: I = I_dc + I_rip w(2 pi f (t - start)) inside [start, stop)   w = sine | square | triangle
Load profiles: constant, step, pulse, repeated (any of these tiled), drive (a measured CALCE drive-cycle current)."""
import numpy as np


def time_grid(duration, dt=1.0):
    return np.arange(0.0, duration + 1e-9, dt)


def pulse(t, base, pulse_current, duration, interval, start=0.0, n=None, stop=None):
    if duration <= 0 or interval <= 0 or duration > interval:
        raise ValueError("need 0 < pulse duration <= interval")
    stop = start + n * interval if n is not None else (np.inf if stop is None else stop)
    win = (t >= start) & (t < stop)
    on = win & (np.mod(t - start, interval) < duration)
    return np.where(win, base + (pulse_current - base) * on, 0.0)


def ripple(t, dc, amplitude, freq, start=0.0, stop=np.inf, waveform="sine"):
    if freq <= 0:
        raise ValueError("ripple frequency must be > 0")
    ph = 2 * np.pi * freq * (t - start)
    w = {"sine": np.sin(ph),
         "square": np.sign(np.sin(ph)),
         "triangle": (2 / np.pi) * np.arcsin(np.sin(ph))}.get(waveform)
    if w is None:
        raise ValueError(f"unknown waveform {waveform!r}")
    win = (t >= start) & (t < stop)
    return np.where(win, dc + amplitude * w, 0.0)


def step_load(t, levels, durations):
    """Piecewise-constant load: levels[i] for durations[i] seconds, then 0."""
    edges = np.concatenate([[0.0], np.cumsum(durations)])
    out = np.zeros_like(t)
    for lv, a, b in zip(levels, edges[:-1], edges[1:]):
        out[(t >= a) & (t < b)] = lv
    return out


def build(cfg, dt=1.0):
    """Profile from an experiment config dict. Components add together.
    cfg: duration_s, and any of: constant_A, step {levels, durations}, pulse {...}, ripple {...}, drive {name, scale}."""
    t = time_grid(cfg["duration_s"], cfg.get("dt_s", dt))
    I = np.full_like(t, float(cfg.get("constant_A", 0.0)))
    if cfg.get("step"):
        I += step_load(t, cfg["step"]["levels"], cfg["step"]["durations"])
    p = cfg.get("pulse")
    if p and p.get("enabled", True):
        I += pulse(t, p["base_A"], p["pulse_A"], p["duration_s"], p["interval_s"], p.get("start_s", 0.0),
                   p.get("n"), p.get("stop_s"))
    r = cfg.get("ripple")
    if r and r.get("enabled", True):
        I += ripple(t, r.get("dc_A", 0.0), r["amplitude_A"], r["freq_Hz"], r.get("start_s", 0.0),
                    r.get("stop_s", np.inf), r.get("waveform", "sine"))
    dv = cfg.get("drive")
    if dv:
        from .data import drive_cycle
        d = drive_cycle(dv["name"]); m = d["step"] >= 7
        td = d["t"][m] - d["t"][m][0]; Id = -d["I_chg"][m] * dv.get("scale", 1.0)
        I += np.interp(t, td, Id, period=td[-1])   # repeated measured drive-cycle current
    return t, I
