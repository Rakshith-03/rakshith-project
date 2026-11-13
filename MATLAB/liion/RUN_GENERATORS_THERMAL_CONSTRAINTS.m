%% RUN_GENERATORS_THERMAL_CONSTRAINTS
% Tests for the Current_Generator and Thermal_Model subsystems and the offline constraint monitor.
%   T1  generators off: Simulink still reproduces the validated model on an unseen drive cycle
%   T2  pulse train equals I_base + (I_pulse - I_base) P(t) exactly, and the voltage matches bp_ecm_sim
%   T3  ripple equals I_dc + I_rip sin(2 pi f (t - t0)) exactly inside its window; RMS = I_rip / sqrt(2)
%   T4  ripple response: voltage amplitude is linear in ripple amplitude and matches the analytic impedance
%       |Z(jw)| = |R0 + sum R_i/(1 + jw tau_i) + (dOCV/dz)/(jw 3600 Q)|  (hysteresis off, M = 0, for a linear test)
%   T5  thermal: Q = I^2 (R0 + R1 + R2) at steady state and energy balance closes (model is PROVISIONAL)
%   T6  constraint monitor flags a STRESS TEST (6 A at 8 % SOC) and leaves a normal pulse test NORMAL
here = fileparts(mfilename('fullpath')); addpath(here);
root = fullfile(userpath, "battery_platform"); raw = fullfile(root, "data", "raw", "CALCE_INR18650-20R");
mdl = bp_build_slx(fullfile(root, "simulink"));
[P0, info] = bp_liion_params(here, raw);
Lim = bp_limits_liion();
pv = @(P) [P.R0 P.Q P.R1 P.tau1 P.R2 P.tau2 P.M P.gam];
Oc = struct('soc', P0.soc_bp, 'ocv', P0.ocv_tab);
R = struct('test', {}, 'pass', {}, 'detail', {});

%% T1 regression
D = bp_calce_read(bp_find1(raw, "*SP20-2_US06_80SOC.xls")); D = D(find(D.step == 4, 1):end, :);
y = simrun(mdl, P0, D.t_s, -D.I_A, D.t_s);
e = bp_metrics(1000 * bp_ecm_sim(pv(P0), D, 2, true, Oc), 1000 * y.V);
R(end+1) = rec("T1 generators off: US06 80 % equals validated model", e.RMSE <= 0.5 && e.MaxAE <= 2, ...
    sprintf("Simulink vs MATLAB RMSE %.4f mV, MaxAE %.4f mV", e.RMSE, e.MaxAE));
[E1, s1] = bp_constraints(y.t, y.V, y.I, nan(size(y.t)), y.z, Lim);   % T not measured in CALCE files

%% T2 pulse train (base 1 A, pulse 3 A total, 10 s every 60 s, 3 pulses from t = 100 s, SOC 0.8)
P = P0; P.z0 = 0.8; P.h0 = -1;
P.gen.p_on = 1; P.gen.p_base = 1; P.gen.p_pulse = 3; P.gen.p_dur = 10; P.gen.p_interval = 60; P.gen.p_start = 100;
N = 3; P.gen.p_stop = P.gen.p_start + N * P.gen.p_interval;
t = (0:0.25:600)';
y2 = simrun(mdl, P, [0 600], [0 0], t);
win = t >= P.gen.p_start & t < P.gen.p_stop;
inp = win & mod(t - P.gen.p_start, P.gen.p_interval) < P.gen.p_dur;
Iref = win .* (P.gen.p_base + (P.gen.p_pulse - P.gen.p_base) .* inp);
edge = abs(t - round(t)) < 1e-9 & ismember(round(t), [P.gen.p_start + (0:N) * P.gen.p_interval, ...
    P.gen.p_start + (0:N-1) * P.gen.p_interval + P.gen.p_dur]);   % switching instants: left/right value ambiguous
errI = max(abs(y2.I(~edge) - Iref(~edge)));
npulse = nnz(diff([0; inp]) == 1);
R(end+1) = rec("T2a pulse current = I_base + (I_pulse - I_base) P(t)", ...
    errI < 1e-9 && abs(max(y2.I) - 3) < 1e-12 && npulse == N, ...
    sprintf("max |I - I_ref| %.1e A off edges; peak %.4f A (total pulse current, not base + pulse); %d pulses", errI, max(y2.I), npulse));
Dref = table(t, zeros(size(t)), zeros(size(t)), -Iref, 'VariableNames', ["t_s" "step" "V" "I_A"]);
Vref = bp_ecm_sim(pv(P), Dref, 2, true, Oc, P.z0, P.h0);
e2 = bp_metrics(1000 * Vref(~edge), 1000 * y2.V(~edge));
R(end+1) = rec("T2b pulse response equals the validated MATLAB model", e2.RMSE <= 0.5 && e2.MaxAE <= 2, ...
    sprintf("RMSE %.4f mV, MaxAE %.4f mV; voltage swing %.1f mV", e2.RMSE, e2.MaxAE, 1000 * (max(y2.V) - min(y2.V))));
