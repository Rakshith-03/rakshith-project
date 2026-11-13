function L = bp_limits_liion()
%BP_LIMITS_LIION Constraint limits for the CALCE INR18650-20R model. Every limit records its source.
L.V_warn_hi = 4.18;  L.V_crit_hi = 4.20;
L.src.V_hi = "4.20 V: charge cutoff of the CALCE test procedure; 20 mV warning margin ASSUMED";
L.V_warn_lo = 2.80;  L.V_crit_lo = 2.50;
L.src.V_lo = "2.50 V: discharge cutoff of the CALCE test procedure; 2.80 V warning ASSUMED (model error grows below 10 % SOC)";
L.I_dis_warn = 4.0;  L.I_dis_crit = Inf;
L.src.I_dis = "4 A: highest discharge current in the validation data, so the model extrapolates above it. Datasheet max UNVERIFIED -> no critical limit";
L.I_chg_warn = 2.2;  L.I_chg_crit = Inf;
L.src.I_chg = "2.2 A: highest charge current in the validation data (FUDS regen 2.14 A). Datasheet max UNVERIFIED -> no critical limit";
L.T_warn = 45;       L.T_crit = 60;
L.src.T = "ASSUMED generic Li-ion limits, UNVERIFIED for this cell; the thermal model is PROVISIONAL";
L.dTdt_warn = 10;    L.dTdt_crit = 60;
L.src.dTdt = "degC/min, ASSUMED (60 degC/min = 1 degC/s, a common abnormal-heating threshold); normal 1.5C use heats about 1 degC/min in the PROVISIONAL model";
L.soc_warn_lo = 0.10; L.soc_crit_lo = 0;
L.src.soc_lo = "10 %: model accuracy degrades below 10 % SOC (validation run drivecycle_20261112_015732)";
L.soc_warn_hi = 0.95; L.soc_crit_hi = 1;
L.src.soc_hi = "ASSUMED";
end
