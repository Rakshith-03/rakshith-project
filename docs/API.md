# API reference

Generated from the running FastAPI app (`docs/openapi.json`; interactive docs at http://127.0.0.1:8000/docs).
Current sign convention: **I > 0 = discharge** (A, cell level unless stated). All simulated outputs carry a `label`/`source_type`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Index |
| GET | `/api/health` | Health |
| GET | `/api/chemistries` | Chemistries |
| GET | `/api/profiles` | List Profiles |
| POST | `/api/profiles` | Create Profile |
| GET | `/api/profiles/{pid}/versions` | Profile Versions |
| PUT | `/api/profiles/{pid}` | Update Profile |
| POST | `/api/profiles/{pid}/duplicate` | Duplicate Profile |
| GET | `/api/datasets` | Datasets |
| GET | `/api/datasets/sources` | Dataset Sources |
| POST | `/api/datasets/{did}/fetch` | Download a KNOWN dataset from its allow-listed public URL if it is missing locally (originals kept unchanged). |
| POST | `/api/datasets/{did}/clean` | Quality checks on the parsed copy (raw file untouched). CALCE drive-cycle/OCV files only. |
| GET | `/api/validation` | Validation |
| GET | `/api/validation/overlay/{name}` | Measured vs simulated voltage for an unseen CALCE test file (US06_50SOC, US06_80SOC, BJDST_50SOC, BJDST_80SOC). |
| POST | `/api/experiments` | Create Experiment |
| GET | `/api/experiments` | List Experiments |
| GET | `/api/experiments/{eid}` | Experiment |
| GET | `/api/experiments/{eid}/timeseries` | Experiment Ts |
| POST | `/api/experiments/{eid}/characterize` | Characterize Exp |
| POST | `/api/experiments/{eid}/diagnostics` | BMS diagnostics on a stored run: EKF SOC from its voltage/current, capacity SOH where valid, SOP at the end. |
| POST | `/api/experiments/{eid}/report` | Experiment Report |
| GET | `/api/files` | Get File |
| POST | `/api/moderate` | Evaluate one request: {profile_id, state:{soc,T}, request:{base_A, pulse_A, pulse_s, interval_s, horizon_s}}. |
| POST | `/api/live` | Live Start |
| POST | `/api/live/{sid}/step` | Live Step |
| POST | `/api/live/{sid}/update` | Live Update |
| POST | `/api/live/{sid}/{action}` | Live Action |
| POST | `/api/charging/optimize` | Charging Optimize |
| POST | `/api/bms/ekf_demo` | EKF on a MEASURED CALCE test file, starting from a wrong SOC. Reference SOC = coulomb counting (not independent). |
| POST | `/api/pack/balance` | Pack Balance |
| GET | `/api/ml/models` | Ml Models |
| POST | `/api/ml/train` | Ml Train |
| POST | `/api/campaigns` | Campaign |
| GET | `/api/campaigns` | Campaigns |
| GET | `/api/n8n/executions` | N8N Executions |
| POST | `/api/n8n/executions` | N8N Execution |
| GET | `/api/errors` | Recorded errors (diagnostic events with severity ERROR), newest first, max 200 |
| POST | `/api/errors` | Record Error |
| POST | `/api/reports/technical` | Tech Report |
| GET | `/api/reports` | List Reports |
| GET | `/api/learning/registry` | Learning Registry |
| GET | `/api/learning/error_analysis` | Learning Errors |
| POST | `/api/learning/recalibrate` | Long-running (~1-3 min): calibrates on TRAIN files, validates, tests once, registers APPROVED or REJECTED. |
| POST | `/api/learning/rollback` | Learning Rollback |
