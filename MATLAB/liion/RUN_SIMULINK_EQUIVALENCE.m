%% RUN_SIMULINK_EQUIVALENCE
% MULTI_CHEMISTRY_BATTERY_LAB.slx (continuous-time, ode23t) must reproduce the validated MATLAB ECM (bp_ecm_sim, exact ZOH)
% on the unseen CALCE test cycles, and must score the same against the measurements.
here = fileparts(mfilename('fullpath')); addpath(here);
root = fullfile(userpath, "battery_platform");
slx_dir = fullfile(root, "simulink"); if ~isfolder(slx_dir), mkdir(slx_dir); end
mdl = bp_build_slx(slx_dir);
raw = fullfile(root, "data", "raw", "CALCE_INR18650-20R");
thr.eq_RMSE_mV = 0.5; thr.eq_MaxAE_mV = 2;   % editable: Simulink vs MATLAB agreement required

% Parameters: newest drive-cycle validation run (generators off)
[P, info] = bp_liion_params(here, raw);
p = [P.R0 P.Q P.R1 P.tau1 P.R2 P.tau2 P.M P.gam];
O1 = struct('soc', P.soc_bp, 'ocv', P.ocv_tab);

tests = ["US06_50SOC", "US06_80SOC", "BJDST_50SOC", "BJDST_80SOC"];
for k = 1:numel(tests)
    D = bp_calce_read(bp_find1(raw, "*SP20-2_" + tests(k) + ".xls"));
    D = D(find(D.step == 4, 1):end, :);
    Vm = bp_ecm_sim(p, D, 2, true, O1);
    in = Simulink.SimulationInput(mdl);
    in = in.setVariable('P', P);
    in = in.setVariable('I_in', timeseries(-D.I_A, D.t_s));
    in = in.setVariable('t_out', D.t_s);
    in = in.setModelParameter('StartTime', sprintf('%.17g', D.t_s(1)), 'StopTime', sprintf('%.17g', D.t_s(end)));   % full precision: output times must lie inside
    tic; out = sim(in); el = toc;
    y = out.yout.get(1).Values;
    Vs = interp1(y.Time, y.Data(:), D.t_s);   % output times are the data times; interp1 guards against any extra points
    m = D.step >= 7 & D.V > 3.0;
    E(k) = struct('test', tests(k), 'sim_seconds', el, 'eq', bp_metrics(1000 * Vm, 1000 * Vs), ...
        'simulink_vs_measured', bp_metrics(1000 * D.V(m), 1000 * Vs(m)), ...
        'matlab_vs_measured', bp_metrics(1000 * D.V(m), 1000 * Vm(m))); %#ok<SAGROW>
end
ok = all(arrayfun(@(e) e.eq.RMSE <= thr.eq_RMSE_mV && e.eq.MaxAE <= thr.eq_MaxAE_mV, E));
status = ifelse(ok, "EQUIVALENT - Simulink reproduces the validated MATLAB model", "NOT EQUIVALENT - investigate");
out_dir = fullfile(here, "results", "simulink_eq_" + string(datetime('now', 'Format', 'yyyyMMdd_HHmmss'))); mkdir(out_dir);
writelines(jsonencode(struct('model', fullfile(slx_dir, mdl + ".slx"), 'params_from', info.params_from, 'thresholds', thr, ...
    'results', E, 'status', status), 'PrettyPrint', true), fullfile(out_dir, "simulink_equivalence.json"));

fprintf("\n=== Simulink equivalence -> %s\n", out_dir);
for e = E
    fprintf("%-12s sim %5.1f s | SL vs ML: RMSE %.4f MaxAE %.4f mV | SL vs meas RMSE %.2f MAE %.2f | ML vs meas RMSE %.2f MAE %.2f mV\n", ...
        e.test, e.sim_seconds, e.eq.RMSE, e.eq.MaxAE, e.simulink_vs_measured.RMSE, e.simulink_vs_measured.MAE, ...
        e.matlab_vs_measured.RMSE, e.matlab_vs_measured.MAE);
end
disp(status)

function y = ifelse(c, a, b), if c, y = a; else, y = b; end, end
