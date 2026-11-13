# Platform results (2026-11-12, overnight run)

## Tested (backend: 53/53 pytest passing, rerun 2026-11-12 after the n8n fixes)
- Python engine is equivalent to MATLAB v2: OCV table within 2 µV; test RMSE within 0.02 mV on US06/BJDST.
- Generators: the pulse value is the total current; ripple RMS is exact; dt is auto-reduced to <= 1/(20 f) when ripple is enabled.
- Predictive moderator (backend, not n8n): spec example base 2 A / pulse 4 A at 1.5 % SOC -> permitted 3.965 A; logged.
- Closed-loop auto moderation removes CRITICAL undervoltage.
- EKF on MEASURED CALCE test cycles, started 30 % SOC off: 0.76-1.94 % RMS after 10 min. With +50 mA sensor bias: end drift 0.08-0.40 % (coulomb counting: 4.6-7.5 %).
- Adaptive charging 20->80 %: 30 min INFEASIBLE (needs 2.48 A > 2.2 A validated cap; fastest is 33.8 min); 45 min feasible.
- Pack balancing (SIMULATED, 4S, 12 % SOC spread): passive -> 0.25 % (1.70 Wh burned); active -> 1.0 % (0.065 Wh).
- ML (experimental): SOC regressor test RMSE 6.9 % -> REJECTED by rule (EKF is better). Panasonic screen: 5/92 cells flagged (unsupervised, no accuracy claimed).
- Learning loop:
  - Error analysis (FUDS): weak region 0-10 % SOC (20.1 mV), +13.7 mV bias at 50-80 % SOC.
  - Candidates v3 (no gain), v4 (overfit, at bounds) and v5 (unsupported knots) were REJECTED.
  - v6 (v2 dynamics + OCV correction fitted on DST only, data-supported knots, bounded by the measured cell-to-cell spread) was APPROVED: val 8.82 vs 11.41 mV; test US06 14.12/15.26, BJDST 12.13/14.45 mV (v2: 15.36/16.87/14.76/15.92).
- Dashboard: 14 pages verified in the browser (experiment run, live charts, adaptive charging, validation overlay, EKF).
- n8n: 11 workflow JSONs; static checks pass (routes, error branches, retries, no credentials).

## Open
- Nothing open in software. Data limits remain: Ni-Cd and thermal stay PROVISIONAL until real measurements exist.

## Closed since
- n8n: all 11 workflows imported into n8n 2.42.6 (Docker), activated and triggered via webhook: 15/15 live checks PASS
  (`n8n/run_webhooks.py`, record in `docs/N8N.md`). The live run found 2 generator bugs (stray `}}` in expressions; respond
  after an IF false branch), now fixed and covered by the static test.
- v6 Simulink equivalence: after fixing the generator's line-break bug, RUN_V6_SIMULINK_CHECK.m passes. Simulink test RMSE is
  14.123 / 15.266 / 12.132 / 14.451 mV against Python 14.122 / 15.260 / 12.132 / 14.451 mV (max difference 0.0062 mV).
- Ni-Cd: PROVISIONAL only (no real data). Thermal: PROVISIONAL (no temperature data).
