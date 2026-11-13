%% RUN_LIION_DRIVECYCLE_VALIDATION
% Independent dynamic validation, CALCE INR18650-20R (LiNiMnCo/graphite, 2000 mAh rated - CALCE data page).
%   OCV:        cell SP1, C/20 pseudo-OCV                      (calibration)
%   Dynamics:   cell SP2, DST from 50 % and 80 % SOC            (calibration)
%   Model order: cell SP2, FUDS 50 % and 80 %                   (validation / selection)
%   Final test: cell SP2, US06 and BJDST 50 % and 80 %          (scored once, never used for fitting or selection)
%   OCV check:  cell SP3, C/20 pseudo-OCV vs the SP1 curve      (independent cell)
% No file is used in more than one role. All tests are at 25 C; no temperature channel is logged.
here = fileparts(mfilename('fullpath')); addpath(here);
raw = fullfile(userpath, "battery_platform", "data", "raw", "CALCE_INR18650-20R");
bp_fetch_calce(raw);
out = fullfile(here, "results", "drivecycle_" + string(datetime('now', 'Format', 'yyyyMMdd_HHmmss'))); mkdir(out);

%% OCV (SP1) and its independent check (SP3)
[D1, Q1] = bp_import_calce(find1(raw, "*SP20-1.xlsx"));
O1 = bp_pocv(D1, 3, 5, 2);   % top of table anchored to the measured 2 h rest after the CV charge (step 2)
O3 = bp_pocv(bp_calce_read(find1(raw, "*SP20-3.xls")), 6, 8);

%% SP2 1C capacity (separate test)
Dc = bp_calce_read(find1(raw, "*Initial capacity_SP20-2.xls"));
Q2_1C = -trapz(Dc.t_s(Dc.step == 6), Dc.I_A(Dc.step == 6)) / 3600;

%% Baseline: parameters from the SP1 C/20 test only (same code as RUN_LIION_CALIBRATION_VALIDATION)
cfg.R_train_events = ["2to3", "5to6"];
C1 = bp_calibrate_calce(D1, cfg);
base = [C1.R_fast_ohm, O1.Q_Ah, C1.rc.R1_ohm, C1.rc.tau1_s, C1.rc.R2_ohm, C1.rc.tau2_s];

%% Calibrate / select / test
sets.train = {prep(raw, "*SP20-2_DST_50SOC.xls"), prep(raw, "*SP20-2_DST_80SOC.xls")};
sets.val = {prep(raw, "*SP20-2_FUDS_50SOC.xls"), prep(raw, "*SP20-2_FUDS_80SOC.xls")};
sets.test = {prep(raw, "*SP20-2_US06_50SOC.xls"), prep(raw, "*SP20-2_US06_80SOC.xls"), ...
             prep(raw, "*SP20-2_BJDST_50SOC.xls"), prep(raw, "*SP20-2_BJDST_80SOC.xls")};
R = bp_drivecycle_validate(sets, O1, base);

%% Final OCV table, independent OCV check (SP3) and rest voltage after full charge (not part of any fit)
sel = R.selected;
if sel.hyst, Mv = sel.p(3 + 2*sel.nrc); else, Mv = 0; end
ocv_final = bp_ocv_table(O1, Mv);
meas = O3.soc <= min(O1.z_end, O3.soc(find(~isnan(O3.V_chg), 1, 'last')));   % both charge branches measured
ocv_check = bp_metrics(1000 * O3.ocv(meas), 1000 * ocv_final(meas));   % extrapolated tops excluded
rest = struct('file', {}, 'err_mV', {});
for D = [sets.val sets.test]
    Dk = D{1}; Vh = bp_ecm_sim(sel.p, Dk, sel.nrc, sel.hyst, O1); m = find(Dk.step == 4, 1, 'last');
    rest(end+1) = struct('file', string(Dk.Properties.Description), 'err_mV', 1000 * (Vh(m) - Dk.V(m))); %#ok<SAGROW>
end

%% Records, acceptance against the previously approved model
names = ["R0_ohm" "Q_Ah" "R1_ohm" "tau1_s" "R2_ohm" "tau2_s" "M_V" "gamma"];
pn = names([1:2+2*sel.nrc, 7:6+2*sel.hyst]);
prev = dir(fullfile(here, "results", "drivecycle_*", "drivecycle_validation_summary.json"));
prev = prev(~startsWith(string({prev.folder}), out));
version = numel(prev) + 1;
model = struct('id', "LIION_INR18650-20R_ECM_" + sel.nrc + "RC" + string(repmat('_H', 1, double(sel.hyst))) + "_v" + version, ...
    'params', cell2struct(num2cell(sel.p(:)), cellstr(pn), 1), ...
    'ocv_source', "SP1 C/20 pseudo-OCV (CALCULATED); top anchored to measured 2 h rest after CV", 'ocv_method', "anchored_top", ...
    'calibration', "SP2 DST 50/80 % (lsqnonlin, bounded)", ...
    'selection', "SP2 FUDS 50/80 %", 'test', "SP2 US06 + BJDST 50/80 %", 'temperature', "25 C nominal; not logged", ...
    'status', "PENDING", 'approval', "PENDING");
