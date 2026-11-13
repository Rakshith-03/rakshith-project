# Li-ion drive-cycle validation: Python PROTOTYPE results
> SUPERSEDED by the MATLAB run: liion_drivecycle_validation_20261112_015732.md (test metrics agree within 0.01 mV).
**Status: prototype numbers.** They were produced by a scratch Python implementation of the same method, used to debug the
approach while MATLAB Online was unresponsive. The project result is the MATLAB run of `RUN_LIION_DRIVECYCLE_VALIDATION.m`.
That run should reproduce these numbers within optimiser tolerance; a larger gap means one of the two implementations has a bug.

Data: CALCE INR18650-20R, 25 C (see DATA/RAW_REFERENCE/LITHIUM_ION/CALCE_INR18650-20R/PROVENANCE.md).
Roles: OCV = SP1 C/20 | fit = SP2 DST 50/80 | selection = SP2 FUDS 50/80 | **test = SP2 US06 + BJDST 50/80 (unseen)**.
Scored samples: drive-cycle steps with measured V > 3.0 V.

## OCV and capacity
- Q C/20: SP1 2.1569 Ah, SP3 2.0802 Ah (cell-to-cell spread about 3.6 %)
- SP3 pseudo-OCV vs SP1 pseudo-OCV (independent cell): MAE 8.23 mV, max 25.72 mV

## Candidate models (bounded least squares)
| Model | Train RMSE (DST) | Validation RMSE (FUDS) | Parameters at a bound |
|---|---|---|---|
| 1RC | 14.76 mV | 12.98 mV | none |
| 1RC + hysteresis | 13.82 | 11.45 | none |
| 2RC | 14.15 | 12.13 | none |
| **2RC + hysteresis (selected)** | 13.72 | **11.41** | none |

Selected parameters: R0 0.0738 Ohm, Q 2.0669 Ah, R1 0.0087 Ohm / tau1 8.56 s, R2 0.0168 Ohm / tau2 66.6 s, M 0.0214 V, gamma 22.5

## Test (unseen files)
| Test | MAE | RMSE | MaxAE | Bias |
|---|---|---|---|---|
| US06 50 % | 9.76 | 15.35 | 137.5 | -6.1 mV |
| US06 80 % | 11.06 | 16.87 | 225.9 | -1.5 |
| BJDST 50 % | 11.73 | 14.75 | 107.3 | -9.9 |
| BJDST 80 % | 11.37 | 15.92 | 181.8 | -2.1 |

Test RMSE (mV) by modelled SOC band:
| Test | 0-10 % | 10-20 % | 20-50 % | 50-80 % | 80-100 % |
|---|---|---|---|---|---|
| US06 50 % | 32.8 | 11.4 | 6.1 | 4.2 | - |
| US06 80 % | 41.5 | 14.0 | 6.6 | 11.1 | 9.2 |
| BJDST 50 % | 27.4 | 15.3 | 8.8 | 4.5 | - |
| BJDST 80 % | 38.1 | 14.1 | 8.5 | 9.8 | 9.2 |

The worst errors all occur at 2-4 % SOC near 3.0 V (the OCV knee). High-current samples (|I| > 2.5 A, US06) give 23 mV RMSE.

## Baseline: parameters from the SP1 C/20 test only
US06 50/80: RMSE 133.7 / 126.5 mV; BJDST 50/80: 108.9 / 97.7 mV, bias about -75 to -88 mV.
The 0.2 Ohm "fast resistance" measured at 0.1 A steps overstates the resistance seen at 1-4 A (fit: 0.074 Ohm).
The earlier R_fast "VALIDATED" holds **only for about 0.1 A steps**.

## Error analysis
- Systematic: voltage under-predicted at low SOC (negative bias). Likely causes are the OCV borrowed from another cell (SP1) and its knee below 10 % SOC.
- Model is weakest at high current (US06 peaks).
- Possible improvements, each to be judged on FUDS only, never on the test set: SOC-dependent R0, an OCV table matched to SP2, a current-dependent R0.