[E2, s2] = bp_constraints(y2.t, y2.V, y2.I, y2.T, y2.z, Lim);

%% T3 ripple (1 A DC + 0.5 A at 0.2 Hz from 50 s to 250 s)
P = P0; P.z0 = 0.8; P.h0 = -1; P.max_step = 0.05;
P.gen.r_on = 1; P.gen.r_dc = 1; P.gen.r_amp = 0.5; P.gen.r_freq = 0.2; P.gen.r_start = 50; P.gen.r_stop = 250;
t = (0:0.05:300)';
y3 = simrun(mdl, P, [0 300], [0 0], t);
win = t >= P.gen.r_start & t < P.gen.r_stop;
Iref = win .* (P.gen.r_dc + P.gen.r_amp * sin(2 * pi * P.gen.r_freq * (t - P.gen.r_start)));
ok = ~(abs(t - P.gen.r_start) < 1e-9 | abs(t - P.gen.r_stop) < 1e-9);
errI = max(abs(y3.I(ok) - Iref(ok)));
rip_rms = sqrt(mean((y3.I(win) - P.gen.r_dc).^2));
R(end+1) = rec("T3 ripple current = I_dc + I_rip sin(2 pi f t); RMS = I_rip/sqrt(2)", ...
    errI < 1e-9 && abs(rip_rms - P.gen.r_amp / sqrt(2)) < 1e-3, ...
    sprintf("max |I - I_ref| %.1e A; ripple RMS %.5f A (expected %.5f)", errI, rip_rms, P.gen.r_amp / sqrt(2)));

%% T4 ripple amplitude and frequency response (linear test: M = 0, zero-mean ripple, SOC 0.6)
f_list = [0.01 0.1 1]; a_list = [0.25 0.5 1.0];
k_ocv = interp1(P0.soc_bp, gradient(P0.ocv_tab, P0.soc_bp), 0.6);
Zan = @(f) abs(P0.R0 + P0.R1 ./ (1 + 1j * 2 * pi * f * P0.tau1) + P0.R2 ./ (1 + 1j * 2 * pi * f * P0.tau2) ...
    + k_ocv ./ (1j * 2 * pi * f * 3600 * P0.Q));
F = [];
for f = f_list
    for a = a_list
        if f ~= 0.1 && a ~= 0.5, continue; end   % amplitude sweep at 0.1 Hz, frequency sweep at 0.5 A
        P = P0; P.M = 0; P.z0 = 0.6; P.h0 = 0; P.max_step = min(1, 1 / (50 * f));
        Tend = 400 + 5 / f;
        P.gen.r_on = 1; P.gen.r_dc = 0; P.gen.r_amp = a; P.gen.r_freq = f; P.gen.r_start = 0; P.gen.r_stop = Tend + 1;
        t = (0:1 / (50 * f):Tend)';
        y4 = simrun(mdl, P, [0 Tend], [0 0], t);
        k = t >= Tend - 3 / f;                       % last 3 periods (RC transients have decayed: 400 s > 5 tau2)
        X = [ones(nnz(k), 1) t(k) sin(2 * pi * f * t(k)) cos(2 * pi * f * t(k))];
        c = X \ y4.V(k);                             % offset + linear drift + sinusoid
        F(end+1, :) = [f a hypot(c(3), c(4)) hypot(c(3), c(4)) / a Zan(f)]; %#ok<SAGROW>
    end
