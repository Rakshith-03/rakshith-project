# Current generator, thermal model and constraint monitor: test results
MATLAB Online run `battery_platform/liion/results/gen_thermal_<timestamp>/`, from `RUN_GENERATORS_THERMAL_CONSTRAINTS.m`
(tests.csv, ripple_frequency_response.csv, constraints_*.csv, generators_thermal.png, summary.json).
Model: `MULTI_CHEMISTRY_BATTERY_LAB.slx`, rebuilt by `bp_build_slx.m` with the Current_Generator, LiIon_ECM and Thermal_Model subsystems.

## Result: 10 / 10 PASS (on the second run; see "Failure fixed" below)
| Test | Result |
|---|---|
| T1 generators off, US06 80 % | Simulink vs validated MATLAB model: RMSE 0.011 mV, MaxAE 0.10 mV |
| T2a pulse current | max \|I - I_ref\| = 0 A off switching edges; peak 3.0000 A = total pulse current (not base + pulse); 3 pulses |
| T2b pulse voltage response | matches the MATLAB model: RMSE 0.0000 mV; voltage swing 294.7 mV |
| T3 ripple current | max error 2.8e-14 A; ripple RMS 0.35355 A (expected 0.35355) |
| T4a amplitude sweep (0.1 Hz) | voltage ripple 18.545 / 37.089 / 74.178 mV for 0.25 / 0.5 / 1 A: exactly linear |
| T4b frequency response | \|Z\| = 0.08208 / 0.07418 / 0.07385 Ohm at 0.01 / 0.1 / 1 Hz, matching analytic \|Z(jw)\| to < 1e-5 relative |
| T5 thermal (PROVISIONAL) | steady Q = 0.3976 W = I^2(R0+R1+R2); energy balance residual 3.98e-(exponent cut off on screen; full value in tests.csv) J, within the 0.1 % of ∫Q pass limit; 2 A for 3000 s -> +3.97 K |
| T6a stress test (6 A continuous from 8 % SOC) | undervoltage CRITICAL (min 2.135 V), discharge current WARNING (beyond validated 4 A), low SOC CRITICAL |
| T6b normal pulse test | NORMAL |

T4b also checks the integration end to end: the Simulink ripple response reproduces the analytic impedance of the validated parameters,
R0 + R1/(1+jw tau1) + R2/(1+jw tau2) + (dOCV/dz)/(jw 3600 Q).

## Failure fixed during this work
The first run failed T6a. 6 A *pulses* from 8 % SOC only reached 2.654 V, so the monitor correctly reported WARNING (< 2.80 V), not CRITICAL.
The test scenario was wrong, not the monitor. It was replaced with 6 A continuous for 190 s (0.32 Ah demanded vs about 0.17 Ah available).

## Model weakness found (open)
Running the monitor on the simulated US06 80 % profile gives **overvoltage CRITICAL** during the 600 s rest right after the full CC-CV charge.
The model rests at **4.257 V**, while the measured cell rests at about 4.196 V. Cause: at SOC = 1 the model adds the full hysteresis offset (M = 21 mV) to an OCV
that is extrapolated above 89.5 % SOC (the SP1 charge branch stopped near 4.15 V). The drive-cycle validation scored only drive-cycle steps, so it did not see this.
**Not fixed yet.** Candidate fixes (calibrate on DST, select on FUDS, never on the test files): an OCV top segment from SP2/SP3 data that reaches 4.2 V,
or SOC-dependent hysteresis. Any fix needs a new validation run.

Other US06 80 % monitor output: undervoltage WARNING (min simulated 2.768 V; measured run ends at 2.498 V), low-SOC WARNING; temperature NOT MONITORED (none logged).

## Limits used (bp_limits_liion.m)
Every limit records its source. 4.20 / 2.50 V come from the CALCE test procedure. 4 A / 2.2 A are the validated data envelope (WARNING only; datasheet maxima UNVERIFIED).
Temperature and dT/dt limits are ASSUMED. The thermal model is PROVISIONAL: C_th = 45 g (CALCE) x 1000 J/kg/K (assumed cp), R_th = 10 K/W (assumed).

## Not done yet
- This monitor is offline (post-simulation). Predictive real-time moderation (requested vs permitted current) is Phase 13.
- dV/dt and dI/dt are reported, not used as limits (on their own they do not indicate damage).
