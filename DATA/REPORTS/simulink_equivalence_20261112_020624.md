# Simulink equivalence, run simulink_eq_20261112_020624
Model: `MATLAB Drive/battery_platform/simulink/MULTI_CHEMISTRY_BATTERY_LAB.slx`, built by `bp_build_slx.m` from standard blocks
(Integrator, Gain, Sum, Abs, Sign, Product, 1-D Lookup Table). Continuous time, ode23t, RelTol 1e-7, MaxStep 1 s.
The current input is a From Workspace block with zero-order hold and zero-crossing detection.
Parameters: `LIION_INR18650-20R_ECM_2RC_H_v1` from run drivecycle_20261112_015732. OCV: SP1 C/20 table.
Runner: `RUN_SIMULINK_EQUIVALENCE.m`. Output: `battery_platform/liion/results/simulink_eq_20261112_020624/simulink_equivalence.json`.

| Test (unseen) | Sim time | Simulink vs MATLAB RMSE | MaxAE | Simulink vs measured RMSE | MAE |
|---|---|---|---|---|---|
| US06 50 % | 1.3 s | 0.0080 mV | 0.0614 mV | 15.36 mV | 9.76 mV |
| US06 80 % | 1.5 s | 0.0138 | 0.1236 | 16.87 | 11.06 |
| BJDST 50 % | 0.5 s | 0.0020 | 0.0162 | 14.76 | 11.73 |
| BJDST 80 % | 0.6 s | 0.0003 | 0.0032 | 15.92 | 11.37 |

Thresholds (editable): RMSE ≤ 0.5 mV and MaxAE ≤ 2 mV -> **EQUIVALENT**.
The Simulink model reproduces the validated MATLAB model, and its error against the measurements matches the MATLAB validation.

## Scope of the .slx so far
It contains only the Li-ion electrical core (SOC, OCV, R0, 2 RC branches, hysteresis) plus the current input.
Chemistry selector, thermal, ageing, charger, perturbation/ripple generators, cell pack, balancing, BMS estimator,
protection and logging subsystems are **not built yet**. Thermal parameters cannot be calibrated: no temperature data is available.
