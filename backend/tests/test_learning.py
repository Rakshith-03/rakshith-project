"""Learning loop on a temporary copy of the model registry (the real registry is never touched by tests)."""
import json, shutil
import pytest
import bp.model, bp.learning
from bp.learning import error_analysis, recalibrate, rollback, registry


@pytest.fixture()
def tmp_registry(tmp_path, monkeypatch):
    for p in bp.model.MODELS.glob("LIION_*.json"):
        shutil.copy(p, tmp_path)
    monkeypatch.setattr(bp.model, "MODELS", tmp_path); monkeypatch.setattr(bp.learning, "MODELS", tmp_path)
    bp.model._load.cache_clear(); yield tmp_path; bp.model._load.cache_clear()


def test_error_analysis_finds_low_soc_weakness():
    r = error_analysis()
    assert any(w["region"] == "0.0-0.1" for w in r["weak_regions"])
    assert r["recommended_experiments"]


def test_candidate_without_improvement_is_rejected_and_kept(tmp_registry):
    before = bp.model.approved_model_id()
    r = recalibrate(min_improvement_mV=0.5)          # demand a clear validation gain
    assert r["approval"].startswith("REJECTED") and r["test_rmse_mV"] is None   # test set untouched when rejected
    assert bp.model.approved_model_id() == before and (tmp_registry / f"{r['id']}.json").exists()


def test_rollback_restores_previous_approved(tmp_registry):
    before = bp.model.approved_model_id()
    v2 = json.loads((tmp_registry / "LIION_INR18650-20R_ECM_2RC_H_v2.json").read_text())
    v9 = {**v2, "id": "LIION_INR18650-20R_ECM_2RC_H_v9", "version": 9, "approval": "APPROVED - test fixture"}
    (tmp_registry / "LIION_INR18650-20R_ECM_2RC_H_v9.json").write_text(json.dumps(v9))
    assert bp.model.approved_model_id().endswith("_v9")
    r = rollback()
    assert r["rolled_back"].endswith("_v9") and r["active"] == before