end
F = array2table(F, 'VariableNames', ["f_Hz" "amp_A" "V_amp_V" "Z_sim_ohm" "Z_analytic_ohm"]);
F.rel_err = F.Z_sim_ohm ./ F.Z_analytic_ohm - 1;
lin = F(F.f_Hz == 0.1, :);
R(end+1) = rec("T4a voltage ripple is linear in ripple amplitude (0.25/0.5/1 A at 0.1 Hz)", ...
    max(lin.Z_sim_ohm) / min(lin.Z_sim_ohm) - 1 < 1e-3, ...
    sprintf("V amplitude %s mV for %s A", mat2str(round(1000 * lin.V_amp_V', 3)), mat2str(lin.amp_A')));
R(end+1) = rec("T4b |Z| matches analytic impedance at 0.01/0.1/1 Hz", max(abs(F.rel_err)) < 0.01, ...
    sprintf("|Z| sim %s vs analytic %s ohm", mat2str(round(F.Z_sim_ohm', 5)), mat2str(round(F.Z_analytic_ohm', 5))));

%% T5 thermal (PROVISIONAL parameters): 2 A constant discharge for 3000 s from full
P = P0; P.gen.r_on = 1; P.gen.r_dc = 2; P.gen.r_amp = 0; P.gen.r_start = 0; P.gen.r_stop = 3001;
t = (0:1:3000)';
y5 = simrun(mdl, P, [0 3000], [0 0], t);
Qss = 2^2 * (P.R0 + P.R1 + P.R2);
eb = P.th.Cth * (y5.T(end) - P.th.T0) - (trapz(t, y5.Q) - trapz(t, (y5.T - P.th.Tamb) / P.th.Rth));
R(end+1) = rec("T5 thermal: Q -> I^2(R0+R1+R2); energy balance closes", ...
    abs(y5.Q(end) / Qss - 1) < 5e-3 && abs(eb) < 1e-3 * trapz(t, y5.Q), ...
    sprintf("Q_end %.4f W vs %.4f W; T_end %.2f degC (rise %.2f K, PROVISIONAL); energy residual %.2e J of %.1f J", ...
    y5.Q(end), Qss, y5.T(end), y5.T(end) - P.th.T0, eb, trapz(t, y5.Q)));

%% T6 constraint monitor
P = P0; P.z0 = 0.08; P.h0 = -1;   % STRESS TEST: beyond the validated envelope on purpose
P.gen.r_on = 1; P.gen.r_dc = 6; P.gen.r_amp = 0; P.gen.r_start = 10; P.gen.r_stop = 200;   % 6 A x 190 s = 0.32 Ah > ~0.17 Ah left
t = (0:0.5:200)';
y6 = simrun(mdl, P, [0 200], [0 0], t);
[E6, s6] = bp_constraints(y6.t, y6.V, y6.I, y6.T, y6.z, Lim);
sev = @(E, n) E.severity(E.constraint == n);
R(end+1) = rec("T6a STRESS TEST (6 A continuous from 8 % SOC, beyond available charge) flags undervoltage CRITICAL and current WARNING", ...
    sev(E6, "undervoltage") == "CRITICAL" && sev(E6, "discharge current") == "WARNING" && s6 == "CRITICAL", ...
    sprintf("overall %s; min V %.3f V at first critical t = %.1f s", s6, min(y6.V), E6.first_critical_s(E6.constraint == "undervoltage")));
R(end+1) = rec("T6b normal pulse test (T2) stays NORMAL", s2 == "NORMAL", "overall " + s2);

%% Save and report
out = fullfile(here, "results", "gen_thermal_" + string(datetime('now', 'Format', 'yyyyMMdd_HHmmss'))); mkdir(out);
writetable(struct2table(R), fullfile(out, "tests.csv"));
writetable(F, fullfile(out, "ripple_frequency_response.csv"));
writetable(E6, fullfile(out, "constraints_stress_test.csv"));
writetable(E1, fullfile(out, "constraints_US06_80SOC.csv"));
fig = figure('Visible', 'off', 'Position', [0 0 1200 900]); tiledlayout(3, 2);
nexttile; plot(y2.t, y2.I); grid on; ylabel("I (A)"); title("T2 pulse train (generator)");
nexttile; plot(y2.t, y2.V); grid on; ylabel("V"); title("T2 voltage response");
nexttile; plot(y3.t, y3.I); grid on; ylabel("I (A)"); title("T3 ripple 0.5 A @ 0.2 Hz on 1 A");
nexttile; plot(y3.t, y3.V); grid on; ylabel("V"); title("T3 voltage response");
nexttile; plot(y5.t, y5.T); grid on; ylabel("T (degC)"); xlabel("s"); title("T5 2 A discharge, PROVISIONAL thermal");
nexttile; plot(y6.t, y6.V); yline(Lim.V_crit_lo, 'r--'); grid on; ylabel("V"); xlabel("s"); title("T6 STRESS TEST, undervoltage");
exportgraphics(fig, fullfile(out, "generators_thermal.png"), 'Resolution', 100); close(fig);
writelines(jsonencode(struct('model_id', info.model_id, 'thermal', info.thermal, 'tests', R, ...
    'limits', Lim, 'all_pass', all([R.pass])), 'PrettyPrint', true), fullfile(out, "summary.json"));

fprintf("\n=== Generators / thermal / constraints -> %s\n", out);
for r = R, fprintf("[%s] %s\n       %s\n", ifelse(r.pass, "PASS", "FAIL"), r.test, r.detail); end
disp(F); disp(E6(:, ["constraint" "severity" "n_warning" "n_critical" "worst"]));
fprintf("US06 80 %% (validated profile) overall constraint severity: %s\n", s1);
fprintf("ALL PASS: %d\n", all([R.pass]));

function r = rec(name, pass, detail), r = struct('test', string(name), 'pass', logical(pass), 'detail', string(detail)); end
function y = ifelse(c, a, b), if c, y = a; else, y = b; end, end
function y = simrun(mdl, P, tI, I, tout)
in = Simulink.SimulationInput(mdl);
in = in.setVariable('P', P);
in = in.setVariable('I_in', timeseries(I(:), tI(:)));
in = in.setVariable('t_out', tout(:));
in = in.setModelParameter('StartTime', sprintf('%.17g', tout(1)), 'StopTime', sprintf('%.17g', tout(end)));
out = sim(in);
g = @(k) get1(out.yout.get(k).Values, tout);
y = struct('t', tout(:), 'V', g(1), 'z', g(2), 'h', g(3), 'I', g(4), 'T', g(5), 'Q', g(6));
end
function v = get1(ts, tout)
[tt, iu] = unique(ts.Time, 'last');
d = ts.Data(:); v = interp1(tt, d(iu), tout(:));
end
