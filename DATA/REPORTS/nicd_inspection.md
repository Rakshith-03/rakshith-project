# Dataset inspection: Ni-Cd
Generated 2026-11-12T00:51:37 by tools/inspect_datasets.py

| Field | Value |
|---|---|
| File | NiCd_Simulation_Ready.xlsx (XLSX, 1 sheet) |
| SHA-256 | `426ad34c3a3a09665a3bd50977711d3fbf8e5e8bae7f10ce673ff92966a522b5` |
| Chemistry | Ni-Cd (from filename only) |
| Manufacturer / model | UNKNOWN |
| Cell configuration | UNKNOWN (voltage range 1.20-1.37 V implies a single cell) |
| Nominal voltage | UNKNOWN (not stated; 1.2 V is typical for Ni-Cd, but that is an assumption) |
| Rated capacity | UNKNOWN |
| Rows / columns | 961 / ['Time_min', 'Current_A', 'Temperature_C', 'SOC_percent', 'OCV_V', 'Terminal_Voltage_V', 'Data_Status'] |
| Sampling interval | [1.0] min |
| Missing values | 0 |
| Duplicate rows | 0 |
| Data_Status column | ['Simulated/model-derived; OCV endpoints measured'] |

## Phases (segmented on current changes; sign convention: + = charge)
|   start_min |   end_min |   current_A |   soc_start |       soc_end |
|------------:|----------:|------------:|------------:|--------------:|
|           0 |       599 |        0.08 |           0 |  99.8333      |
|         600 |       659 |        0    |         100 | 100           |
|         660 |       960 |       -0.16 |         100 |   3.29847e-13 |

## Provenance findings
- OCV is an exact linear function of SOC: OCV = 0.001630*SOC% + 1.2060 V, max residual 4.4e-16 V.
- (V_terminal - OCV) / I = 0.030000 Ohm on every non-zero-current sample (std 0.0e+00): a fixed R0, with no polarization dynamics.
- Temperature is a smooth first-order curve with no sensor noise.
- The file labels itself "Simulated/model-derived; OCV endpoints measured".

**Classification: SIMULATED / MODEL-DERIVED.** Only the two OCV endpoints
(1.206 V and 1.369 V) are stated to be measured. This file cannot calibrate or validate a Ni-Cd model:
fitting would just recover the generator's own parameters (R0 = 0.03 Ohm, linear OCV), so any match would be circular.

Approval status: **REJECTED as experimental reference**. It can be kept as a SIMULATED regression fixture.
