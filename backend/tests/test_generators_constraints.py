import numpy as np
import pytest
from bp import generators as g
from bp.constraints import LIMITS, monitor, moderate, run_moderated, _violates
from bp.model import load_model, simulate

M = load_model(); L = LIMITS["li-ion-nmc"]


def test_pulse_is_total_current_not_added():
    t = g.time_grid(600, 0.25)
    I = g.pulse(t, base=1.0, pulse_current=3.0, duration=10, interval=60, start=100, n=3)
    assert I.max() == 3.0 and I[(t >= 100) & (t < 280)].min() == 1.0 and I[t < 100].max() == 0.0
    assert np.sum(np.diff((I == 3.0).astype(int)) == 1) == 3


def test_ripple_rms_and_waveforms():
    t = g.time_grid(250, 0.05)
    I = g.ripple(t, dc=1.0, amplitude=0.5, freq=0.2, start=50, stop=250)
    w = (t >= 50) & (t < 250)
    assert np.sqrt(np.mean((I[w] - 1.0) ** 2)) == pytest.approx(0.5 / np.sqrt(2), abs=1e-3)
    assert set(np.round(g.ripple(t, 0, 1, 0.2, waveform="square")[1:], 6)) <= {-1.0, 0.0, 1.0}
    with pytest.raises(ValueError):
        g.ripple(t, 0, 1, 0)


def test_build_combines_components():
    t, I = g.build({"duration_s": 100, "constant_A": 0.5, "pulse": {"base_A": 0, "pulse_A": 2, "duration_s": 5, "interval_s": 20}})
    assert I.max() == pytest.approx(2.5) and I.min() == pytest.approx(0.5)


def test_monitor_normal_and_stress():
    t = g.time_grid(300)
    y = simulate(M, t, g.pulse(t, 1, 3, 10, 60), z0=0.8, h0=-1)
    assert monitor(t, y["V"], y["I"], y["T"], y["z"], L)[1] == "NORMAL"
    y = simulate(M, t, np.full_like(t, 6.0), z0=0.08, h0=-1)   # STRESS TEST beyond available charge
    rows, overall = monitor(t, y["V"], y["I"], y["T"], y["z"], L)
    sev = {r["constraint"]: r["severity"] for r in rows}
    assert overall == "CRITICAL" and sev["undervoltage"] == "CRITICAL" and sev["discharge current"] == "WARNING"


def test_moderator_leaves_safe_request_unchanged():
    t = g.time_grid(30)
    I = g.pulse(t, 1, 2, 10, 20)
    r = moderate(M, {"z": 0.8, "h": -1, "v": (0, 0), "T": 25}, t, I, L)
    assert r["action"] == "none" and np.array_equal(r["I_perm"], I)


def test_moderator_spec_example_base_2A_pulse_4A_at_low_soc():
    t = g.time_grid(30)
    I = g.pulse(t, 2, 4, 10, 20)
    state = {"z": 0.015, "h": -1, "v": (0, 0), "T": 25}   # unmoderated minimum V is 2.492 V here (< 2.50 V)
    r = moderate(M, state, t, I, L)
    assert r["action"] == "reduced" and 0 < r["permitted_peak_A"] < 4 and "undervoltage" in r["reason"]
    sim = lambda s: simulate(M, t, s * I, z0=0.015, h0=-1)
    assert _violates(sim(r["scale"]), L, {"V": 0, "T": 0}) is None            # permitted command is safe
    assert _violates(sim(r["scale"] + 0.01), L, {"V": 0, "T": 0}) is not None  # and (nearly) the largest safe one


def test_moderator_keeps_base_and_reduces_pulse():
    t = g.time_grid(30)
    I = g.pulse(t, 2, 4, 10, 20); base = g.pulse(t, 2, 2, 10, 20)
    r = moderate(M, {"z": 0.015, "h": -1, "v": (0, 0), "T": 25}, t, I, L, I_keep=base)
    assert r["mode"] == "pulse reduced, base kept"
    assert np.allclose(r["I_perm"][I == 2], 2.0) and 2.0 < r["permitted_peak_A"] < 4.0


def test_closed_loop_moderation_removes_critical_violations():
    t = g.time_grid(400)
    I = g.pulse(t, 2, 4, 10, 30)
    y0 = simulate(M, t, I, z0=0.12, h0=-1)
    assert monitor(t, y0["V"], y0["I"], y0["T"], y0["z"], L)[1] == "CRITICAL"
    y, I_app, log = run_moderated(M, t, I, L, z0=0.12, h0=-1)
    rows, _ = monitor(t, y["V"], y["I"], y["T"], y["z"], L)
    sev = {r["constraint"]: r["severity"] for r in rows}
    assert sev["undervoltage"] != "CRITICAL" and len(log) > 0 and np.all(np.abs(I_app) <= np.abs(I) + 1e-12)
    assert all({"t_s", "requested_A", "permitted_A", "reason"} <= set(e) for e in log)
