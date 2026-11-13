# Dataset inspection: Li-ion
Generated 2026-11-12T00:51:37 by tools/inspect_datasets.py

| Field | Value |
|---|---|
| File | Panasonic_NCR18650B_Consolidated.mat (MAT v5) |
| SHA-256 | `5a50d0e275e36a0f7fc5923ec1bd4a3f72e5010513b0f401db4071533f4afb30` |
| Battery | Panasonic NCR18650B (file metadata) |
| Chemistry / subtype | Li-ion; the NCR18650B is commonly listed as NCA, but the file does not state it -> UNVERIFIED |
| Cells | 92 (one column per cell) |
| Nominal voltage / rated capacity | UNKNOWN in file (datasheet values not imported; must be entered and marked MANUFACTURER-RATED) |
| Current | **NOT PRESENT** |
| Temperature | **NOT PRESENT** |
| Cycling / ageing history | **NOT PRESENT** |
| NaN values | 0 in all arrays |
| File notes | Consolidated from supplied Panasonic NCR18650B files. POCV and pulse data are kept in native matrix form: rows=samples, columns=cells. Z_imag is preserved raw because matching frequency/cell metadata and Z_real were not supplied. |

## Pseudo-OCV (POCV)
- 5000 SOC points (0-1 normalised; capacity in Ah not given) x 92 cells, charge and discharge branches.
- Charge branch 2.688-4.200 V; discharge branch 2.500-4.178 V.
- Charge/discharge gap at 50 % SOC: 64.2 mV mean (hysteresis plus residual IR at the POCV rate).
- Cell-to-cell spread at 50 % SOC: 2.36 mV std.

## Pulse tests (rows=samples, columns=cells, zero-padded)
| Pulse | Valid samples/cell | Median dt | Duration | Largest voltage step |
|---|---|---|---|---|
| positive | 2212-2214 | 1.000 s | 1849 s | -79.7 mV (std 1.4) |
| negative | 2213-2214 | 1.000 s | 1849 s | +77.4 mV (std 16.4) |

Both directions apply a step at about t = 9 s and remove it at about t = 19 s (a 10 s pulse), then roughly 30 min of relaxation.
Because **pulse current is not recorded**, R0/R1 cannot be reported in ohms. Without the current, only these are supported:
dV amplitudes, the ratio of instantaneous step to 10 s polarisation, and relaxation time constants (tau = R1*C1).

## EIS
Z_imag_raw is (92, 70). Z_real and the frequency vector are missing, so it cannot be used for a fit -> NOT USABLE.

## What this dataset supports
| Quantity | Status |
|---|---|
| OCV-SOC curve (charge, discharge, mean) | MEASURED |
| OCV hysteresis | CALCULATED from measurements |
| Cell-to-cell variation (OCV, pulse dV) | CALCULATED, 92 cells |
| Polarisation time constants | ESTIMABLE by fitting relaxation |
| R0, R1 in ohms; C1 in farads | BLOCKED: pulse current missing |
| Capacity (Ah), SOH, coulombic efficiency | BLOCKED: no current or capacity |
| Thermal R_th / C_th | BLOCKED: no temperature |

Independent validation is possible **by cell**: 92 cells allow train/validation/test splits at cell level with no time-series leakage.

Approval status: **APPROVED (partial)** for OCV and pulse-shape work. **NEEDS REVIEW** for anything that needs current or temperature.
