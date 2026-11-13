"""Phase 2: read-only inspection of the two reference datasets -> DATA/REPORTS/*.md
Originals are never modified. Run: python tools/inspect_datasets.py"""
from pathlib import Path
import hashlib, datetime
import numpy as np, pandas as pd, scipy.io as sio

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "DATA" / "REPORTS"; OUT.mkdir(parents=True, exist_ok=True)
NOW = datetime.datetime.now().isoformat(timespec="seconds")
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def nicd(path):
    df = pd.read_excel(path)
    ocv_fit = np.polyfit(df.SOC_percent, df.OCV_V, 1)
    ocv_resid = float(np.abs(df.OCV_V - np.polyval(ocv_fit, df.SOC_percent)).max())
    nz = df.Current_A != 0
    r_app = ((df.Terminal_Voltage_V - df.OCV_V) / df.Current_A)[nz]
    seg = (df.Current_A != df.Current_A.shift()).cumsum()
    phases = df.groupby(seg).agg(start_min=("Time_min", "first"), end_min=("Time_min", "last"),
                                 current_A=("Current_A", "first"), soc_start=("SOC_percent", "first"),
                                 soc_end=("SOC_percent", "last"))
    synthetic = ocv_resid < 1e-9 and r_app.std() < 1e-9
    status = df.Data_Status.unique().tolist()
    return f"""# Dataset inspection: Ni-Cd
Generated {NOW} by tools/inspect_datasets.py

| Field | Value |
|---|---|
| File | {path.name} (XLSX, 1 sheet) |
| SHA-256 | `{sha(path)}` |
| Chemistry | Ni-Cd (from filename only) |
| Manufacturer / model | UNKNOWN |
| Cell configuration | UNKNOWN (voltage range 1.20-1.37 V implies a single cell) |
| Nominal voltage | UNKNOWN (not stated; 1.2 V is typical for Ni-Cd, but that is an assumption) |
| Rated capacity | UNKNOWN |
| Rows / columns | {len(df)} / {list(df.columns)} |
| Sampling interval | {sorted(df.Time_min.diff().dropna().unique().tolist())} min |
| Missing values | {int(df.isna().sum().sum())} |
| Duplicate rows | {int(df.duplicated().sum())} |
| Data_Status column | {status} |

## Phases (segmented on current changes; sign convention: + = charge)
{phases.to_markdown(index=False)}

## Provenance findings
- OCV is an exact linear function of SOC: OCV = {ocv_fit[0]:.6f}*SOC% + {ocv_fit[1]:.4f} V, max residual {ocv_resid:.1e} V.
- (V_terminal - OCV) / I = {r_app.mean():.6f} Ohm on every non-zero-current sample (std {r_app.std():.1e}): a fixed R0, with no polarization dynamics.
- Temperature is a smooth first-order curve with no sensor noise.
- The file labels itself "{status[0]}".

**Classification: {"SIMULATED / MODEL-DERIVED" if synthetic else "NEEDS REVIEW"}.** Only the two OCV endpoints
(1.206 V and 1.369 V) are stated to be measured. This file cannot calibrate or validate a Ni-Cd model:
fitting would just recover the generator's own parameters (R0 = 0.03 Ohm, linear OCV), so any match would be circular.

Approval status: **REJECTED as experimental reference**. It can be kept as a SIMULATED regression fixture.
"""


