# Li-ion drive-cycle validation, MATLAB run drivecycle_20261112_015732
Executed in MATLAB Online R2026b: `battery_platform/liion/RUN_LIION_DRIVECYCLE_VALIDATION.m`
Outputs (MATLAB Drive): `battery_platform/liion/results/drivecycle_20261112_015732/` (summary JSON, test_error_by_soc.csv, test_overlay_US06_80SOC.png)
Raw data in MATLAB Drive: `battery_platform/data/raw/CALCE_INR18650-20R/` (fetched by bp_fetch_calce; provenance in DATA/RAW_REFERENCE/LITHIUM_ION/CALCE_INR18650-20R/PROVENANCE.md)

Cell: CALCE INR18650-20R, LiNiMnCo/graphite, 2000 mAh rated (CALCE data page). 25 C; temperature not logged.
Roles (no file used twice): OCV = SP1 C/20 | fit = SP2 DST 50/80 % | model selection = SP2 FUDS 50/80 % | **test = SP2 US06 + BJDST 50/80 % (unseen)**.
Scored samples: drive-cycle steps with measured V > 3.0 V (fixed by the data, independent of parameters).

## Capacity and OCV
- Q: SP1 C/20 2.1569 Ah | SP3 C/20 2.0802 Ah | SP2 1C 2.0281 Ah (all CALCULATED from measured current)
- SP3 pseudo-OCV vs SP1 (independent cell): MAE 8.63, RMSE 12.05, MaxAE 32.08, Bias +8.56 mV.
  The maximum is at SOC 1.0, inside the SP1 region extrapolated above SOC 0.895 (22 grid points), where the SP1 charge branch stopped at about 4.15 V.

## Model selection (lsqnonlin, bounded; no parameter at a bound in any candidate)
| Candidate | Train RMSE (DST) | Validation RMSE (FUDS) |
|---|---|---|
| 1RC | 14.76 mV | 12.98 |
| 1RC + hysteresis | 13.82 | 11.45 |
| 2RC | 14.15 | 12.13 |
| **2RC + hysteresis (selected)** | 13.72 | **11.41** |

Selected model `LIION_INR18650-20R_ECM_2RC_H_v1` (ESTIMATED by fitting on DST):
R0 0.0739 Ohm, Q 2.0669 Ah, R1 0.0088 Ohm, tau1 8.68 s, R2 0.0167 Ohm, tau2 67.3 s, M 0.0214 V, gamma 22.65.

## Independent test (never used for fitting or selection)
| Test | N | MAE | RMSE | MaxAE | Bias |
|---|---|---|---|---|---|
| US06 50 % | 6809 | 9.76 | 15.36 | 137.49 | -6.08 mV |
| US06 80 % | 10659 | 11.06 | 16.87 | 225.92 | -1.46 |
| BJDST 50 % | 6890 | 11.73 | 14.76 | 107.36 | -9.95 |
| BJDST 80 % | 11159 | 11.37 | 15.92 | 181.84 | -2.12 |

**Status: VALIDATED** (worst test RMSE 16.9 mV vs 25 mV threshold; the threshold is an editable engineering default, not a standard).

Test RMSE (mV) by modelled SOC band (test_error_by_soc.csv):
| Test | 0-10 % | 10-20 % | 20-50 % | 50-80 % | 80-100 % |
|---|---|---|---|---|---|
| US06 50 % | 32.8 | 11.5 | 6.2 | 4.3 | - |
| US06 80 % | 41.5 | 14.1 | 6.7 | 11.0 | 9.0 |
| BJDST 50 % | 27.4 | 15.4 | 8.9 | 4.5 | - |
| BJDST 80 % | 38.1 | 14.2 | 8.6 | 9.7 | 9.1 |

## Baseline: SP1 C/20 parameters only (comparison)
RMSE: US06 50/80 133.74 / 126.55 mV; BJDST 50/80 108.94 / 97.67 mV.
Parameters from a 0.1 A test do not transfer to 1-4 A drive cycles. The earlier "R_fast VALIDATED" applies only to about 0.1 A steps.

## Cross-implementation check
An independent Python prototype of the same method (scratch, not a deliverable) gave the same test metrics within 0.01 mV and the same model selection.
The SP3-vs-SP1 OCV metric differs (prototype MAE 8.23, max 25.7 mV) because the prototype left out the extrapolated top-of-charge points.

## Limitations and weaknesses found
- **Below 10 % SOC the model is weak** (27-42 mV RMSE; worst errors at 2-4 % SOC near 3.0 V). The OCV comes from another cell, and the knee region dominates.
- Validated at 25 C only. 0 C / 45 C files exist at CALCE but are not used. No thermal validation is possible (no temperature logged).
- One test cell (SP2) for dynamics. Generalisation across cells is shown only for OCV (SP3) and capacity spread (2.08-2.16 Ah).
- Not yet in Simulink. Next step: build the Simulink model and require it to reproduce these MATLAB results.
