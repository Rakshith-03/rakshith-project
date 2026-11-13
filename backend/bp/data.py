"""Reference-data access. Raw files under DATA/RAW_REFERENCE are never modified; parsed copies are cached as .npz in
DATA/PROCESSED/calce_npz together with their source path (provenance)."""
from pathlib import Path
import io
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_CALCE = ROOT / "DATA" / "RAW_REFERENCE" / "LITHIUM_ION" / "CALCE_INR18650-20R" / "extracted"
CACHE = ROOT / "DATA" / "PROCESSED" / "calce_npz"


def calce(pattern):
    """Single CALCE file matching `pattern` -> dict t, step, V, I_chg (A, + = charge as logged), source, name."""
    hits = sorted(RAW_CALCE.rglob(pattern))
    if len(hits) != 1:
        raise FileNotFoundError(f"expected one CALCE file for {pattern!r}, found {len(hits)}")
    f = hits[0]
    c = CACHE / (f.stem.replace(" ", "_") + ".npz")
    if not c.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        x = pd.ExcelFile(io.BytesIO(f.read_bytes()), engine="openpyxl")   # CALCE .xls files are xlsx inside
        sheets = [s for s in x.sheet_names if s.startswith("Channel")] or x.sheet_names[:1]
        df = pd.concat([x.parse(s) for s in sheets], ignore_index=True)
        if "Test_Time(s)" in df:
            d = dict(t=df["Test_Time(s)"], step=df["Step_Index"], V=df["Voltage(V)"], I_chg=df["Current(A)"])
        else:   # low-current OCV workbook: Duration (sec), Pgm step, mV, mA
            d = dict(t=df["Duration (sec)"], step=df["Pgm step"], V=df["mV"] / 1000, I_chg=df["mA"] / 1000)
        np.savez(c, **{k: np.asarray(v, float) for k, v in d.items()}, source=str(f.relative_to(ROOT)))
    z = np.load(c)
    return {k: z[k] for k in ("t", "step", "V", "I_chg")} | {"source": str(z["source"]), "name": f.stem}


def drive_cycle(name):
    """SP2 drive-cycle file (e.g. 'US06_80SOC') from the first sample after the CC-CV charge (SOC = 1 by definition)."""
    d = calce(f"*SP20-2_{name}.xls")
    i0 = int(np.argmax(d["step"] == 4))
    return {k: (v[i0:] if isinstance(v, np.ndarray) else v) for k, v in d.items()} | {"name": name}


def scored(d):
    """Samples scored in validation: drive-cycle steps (>= 7) with measured V > 3.0 V."""
    return (d["step"] >= 7) & (d["V"] > 3.0)
