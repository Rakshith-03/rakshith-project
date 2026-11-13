import numpy as np
from bp import ml


def test_features_are_causal():
    t = np.arange(0.0, 400); V = np.linspace(4, 3, 400); I = np.sin(t / 7)
    F1 = ml.features(t, V, I)
    V2 = V.copy(); I2 = I.copy(); V2[300:] += 1; I2[300:] -= 5          # change only the future
    F2 = ml.features(t, V2, I2)
    assert np.allclose(F1[:300], F2[:300])


def test_splits_are_disjoint_by_file():
    s = ml.SPLIT
    assert not (set(s["train"]) & set(s["val"]) or set(s["train"]) & set(s["test"]) or set(s["val"]) & set(s["test"]))


def test_panasonic_screen_runs_on_all_cells():
    r = ml.panasonic_anomalies()
    assert r["n_cells"] == 92 and 1 <= r["n_flagged"] <= 10 and "No accuracy claimed" in r["note"]
