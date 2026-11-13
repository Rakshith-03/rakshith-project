function O = bp_pocv(D, dis_step, chg_step, rest_step)
%BP_POCV Pseudo-OCV from a low-current test: mean of the discharge and charge branches on a common SOC grid.
% SOC is normalised by the measured discharge capacity of the same test.
% With REST_STEP (the rest after the full CC-CV charge), the top of the table is anchored to that measured rest voltage
% (see bp_ocv_table); without it, the v1 mean-half-gap extrapolation is used.
d = D(D.step == dis_step, :); c = D(D.step == chg_step, :);
O.Q_Ah = -trapz(d.t_s, d.I_A) / 3600;
socd = 1 + cumtrapz(d.t_s, d.I_A) / 3600 / O.Q_Ah;
socc = cumtrapz(c.t_s, c.I_A) / 3600 / O.Q_Ah;
O.soc = linspace(0, 1, 201)';
O.V_dis = branch(socd, d.V, O.soc);
O.V_chg = branch(socc, c.V, O.soc);
O.ocv = (O.V_dis + O.V_chg) / 2;
% The charge branch can stop short of full; extend it with the discharge branch + mean half-gap at 75-95 % SOC
top = isnan(O.ocv);
gap = O.V_chg - O.V_dis;
O.ocv(top) = O.V_dis(top) + mean(gap(O.soc >= 0.75 & O.soc <= 0.95), 'omitnan') / 2;
O.extrapolated_points = nnz(top);
if nargin >= 4
    r = D.V(D.step == rest_step); O.V_rest_full = r(end);
    ie = find(~isnan(O.V_chg), 1, 'last'); O.z_end = O.soc(ie);
    O.gap_end = (O.V_chg(ie) - O.V_dis(ie)) / 2;
    O.ocv = bp_ocv_table(O, 0);   % M = 0 placeholder; simulations rebuild the table with the fitted M
end
end

function y = branch(s, v, g)
[s, i] = unique(s);   % also drops the duplicated timestamps CALCE logs occasionally
y = interp1(s, v(i), g);
end
