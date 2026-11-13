function ocv = bp_ocv_table(O, M)
%BP_OCV_TABLE Pseudo-OCV table with its top segment anchored to the measured rest voltage after a full CC-CV charge.
% Above O.z_end (where the C/20 charge branch stopped) the table is the discharge branch plus an offset that tapers linearly
% from the last measured half-gap to (V_rest_full - M - V_dis(1)), so that OCV(1) + M*h(+1) equals the measured rest.
% Replaces the v1 extrapolation, which used the 75-95 % mean half-gap and put OCV(1) at 4.236 V (above the 4.20 V cutoff).
ocv = (O.V_dis + O.V_chg) / 2;
top = O.soc > O.z_end;
off1 = O.V_rest_full - M - O.V_dis(end);
ocv(top) = O.V_dis(top) + O.gap_end + (off1 - O.gap_end) * (O.soc(top) - O.z_end) / (1 - O.z_end);
end
