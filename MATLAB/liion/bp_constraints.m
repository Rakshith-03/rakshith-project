function [E, overall] = bp_constraints(t, V, I, T, z, L)
%BP_CONSTRAINTS Offline check of a run against limits L (I = discharge current, A). This is NOT the real-time moderator.
% Returns one row per constraint (severity NORMAL / WARNING / CRITICAL / NOT MONITORED) and the overall severity.
% dV/dt and dI/dt are not limits here: on their own they do not indicate damage.
dTdt = 60 * gradient(T(:), t(:));   % degC/min
chk = { "overvoltage",       V,    L.V_warn_hi,   L.V_crit_hi,   +1, L.src.V_hi
        "undervoltage",      V,    L.V_warn_lo,   L.V_crit_lo,   -1, L.src.V_lo
        "discharge current", I,    L.I_dis_warn,  L.I_dis_crit,  +1, L.src.I_dis
        "charge current",    -I,   L.I_chg_warn,  L.I_chg_crit,  +1, L.src.I_chg
        "overtemperature",   T,    L.T_warn,      L.T_crit,      +1, L.src.T
        "temperature rate",  dTdt, L.dTdt_warn,   L.dTdt_crit,   +1, L.src.dTdt
        "low SOC",           z,    L.soc_warn_lo, L.soc_crit_lo, -1, L.src.soc_lo
        "high SOC",          z,    L.soc_warn_hi, L.soc_crit_hi, +1, L.src.soc_hi };
lev = ["NORMAL" "WARNING" "CRITICAL"];
for k = 1:size(chk, 1)
    [name, x, w, c, s, src] = chk{k, :};
    x = x(:);
    if all(isnan(x))
        sev = "NOT MONITORED"; nw = 0; nc = 0; tw = NaN; tc = NaN; worst = NaN;
    else
        bw = s * x > s * w; bc = s * x > s * c;   % s = -1 turns "below the limit" into "above"
        nw = nnz(bw); nc = nnz(bc); tw = first(t, bw); tc = first(t, bc);
        if s > 0, worst = max(x); else, worst = min(x); end
        sev = lev(1 + (nw > 0) + (nc > 0));
    end
    E(k, 1) = struct('constraint', name, 'severity', sev, 'n_warning', nw, 'n_critical', nc, ...
        'first_warning_s', tw, 'first_critical_s', tc, 'worst', worst, 'warn_limit', w, 'crit_limit', c, ...
        'source', src); %#ok<AGROW>
end
E = struct2table(E);
r = find(ismember(lev, E.severity), 1, 'last');
overall = lev(max([r 1]));
end

function v = first(t, b)
i = find(b, 1);
if isempty(i), v = NaN; else, v = t(i); end
end
