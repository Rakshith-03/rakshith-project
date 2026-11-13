function [P, info] = bp_liion_params(here, raw)
%BP_LIION_PARAMS Workspace struct P for MULTI_CHEMISTRY_BATTERY_LAB, from the newest validated drive-cycle run.
% Generators default to OFF. Thermal parameters are PROVISIONAL (no temperature data exists to calibrate them).
d = dir(fullfile(here, "results", "drivecycle_*", "drivecycle_validation_summary.json"));
[~, order] = sort([d.datenum], 'descend');
S = [];
for i = order   % newest APPROVED model (v1 predates the approval field and counts as approved)
    Si = jsondecode(fileread(fullfile(d(i).folder, d(i).name)));
    if ~isfield(Si.model, 'approval') || startsWith(Si.model.approval, "APPROVED"), S = Si; break; end
end
assert(~isempty(S), "No approved Li-ion model found");
mp = S.model.params;
assert(all(isfield(mp, ["R2_ohm" "M_V"])), "Simulink model implements 2RC + hysteresis; selected model is %s", S.model.id);
D1 = bp_import_calce(bp_find1(raw, "*SP20-1.xlsx"));
if isfield(S.model, 'ocv_method') && S.model.ocv_method == "anchored_top"
    O = bp_pocv(D1, 3, 5, 2); ocv = bp_ocv_table(O, mp.M_V);
else
    O = bp_pocv(D1, 3, 5); ocv = O.ocv;
end
P = struct('R0', mp.R0_ohm, 'Q', mp.Q_Ah, 'R1', mp.R1_ohm, 'tau1', mp.tau1_s, 'R2', mp.R2_ohm, 'tau2', mp.tau2_s, ...
    'M', mp.M_V, 'gam', mp.gamma, 'soc_bp', O.soc, 'ocv_tab', ocv, 'z0', 1, 'h0', 1, 'max_step', 1);
P.gen = struct('p_on', 0, 'p_base', 0, 'p_pulse', 0, 'p_dur', 1, 'p_interval', 2, 'p_start', 0, 'p_stop', 0, ...
               'r_on', 0, 'r_dc', 0, 'r_amp', 0, 'r_freq', 1, 'r_start', 0, 'r_stop', 0);
% C_th = 45 g (CALCE cell spec) x 1000 J/(kg K) (ASSUMED specific heat); R_th = 10 K/W (ASSUMED, still air)
P.th = struct('Rth', 10, 'Cth', 0.045 * 1000, 'Tamb', 25, 'T0', 25);
info = struct('model_id', S.model.id, 'params_from', string(d(i).folder), 'ocv', O, ...
    'thermal', "PROVISIONAL: C_th = 45 g (CALCE spec) x 1000 J/kg/K ASSUMED cp; R_th = 10 K/W ASSUMED; not calibrated");
end
