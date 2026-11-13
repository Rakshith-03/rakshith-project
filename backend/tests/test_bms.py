"""BMS tests on MEASURED CALCE drive cycles (files never used for model fitting or selection).
Reference SOC = coulomb counting of the measured current from the full CC-CV charge with the model capacity
(labelled: not an independent SOC measurement)."""
import numpy as np
import pytest
from bp.data import drive_cycle
from bp.model import load_model
from bp.bms import coulomb_count, ekf_soc, soh_capacity, apparent_resistance, sop
from bp.constraints import LIMITS

M = load_model()


def _case(name):
    d = drive_cycle(name)
    I = -d["I_chg"]
    z_ref = coulomb_count(d["t"], I, 1.0, M["Q"])
    k0 = int(np.argmax(d["step"] >= 7))           # start estimation at the first drive-cycle sample
    k1 = int(np.where(d["V"] > 3.0)[0][-1])        # stop where the validated region ends
    s = slice(k0, k1)
    return d["t"][s], I[s], d["V"][s], z_ref[s]


@pytest.mark.parametrize("name", ["US06_80SOC", "BJDST_50SOC"])
def test_ekf_recovers_from_wrong_initial_soc(name):
    t, I, V, z_ref = _case(name)
    z0 = z_ref[0] - 0.3                                      # start 30 % SOC wrong
    est = ekf_soc(M, t, I, V, z0=z0)
    err = est["z"] - z_ref
    after = t - t[0] > 600
    assert np.sqrt(np.mean(err[after] ** 2)) < 0.03         # < 3 % SOC RMS after 10 min
    assert np.max(np.abs(err[after])) < 0.06


def test_ekf_bounds_drift_from_current_sensor_bias():
    t, I, V, z_ref = _case("US06_80SOC")
    I_biased = I + 0.05                                      # +50 mA sensor offset (simulated fault on measured data)
    cc = coulomb_count(t, I_biased, z_ref[0], M["Q"])
    ek = ekf_soc(M, t, I_biased, V, z0=z_ref[0])
    drift_cc = abs(cc[-1] - z_ref[-1]); drift_ek = abs(ek["z"][-1] - z_ref[-1])
    assert drift_cc > 0.05 and drift_ek < drift_cc / 2


def test_soh_and_resistance_indicator_are_separate_and_measured():
    assert soh_capacity(2.0281, 2.0) == pytest.approx(101.405, abs=1e-3)   # SP2 1C capacity vs CALCE rating
    d = drive_cycle("US06_80SOC")
    r = apparent_resistance(d["t"], d["V"], -d["I_chg"])
    assert r["n_steps"] > 50 and 0.05 < r["R_app_median_ohm"] < 0.15


def test_sop_is_limited_at_low_soc():
    L = LIMITS["li-ion-nmc"]
    hi = sop(M, {"z": 0.8, "h": -1, "v": (0, 0), "T": 25}, L)
    lo = sop(M, {"z": 0.005, "h": -1, "v": (0, 0), "T": 25}, L)  # 4 A for 10 s reaches 2.397 V here
    assert hi["discharge"]["limited_by"] == "validated current envelope"
    assert lo["discharge"]["I_A"] < hi["discharge"]["I_A"] and lo["discharge"]["limited_by"] != "validated current envelope"
