function m = bp_metrics(y, yhat)
%BP_METRICS Error metrics of a prediction yhat against a reference y (same units as y).
e = yhat(:) - y(:);
ok = ~isnan(e); e = e(ok); y = y(ok);
m = struct('N', numel(e), 'MAE', mean(abs(e)), 'RMSE', sqrt(mean(e.^2)), ...
    'MaxAE', max(abs(e)), 'Bias', mean(e), ...
    'R2', 1 - sum(e.^2) / sum((y - mean(y)).^2));
end