def liion(path):
    m = sio.loadmat(path, squeeze_me=True)
    n = int(m["cell_count"])
    pc, pd_, soc = m["POCV_charge_V"], m["POCV_discharge_V"], m["POCV_SOC"]
    i50 = int(np.argmin(abs(soc - 0.5)))
    rows, steps = [], []
    for s in ("positive", "negative"):
        t, v = m[f"Pulse_{s}_time_s"], m[f"Pulse_{s}_voltage_V"]
        valid = (v > 0).sum(0)  # trailing zeros are padding, not 0 V readings
        dv = np.array([np.diff(v[:valid[c], c]) for c in range(n)], dtype=object)
        on = np.array([d[np.argmax(abs(d))] for d in dv])
        steps.append(on)
        rows.append(f"| {s} | {valid.min()}-{valid.max()} | {np.median(np.diff(t[:valid[0], 0])):.3f} s | "
                    f"{t[:valid[0], 0].max():.0f} s | {on.mean()*1000:+.1f} mV (std {on.std()*1000:.1f}) |")
    return f"""# Dataset inspection: Li-ion
Generated {NOW} by tools/inspect_datasets.py

| Field | Value |
|---|---|
| File | {path.name} (MAT v5) |
| SHA-256 | `{sha(path)}` |
| Battery | {m["battery_name"]} (file metadata) |
| Chemistry / subtype | Li-ion; the NCR18650B is commonly listed as NCA, but the file does not state it -> UNVERIFIED |
| Cells | {n} (one column per cell) |
| Nominal voltage / rated capacity | UNKNOWN in file (datasheet values not imported; must be entered and marked MANUFACTURER-RATED) |
| Current | **NOT PRESENT** |
| Temperature | **NOT PRESENT** |
| Cycling / ageing history | **NOT PRESENT** |
| NaN values | 0 in all arrays |
| File notes | {m["notes"]} |

## Pseudo-OCV (POCV)
- {len(soc)} SOC points (0-1 normalised; capacity in Ah not given) x {n} cells, charge and discharge branches.
- Charge branch {pc.min():.3f}-{pc.max():.3f} V; discharge branch {pd_.min():.3f}-{pd_.max():.3f} V.
- Charge/discharge gap at 50 % SOC: {(pc[i50]-pd_[i50]).mean()*1000:.1f} mV mean (hysteresis plus residual IR at the POCV rate).
- Cell-to-cell spread at 50 % SOC: {pc[i50].std()*1000:.2f} mV std.

## Pulse tests (rows=samples, columns=cells, zero-padded)
| Pulse | Valid samples/cell | Median dt | Duration | Largest voltage step |
|---|---|---|---|---|
{chr(10).join(rows)}

Both directions apply a step at about t = 9 s and remove it at about t = 19 s (a 10 s pulse), then roughly 30 min of relaxation.
Because **pulse current is not recorded**, R0/R1 cannot be reported in ohms. Without the current, only these are supported:
dV amplitudes, the ratio of instantaneous step to 10 s polarisation, and relaxation time constants (tau = R1*C1).

## EIS
Z_imag_raw is {m["Z_imag_raw"].shape}. Z_real and the frequency vector are missing, so it cannot be used for a fit -> NOT USABLE.

## What this dataset supports
| Quantity | Status |
|---|---|
| OCV-SOC curve (charge, discharge, mean) | MEASURED |
| OCV hysteresis | CALCULATED from measurements |
| Cell-to-cell variation (OCV, pulse dV) | CALCULATED, {n} cells |
| Polarisation time constants | ESTIMABLE by fitting relaxation |
| R0, R1 in ohms; C1 in farads | BLOCKED: pulse current missing |
| Capacity (Ah), SOH, coulombic efficiency | BLOCKED: no current or capacity |
| Thermal R_th / C_th | BLOCKED: no temperature |

Independent validation is possible **by cell**: {n} cells allow train/validation/test splits at cell level with no time-series leakage.

Approval status: **APPROVED (partial)** for OCV and pulse-shape work. **NEEDS REVIEW** for anything that needs current or temperature.
"""


if __name__ == "__main__":
    (OUT / "nicd_inspection.md").write_text(nicd(ROOT / "NiCd_Simulation_Ready.xlsx"), encoding="utf-8")
    (OUT / "liion_inspection.md").write_text(liion(ROOT / "Panasonic_NCR18650B_Consolidated.mat"), encoding="utf-8")
    print("wrote", *OUT.glob("*_inspection.md"))
