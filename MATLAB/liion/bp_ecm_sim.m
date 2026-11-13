function [V, z] = bp_ecm_sim(p, D, nrc, hyst, O, z0, h0)
%BP_ECM_SIM Thevenin ECM with NRC RC branches and optional one-state hysteresis, exact zero-order hold per sample.
% p = [R0 Q R1 tau1 (R2 tau2) (M gamma)]. D.I_A uses + = charge (CALCE). Starts at SOC z0 (default 1), RC = 0,
% h = h0 (default +1, i.e. after a charge).
if nargin < 6, z0 = 1; end
if nargin < 7, h0 = 1; end
%   V = OCV(z) + M*h - R0*I - sum(v_i),  I = discharge current
%   v_i(k+1) = a_i v_i(k) + R_i (1 - a_i) I(k),  a_i = exp(-dt/tau_i)
%   h(k+1)   = e h(k) - (1 - e) sign(I(k)),       e = exp(-|I| gamma dt / (3600 Q))
R0 = p(1); Q = p(2); rc = p(3:2 + 2*nrc);
if hyst, M = p(3 + 2*nrc); gam = p(4 + 2*nrc); else, M = 0; gam = 0; end
t = D.t_s; I = -D.I_A; n = numel(t);
dt = [diff(t); 0];
z = z0 - [0; cumsum(I(1:end-1) .* dt(1:end-1))] / 3600 / Q;
R = rc(1:2:end); tau = rc(2:2:end);
A = exp(-dt ./ tau(:)');
B = (1 - A) .* R(:)';
vr = zeros(1, nrc); h = h0; Vp = zeros(n, 1); H = zeros(n, 1);
for k = 1:n
    Vp(k) = sum(vr); H(k) = h;
    vr = A(k, :) .* vr + B(k, :) * I(k);
    if hyst && I(k) ~= 0
        e = exp(-abs(I(k)) * gam * dt(k) / 3600 / Q);
        h = e * h - (1 - e) * sign(I(k));
    end
end
if hyst && isfield(O, 'V_rest_full'), ocv = bp_ocv_table(O, M); else, ocv = O.ocv; end   % anchored top needs M
V = interp1(O.soc, ocv, min(max(z, 0), 1)) + M * H - R0 * I - Vp;   % OCV table clamped at its ends
end
