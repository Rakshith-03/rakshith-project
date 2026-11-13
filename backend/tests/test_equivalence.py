"""The Python engine must reproduce the MATLAB-approved model (run drivecycle_20261112_024805) on unseen CALCE files."""
import json
import numpy as np
import pytest
from bp.data import drive_cycle, scored
from bp.model import load_model, simulate, metrics, MODELS

M = load_model("LIION_INR18650-20R_ECM_2RC_H_v2")   # the MATLAB-validated version
META = json.loads((MODELS / f"{M['id']}.json").read_text())


def test_ocv_table_matches_matlab():
    for z, v in META["ocv"]["matlab_checkpoints"].items():
        assert np.interp(float(z), M["soc_bp"], M["ocv"]) == pytest.approx(v, abs=2e-6), z


@pytest.mark.parametrize("name", ["US06_50SOC", "US06_80SOC", "BJDST_50SOC", "BJDST_80SOC"])
def test_unseen_drive_cycle_metrics_match_matlab(name):
    d = drive_cycle(name)
    y = simulate(M, d["t"], -d["I_chg"])
    m = scored(d)
    got = metrics(1000 * d["V"][m], 1000 * y["V"][m])
    ref = META["matlab_test_metrics_mV"][name]
    assert got["RMSE"] == pytest.approx(ref["RMSE"], abs=0.02)
    assert got["MAE"] == pytest.approx(ref["MAE"], abs=0.02)
