%% RUN_LIION_CALIBRATION_VALIDATION
% Phases 3/6/7 for Li-ion. CALCE INR18650-20R = primary calibration; Panasonic NCR18650B = held-out-cell
% validation. The two datasets are processed separately and never pooled.
here = fileparts(mfilename('fullpath')); addpath(here);
cfg.calce_file = fullfile(userpath, "battery_baseline/data/CALCE/11_5_2015_low current OCV test_SP20-1.xlsx");
cfg.pana_file = fullfile(userpath, "Panasonic_NCR18650B_Consolidated.mat");
cfg.seed = 20261112;
cfg.R_train_events = ["2to3", "5to6"];   % held-out events: 1to2, 4to5
% Acceptance thresholds: editable engineering defaults, not taken from any standard
cfg.thr.R_event_err_mV = 3;   % 1 mV voltage resolution -> about +/-2 mV noise on a single jump
cfg.thr.ocv_MAE_mV = 10;
cfg.thr.pulse_RMSE_mV = 2;
out = fullfile(here, "results", string(datetime('now', 'Format', 'yyyyMMdd_HHmmss'))); mkdir(out);

[D, Q] = bp_import_calce(cfg.calce_file);
C = bp_calibrate_calce(D, cfg);
P = bp_validate_panasonic(cfg.pana_file, cfg.seed);

%% Verdicts (held-out data only)
S = struct(); X = struct();   % script runs in the base workspace; never reuse stale variables
te = C.events([C.events.role] == "test");
S.calce_R_fast = verdict(max(abs([te.err_mV])), cfg.thr.R_event_err_mV);
S.calce_RC = C.rc.status;
S.calce_pocv = "CALCULATED from measurements - no independent OCV test for this cell";
S.pana_ocv_test = verdict(1000 * mean([P.ocv.test.MAE]), cfg.thr.ocv_MAE_mV);
for dirn = ["positive", "negative"]
    S.("pana_pulse_" + dirn) = verdict(1000 * mean([P.pulse.(dirn).test.RMSE]), cfg.thr.pulse_RMSE_mV);
end
% Cross-cell comparison only: a CALCE (Samsung) OCV is not expected to match a Panasonic cell
calce_on_pana = interp1(C.soc, C.pocv, P.soc);
X.calce_ocv_vs_pana_test_MAE_mV = 1000 * mean(arrayfun(@(k) mean(abs(calce_on_pana - P.ocv_cells(:, k)), 'omitnan'), P.split.test));

