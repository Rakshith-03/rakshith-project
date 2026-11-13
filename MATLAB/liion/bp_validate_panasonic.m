function R = bp_validate_panasonic(file, seed)
%BP_VALIDATE_PANASONIC Held-out-cell validation on the Panasonic NCR18650B set (OCV-SOC and pulse relaxation).
% Split is by cell: test cells are never used in fitting or in model selection.
M = load(file);
n = double(M.cell_count);
rng(seed); p = randperm(n);
R.split = struct('train', sort(p(1:60)), 'val', sort(p(61:76)), 'test', sort(p(77:end)));

% OCV: pseudo-OCV per cell = mean of the charge and discharge branches; model = mean of training cells
R.soc = M.POCV_SOC(:);
R.ocv_cells = (M.POCV_charge_V + M.POCV_discharge_V) / 2;
R.ocv_model = mean(R.ocv_cells(:, R.split.train), 2);
for s = ["val", "test"]
    R.ocv.(s) = arrayfun(@(k) bp_metrics(R.ocv_cells(:, k), R.ocv_model), R.split.(s));
end

% Pulse relaxation: predict V after the pulse ends from the off-jump alone (no future samples used)
for dirn = ["positive", "negative"]
    t = M.("Pulse_" + dirn + "_time_s"); v = M.("Pulse_" + dirn + "_voltage_V");
    ev = arrayfun(@(k) pulse_event(t(:, k), v(:, k)), 1:n);
    best = [];
    for nrc = 1:2   % number of RC branches is chosen on validation cells
        th = fit_shape(ev(R.split.train), nrc);
        mv = arrayfun(@(e) bp_metrics(e.v, predict(e, th)), ev(R.split.val));
        cand = struct('nrc', nrc, 'theta', th, 'val_RMSE_mV', 1000 * mean([mv.RMSE]));
        R.pulse.(dirn).candidates(nrc) = cand;
        if isempty(best) || cand.val_RMSE_mV < best.val_RMSE_mV, best = cand; end
    end
    R.pulse.(dirn).selected = best;
    R.pulse.(dirn).test = arrayfun(@(e) bp_metrics(e.v, predict(e, best.theta)), ev(R.split.test));
    R.pulse.(dirn).events = ev;
end
end

function e = pulse_event(t, v)
ok = v > 0; t = t(ok); v = v(ok);   % trailing zeros are padding
dv = diff(v);
[~, on] = max(abs(dv(1:find(t > 15, 1))));                         % pulse applied near t = 9 s
win = find(t(1:end-1) > t(on) + 2 & t(1:end-1) < t(on) + 30);
[~, k] = max(abs(dv(win))); off = win(k);                           % pulse removed
a = off + 1;                                                        % last sample the predictor may see
e = struct('pulse_s', t(off) - t(on), 'J', dv(off), 'Va', v(a), 't', t(a+1:end) - t(a), 'v', v(a+1:end));
end

function th = fit_shape(E, nrc)
% Relaxation continues in the direction of the off-jump J: v = Va + J * sum k_i (1 - exp(-t/tau_i))
x0 = [0.2 log(20) 0.2 log(600)]; x0 = x0(1:2*nrc);
lb = repmat([0 log(0.5)], 1, nrc); ub = repmat([5 log(1e4)], 1, nrc);
res = @(x) cell2mat(arrayfun(@(e) predict(e, x) - e.v, E(:), 'UniformOutput', false));
th = lsqnonlin(res, x0, lb, ub, optimoptions('lsqnonlin', 'Display', 'off'));
end

function vh = predict(e, x)
k = x(1:2:end); tau = exp(x(2:2:end));
vh = e.Va + e.J * sum(k .* (1 - exp(-e.t ./ tau)), 2);
end