thr_test_RMSE_mV = 25;   % editable engineering default: about 0.6 % of the 3.6 V nominal, scored over V > 3.0 V
model.status = string(ifelse(max([R.test.RMSE]) <= thr_test_RMSE_mV, "VALIDATED", "NEEDS IMPROVEMENT")) + ...
    sprintf(" (worst test RMSE %.1f mV vs %.0f mV threshold)", max([R.test.RMSE]), thr_test_RMSE_mV);
% Acceptance: candidate must not be worse on the validation set (FUDS) than the newest approved model (+0.1 mV tolerance)
% and must itself be VALIDATED. The test set is reported, never used to choose.
ok_prev = true; prev_txt = "no previous model";
if ~isempty(prev)
    [~, j] = max([prev.datenum]); PS = jsondecode(fileread(fullfile(prev(j).folder, prev(j).name)));
    pv = min([PS.candidates.val_RMSE_mV]);
    ok_prev = sel.val_RMSE_mV <= pv + 0.1;
    prev_txt = sprintf("%s val RMSE %.3f mV vs candidate %.3f mV", PS.model.id, pv, sel.val_RMSE_mV);
end
model.approval = string(ifelse(ok_prev && startsWith(model.status, "VALIDATED"), "APPROVED", "REJECTED")) + " - " + prev_txt;
summary = struct('generated', string(datetime('now')), 'model', model, 'ocv_SP3_vs_SP1_mV', ocv_check, ...
    'Q_C20_SP1_Ah', O1.Q_Ah, 'Q_C20_SP3_Ah', O3.Q_Ah, 'Q_1C_SP2_Ah', Q2_1C, 'calce_SP1_quality', Q1, ...
    'candidates', rmfield(R.candidates, ["x0"]), 'test', R.test, 'baseline_SP1_C20_params', R.baseline, ...
    'full_charge_rest_error', rest, 'ocv_table', struct('soc', O1.soc, 'ocv', ocv_final), ...
    'unknown', ["thermal parameters (no temperature logged)", "behaviour at 0 C / 45 C (files not used yet)", "ageing"]);
writelines(jsonencode(summary, 'PrettyPrint', true), fullfile(out, "drivecycle_validation_summary.json"));
writetable(R.test_bands, fullfile(out, "test_error_by_soc.csv"));

%% Figure (saved only; not displayed)
D = sets.test{2}; [Vh, z] = bp_ecm_sim(sel.p, D, sel.nrc, sel.hyst, O1);
f = figure('Visible', 'off', 'Position', [0 0 1200 800]); tiledlayout(3, 1);
nexttile; plot((D.t_s - D.t_s(1)) / 3600, [D.V Vh]); grid on; ylabel("V");
legend("measured", "model", 'Location', 'southwest'); title("TEST (unseen): " + D.Properties.Description);
nexttile; plot((D.t_s - D.t_s(1)) / 3600, 1000 * (Vh - D.V)); grid on; ylabel("model - measured (mV)"); ylim([-100 100]);
nexttile; plot((D.t_s - D.t_s(1)) / 3600, -D.I_A); grid on; ylabel("discharge current (A)"); xlabel("h");
exportgraphics(f, fullfile(out, "test_overlay_US06_80SOC.png"), 'Resolution', 110); close(f);

%% Console report
fprintf("\n=== Drive-cycle validation -> %s\n", out);
fprintf("Q: SP1 C/20 %.4f Ah | SP3 C/20 %.4f Ah | SP2 1C %.4f Ah\n", O1.Q_Ah, O3.Q_Ah, Q2_1C);
fprintf("OCV SP3 vs SP1: MAE %.2f RMSE %.2f MaxAE %.2f Bias %+.2f mV (SP1 top points extrapolated: %d)\n", ...
    ocv_check.MAE, ocv_check.RMSE, ocv_check.MaxAE, ocv_check.Bias, O1.extrapolated_points);
for c = R.candidates
    fprintf("cand %dRC hyst=%d: train %.2f mV, val %.2f mV, p=%s, at-bound=%s\n", c.nrc, c.hyst, ...
        c.train_RMSE_mV, c.val_RMSE_mV, mat2str(c.p, 4), mat2str(c.at_bound));
end
fprintf("SELECTED %dRC hyst=%d\n", sel.nrc, sel.hyst);
for s = R.test, fprintf("  TEST %-12s MAE %6.2f RMSE %6.2f MaxAE %7.2f Bias %+6.2f mV (N=%d)\n", s.name, s.MAE, s.RMSE, s.MaxAE, s.Bias, s.N); end
for s = R.baseline, fprintf("  BASELINE SP1-C/20 params %-12s RMSE %7.2f mV\n", s.name, s.RMSE); end
disp(R.test_bands); disp(model.status)
fprintf("OCV(1) = %.4f V; rest after full charge, model - measured (mV): %s\n", ocv_final(end), mat2str(round([rest.err_mV], 1)));
fprintf("%s: %s\n", model.id, model.approval);

function p = find1(raw, pat)
d = dir(fullfile(raw, "**", pat));
assert(numel(d) == 1, "Expected one file for %s, found %d", pat, numel(d));
p = fullfile(d.folder, d.name);
end

function D = prep(raw, pat)
D = bp_calce_read(find1(raw, pat));
D = D(find(D.step == 4, 1):end, :);   % first sample after the CC-CV charge: SOC = 1 by test definition
D.Properties.Description = erase(pat, ["*SP20-2_", ".xls"]);
end

function y = ifelse(c, a, b), if c, y = a; else, y = b; end, end
