# MATLAB environment and MATLAB Drive inventory
Inspected 2026-11-12 in MATLAB Online (Chrome), by reading screenshots of the Command Window.

## Environment
- MATLAB 26.2.0.3437455 (R2026b) Update 2, MATLAB Online, 121 products.
- Licensed: Simulink, Simscape, Simscape Electrical, Simscape Battery, Optimization, Global Optimization,
  Statistics and ML, Deep Learning, Model Predictive Control, Control System, Simulink Design Optimization,
  System Identification, Curve Fitting, Signal Processing, MATLAB Report Generator, Stateflow (16 of 16 checked).
- Integration constraint: MATLAB Online cannot be reached by the MATLAB Engine API for Python from this PC.
  Options are file exchange through MATLAB Drive, or a local MATLAB install for batch/Engine runs.

## Battery-related files in MATLAB Drive (excluding .session and Examples)
- `Panasonic_NCR18650B_Consolidated.mat` (same name as the local copy)
- `battery_baseline/` : earlier "Ester 18650 4S1P" project
  - `Simulink/models/Ester18650_4S1P_Baseline_Model.slx`, `models/ester_4s1p_phase12.slx`, `models/ester_4s1p_baseline.cir`
  - `scripts/run_master_battery_baseline.m`, `battery_baseline.m`
  - `data/CALCE/11_5_2015_low current OCV test_SP20-1.xlsx` (+ the same file zipped)
  - `data/processed/ester_101pt_ocv_soc_grid.csv`, `ester_experimental_soc_checkpoints.csv`
  - `results/*.csv|mat` (baseline DB, phase1 charge, phase2 discharge 0.4/1/2 A, CALCE comparison, validation metrics)
  - `figures/*.png`
- `Examples/R2026a/simscapeelectrical/BatteryDCFastChargingExample/` : MathWorks example plus user edits (`claud.slx`, `battery_pertubati...`, `untitled*.m/.slx`)
- Unrelated: AEB_*, convulation*.m, controlled_time_signal4.m, ev1 christ.m, untitled*.m

**No Ni-Cd file exists in MATLAB Drive.** No Panasonic pulse-current or temperature files were found either.

## battery_baseline/README.md: provenance statements (quoted from the file)
- Ester target specs are user supplied. CALCE INR 18650-20R 2 Ah NMC/graphite is reference data, not Ester.
- OCV curve is a synthetic prior; outputs are simulated.
- ECM/thermal and matched-cell parameters are assumptions.
- SOH and target validation unavailable without Ester cycling data.

## CALCE INR 18650-20R (Samsung, NMC), sheet "SP20-OCVSOC-0.05C": MEASURED
- 169,412 rows: Duration (s), Pgm step (0-6), mV, mA, Temperature
- 47.1 h; current -107..+135 mA (about C/20); voltage 2.496-4.205 V
- Temperature: only 1 valid reading (23 C) -> thermal calibration BLOCKED
- Integrated discharge throughput: 2.152 Ah (C/20 measured capacity; rated 2.0 Ah per README)
- Supports: OCV-SOC (charge/discharge), measured capacity, and R0 from current-step transitions (current is recorded)
