# Multi-chemistry battery characterization and software BMS platform

A virtual BMS development platform, **not a certified battery controller**. Simulated data is always labelled as simulated.

## Status at a glance
| Part | Status |
|---|---|
| Li-ion INR18650-20R (NMC) model | **VALIDATED** (approved v6) on unseen CALCE drive cycles (US06/BJDST, 25 °C): RMSE 12.1–15.3 mV (v2: 14.8–16.9 mV); weak below 10 % SOC |
| Li-ion NCA / LFP | NOT SUPPORTED (no calibratable data) |
| Ni-Cd | **PROVISIONAL – NOT VALIDATED** (the only Ni-Cd file is simulated) |
| Thermal model | **PROVISIONAL** (no temperature measurements available) |
| Simulink model | Electrical core + generators + thermal, equivalent to MATLAB (≤ 0.014 mV RMSE; v6 vs Python ≤ 0.0062 mV) |
| Python engine | Equivalent to the MATLAB model (≤ 0.02 mV on test metrics) |
| n8n | 11 workflows, running in n8n 2.42.6 (Docker); live webhook test 15/15 PASS (see `docs/N8N.md`) |

## Install and run (Windows)
```
python -m pip install --user fastapi uvicorn scikit-learn httpx pytest numpy pandas scipy openpyxl matplotlib
cd backend
python -m pytest -q                       # full test suite
python -m uvicorn bp.api:app --port 8000  # dashboard at http://127.0.0.1:8000/
```
The raw CALCE files must be under `DATA/RAW_REFERENCE/LITHIUM_ION/CALCE_INR18650-20R/` (see `PROVENANCE.md` there).
Running `POST /api/datasets/{id}/fetch` downloads a missing allow-listed file.

MATLAB side (MATLAB Online, `MATLAB Drive/battery_platform/liion/`):
`RUN_LIION_CALIBRATION_VALIDATION`, `RUN_LIION_DRIVECYCLE_VALIDATION`, `RUN_SIMULINK_EQUIVALENCE`, `RUN_GENERATORS_THERMAL_CONSTRAINTS`.
The sources are in `MATLAB/liion/`.

n8n: see `docs/N8N.md`.

## Documents
- `docs/BATTERY_LAB_EXPLAINED.pdf`: the whole project explained simply, how to run it, how to change it, troubleshooting (rebuild: `python tools/make_guide.py`)
- `docs/ARCHITECTURE.md`: components and data flow
- `docs/API.md`, `docs/openapi.json`: API reference
- `docs/N8N.md`: workflow setup and test record
- `DATA/REPORTS/`: dated inspection, validation and test reports; `DATA/REPORTS/platform_results.md` summarises them
- Technical report: `POST /api/reports/technical` -> `DATA/REPORTS/generated/TECHNICAL_REPORT.html`
- Demo video (3 min 25 s, narrated): `DATA/REPORTS/demo/BATTERY_PLATFORM_DEMO.mp4`. Re-record with backend + n8n running:
  `python -m pip install --user playwright piper-tts` + Piper voice `en_US-lessac-high` in `%LOCALAPPDATA%\piper-voices`, then `python tools/demo_video/make_video.py` (narration text in `tools/demo_video/scenes.py`)
