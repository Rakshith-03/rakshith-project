function C = bp_calibrate_calce(D, cfg)
%BP_CALIBRATE_CALCE Extract Li-ion parameters from the CALCE C/20 OCV test, with an event-level holdout.
% Test steps: 1 CV top-off, 2 rest, 3 CC discharge to 2.5 V, 4 rest, 5 CC charge, 6 rest.
st = D.step;
d = D(st == 3, :); c = D(st == 5, :);

% Capacity (CALCULATED from measured current)
C.Q_dis_Ah = -trapz(d.t_s, d.I_A) / 3600;
C.Q_chg_Ah = trapz(c.t_s, c.I_A) / 3600;
C.I_dis_mean_A = mean(d.I_A); C.I_chg_mean_A = mean(c.I_A);

% Pseudo-OCV: discharge starts full (after CV top-off and rest); charge starts at the 2.5 V cutoff
socd = 1 + cumtrapz(d.t_s, d.I_A) / 3600 / C.Q_dis_Ah;
socc = cumtrapz(c.t_s, c.I_A) / 3600 / C.Q_dis_Ah;
C.soc = linspace(0, 1, 201)';
C.V_dis = branch(socd, d.V, C.soc);
C.V_chg = branch(socc, c.V, C.soc);
C.pocv = (C.V_dis + C.V_chg) / 2;       % NaN where the charge branch did not reach
C.half_gap = (C.V_chg - C.V_dis) / 2;   % hysteresis + C/20 IR drop; this test cannot separate them

% Apparent fast resistance at each current step (1-2 s window, 1 s sampling -> not pure ohmic R0)
names = ["1to2", "2to3", "4to5", "5to6"]; from = [1 2 4 5];
for k = 1:4
    i1 = find(st == from(k) + 1, 1);
    j = i1;
    while abs(D.I_A(j) - D.I_A(i1 + 3)) > 0.01, j = j + 1; end   % skip a sample taken mid-transition
    E(k) = struct('name', names(k), 'dI_A', D.I_A(j) - D.I_A(i1 - 1), 'dV_V', D.V(j) - D.V(i1 - 1), ...
        'window_s', D.t_s(j) - D.t_s(i1 - 1), 'R_app_ohm', NaN, 'role', "train", 'err_mV', NaN); %#ok<AGROW>
    E(k).R_app_ohm = E(k).dV_V / E(k).dI_A;
end
tr = ismember([E.name], cfg.R_train_events);
C.R_fast_ohm = mean([E(tr).R_app_ohm]);
for k = find(~tr)
    E(k).role = "test";
    E(k).err_mV = 1000 * (C.R_fast_ohm * E(k).dI_A - E(k).dV_V);
end
C.events = E;

% Polarisation: 2-RC fit to the 2 h relaxation after the 19 h C/20 charge (RC branches at steady state)
r = D(st == 6, :); Iprev = c.I_A(end);
j = find(abs(r.I_A) < 1e-3, 1);
t = r.t_s(j:end) - r.t_s(j); v = r.V(j:end);
f = @(x, t) x(1) + Iprev * (x(2) * exp(-t / x(3)) + x(4) * exp(-t / x(5)));
x0 = [v(end) 0.05 30 0.1 1500]; lb = [3 0 1 0 100]; ub = [4.3 1 100 1 2e4];
x = lsqcurvefit(f, x0, t, v, lb, ub, optimoptions('lsqcurvefit', 'Display', 'off'));
C.rc = struct('V_inf_V', x(1), 'R1_ohm', x(2), 'tau1_s', x(3), 'C1_F', x(3) / x(2), ...
    'R2_ohm', x(4), 'tau2_s', x(5), 'C2_F', x(5) / x(4), 'I_prev_A', Iprev, ...
    'fit', bp_metrics(v, f(x, t)), ...
    'status', "ESTIMATED - in-sample fit only; one usable relaxation event, no independent test");
C.relax_t = t; C.relax_v = v; C.relax_fit = f(x, t);
end

function y = branch(soc, v, g)
[s, i] = unique(soc);
y = interp1(s, v(i), g);   % NaN outside the measured SOC span
end
