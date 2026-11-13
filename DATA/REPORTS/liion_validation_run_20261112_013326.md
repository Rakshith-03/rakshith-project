# Li-ion calibration / validation, run 20261112_013326
Executed in MATLAB Online R2026b by `battery_platform/liion/RUN_LIION_CALIBRATION_VALIDATION.m`.
Outputs in MATLAB Drive: `battery_platform/liion/results/20261112_013326/`
(liion_validation_summary.json, calce_R_events.csv, calce_ocv_soc.csv, liion_validation.png).
Numbers below were copied from the run's console output.

## CALCE INR18650-20R (primary calibration, MEASURED)
| Item | Value | Provenance |
|---|---|---|
| Rows | 169,412 | |
| Missing V / I / T | 0 / 0 / 169,411 | temperature effectively absent |
| Duplicate rows | 0 | |
| Non-monotonic timestamps | **5** (not yet diagnosed) | dt median 1.00 s, max 7 s |
| Discharge capacity, C/20 | **2.1569 Ah** at -0.0996 A mean | CALCULATED from measured current |
| Charge throughput | 1.9262 Ah at 0.0995 A (charge stopped near 4.15 V, so not a full charge) | CALCULATED |
| R_fast (1-2 s apparent, not pure R0) | **0.1996 Ohm** (mean of train events 2to3, 5to6) | CALCULATED |
| RC, 2-branch, step-6 relaxation | R1 0.0310 Ohm, tau1 **100.0 s (at upper bound)**, R2 0.0813 Ohm, tau2 2251 s; fit RMSE 0.33 mV | ESTIMATED, in-sample only |

Apparent resistance per current step (1 mV / 1 mA resolution):
| Event | Role | dI (A) | dV (V) | R_app (Ohm) | Held-out error |
|---|---|---|---|---|---|
| 1to2 (end of CV, high SOC) | test | -0.0990 | -0.0190 | 0.1919 | -0.76 mV |
| 2to3 (discharge start, ~100 % SOC) | train | -0.1010 | -0.0180 | 0.1782 | - |
| 4to5 (charge start, ~0 % SOC) | test | +0.1010 | +0.0220 | 0.2178 | -1.84 mV |
| 5to6 (charge end) | train | -0.0950 | -0.0210 | 0.2211 | - |

## Panasonic NCR18650B (held-out cells; split 60/16/16 by cell, seed 20261112)
| Test | Validation cells | **Test cells (unseen)** |
|---|---|---|
| OCV: train-mean pseudo-OCV vs each cell, [MAE RMSE MaxAE Bias] mV | 1.358 / 1.559 / 3.835 / -0.758 | **1.105 / 1.309 / 3.124 / 0.105**, R2 ≈ 1 |
| Positive-pulse relaxation | 1-RC 1.081 vs 2-RC 0.468 mV RMSE -> 2-RC chosen | **RMSE 0.432 mV, MaxAE 1.768 mV** |
| Negative-pulse relaxation | 1-RC 0.694 vs 2-RC 0.270 mV RMSE -> 2-RC chosen | **RMSE 0.280 mV, MaxAE 1.244 mV** |

Pulse shape parameters (k = fraction of the off-jump, tau in s):
- positive: k1 0.137 / tau1 4.25, k2 0.0972 / tau2 104
- negative: k1 0.0984 / tau1 3.43, k2 0.0876 / tau2 54.7

Cross-cell comparison only (different manufacturer, not validation): CALCE pseudo-OCV vs Panasonic test cells, MAE 40.9 mV.

## Verdicts (thresholds are editable engineering defaults)
| Item | Status |
|---|---|
| CALCE R_fast | VALIDATED (max held-out error 1.84 mV ≤ 3 mV), **on only 2 held-out events** |
| CALCE RC | ESTIMATED, in-sample only; tau1 sits on its bound -> not identified |
| CALCE pseudo-OCV | CALCULATED, no independent OCV test |
| Panasonic OCV | VALIDATED (1.11 ≤ 10 mV MAE) |
| Panasonic +pulse shape | VALIDATED (0.432 ≤ 2 mV RMSE) |
| Panasonic -pulse shape | VALIDATED (0.28 ≤ 2 mV RMSE) |

## Limitations
- Panasonic validation shows that a population model predicts unseen cells **of the same type**. It says nothing about resistances in ohms (pulse current missing), temperature or ageing.
- CALCE is a C/20 test only. Dynamic terminal-voltage generalisation is **not demonstrated**; that needs CALCE DST/US06/FUDS data.
- R_fast mixes R0 with sub-second dynamics (1 s sampling), and rises at low SOC (0.218 vs about 0.19 Ohm).
- The 5 non-monotonic CALCE timestamps and the figure have not been inspected yet.
- Not in Simulink yet. The equations are MATLAB code; the Simulink model must be checked against this code.