%% Saved records
mv = @(m) structfun(@(x) x, rmfield(m, 'N'))' .* [1000 1000 1000 1000 1];   % MAE RMSE MaxAE Bias in mV, R2
summary = struct('generated', string(datetime('now')), 'cfg', cfg, 'calce_quality', Q, ...
    'calce', rmfield(C, ["soc" "V_dis" "V_chg" "pocv" "half_gap" "relax_t" "relax_v" "relax_fit"]), ...
    'pana_split', P.split, ...
    'pana_ocv_val_mV', mean(cell2mat(arrayfun(mv, P.ocv.val, 'UniformOutput', false)'), 1), ...
    'pana_ocv_test_mV', mean(cell2mat(arrayfun(mv, P.ocv.test, 'UniformOutput', false)'), 1), ...
    'pana_pulse_pos', rmfield(P.pulse.positive, "events"), 'pana_pulse_neg', rmfield(P.pulse.negative, "events"), ...
    'cross_cell', X, 'status', S, ...
    'metric_order', "MAE RMSE MaxAE Bias (mV), R2", ...
    'chemistry', struct('calce', "UNVERIFIED in file; battery_baseline README states Samsung INR18650-20R NMC/graphite 2.0 Ah", ...
                        'panasonic', "Panasonic NCR18650B per file metadata; chemistry not stated -> UNVERIFIED"), ...
    'unknown', ["thermal R_th/C_th (no temperature data)", "Panasonic pulse current (R in ohms)", "SOH/ageing (no cycling)"]);
writelines(jsonencode(summary, 'PrettyPrint', true), fullfile(out, "liion_validation_summary.json"));
writetable(struct2table(C.events), fullfile(out, "calce_R_events.csv"));
writetable(table(C.soc, C.V_dis, C.V_chg, C.pocv, C.half_gap, 'VariableNames', ...
    ["soc", "V_dis", "V_chg", "pocv", "half_gap"]), fullfile(out, "calce_ocv_soc.csv"));

%% Figures
f = figure('Visible', 'off', 'Position', [0 0 1200 800]);
tiledlayout(2, 2);
nexttile; plot(C.soc, [C.V_dis C.V_chg C.pocv]); grid on;
legend("C/20 discharge", "C/20 charge", "pseudo-OCV", 'Location', 'southeast');
xlabel("SOC"); ylabel("V"); title(sprintf("CALCE: Q_{dis} = %.3f Ah (measured current)", C.Q_dis_Ah));
nexttile; yyaxis left; plot(C.relax_t, C.relax_v, '.', C.relax_t, C.relax_fit, '-'); ylabel("V");
yyaxis right; plot(C.relax_t, 1000 * (C.relax_fit - C.relax_v)); ylabel("residual mV");
xlabel("s after charge end"); title("CALCE step-6 relaxation, 2-RC fit (in-sample)"); grid on;
nexttile; k = P.split.test;
plot(P.soc, 1000 * (P.ocv_model - P.ocv_cells(:, k))); grid on;
xlabel("SOC"); ylabel("model - measured (mV)");
title(sprintf("Panasonic OCV, %d held-out test cells", numel(k)));
nexttile; e = P.pulse.positive.events(k(1)); th = P.pulse.positive.selected.theta;
kk = th(1:2:end); tau = exp(th(2:2:end));
semilogx(e.t, e.v, '.', e.t, e.Va + e.J * sum(kk .* (1 - exp(-e.t ./ tau)), 2), '-'); grid on;
xlabel("s after pulse end"); ylabel("V");
title(sprintf("Panasonic +pulse relaxation, test cell %d (%d-RC)", k(1), P.pulse.positive.selected.nrc));
legend("measured", "predicted");
exportgraphics(f, fullfile(out, "liion_validation.png"), 'Resolution', 110);

%% Console report
fprintf("\n=== Li-ion calibration/validation -> %s\n", out);
fprintf("CALCE quality: rows %d, missing V/I/T %d/%d/%d, dup %d, nonmono t %d, dt med %.2f max %.0f s\n", ...
    Q.rows, Q.missing_V, Q.missing_I, Q.missing_T, Q.duplicate_rows, Q.nonmonotonic_time, Q.dt_median_s, Q.dt_max_s);
fprintf("CALCE Q_dis %.4f Ah  Q_chg %.4f Ah  I_dis %.4f A  I_chg %.4f A\n", C.Q_dis_Ah, C.Q_chg_Ah, C.I_dis_mean_A, C.I_chg_mean_A);
for e = C.events, fprintf("  event %-5s %-5s dI %+.4f A dV %+.4f V R_app %.4f ohm err %+.2f mV\n", e.name, e.role, e.dI_A, e.dV_V, e.R_app_ohm, e.err_mV); end
fprintf("CALCE R_fast %.4f ohm | RC: R1 %.4f tau1 %.1f s, R2 %.4f tau2 %.0f s, fit RMSE %.2f mV\n", ...
    C.R_fast_ohm, C.rc.R1_ohm, C.rc.tau1_s, C.rc.R2_ohm, C.rc.tau2_s, 1000 * C.rc.fit.RMSE);
fprintf("Pana OCV  val  [MAE RMSE MaxAE Bias mV, R2]: %s\n", mat2str(summary.pana_ocv_val_mV, 4));
fprintf("Pana OCV  test [MAE RMSE MaxAE Bias mV, R2]: %s\n", mat2str(summary.pana_ocv_test_mV, 4));
for dirn = ["positive", "negative"]
    pp = P.pulse.(dirn);
    fprintf("Pana pulse %s: val RMSE 1RC %.3f / 2RC %.3f mV -> %d-RC; TEST RMSE %.3f mV, MaxAE %.3f mV, theta %s\n", dirn, ...
        pp.candidates(1).val_RMSE_mV, pp.candidates(2).val_RMSE_mV, pp.selected.nrc, ...
        1000 * mean([pp.test.RMSE]), 1000 * max([pp.test.MaxAE]), mat2str(pp.selected.theta, 4));
end
fprintf("Cross-cell (comparison only): CALCE OCV vs Panasonic test cells MAE %.1f mV\n", X.calce_ocv_vs_pana_test_MAE_mV);
disp(S)

function s = verdict(x, thr)
if x <= thr, s = sprintf("VALIDATED (%.3g <= %.3g)", x, thr); else, s = sprintf("NEEDS IMPROVEMENT (%.3g > %.3g)", x, thr); end
end
