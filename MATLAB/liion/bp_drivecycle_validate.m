function R = bp_drivecycle_validate(sets, O, base)
%BP_DRIVECYCLE_VALIDATE Fit ECM candidates on sets.train, choose one on sets.val, score it once on sets.test.
% Scored samples are drive-cycle steps (step >= 7) with measured V > 3.0 V: fixed by the data, never by parameters.
% BASE = parameter vector of a 2-RC model with no hysteresis, scored on the test set for comparison only.
C = candidates();
opts = optimoptions('lsqnonlin', 'Display', 'off');
for c = 1:numel(C)
    r = @(p) cell2mat(cellfun(@(D) resid(p, D, C(c), O), sets.train(:), 'UniformOutput', false));
    p = lsqnonlin(r, C(c).x0, C(c).lb, C(c).ub, opts);
    C(c).p = p;
    C(c).train_RMSE_mV = 1000 * sqrt(mean(r(p).^2));
    v = cellfun(@(D) score(p, D, C(c), O), sets.val, 'UniformOutput', false);
    C(c).val_RMSE_mV = mean(cellfun(@(s) s.RMSE, v));
    C(c).at_bound = find(min(p - C(c).lb, C(c).ub - p) < 1e-3 * (C(c).ub - C(c).lb));
end
[~, b] = min([C.val_RMSE_mV]);
R.candidates = C; R.selected = C(b);
x = cellfun(@(D) score(C(b).p, D, C(b), O), sets.test, 'UniformOutput', false); R.test = [x{:}];
x = cellfun(@(D) bands(C(b).p, D, C(b), O), sets.test, 'UniformOutput', false); R.test_bands = vertcat(x{:});
bc = struct('nrc', 2, 'hyst', false);
x = cellfun(@(D) score(base, D, bc, O), sets.test, 'UniformOutput', false); R.baseline = [x{:}];
end

function m = scored(D), m = D.step >= 7 & D.V > 3.0; end

function e = resid(p, D, c, O)
V = bp_ecm_sim(p, D, c.nrc, c.hyst, O); m = scored(D);
e = V(m) - D.V(m);
end

function s = score(p, D, c, O)
V = bp_ecm_sim(p, D, c.nrc, c.hyst, O); m = scored(D);
s = bp_metrics(1000 * D.V(m), 1000 * V(m));   % mV
s.name = string(D.Properties.Description);
end

function b = bands(p, D, c, O)
[V, z] = bp_ecm_sim(p, D, c.nrc, c.hyst, O); m = scored(D);
e = 1000 * (V - D.V); edges = [0 0.1 0.2 0.5 0.8 1.01];
b = table(repmat(string(D.Properties.Description), 5, 1), edges(1:end-1)', edges(2:end)', zeros(5, 1), nan(5, 1), ...
    'VariableNames', ["test", "soc_lo", "soc_hi", "n", "RMSE_mV"]);
for k = 1:5
    q = m & z >= edges(k) & z < edges(k + 1); b.n(k) = nnz(q);
    if b.n(k), b.RMSE_mV(k) = sqrt(mean(e(q).^2)); end
end
end

function C = candidates()
x0 = {[0.03 2.05 0.02 30], [0.03 2.05 0.01 10 0.02 500]};
lb = {[0.005 1.8 0.001 1], [0.005 1.8 0.001 1 0.001 50]};
ub = {[0.2 2.4 0.2 200], [0.2 2.4 0.2 50 0.2 5000]};
k = 0;
for nrc = 1:2
    for hyst = [false true]
        k = k + 1; hy = double(hyst);
        C(k) = struct('nrc', nrc, 'hyst', hyst, 'x0', [x0{nrc} repmat([0.02 50], 1, hy)], ...
            'lb', [lb{nrc} repmat([0 1], 1, hy)], 'ub', [ub{nrc} repmat([0.1 2000], 1, hy)], ...
            'p', [], 'train_RMSE_mV', NaN, 'val_RMSE_mV', NaN, 'at_bound', []); %#ok<AGROW>
    end
end
end
