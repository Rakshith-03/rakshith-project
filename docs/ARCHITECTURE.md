# Architecture

```
 Experimental data (MEASURED)                MATLAB Online R2026b (reference physics engine)
 ├─ CALCE INR18650-20R SP1/SP2/SP3 (25 C)  ─► bp_* scripts: import, pseudo-OCV, calibration (DST),
 ├─ Panasonic NCR18650B, 92 cells             selection (FUDS), one-time test (US06/BJDST), acceptance
 └─ Ni-Cd file: SIMULATED, rejected           MULTI_CHEMISTRY_BATTERY_LAB.slx (ECM + generator + thermal)
                                                       │ approved parameters (DATA/MODELS/*.json)
                                                       ▼
 backend/bp (Python, FastAPI) ── equivalence-tested port of the approved model (tests/test_equivalence.py)
   model.py        ECM 2RC + hysteresis, PROVISIONAL thermal, Stepper (closed loop), Ni-Cd PROVISIONAL model
   generators.py   pulse (I_pulse = total current), ripple (sine/square/triangle), step, drive-cycle loads
   constraints.py  chemistry limits with sources, monitor, predictive moderator (requested vs permitted, logged)
   bms.py          coulomb counting, EKF SOC, capacity SOH, apparent-resistance indicator, SOP
   charging.py     CC-CV, fixed, adaptive receding-horizon with feasibility, Ni-Cd CC + termination
   pack.py         per-cell series pack, passive/active balancing (SIMULATED)
   ml.py           SOC regressor (split by file) + Panasonic anomaly screen, registry with acceptance rule
   learning.py     error analysis -> recalibration (train) -> validation -> test once -> approve/reject, rollback
   experiments.py  profiles (validated, versioned), experiment execution, characterization, persistence
   live.py         live sessions: changes apply at the next step boundary
   reports.py      experiment HTML/CSV reports, technical report
   db.py           SQLite (DATA/DATABASE/platform.sqlite), 28 tables, provenance on every row
   api.py          44 routes (docs/openapi.json); serves the dashboard (static/index.html)
                                                       │ HTTP only
                                                       ▼
 n8n (11 workflows, n8n/workflows) ── orchestration only: webhooks -> backend calls with retries,
                                       idempotency keys, error branch -> /api/errors, execution records.
                                       Never in the control loop; no physics; base URL from $env.BP_API_URL.
```

## Why the backend has a Python port of the model
MATLAB is available only as MATLAB Online, which a local backend cannot call (no Engine API). So:
1. Calibration, validation and Simulink runs happen in MATLAB.
2. The approved parameters are exported to `DATA/MODELS/<id>.json`.
3. The backend uses an equivalence-tested Python port. `tests/test_equivalence.py` requires it to reproduce the MATLAB
   OCV table (within 2 µV) and the MATLAB test metrics on all four unseen drive cycles (within 0.02 mV).

If a local MATLAB installation becomes available, `simulate()` can be swapped for a MATLAB Engine call behind the same interface.

## Data separation
| Category | Where |
|---|---|
| Original measurements | `DATA/RAW_REFERENCE/...` (zips unchanged, SHA-256 recorded), root-level user files |
| Parsed copies | `DATA/PROCESSED/calce_npz` (with source path) |
| Simulated outputs | DB `time_series_data.source_type = SIMULATED (...)`, experiment `label` |
| Estimated parameters | `DATA/MODELS/*.json` (approval, provenance, metrics) |
| Predictions | `DATA/MODELS/ml/*.json` (+ `.joblib` only for approved models) |

## Control-loop rule
Moderation (`constraints.run_moderated`, `live.LiveSession`) runs in the backend at the simulation step.
n8n only triggers and records non-real-time jobs.
