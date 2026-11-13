import numpy as np
import pytest
from bp.model import load_model, nicd_provisional
from bp.charging import cccv, fixed_current, adaptive, feasibility, nicd_charge
from bp.constraints import LIMITS

M = load_model(); L = LIMITS["li-ion-nmc"]; VMAX = L["V_crit_hi"]; ICAP = L["I_chg_warn"]


def test_cccv_never_exceeds_vmax_and_reaches_target():
    r = cccv(M, 0.2, 0.95, I_cc=1.0, V_max=VMAX)
    assert r["reached"] and r["V_max_V"] <= VMAX + 1e-9
    I = -np.array(r["series"]["I"])
    assert I.min() < 0.99   # CV taper happened near the top


def test_30_min_20_to_80_is_infeasible_and_says_why():
    f = feasibility(M, 0.2, 0.8, 30 * 60, L, VMAX, ICAP)
    assert not f["feasible"] and f["I_avg_needed_A"] > ICAP and "cap" in f["reason"]


def test_adaptive_meets_feasible_target_without_violations():
    f = feasibility(M, 0.2, 0.8, 45 * 60, L, VMAX, ICAP)
    assert f["feasible"]
    a = adaptive(M, 0.2, 0.8, 45 * 60, L, VMAX, ICAP)
    fast = adaptive(M, 0.2, 0.8, None, L, VMAX, ICAP, fastest=True)
    assert a["reached"] and a["t_charge_s"] <= 45 * 60 and a["V_max_V"] <= VMAX + 1e-9 and a["I_max_A"] <= ICAP + 1e-9
    assert a["losses_Wh"] < fast["losses_Wh"] and a["T_max_C"] <= fast["T_max_C"]   # just-enough current costs less


def test_fixed_current_reports_its_overvoltage():
    r = fixed_current(M, 0.2, 0.99, 2.0)
    assert r["V_max_V"] > VMAX   # no voltage control: crossing is reported, not hidden


def test_nicd_uses_cc_with_termination_not_cccv():
    m = nicd_provisional(Q_Ah=1.0)
    r = nicd_charge(m, 0.0, I_cc=0.5, Q_rated_Ah=1.0)
    I = np.array(r["series"]["I"])
    assert np.allclose(I, -0.5) and r["termination"] == "charge input limit"
    assert r["charge_input_Ah"] == pytest.approx(1.5, abs=1e-3)
