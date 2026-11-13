"""End-to-end API test following the acceptance demonstration (temporary database)."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import bp.db


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    bp.db.DB_PATH = tmp_path_factory.mktemp("db") / "test.sqlite"
    from bp.api import app
    return TestClient(app)


def pulse_ripple(amp):
    return {"duration_s": 300, "initial_soc": 0.7, "mode": "manual",
            "load": {"constant_A": 0.5, "pulse": {"base_A": 0.0, "pulse_A": 1.5, "duration_s": 10, "interval_s": 60, "start_s": 30},
                     "ripple": {"dc_A": 0.0, "amplitude_A": amp, "freq_Hz": 0.5, "start_s": 0, "stop_s": 300}}}


def test_health_and_profiles(client):
    from bp.model import approved_model_id
    assert client.get("/api/health").json()["model"] == approved_model_id()
    ids = [p["id"] for p in client.get("/api/profiles").json()]
    assert {"INR18650-20R", "NICD-GENERIC-1S"} <= set(ids)
    r = client.put("/api/profiles/INR18650-20R", json={"capacity_Ah": 2.0, "n_series": 4, "initial_soc": 0.6}).json()
    assert r["version"] == 2 and r["n_series"] == 4
    assert client.put("/api/profiles/INR18650-20R", json={"V_min": 4.5}).status_code == 422
    assert client.post("/api/profiles", json={"id": "LFP1", "chemistry": "li-ion-lfp"}).status_code == 422


def test_datasets_and_validation(client):
    ds = {d["id"]: d for d in client.get("/api/datasets").json()}
    assert ds["NICD_SIM_READY"]["approval"].startswith("REJECTED") and ds["CALCE_SP2_US06"]["sha256"]
    q = client.post("/api/datasets/CALCE_SP2_US06/clean").json()
    assert q["status"] == "APPROVED"
    import json
    from bp.model import approved_model_id, MODELS
    rec = json.loads((MODELS / f"{approved_model_id()}.json").read_text())
    expected = (rec.get("test_rmse_mV") or {}).get("US06_80SOC") or rec["matlab_test_metrics_mV"]["US06_80SOC"]["RMSE"]
    ov = client.get("/api/validation/overlay/US06_80SOC").json()
    assert ov["role"] == "test" and abs(ov["metrics_mV"]["RMSE"] - expected) < 0.05


def ripple_only(amp):
    return {"duration_s": 120, "initial_soc": 0.7, "load": {"constant_A": 0.5,
            "ripple": {"amplitude_A": amp, "freq_Hz": 0.5, "start_s": 0, "stop_s": 120}}}


def test_ripple_amplitude_changes_simulated_response(client):
    a = client.post("/api/experiments", json={"config": ripple_only(0.2)}).json()
    b = client.post("/api/experiments", json={"config": ripple_only(0.8)}).json()
    assert a["dt_s"] == 0.1
    assert b["features"]["I_ripple_rms_A"] > 3 * a["features"]["I_ripple_rms_A"]
    assert b["features"]["V_ripple_rms_V"] > 3 * a["features"]["V_ripple_rms_V"]
    p = client.post("/api/experiments", json={"config": pulse_ripple(0.3)}).json()   # pulse + ripple together
    assert p["features"]["I_max"] > 1.5
    ts = client.get(f"/api/experiments/{a['id']}/timeseries").json()
    assert {"dVdt", "dIdt", "dTdt"} <= set(ts) and ts["label"].startswith("SIMULATED")


def test_auto_moderation_logs_requested_vs_permitted(client):
    cfg = {"duration_s": 200, "initial_soc": 0.03, "mode": "auto",
           "load": {"pulse": {"base_A": 2.0, "pulse_A": 4.0, "duration_s": 10, "interval_s": 20}}}
    r = client.post("/api/experiments", json={"config": cfg}).json()
    e = client.get(f"/api/experiments/{r['id']}").json()
    assert r["moderation_events"] > 0 and all(m["permitted_A"] < m["requested_A"] for m in e["moderation_events"])
    assert all(x["constraint_name"] != "undervoltage" or x["severity"] != "CRITICAL" for x in e["constraint_events"])


def test_healthy_vs_degraded_and_idempotency(client):
    client.put("/api/profiles/INR18650-20R", json={"health": {"capacity_factor": 0.8, "r0_factor": 1.5}})
    cfg = {"duration_s": 600, "initial_soc": 0.8, "compare_healthy": True, "discharging": {"enabled": True, "current_A": 2.0}}
    r = client.post("/api/experiments", json={"config": cfg}, headers={"idempotency-key": "k1"}).json()
    d = r["healthy_comparison"]["delta"]
    assert d["V_avg"] < 0 and d["T_max"] > 0
    again = client.post("/api/experiments", json={"config": cfg}, headers={"idempotency-key": "k1"}).json()
    assert again["id"] == r["id"] and again["idempotent_replay"]
    client.put("/api/profiles/INR18650-20R", json={"health": {"capacity_factor": 1.0, "r0_factor": 1.0}})


def test_live_session_changes_apply_at_boundary(client):
    sid = client.post("/api/live", json={"config": {"initial_soc": 0.7, "load": {"constant_A": 1.0}}}).json()["session"]
    s1 = client.post(f"/api/live/{sid}/step?seconds=20").json()
    client.post(f"/api/live/{sid}/update", json={"load": {"constant_A": 2.0}})
    s2 = client.post(f"/api/live/{sid}/step?seconds=20").json()
    assert set(s1["samples"]["I"]) == {1.0} and set(s2["samples"]["I"]) == {2.0}
    assert client.post(f"/api/live/{sid}/pause").json()["state"] == "PAUSED"
    assert "samples" not in client.post(f"/api/live/{sid}/step").json()
    client.post(f"/api/live/{sid}/resume")
    st = client.post(f"/api/live/{sid}/stop").json()
    assert st["experiment_id"].startswith("EXP_") and st["changes_applied"][0]["t_s"] == 20.0


def test_moderation_endpoint_spec_example(client):
    r = client.post("/api/moderate", json={"state": {"soc": 0.015, "T": 25},
                                           "request": {"base_A": 2.0, "pulse_A": 4.0, "pulse_s": 10, "interval_s": 20}}).json()
    assert r["action"] == "reduced" and 2.0 < r["permitted_pulse_A"] < 4.0 and "undervoltage" in r["reason"]


def test_charging_targets(client):
    r = client.post("/api/charging/optimize", json={"initial_soc": 0.2, "target_soc": 0.8, "target_time_s": 1800}).json()
    assert r["verdict"] == "INFEASIBLE" and "2.48" in r["feasibility"]["reason"]
    r = client.post("/api/charging/optimize", json={"initial_soc": 0.2, "target_soc": 0.8, "target_time_s": 2700}).json()
    assert r["verdict"] == "FEASIBLE" and r["adaptive"]["reached"] and r["adaptive"]["t_charge_s"] <= 2700


def test_bms_pack_report_campaign(client):
    own = client.post("/api/experiments", json={"config": pulse_ripple(0.3)}).json()["id"]
    exps = [{"id": own}]
    d = client.post(f"/api/experiments/{own}/diagnostics").json()
    assert "sop" in d and 0 <= d["soc_ekf_end"] <= 1.05
    ek = client.post("/api/bms/ekf_demo", json={"file": "US06_80SOC"}).json()
    assert ek["ekf_rmse_after_600s"] < 0.03
    pb = client.post("/api/pack/balance", json={"soc0": [0.5, 0.58, 0.62, 0.53], "mode": "active", "duration_s": 3600}).json()
    assert pb["active"]["dSOC_final"] < pb["off"]["dSOC_final"]
    rep = client.post(f"/api/experiments/{exps[0]['id']}/report").json()
    assert Path(rep["html"]).exists() and Path(rep["csv"]).exists()
    cmp1 = client.post("/api/campaigns", headers={"idempotency-key": "c1"},
                       json={"name": "t", "experiments": [{"config": pulse_ripple(0.3)}, {"config": {"duration_s": 100}}]}).json()
    assert cmp1["status"] == "COMPLETED" and len(cmp1["experiments"]) == 2
    assert client.post("/api/campaigns", headers={"idempotency-key": "c1"}, json={}).json()["idempotent_replay"]
    assert client.post("/api/errors", json={"experiment_id": cmp1["experiments"][0], "source": "test"}).json()["retry_allowed"] is False
    assert client.get("/api/errors").json()[0]["constraint_name"] == "test"   # newest recorded error is listed first
    assert client.post("/api/n8n/executions", json={"workflow": "02", "execution_id": "x"}).json()["recorded"]


def test_timeseries_temperature_is_not_time(client):
    r = client.post("/api/experiments", json={"config": {"duration_s": 300, "discharging": {"enabled": True, "current_A": 2.0}}}).json()
    ts = client.get(f"/api/experiments/{r['id']}/timeseries").json()
    assert ts["T"][0] == 25.0 and ts["T"][-1] < 40 and ts["t"][-1] == 300.0
